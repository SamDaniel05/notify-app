"""Free rule-based intent + snooze. Optional free LLM later via env."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

WEATHER_WORDS = re.compile(
    r"(?:\brain(?:s|y)?\b|\bweather\b|\bstorm\b|\bdownpour\b|\bdrizzle\b|"
    r"\bflood(?:ing)?\b|\bmonsoon\b|மழை|வானிலை)",
    re.I,
)

REMINDER_WORDS = re.compile(
    r"(?i)\b(remind|reminder|remember|daily\s+login|daily\s+task|every\s+day|"
    r"each\s+day|every\s+\d+|for\s+the\s+next|next\s+\d+\s+weeks?|next\s+\d+\s+days?)\b"
)

SNOOZE_WORDS = re.compile(
    r"(?i)\b(not\s+today|snooze|skip\s+today|later|postpone|push\s+(it\s+)?back|"
    r"remind\s+me\s+after|after\s+\d+\s*days?|in\s+\d+\s*days?|tomorrow)\b"
)

DONE_WORDS = re.compile(r"(?i)\b(done|finished|completed|i\s+did\s+it|mark\s+done)\b")

SPLIT_CLAUSES = re.compile(
    r"\s*(?:,|\band\b|\balso\b|\bplus\b)\s*(?=news|update|updates|alert|alerts|about|regarding|follow|notify)|"
    r"\s+and\s+(?=news|update|updates|about|regarding)",
    re.I,
)

PLACE_AFTER = re.compile(
    r"(?:in|at|near|around|for)\s+([A-Za-z\u0B80-\u0BFFa-z][A-Za-z\u0B80-\u0BFFa-z .'\-]{1,48})",
    re.I,
)

KNOWN_PLACES = [
    "Kodambakkam", "Chennai Central", "Wimco Nagar", "Sholinganallur", "Tambaram",
    "T Nagar", "Anna Nagar", "Velachery", "Adyar", "Guindy", "Porur", "Ambattur",
    "Avadi", "Chromepet", "Pallavaram", "OMR", "ECR", "Chennai", "Coimbatore",
    "Madurai", "Trichy", "Salem",
]

JUNK = re.compile(
    r"^(hi|hello|hey|ok|okay|test|yo|sup|thanks|thank you|help|menu|start|\.|\?|!+)$",
    re.I,
)

STOP = {
    "when", "it", "is", "to", "my", "the", "a", "an", "me", "please", "now", "today",
    "tonight", "tomorrow", "area", "city", "news", "update", "updates", "alert",
    "alerts", "notify", "notification", "about", "regarding", "follow", "watch",
    "want", "i", "and", "or", "for", "of", "on", "in", "at", "near",
}


def _clean(s: str) -> str:
    s = (s or "").strip(" .,!?;:\"'“”")
    s = re.sub(r"\b(please|now|today|tonight|tomorrow|area|city|news|updates?|alerts?)\b", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" .,!")


def _find_place(text: str) -> str | None:
    lower = text.lower()
    for p in sorted(KNOWN_PLACES, key=len, reverse=True):
        if p.lower() in lower:
            return p
    m = PLACE_AFTER.search(text)
    if not m:
        return None
    place = _clean(m.group(1))
    place = re.split(r"\s+(and|or|about|regarding|news|updates?)\b", place, flags=re.I)[0].strip()
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
    for m in re.finditer(r"\b(?:about|regarding|on|follow|watch|news(?:\s+about)?)\s+(.+)$", text, re.I):
        chunk = re.sub(r"\b(news|updates?|alerts?|please|me|the)\b", " ", m.group(1), flags=re.I)
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


def _parse_interval_days(text: str) -> int | None:
    m = re.search(r"(?i)every\s+(\d+)\s*days?", text)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(?i)every\s+(\d+)\s*weeks?", text)
    if m:
        return max(1, int(m.group(1)) * 7)
    m = re.search(r"(?i)once\s+in\s+(\d+)\s*days?", text)
    if m:
        return max(1, int(m.group(1)))
    return None


def _parse_duration_days(text: str) -> int:
    m = re.search(r"(?i)(?:for\s+)?(?:the\s+)?next\s+(\d+)\s*weeks?", text)
    if m:
        return max(1, int(m.group(1)) * 7)
    m = re.search(r"(?i)(?:for\s+)?(?:the\s+)?next\s+(\d+)\s*days?", text)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(?i)(?:for\s+)(\d+)\s*weeks?", text)
    if m:
        return max(1, int(m.group(1)) * 7)
    m = re.search(r"(?i)(?:for\s+)(\d+)\s*days?", text)
    if m:
        return max(1, int(m.group(1)))
    if re.search(r"(?i)\bevery\s+day\b|\bdaily\b", text):
        return 14
    return 14


def _parse_time_local(text: str) -> str:
    m = re.search(r"(?i)\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if m:
        h = int(m.group(1))
        minute = int(m.group(2) or 0)
        ap = (m.group(3) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{minute:02d}"
    m = re.search(r"(?i)\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text)
    if m:
        h, minute = int(m.group(1)), int(m.group(2))
        ap = (m.group(3) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{minute:02d}"
    if re.search(r"(?i)\b(morning)\b", text):
        return "09:00"
    if re.search(r"(?i)\b(evening|night)\b", text):
        return "20:00"
    return "10:00"


def _reminder_message(text: str) -> str:
    t = text
    t = re.sub(r"(?i)\bremind\s+me\s+(to\s+)?", "", t)
    t = re.sub(r"(?i)^\s*to\s+", "", t)
    t = re.sub(r"(?i)\bplease\s+", "", t)
    t = re.sub(r"(?i)\bevery\s+\d+\s*(days?|weeks?)\b", "", t)
    t = re.sub(r"(?i)\bonce\s+in\s+\d+\s*days?\b", "", t)
    t = re.sub(r"(?i)\bfor\s+(the\s+)?next\s+\d+\s*(days?|weeks?)\b", "", t)
    t = re.sub(r"(?i)\bfor\s+\d+\s*(days?|weeks?)\b", "", t)
    t = re.sub(r"(?i)\bevery\s+day\b|\bdaily\b", "", t)
    t = re.sub(r"(?i)\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?\b", "", t)
    t = re.sub(r"(?i)\b\d{1,2}:\d{2}\s*(am|pm)?\b", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .,!")
    t = re.sub(r"(?i)^to\s+", "", t).strip()
    return t[:200] if t else text[:200]


def _parse_snooze_days(text: str) -> int:
    if re.search(r"(?i)\btomorrow\b", text):
        return 1
    m = re.search(r"(?i)(?:after|in|for)\s+(\d+)\s*days?", text)
    if m:
        return max(1, int(m.group(1)))
    m = re.search(r"(?i)(?:after|in)\s+(\d+)\s*weeks?", text)
    if m:
        return max(1, int(m.group(1)) * 7)
    if re.search(r"(?i)not\s+today|snooze|skip\s+today|later|postpone", text):
        return 1
    return 1


def parse_control_command(text: str) -> dict[str, Any] | None:
    """Snooze / done — applied to existing reminders in the chat view."""
    t = (text or "").strip()
    if not t:
        return None
    if SNOOZE_WORDS.search(t):
        return {
            "action": "snooze",
            "days": _parse_snooze_days(t),
            "query": _reminder_message(t) or t,
        }
    if DONE_WORDS.search(t):
        return {
            "action": "done",
            "query": _reminder_message(t) or t,
        }
    return None


def _extract_reminder(text: str) -> dict[str, Any] | None:
    interval = _parse_interval_days(text)
    is_reminder = bool(REMINDER_WORDS.search(text) or interval)
    if not is_reminder:
        if not re.search(
            r"(?i)\b(efootball|e\s*football|coc|clash\s+of\s+clans|bing|daily\s+spin|daily\s+login|do\s+attacks|clean\s+ac|a/?c)\b",
            text,
        ):
            return None
        if not re.search(r"(?i)\b(daily|every|next\s+\d+|for\s+\d+|remind)\b", text):
            return None

    time_local = _parse_time_local(text)
    message = _reminder_message(text)
    if len(message) < 3:
        return None

    today = date.today()

    if interval:
        # Recurring every N days — first due = tomorrow (or today evening if time still ahead — keep simple: tomorrow)
        next_due = (today + timedelta(days=1)).isoformat()
        return {
            "title": message[:80],
            "alert_type": "reminder",
            "params": {
                "message": message,
                "mode": "interval",
                "interval_days": interval,
                "time_local": time_local,
                "timezone": "Asia/Kolkata",
                "next_due": next_due,
            },
            "reason": (
                f"Recurring every {interval} days at {time_local} IST: {message} "
                f"(next: {next_due}). Say “not today, after 2 days” to snooze."
            ),
        }

    days = _parse_duration_days(text)
    return {
        "title": message[:80],
        "alert_type": "reminder",
        "params": {
            "message": message,
            "mode": "daily_window",
            "days": days,
            "time_local": time_local,
            "timezone": "Asia/Kolkata",
        },
        "reason": f"Daily reminder for {days} day(s) at {time_local} IST: {message}",
    }


def extract_intents(message: str) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        return {
            "reply": (
                "I’m your personal assistant for alerts. Try:\n"
                "• Remind me to clean AC every 15 days\n"
                "• Not today, remind me after 2 days\n"
                "• Rain in Tambaram\n"
                "• News about CSK\n"
                "Or tap the mic and speak."
            ),
            "proposals": [],
            "speak": True,
        }

    # Control commands are handled in the view with DB access
    ctrl = parse_control_command(text)
    if ctrl and not _parse_interval_days(text):
        # If it looks like pure snooze/done, signal the view
        if re.search(r"(?i)not\s+today|snooze|after\s+\d+|in\s+\d+\s*days|tomorrow|done|finished|completed",
                      text):
            return {"reply": "", "proposals": [], "control": ctrl}

    if len(text) < 4 or JUNK.match(text):
        return {
            "reply": (
                "Tell me a task or watch. Examples:\n"
                "• Remind me to clean AC every 15 days\n"
                "• Remind me daily to open eFootball"
            ),
            "proposals": [],
            "speak": True,
        }

    proposals: list[dict[str, Any]] = []

    rem = _extract_reminder(text)
    if rem:
        proposals.append(rem)
        if not WEATHER_WORDS.search(text) and not re.search(r"(?i)\b(news|about\s+[A-Z])\b", text):
            lines = ["Here’s what I’ll set up:"]
            for i, p in enumerate(proposals, 1):
                lines.append(f"{i}. {p['reason']}")
            lines.append("Confirm to save, or describe something else.")
            return {"reply": "\n".join(lines), "proposals": proposals, "speak": True}

    clauses = [text]
    if WEATHER_WORDS.search(text) and re.search(r"\b(news|about|regarding|update)\b", text, re.I):
        parts = [p for p in SPLIT_CLAUSES.split(text) if p and not re.match(r"^(and|or|,)$", p.strip(), re.I)]
        clauses = parts if len(parts) >= 2 else re.split(r"\s+and\s+", text, maxsplit=1, flags=re.I)

    weather_done = False
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        is_weather_clause = bool(WEATHER_WORDS.search(clause))
        if is_weather_clause or (
            not weather_done and WEATHER_WORDS.search(text) and "news" not in clause.lower()
        ):
            place = _find_place(clause) or (_find_place(text) if is_weather_clause else None)
            if place and not weather_done:
                proposals.append(
                    {
                        "title": f"Rain / weather · {place}",
                        "alert_type": "weather",
                        "params": {"place_name": place},
                        "reason": f"Weather / rain watch for {place}",
                    }
                )
                weather_done = True
                if is_weather_clause and not re.search(r"\b(news|about|regarding)\b", clause, re.I):
                    continue
            elif is_weather_clause and not place:
                return {
                    "reply": "I can watch rain, but need a place. Try: “Rain in Tambaram”.",
                    "proposals": [],
                    "speak": True,
                }

        if re.search(r"\b(news|update|about|regarding|follow|injury|injuries)\b", clause, re.I) or (
            not is_weather_clause and not weather_done and not rem
        ):
            if is_weather_clause and weather_done and not re.search(r"\b(news|about)\b", clause, re.I):
                continue
            for t in _keyword_topics(clause):
                proposals.append(
                    {
                        "title": t,
                        "alert_type": "keyword",
                        "params": {"query": t},
                        "reason": f"Keyword / news watch for “{t}”",
                    }
                )

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
        q = re.sub(r"\b(notify me|please|i want|alerts?|about|news|updates?)\b", " ", text, flags=re.I)
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
                "I couldn’t parse that. Try:\n"
                "• Remind me to clean AC every 15 days\n"
                "• Not today, after 2 days\n"
                "• Rain in Tambaram"
            ),
            "proposals": [],
            "speak": True,
        }

    lines = ["Here’s what I’ll set up:"]
    for i, p in enumerate(proposals, 1):
        lines.append(f"{i}. {p['reason']}")
    lines.append("Confirm to save these watches, or describe something else.")
    return {"reply": "\n".join(lines), "proposals": proposals, "speak": True}
