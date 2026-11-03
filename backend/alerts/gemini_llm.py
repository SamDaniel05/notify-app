"""Optional free LLM via Google Gemini. Used if Groq fails or is unset."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

SYSTEM = """You are Aria, a personal AI assistant inside a mobile/web app.
You help with reminders, weather, news keywords, and trend/event tracking (influencer-style).

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
- keyword / trend / event: {"query": "name", "kind": "trend"|"event"|"news" optional}

TREND / EVENT (Instagram-style):
- Track a trend/challenge/viral sound/event → keyword with kind trend or event.
- If user wants to DO the trend (post, film, try it) → also add a reminder like "Do the {name} trend / post about it".
Examples: "Track coral trend and remind me to post" → keyword + reminder.

Snooze/done → control object, empty proposals.
Default timezone Asia/Kolkata, time 10:00. Reply under 400 chars.
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
