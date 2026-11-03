"""Optional free LLM via Groq. Falls back silently if key missing or API errors."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM = """You are Aria, a personal AI assistant inside a mobile/web app.
You help with reminders, weather, news, trends/events, and movie booking alerts (free public news only — no seat-map scraping).

Respond with ONLY valid JSON (no markdown fences):
{
  "reply": "short friendly message",
  "proposals": [ { "title", "alert_type", "params", "reason" } ],
  "control": null
}

alert_type: reminder | weather | keyword

params:
- reminder interval: {"message", "mode": "interval", "interval_days": N, "time_local": "HH:MM", "timezone": "Asia/Kolkata", "next_due": "YYYY-MM-DD"}
- reminder daily: {"message", "mode": "daily_window", "days": N, "time_local": "HH:MM", "timezone": "Asia/Kolkata"}
- weather: {"place_name"}
- keyword / trend / event / booking: {"query": "search phrase", "kind": "trend"|"event"|"news"|"booking" optional}

MOVIE BOOKING (what we CAN do free):
- User wants to know when theatre bookings open / tickets go on sale / advance booking starts:
  Create a keyword proposal with kind "booking" and a strong query, e.g.
  "{Movie Name} bookings open" or "{Movie Name} advance booking" or "{Movie Name} tickets BookMyShow".
  Prefer including city if user named one: "{Movie} bookings open Chennai".
- Be clear in reply: we watch public news/headlines for booking announcements — we cannot see live seat maps.
- Optional: also add a nightly reminder if they ask to check seats at a time, e.g. 00:10.

TREND / EVENT:
- Track trend/challenge → keyword kind trend/event.
- "Remind me to do/post the trend" → also a reminder.

Snooze/done on reminder → proposals=[] and control {"action":"snooze"|"done","days":N,"query":"..."}.
Greeting → short help, empty proposals.
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
