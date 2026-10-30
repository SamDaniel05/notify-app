"""Free rule-based intent extraction from natural language.
No paid LLM required. Optional GROQ_API_KEY can improve later.
"""
from __future__ import annotations

import re
from typing import Any


WEATHER_WORDS = re.compile(
    r"\b(rain|rains|rainy|weather|storm|downpour|drizzle|flood|flooding|"
    r"மழை|வானிலை)\b",
    re.I,
)
PLACE_HINT = re.compile(
    r"\b(?:in|at|near|around|for)\s+([A-Za-z][A-Za-z .'\-]{1,40})",
    re.I,
)
KNOWN_PLACES = [
    "Tambaram", "Sholinganallur", "Kodambakkam", "Chennai Central", "Wimco Nagar",
    "Chennai", "T Nagar", "Anna Nagar", "Velachery", "Adyar", "Guindy", "OMR",
    "ECR", "Porur", "Ambattur", "Avadi", "Chromepet", "Pallavaram",
]


def _clean_place(s: str) -> str:
    s = s.strip(" .,!?;:\"'")
    s = re.sub(r"\b(please|now|today|tonight|tomorrow|area|city)\b", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" .,!")


def extract_intents(message: str) -> dict[str, Any]:
    """Return {reply, proposals:[{title, alert_type, params, reason}]}."""
    text = (message or "").strip()
    if not text:
        return {
            "reply": "Tell me what you want to follow. Examples:\n"
            "• Notify me when it rains in Tambaram\n"
            "• News about Real Madrid or CSK injuries\n"
            "• Updates on Tamil Nadu politics",
            "proposals": [],
        }

    proposals: list[dict[str, Any]] = []
    lower = text.lower()

    # Weather / rain + place
    if WEATHER_WORDS.search(text):
        place = None
        m = PLACE_HINT.search(text)
        if m:
            place = _clean_place(m.group(1))
        if not place:
            for p in KNOWN_PLACES:
                if p.lower() in lower:
                    place = p
                    break
        if place:
            proposals.append(
                {
                    "title": f"Rain / weather · {place}",
                    "alert_type": "weather",
                    "params": {"place_name": place},
                    "reason": f"Detected weather watch for {place}",
                }
            )
        else:
            return {
                "reply": "I can watch rain/weather, but need a place. "
                "Try: “Notify me when it rains in Tambaram”.",
                "proposals": [],
            }

    # Keyword / news topics (split on and/or commas)
    newsy = bool(
        re.search(
            r"\b(news|update|updates|alert|alerts|notify|notification|"
            r"follow|about|regarding|injury|injuries|return|politics|scores?)\b",
            text,
            re.I,
        )
    ) or not proposals

    if newsy and not (WEATHER_WORDS.search(text) and len(proposals) == 1 and not re.search(r"\band\b|,|news|about", text, re.I)):
        # Pull quoted phrases or proper-ish tokens
        topics: list[str] = []
        for q in re.findall(r'["“](.+?)["”]', text):
            topics.append(q.strip())

        # after about/regarding/for news on
        for m in re.finditer(
            r"\b(?:about|regarding|on|for|follow|watch)\s+(.+)$",
            text,
            re.I,
        ):
            chunk = m.group(1)
            chunk = re.sub(r"\b(news|updates?|alerts?|please|me|the)\b", " ", chunk, flags=re.I)
            parts = re.split(r"\s*(?:,|/|\band\b|\bor\b)\s*", chunk, flags=re.I)
            for p in parts:
                p = _clean_place(p)
                if len(p) >= 2 and p.lower() not in {"when", "it", "is", "to", "my"}:
                    topics.append(p)

        # Fallback: capitalize-looking multiwords / teams
        if not topics:
            for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
                topics.append(m.group(1))

        # Dedupe
        seen = set()
        uniq = []
        for t in topics:
            k = t.lower()
            if k in seen or len(t) < 2:
                continue
            # skip pure weather places already added
            if any(p["alert_type"] == "weather" and p["params"].get("place_name", "").lower() == k for p in proposals):
                continue
            seen.add(k)
            uniq.append(t)

        for t in uniq[:5]:
            proposals.append(
                {
                    "title": t,
                    "alert_type": "keyword",
                    "params": {"query": t},
                    "reason": f"Keyword / news watch for “{t}”",
                }
            )

    if not proposals:
        # Treat whole message as one keyword query
        q = re.sub(r"\b(notify me|please|i want|alerts?|about|news)\b", " ", text, flags=re.I)
        q = re.sub(r"\s+", " ", q).strip(" .,!")
        if len(q) >= 2:
            proposals.append(
                {
                    "title": q[:80],
                    "alert_type": "keyword",
                    "params": {"query": q[:200]},
                    "reason": "Using your message as a keyword watch",
                }
            )

    if not proposals:
        return {
            "reply": "I couldn’t extract a clear topic. Try something like:\n"
            "• Rain in Sholinganallur\n"
            "• CSK injury updates\n"
            "• News about Real Madrid",
            "proposals": [],
        }

    lines = ["Here’s what I’ll set up:"]
    for i, p in enumerate(proposals, 1):
        lines.append(f"{i}. {p['reason']}")
    lines.append("Confirm to save these watches, or describe something else.")
    return {"reply": "\n".join(lines), "proposals": proposals}
