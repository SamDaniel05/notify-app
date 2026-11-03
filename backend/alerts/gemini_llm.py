"""Optional free LLM via Google Gemini. Used if Groq fails or is unset."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

SYSTEM = """You are Aria, a personal AI assistant inside a mobile/web app.
You help the user set reminders, weather watches, and news keyword watches.

Respond with ONLY valid JSON (no markdown fences) in this shape:
{
  "reply": "short friendly message to the user",
  "proposals": [
    {
      "title": "short title",
      "alert_type": "reminder" | "weather" | "keyword",
      "params": { ... },
      "reason": "one line why"
    }
  ],
  "control": null
}

params rules:
- reminder interval: {"message": "...", "mode": "interval", "interval_days": N, "time_local": "HH:MM", "timezone": "Asia/Kolkata", "next_due": "YYYY-MM-DD"}
- reminder daily window: {"message": "...", "mode": "daily_window", "days": N, "time_local": "HH:MM", "timezone": "Asia/Kolkata"}
- weather: {"place_name": "..."}
- keyword: {"query": "..."}

If the user is snoozing or marking done an EXISTING reminder, set proposals to [] and:
  "control": {"action": "snooze"|"done", "days": N, "query": "optional match text"}

If the message is only greeting/junk, proposals=[] and a short help reply.
Default timezone Asia/Kolkata. Default reminder time 10:00 if unspecified.
Keep reply under 400 characters. English unless user writes Tamil.
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
            clean.append(
                {
                    "title": str(p.get("title") or "Alert")[:120],
                    "alert_type": at,
                    "params": p.get("params") if isinstance(p.get("params"), dict) else {},
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
