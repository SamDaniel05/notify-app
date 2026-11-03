"""Rules + NN intent. Booking/trend helpers when LLM is offline."""
from __future__ import annotations
import re
from datetime import date, timedelta
from typing import Any

try:
    from .ml_intent import classify_intent
except Exception:
    def classify_intent(text, min_conf=0.55):
        return {"intent": "unknown", "confidence": 0.0, "scores": {}}

WEATHER_WORDS = re.compile(r"(?:\brain(?:s|y)?\b|\bweather\b|\bstorm\b|\bmonsoon\b|மழை)", re.I)
REMINDER_WORDS = re.compile(r"(?i)\b(remind|reminder|every\s+\d+|daily|for\s+the\s+next|next\s+\d+)\b")
SNOOZE_WORDS = re.compile(r"(?i)\b(not\s+today|snooze|after\s+\d+|tomorrow|postpone|skip\s+today)\b")
DONE_WORDS = re.compile(r"(?i)\b(done|finished|completed|i\s+did\s+it|mark\s+done)\b")
BOOKING_WORDS = re.compile(
    r"(?i)\b(booking\s*s?\s*open|advance\s+booking|tickets?\s+open|book\s+tickets?|"
    r"seat\s*s?\s*(open|unlock)|bookmyshow|theatre\s+booking|movie\s+booking)\b"
)
TREND_WORDS = re.compile(r"(?i)\b(trend(?:ing)?|viral\s+sound|challenge|reel\s+trend)\b")
PLACE_AFTER = re.compile(r"(?:in|at|near|around|for)\s+([A-Za-z\u0B80-\u0BFFa-z][A-Za-z\u0B80-\u0BFFa-z .'\-]{1,48})", re.I)
KNOWN = ["Kodambakkam","Chennai Central","Wimco Nagar","Sholinganallur","Tambaram","T Nagar","Velachery","Chennai"]
JUNK = re.compile(r"^(hi|hello|hey|ok|okay|test|yo|thanks|thank you|help|\.|\?|!+)$", re.I)

def _clean(s):
    s = (s or "").strip(" .,!?;:\"'")
    return re.sub(r"\s+", " ", s).strip(" .,!")

def _place(text):
    low = text.lower()
    for p in sorted(KNOWN, key=len, reverse=True):
        if p.lower() in low:
            return p
    m = PLACE_AFTER.search(text)
    if not m:
        return None
    place = _clean(m.group(1))
    return place[:80] if len(place) >= 2 else None

def _interval(text):
    m = re.search(r"(?i)every\s+(\d+)\s*days?", text)
    if m: return max(1, int(m.group(1)))
    m = re.search(r"(?i)every\s+(\d+)\s*weeks?", text)
    if m: return max(1, int(m.group(1))*7)
    return None

def _days(text):
    m = re.search(r"(?i)(?:for\s+)?(?:the\s+)?next\s+(\d+)\s*weeks?", text)
    if m: return max(1, int(m.group(1))*7)
    m = re.search(r"(?i)(?:for\s+)?(?:the\s+)?next\s+(\d+)\s*days?", text)
    if m: return max(1, int(m.group(1)))
    return 14

def _time(text):
    m = re.search(r"(?i)\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if m:
        h, minute = int(m.group(1)), int(m.group(2) or 0)
        ap = (m.group(3) or "").lower()
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
        return f"{h:02d}:{minute:02d}"
    return "10:00"

def _msg(text):
    t = re.sub(r"(?i)\bremind\s+me\s+(to\s+)?", "", text)
    t = re.sub(r"(?i)\bevery\s+\d+\s*(days?|weeks?)\b", "", t)
    t = re.sub(r"(?i)\bfor\s+(the\s+)?next\s+\d+\s*(days?|weeks?)\b", "", t)
    t = re.sub(r"(?i)\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?\b", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .,!")
    return t[:200] or text[:200]

def _snooze_days(text):
    if re.search(r"(?i)\btomorrow\b", text): return 1
    m = re.search(r"(?i)(?:after|in|for)\s+(\d+)\s*days?", text)
    if m: return max(1, int(m.group(1)))
    return 1

def parse_control_command(text):
    t = (text or "").strip()
    if not t: return None
    if SNOOZE_WORDS.search(t):
        return {"action": "snooze", "days": _snooze_days(t), "query": _msg(t) or t}
    if DONE_WORDS.search(t):
        return {"action": "done", "query": _msg(t) or t}
    return None

def _movie_name(text: str) -> str | None:
    """Best-effort movie title extraction for booking phrases."""
    t = text
    t = re.sub(r"(?i)\b(track|tell me|notify|alert|when|if|for|the|a|an)\b", " ", t)
    t = re.sub(
        r"(?i)\b(bookings?\s*open|advance\s+booking|tickets?\s*(open|on\s+sale)|book\s+tickets?|"
        r"seat\s*s?\s*(open|unlock)|bookmyshow|theatre|theater|movie|in\s+chennai|chennai)\b",
        " ",
        t,
    )
    t = _clean(t)
    if len(t) < 2:
        return None
    return t[:80]

def _booking_proposal(text: str) -> dict | None:
    if not BOOKING_WORDS.search(text) and not re.search(r"(?i)\b(movie|film|theatre|theater)\b", text):
        if not re.search(r"(?i)\bbookings?\b", text):
            return None
    movie = _movie_name(text)
    city = _place(text)
    if movie:
        q = f"{movie} bookings open"
        if city:
            q = f"{movie} bookings open {city}"
        title = f"Bookings · {movie}" + (f" · {city}" if city else "")
    else:
        q = "movie bookings open"
        title = "Movie bookings open"
    return {
        "title": title[:120],
        "alert_type": "keyword",
        "params": {"query": q[:200], "kind": "booking"},
        "reason": f"Watch public news for: {q} (not live seat maps)",
    }

def _trend_proposal(text: str) -> dict | None:
    if not TREND_WORDS.search(text):
        return None
    t = re.sub(r"(?i)\b(track|follow|remind me to|do|post|the|a|an|trend(?:ing)?|viral\s+sound|challenge)\b", " ", text)
    name = _clean(t) or "trending"
    return {
        "title": f"Trend · {name[:60]}",
        "alert_type": "keyword",
        "params": {"query": name[:200], "kind": "trend"},
        "reason": f"Trend / topic watch for “{name[:60]}”",
    }

def _reminder(text):
    interval = _interval(text)
    if not (REMINDER_WORDS.search(text) or interval):
        if not re.search(r"(?i)\b(efootball|coc|bing|clean\s+ac|post\s+the\s+trend|do\s+the\s+trend)\b", text):
            return None
        if not re.search(r"(?i)\b(daily|every|remind|next\s+\d+)\b", text):
            return None
    message = _msg(text)
    if len(message) < 3: return None
    tl = _time(text)
    today = date.today()
    if interval:
        nd = (today + timedelta(days=1)).isoformat()
        return {
            "title": message[:80], "alert_type": "reminder",
            "params": {"message": message, "mode": "interval", "interval_days": interval,
                       "time_local": tl, "timezone": "Asia/Kolkata", "next_due": nd},
            "reason": f"Recurring every {interval} days at {tl} IST: {message} (next: {nd})",
        }
    days = _days(text)
    return {
        "title": message[:80], "alert_type": "reminder",
        "params": {"message": message, "mode": "daily_window", "days": days,
                   "time_local": tl, "timezone": "Asia/Kolkata"},
        "reason": f"Daily reminder for {days} day(s) at {tl} IST: {message}",
    }

def extract_intents(message: str) -> dict[str, Any]:
    text = (message or "").strip()
    ml = classify_intent(text) if text else {"intent": "unknown", "confidence": 0.0}
    if text and ml.get("intent") == "junk" and ml.get("confidence", 0) >= 0.7 and len(text) < 40:
        return {"reply": "I'm your personal assistant. Try reminders, weather, trends, or movie booking watches.",
                "proposals": [], "speak": True, "ml_intent": ml}
    if not text:
        return {"reply": "I'm your personal assistant. Try reminders, weather, news, or booking watches.",
                "proposals": [], "speak": True}
    ctrl = parse_control_command(text)
    if ctrl and not _interval(text) and re.search(r"(?i)not\s+today|snooze|after\s+\d+|tomorrow|done|finished", text):
        return {"reply": "", "proposals": [], "control": ctrl, "ml_intent": ml}
    if len(text) < 4 or JUNK.match(text):
        return {"reply": "Tell me a task or watch.", "proposals": [], "speak": True, "ml_intent": ml}

    proposals = []

    book = _booking_proposal(text)
    if book:
        proposals.append(book)

    trend = _trend_proposal(text)
    if trend:
        proposals.append(trend)

    rem = _reminder(text)
    if rem:
        proposals.append(rem)
        if not WEATHER_WORDS.search(text) and not book and not re.search(r"(?i)\bnews\b", text):
            if not trend:
                lines = ["Here's what I'll set up:"] + [f"{i}. {p['reason']}" for i, p in enumerate(proposals, 1)]
                lines.append("Confirm to save, or describe something else.")
                return {"reply": "\n".join(lines), "proposals": proposals, "speak": True, "ml_intent": ml}

    if WEATHER_WORDS.search(text):
        place = _place(text)
        if place:
            proposals.append({"title": f"Rain / weather · {place}", "alert_type": "weather",
                              "params": {"place_name": place}, "reason": f"Weather / rain watch for {place}"})
        elif not book:
            return {"reply": "Need a place for weather. Try: Rain in Tambaram", "proposals": [], "speak": True, "ml_intent": ml}

    if re.search(r"(?i)\b(news|about|regarding|follow)\b", text) or (not rem and not WEATHER_WORDS.search(text) and not book and not trend):
        m = re.search(r"(?i)(?:about|regarding|news(?:\s+about)?)\s+(.+)$", text)
        topic = _clean(m.group(1)) if m else _clean(re.sub(r"(?i)\b(news|updates?|please)\b", " ", text))
        if topic and len(topic) >= 2 and not JUNK.match(topic):
            # avoid duplicating booking query
            if not any((p.get("params") or {}).get("query") == topic for p in proposals):
                proposals.append({"title": topic[:80], "alert_type": "keyword",
                                  "params": {"query": topic[:200]}, "reason": f'Keyword / news watch for "{topic[:80]}"'})

    if not proposals:
        return {"reply": "Couldn't parse that. Try: Track Coolie bookings open in Chennai",
                "proposals": [], "speak": True, "ml_intent": ml}
    lines = ["Here's what I'll set up:"] + [f"{i}. {p['reason']}" for i, p in enumerate(proposals, 1)]
    lines.append("Confirm to save these watches, or describe something else.")
    return {"reply": "\n".join(lines), "proposals": proposals, "speak": True, "ml_intent": ml}
