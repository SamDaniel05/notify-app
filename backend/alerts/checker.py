"""Evaluate active alert rules and push via delivery channels (free APIs)."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from django.utils import timezone

from delivery.models import DeliveryChannel
from delivery.services import send_ntfy, send_telegram, send_webpush

from .models import AlertRule, NotificationLog

OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FX = "https://api.open-meteo.com/v1/forecast"
GNEWS_RSS = "https://news.google.com/rss/search"
IST = ZoneInfo("Asia/Kolkata")


def _get(url: str, params: dict | None = None, timeout: int = 12):
    return requests.get(url, params=params or {}, timeout=timeout, headers={"User-Agent": "NotifyApp/1.0"})


def check_weather(place_name: str) -> tuple[bool, str]:
    place_name = (place_name or "").strip()
    if not place_name:
        return False, "No place"
    try:
        geo = _get(OPEN_METEO_GEO, {"name": place_name, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        results = (geo.json() or {}).get("results") or []
        if not results:
            return False, f"Place not found: {place_name}"
        lat, lon = results[0]["latitude"], results[0]["longitude"]
        label = results[0].get("name") or place_name
        fx = _get(
            OPEN_METEO_FX,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation_probability,precipitation",
                "forecast_days": 1,
                "timezone": "Asia/Kolkata",
            },
        )
        fx.raise_for_status()
        hourly = (fx.json() or {}).get("hourly") or {}
        probs = hourly.get("precipitation_probability") or []
        precs = hourly.get("precipitation") or []
        p0 = probs[0] if probs else 0
        p1 = probs[1] if len(probs) > 1 else p0
        r0 = precs[0] if precs else 0
        r1 = precs[1] if len(precs) > 1 else r0
        if (p0 or 0) >= 50 or (p1 or 0) >= 50 or (r0 or 0) >= 0.2 or (r1 or 0) >= 0.2:
            return True, f"Rain likely near {label} (prob {max(p0 or 0, p1 or 0)}%, precip ~{max(r0 or 0, r1 or 0)} mm)"
        return False, f"No rain signal near {label}"
    except Exception as e:
        return False, f"weather error: {e}"


def check_keyword(query: str) -> tuple[bool, str]:
    query = (query or "").strip()
    if not query:
        return False, "No query"
    try:
        res = _get(GNEWS_RSS, {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}, timeout=15)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        items = root.findall(".//item")[:5]
        titles = [(it.findtext("title") or "").strip() for it in items]
        titles = [t for t in titles if t]
        if not titles:
            return False, f"No headlines for {query}"
        return True, titles[0][:240]
    except Exception as e:
        return False, f"keyword error: {e}"


def check_rss(feed_url: str) -> tuple[bool, str]:
    feed_url = (feed_url or "").strip()
    if not feed_url.startswith("http"):
        return False, "Invalid feed URL"
    try:
        res = _get(feed_url, timeout=15)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        item = root.find(".//item")
        if item is None:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            item = root.find(".//a:entry", ns)
            title = (item.findtext("a:title", default="", namespaces=ns) if item is not None else "") or ""
        else:
            title = (item.findtext("title") or "").strip()
        if title:
            return True, title[:240]
        return False, "Empty feed"
    except Exception as e:
        return False, f"rss error: {e}"


def check_reminder(params: dict, rule: AlertRule) -> tuple[bool, str]:
    params = params or {}
    message = (params.get("message") or params.get("task") or rule.title or "Reminder").strip()
    days = int(params.get("days") or 14)
    time_local = (params.get("time_local") or "20:00").strip()
    tz_name = params.get("timezone") or "Asia/Kolkata"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = IST

    now = timezone.now().astimezone(tz)
    today = now.date()

    start = params.get("start_date")
    if start:
        try:
            start_d = datetime.strptime(start[:10], "%Y-%m-%d").date()
        except ValueError:
            start_d = rule.created_at.astimezone(tz).date() if rule.created_at else today
    else:
        start_d = rule.created_at.astimezone(tz).date() if rule.created_at else today

    end_d = start_d + timedelta(days=max(1, days) - 1)
    if today < start_d or today > end_d:
        if today > end_d:
            rule.is_active = False
            rule.save(update_fields=["is_active", "updated_at"])
            return False, "Reminder period ended"
        return False, "Not started yet"

    try:
        hh, mm = time_local.split(":")[:2]
        target_h, target_m = int(hh), int(mm)
    except Exception:
        target_h, target_m = 20, 0

    if (now.hour, now.minute) < (target_h, target_m):
        return False, f"Waiting until {time_local} {tz_name}"

    if rule.last_triggered_at:
        last_local = rule.last_triggered_at.astimezone(tz).date()
        if last_local == today:
            return False, "Already reminded today"

    params["last_sent_date"] = today.isoformat()
    params["start_date"] = start_d.isoformat()
    rule.params = params
    return True, message


def _notify_user(user, title: str, body: str, rule: AlertRule | None):
    channels = DeliveryChannel.objects.filter(user=user, is_active=True)
    if not channels.exists():
        NotificationLog.objects.create(
            user=user, rule=rule, channel="none", title=title, body=body, success=False, detail="No delivery channel"
        )
        return 0
    sent = 0
    bot = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    for ch in channels:
        if ch.channel_type == DeliveryChannel.CHANNEL_NTFY:
            ok, detail = send_ntfy(ch.config.get("topic", ""), title, body)
        elif ch.channel_type == DeliveryChannel.CHANNEL_TELEGRAM:
            ok, detail = send_telegram(bot, str(ch.config.get("chat_id", "")), title, body)
        elif ch.channel_type == DeliveryChannel.CHANNEL_WEBPUSH:
            ok, detail = send_webpush(ch.config, title, body)
        else:
            ok, detail = False, "unknown"
        NotificationLog.objects.create(
            user=user, rule=rule, channel=ch.channel_type, title=title, body=body, success=ok, detail=detail
        )
        if ok:
            sent += 1
    return sent


def run_checks(limit: int = 100) -> dict:
    now = timezone.now()
    min_gap_other = timedelta(hours=3)
    qs = AlertRule.objects.filter(is_active=True).select_related("user")[:limit]
    checked = triggered = errors = 0
    for rule in qs:
        checked += 1
        try:
            if rule.alert_type == AlertRule.TYPE_REMINDER:
                ok, detail = check_reminder(rule.params or {}, rule)
            else:
                if rule.last_triggered_at and now - rule.last_triggered_at < min_gap_other:
                    rule.last_checked_at = now
                    rule.save(update_fields=["last_checked_at"])
                    continue
                if rule.alert_type == AlertRule.TYPE_WEATHER:
                    ok, detail = check_weather((rule.params or {}).get("place_name", ""))
                elif rule.alert_type == AlertRule.TYPE_KEYWORD:
                    ok, detail = check_keyword((rule.params or {}).get("query", ""))
                elif rule.alert_type == AlertRule.TYPE_RSS:
                    ok, detail = check_rss(
                        (rule.params or {}).get("feed_url") or (rule.params or {}).get("page_url", "")
                    )
                else:
                    ok, detail = False, "Unknown type"

            rule.last_checked_at = now
            if ok:
                title = rule.title or "Notify"
                _notify_user(rule.user, title, detail, rule)
                rule.last_triggered_at = now
                triggered += 1
            rule.save()
        except Exception as e:
            errors += 1
            rule.last_checked_at = now
            rule.save(update_fields=["last_checked_at"])
            NotificationLog.objects.create(
                user=rule.user,
                rule=rule,
                channel="system",
                title="check failed",
                body=str(e)[:300],
                success=False,
                detail=str(e)[:300],
            )
    return {"checked": checked, "triggered": triggered, "errors": errors}
