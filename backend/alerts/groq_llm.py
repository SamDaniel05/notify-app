"""Optional free LLM via Groq. Falls back silently if key missing or API errors."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM = """You are Aria, a personal AI assistant inside a mobile/web app.
You help with reminders, weather, news keywords, and trend/event tracking (influencer-style).

Respond with ONLY valid JSON (no markdown fences):
{
  "reply": "short friendly message",
  "proposals": [ { "title", "alert_type", "params", "reason" } ],
  "control": null
}

alert_type values: reminder | weather | keyword

params:
- reminder interval: {"message", "mode": "interval", "interval_days": N, "time_local": "HH:MM", "timezone": "Asia/Kolkata", "next_due": "YYYY-MM-DD"}
- reminder daily: {"message", "mode": "daily_window", "days": N, "time_local": "HH:MM", "timezone": "Asia/Kolkata"}
- weather: {"place_name"}
- keyword / trend / event: {"query": "topic or trend name", "kind": "trend"|"event"|"news" (optional)}

TREND / EVENT rules (Instagram-style):
- If user wants to track a trend, viral sound, challenge, event, or “what’s trending” on a topic:
  create a keyword proposal with kind "trend" or "event" and query set to the trend/event name.
- If they also want to *do* the trend (post, film, try the dance, etc.):
  ALSO add a reminder proposal, e.g. message "Do the {trend} trend / post about it", daily or interval as they say.
- Examples:
  "Track the coral trend and remind me to post it" → keyword(kind=trend) + reminder
  "Follow IPL final event" → keyword(kind=event)
  "Remind me to do today’s trending reel" → reminder (and keyword if they named it)

Snooze/done on existing reminder → proposals=[] and control: {"action":"snooze"|"done","days":N,"query":"..."}
Greeting/junk → empty proposals + short help.
Timezone Asia/Kolkata. Default reminder time 10:00. Reply under 400 chars.
"""


def groq_enabled() -> bool:
    return bool((os.environ.get("GROQ_API_KEY") or "").strip())


def interpret_with_groq(message: str) -> dict[str, Any] | None:
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        return None
    model = (os.environ.get("GROQ_MODEL") or "llama-3.1-8b-instant").strip()
    try:
        res = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": message},
                ],
            },
            timeout=25,
        )
        if res.status_code >= 400:
            return None
        data = res.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if not content:
            return None
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None
        reply = str(parsed.get("reply") or "").strip()
        proposals = parsed.get("proposals") or []
        if not isinstance(proposals, list):
            proposals = []
        clean = []
        for p in proposals[:6]:
            if not isinstance(p, dict):
                continue
            at = p.get("alert_type") or "keyword"
            if at not in ("reminder", "weather", "keyword", "rss"):
                at = "keyword"
            params = p.get("params") if isinstance(p.get("params"), dict) else {}
            clean.append(
                {
                    "title": str(p.get("title") or "Alert")[:120],
                    "alert_type": at,
                    "params": params,
                    "reason": str(p.get("reason") or p.get("title") or "")[:200],
                }
            )
        control = parsed.get("control")
        if control is not None and not isinstance(control, dict):
            control = None
        out: dict[str, Any] = {
            "reply": reply or "Okay.",
            "proposals": clean,
            "speak": True,
            "source": "groq",
        }
        if control:
            out["control"] = control
        return out
    except Exception:
        return None
