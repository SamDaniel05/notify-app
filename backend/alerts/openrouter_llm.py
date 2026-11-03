"""Optional free-route LLM via OpenRouter."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM = """You are Aria, a personal AI assistant.
Return ONLY valid JSON:
{"reply":"...","proposals":[{"title","alert_type","params","reason"}],"control":null}
alert_type: reminder|weather|keyword
For movie bookings open: keyword with query like "{Movie} bookings open" and kind booking.
Timezone Asia/Kolkata. Short reply.
"""


def openrouter_enabled() -> bool:
    return bool((os.environ.get("OPENROUTER_API_KEY") or "").strip())


def interpret_with_openrouter(message: str) -> dict[str, Any] | None:
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    # Prefer free models; user can override
    model = (os.environ.get("OPENROUTER_MODEL") or "meta-llama/llama-3.1-8b-instruct:free").strip()
    try:
        res = requests.post(
            URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.environ.get("OPENROUTER_REFERER") or "https://samdaniel05.github.io/notify-app/",
                "X-Title": "Aria Personal AI",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": message},
                ],
            },
            timeout=30,
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
        return _normalize(parsed, "openrouter")
    except Exception:
        return None


def _normalize(parsed: dict, source: str) -> dict[str, Any] | None:
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
        "source": source,
    }
    if control:
        out["control"] = control
    return out
