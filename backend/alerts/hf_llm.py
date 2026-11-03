"""Optional free LLM via Hugging Face Inference Router (OpenAI-compatible)."""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

URL = "https://router.huggingface.co/v1/chat/completions"

SYSTEM = """You are Aria, a personal AI assistant.
Return ONLY valid JSON:
{"reply":"...","proposals":[{"title","alert_type","params","reason"}],"control":null}
alert_type: reminder|weather|keyword
Timezone Asia/Kolkata. Short reply.
"""


def hf_enabled() -> bool:
    return bool((os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or "").strip())


def interpret_with_hf(message: str) -> dict[str, Any] | None:
    key = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or "").strip()
    if not key:
        return None
    model = (os.environ.get("HF_MODEL") or "meta-llama/Llama-3.1-8B-Instruct").strip()
    try:
        res = requests.post(
            URL,
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
            timeout=45,
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
            "source": "huggingface",
        }
        if control:
            out["control"] = control
        return out
    except Exception:
        return None
