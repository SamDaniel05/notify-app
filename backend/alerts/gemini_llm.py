"""Optional free LLM via Google Gemini. Used if Groq fails or is unset."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

SYSTEM = """You are Aria, a personal AI assistant.
Help with reminders, weather, news, trends, and movie booking alerts via public news only (no seat-map scraping).

ONLY valid JSON:
{
  "reply": "short message",
  "proposals": [ { "title", "alert_type", "params", "reason" } ],
  "control": null
}

alert_type: reminder | weather | keyword

params:
- reminder: interval or daily_window as usual, timezone Asia/Kolkata
- weather: {"place_name"}
- keyword: {"query", "kind": "trend"|"event"|"news"|"booking" optional}

MOVIE BOOKING (free):
- When user asks to know when bookings/tickets open: keyword kind "booking",
  query like "{Movie} bookings open" or "{Movie} advance booking" (+ city if given).
- Reply must say we use public headlines, not live seat maps.
- Optional night reminder only if they ask for a check time.

TREND: keyword + optional "do the trend" reminder.
Snooze/done → control object.
Reply under 400 chars.
"""


def gemini_enabled() -> bool:
    return bool((os.environ.get("GEMINI_API_KEY") or "").strip())


def interpret_with_gemini(message: str) -> dict[str, Any] | None:
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    model = (os.environ.get("GEMINI_MODEL") or "gemini-3.8-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        res = requests.post(
            url,
            params={"key": key},
            headers={"Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM}]},
                "contents": [{"role": "user", "parts": [{"text": message}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=25,
        )
        if res.status_code >= 400:
            return None
        data = res.json()
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        content = "".join(str(p.get("text") or "") for p in parts).strip()
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
            "source": "gemini",
        }
        if control:
            out["control"] = control
        return out
    except Exception:
        return None
