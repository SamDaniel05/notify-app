"""Evaluate active alert rules and push via delivery channels (free APIs)."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import timedelta

import requests
from django.utils import timezone

from delivery.models import DeliveryChannel
from delivery.services import send_ntfy, send_telegram

from .models import AlertRule, NotificationLog

OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FX = "https://api.open-meteo.com/v1/forecast"
GNEWS_RSS = "https://news.google.com/rss/search"


def _get(url: str, params: dict | None = None, timeout: int = 12):
    return requests.get(url, params=params or {}, timeout=timeout, headers={"User-Agent": "NotifyApp/1.0"})


def check_weather(place_name: str) -> tuple[bool, str]:
    """Return (should_notify, detail). Rain in next ~1 hour."""
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
        # Next 2 hours
        p0 = probs[0] if probs else 0
        p1 = probs[1] if len(probs) > 1 else p0
        r0 = precs[0] if precs else 0
        r1 = precs[1] if len(precs) > 1 else r0
        if (p0 or 0) >= 50 or (p1 or 0) >= 50 or (r0 or 0) >= 0.2 or (r1 or 0) >= 0.2:
            return True, f"Rain likely near {label} (prob {max(p0 or 0, p1 or 0)}%, precip ~{max(r0 or 0, r1 or 0)} mm)"
        return False, f"No rain signal near {label}"
    except Exception as e:
        return False, f"weather error: {e}"


def check_keyword(query: str, since_hours: int = 6) -> tuple[bool, str]:
    """Google News RSS — free, no key."""
    query = (query or "").strip()
    if not query:
        return False, "No query"
    try:
        res = _get(
            GNEWS_RSS,
            {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
            timeout=15,
        )
        res.raise_for_status()
        root = ET.fromstring(res.content)
        items = root.findall(".//item")[:5]
        if not items:
            return False, f"No headlines for {query}"
        titles = []
        for it in items:
            t = (it.findtext("title") or "").strip()
            if t:
                titles.append(t)
        if not titles:
            return False, f"No headlines for {query}"
        # Always surface newest headline as potential notify; caller rate-limits by last_triggered
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
            # Atom
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
        else:
            ok, detail = send_telegram(bot, str(ch.config.get("chat_id", "")), title, body)
        NotificationLog.objects.create(
            user=user, rule=rule, channel=ch.channel_type, title=title, body=body, success=ok, detail=detail
        )
        if ok:
            sent += 1
    return sent


def run_checks(limit: int = 100) -> dict:
    """Scan active rules; notify at most once per 3 hours per rule."""
    now = timezone.now()
    min_gap = timedelta(hours=3)
    qs = AlertRule.objects.filter(is_active=True).select_related("user")[:limit]
    checked = triggered = errors = 0
    for rule in qs:
        checked += 1
        if rule.last_triggered_at and now - rule.last_triggered_at < min_gap:
            rule.last_checked_at = now
            rule.save(update_fields=["last_checked_at"])
            continue
        try:
            if rule.alert_type == AlertRule.TYPE_WEATHER:
                ok, detail = check_weather((rule.params or {}).get("place_name", ""))
            elif rule.alert_type == AlertRule.TYPE_KEYWORD:
                ok, detail = check_keyword((rule.params or {}).get("query", ""))
            elif rule.alert_type == AlertRule.TYPE_RSS:
                ok, detail = check_rss((rule.params or {}).get("feed_url") or (rule.params or {}).get("page_url", ""))
            else:
                ok, detail = False, "Unknown type"
            rule.last_checked_at = now
            if ok:
                title = rule.title or "Notify"
                _notify_user(rule.user, title, detail, rule)
                rule.last_triggered_at = now
                triggered += 1
            rule.save(update_fields=["last_checked_at", "last_triggered_at"])
        except Exception as e:
            errors += 1
            rule.last_checked_at = now
            rule.save(update_fields=["last_checked_at"])
            NotificationLog.objects.create(
                user=rule.user, rule=rule, channel="system", title="check failed", body=str(e)[:300], success=False, detail=str(e)[:300]
            )
    return {"checked": checked, "triggered": triggered, "errors": errors}
