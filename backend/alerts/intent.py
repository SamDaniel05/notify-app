"""Free rule-based intent extraction. No paid LLM required."""
from __future__ import annotations

import re
from typing import Any

WEATHER_WORDS = re.compile(
    r"(?i)(?:\brain(?:s|y)?\b|\bweather\b|\bstorm\b|\bdownpour\b|\bdrizzle\b|"
    r"\bflood(?:ing)?\b|\bmonsoon\b|மழை|வானிலை)"
)

# Split compound clauses: "weather in X and news about Y"
SPLIT_CLAUSES = re.compile(
    r"\s*(?:,|\band\b|\balso\b|\bplus\b)\s*(?=news|update|updates|alert|alerts|about|regarding|follow|notify)|"
    r"\s+and\s+(?=news|update|updates|about|regarding)",
    re.I,
)

PLACE_AFTER = re.compile(
    r"(?i)(?:in|at|near|around|for)\s+([A-Za-z\u0B80-\u0BFFa-z][A-Za-z\u0B80-\u0BFFa-z .'\-]{1,48})"
)

KNOWN_PLACES = [
    "Kodambakkam", "Chennai Central", "Wimco Nagar", "Sholinganallur", "Tambaram",
    "T Nagar", "Anna Nagar", "Velachery", "Adyar", "Guindy", "Porur", "Ambattur",
    "Avadi", "Chromepet", "Pallavaram", "OMR", "ECR", "Chennai", "Coimbatore",
    "Madurai", "Trichy", "Salem",
]

JUNK = re.compile(
    r"^(?i)(hi|hello|hey|ok|okay|test|yo|sup|thanks|thank you|help|menu|start|\.|\?|!+)$"
)

STOP = {
    "when", "it", "is", "to", "my", "the", "a", "an", "me", "please", "now", "today",
    "tonight", "tomorrow", "area", "city", "news", "update", "updates", "alert",
    "alerts", "notify", "notification", "about", "regarding", "follow", "watch",
    "want", "i", "and", "or", "for", "of", "on", "in", "at", "near",
}


def _clean(s: str) -> str:
    s = (s or "").strip(" .,!?;:\"'“”")
    s = re.sub(r"(?i)\b(please|now|today|tonight|tomorrow|area|city|news|updates?|alerts?)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .,!")


def _find_place(text: str) -> str | None:
    lower = text.lower()
    # Prefer known places (longest first)
    for p in sorted(KNOWN_PLACES, key=len, reverse=True):
        if p.lower() in lower:
            return p
    m = PLACE_AFTER.search(text)
    if not m:
        return None
    place = _clean(m.group(1))
    # Cut trailing junk phrases
    place = re.split(r"(?i)\s+(and|or|about|regarding|news|updates?)\b", place)[0].strip()
    place = _clean(place)
    if len(place) < 2 or place.lower() in STOP:
        return None
    return place[:80]


def _keyword_topics(text: str) -> list[str]:
    topics: list[str] = []
    for q in re.findall(r'["“](.+?)["”]', text):
        q = _clean(q)
        if len(q) >= 2:
            topics.append(q)

    for m in re.finditer(
        r"(?i)\b(?:about|regarding|on|follow|watch|news(?:\s+about)?)\s+(.+)$",
        text,
    ):
        chunk = m.group(1)
        chunk = re.sub(r"(?i)\b(news|updates?|alerts?|please|me|the)\b", " ", chunk)
        for p in re.split(r"\s*(?:,|/|\band\b|\bor\b)\s*", chunk):
            p = _clean(p)
            if len(p) >= 2 and p.lower() not in STOP:
                topics.append(p)

    if not topics:
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text):
            p = _clean(m.group(1))
            if p and p.lower() not in STOP and len(p) >= 2:
                topics.append(p)

    seen: set[str] = set()
    out: list[str] = []
    for t in topics:
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t[:120])
    return out[:5]


def extract_intents(message: str) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        return {
            "reply": (
                "Tell me what you want to follow. Examples:\n"
                "• Notify me when it rains in Tambaram\n"
                "• News about Real Madrid or CSK injuries\n"
                "• Updates on Tamil Nadu politics"
            ),
            "proposals": [],
        }

    if len(text) < 4 or JUNK.match(text):
        return {
            "reply": (
                "I need a concrete topic. Try:\n"
                "• Rain in Tambaram\n"
                "• CSK injury updates\n"
                "• News about Real Madrid"
            ),
            "proposals": [],
        }

    proposals: list[dict[str, Any]] = []

    # Split into weather vs news-ish clauses when both appear
    clauses = [text]
    if WEATHER_WORDS.search(text) and re.search(r"(?i)\b(news|about|regarding|update)\b", text):
        parts = SPLIT_CLAUSES.split(text)
        parts = [p for p in parts if p and not re.match(r"(?i)^(and|or|,)$", p.strip())]
        if len(parts) >= 2:
            clauses = parts
        else:
            # Heuristic split on " and "
            clauses = re.split(r"\s+and\s+", text, maxsplit=1, flags=re.I)

    weather_done = False
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        if WEATHER_WORDS.search(clause) or (not weather_done and WEATHER_WORDS.search(text) and "news" not in clause.lower()):
            if weather_done and not WEATHER_WORDS.search(clause):
                pass
            else:
                place = _find_place(clause) or _find_place(text)
                if place:
                    proposals.append(
                        {
                            "title": f"Rain / weather · {place}",
                            "alert_type": "weather",
                            "params": {"place_name": place},
                            "reason": f"Weather / rain watch for {place}",
                        }
                    )
                    weather_done = True
                    continue
                if WEATHER_WORDS.search(clause):
                    return {
                        "reply": "I can watch rain/weather, but need a place. "
                        "Try: “Notify me when it rains in Tambaram”.",
                        "proposals": [],
                    }

        # Keyword clause
        if re.search(r"(?i)\b(news|update|about|regarding|follow|injury|injuries|politics|score)\b", clause) or not weather_done:
            if WEATHER_WORDS.search(clause) and weather_done:
                continue
            for t in _keyword_topics(clause):
                # Skip if same as weather place
                if any(
                    p["alert_type"] == "weather"
                    and p["params"].get("place_name", "").lower() == t.lower()
                    for p in proposals
                ):
                    continue
                proposals.append(
                    {
                        "title": t,
                        "alert_type": "keyword",
                        "params": {"query": t},
                        "reason": f"Keyword / news watch for “{t}”",
                    }
                )

    # Dedupe by (type, canonical params)
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for p in proposals:
        key = f"{p['alert_type']}:{p['params']}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    proposals = uniq[:6]

    if not proposals:
        q = re.sub(
            r"(?i)\b(notify me|please|i want|alerts?|about|news|updates?)\b",
            " ",
            text,
        )
        q = _clean(re.sub(r"\s+", " ", q))
        if len(q) >= 3 and not JUNK.match(q):
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
            "reply": (
                "I couldn’t extract a clear topic. Try:\n"
                "• Rain in Sholinganallur\n"
                "• CSK injury updates\n"
                "• News about Real Madrid"
            ),
            "proposals": [],
        }

    lines = ["Here’s what I’ll set up:"]
    for i, p in enumerate(proposals, 1):
        lines.append(f"{i}. {p['reason']}")
    lines.append("Confirm to save these watches, or describe something else.")
    return {"reply": "\n".join(lines), "proposals": proposals}
