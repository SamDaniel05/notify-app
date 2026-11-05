"""Parallel free-LLM ensemble + merge. Enabled with ENSEMBLE_LLM=1."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .gemini_llm import gemini_enabled, interpret_with_gemini
from .groq_llm import groq_enabled, interpret_with_groq
from .hf_llm import hf_enabled, interpret_with_hf
from .openrouter_llm import interpret_with_openrouter, openrouter_enabled


def ensemble_enabled() -> bool:
    v = (os.environ.get("ENSEMBLE_LLM") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _providers() -> list[tuple[str, Callable[[str], dict | None]]]:
    out: list[tuple[str, Callable[[str], dict | None]]] = []
    if groq_enabled():
        out.append(("groq", interpret_with_groq))
    if gemini_enabled():
        out.append(("gemini", interpret_with_gemini))
    if openrouter_enabled():
        out.append(("openrouter", interpret_with_openrouter))
    if hf_enabled():
        out.append(("hf", interpret_with_hf))
    return out


def _run_one(name: str, fn: Callable, message: str) -> tuple[str, dict | None]:
    try:
        return name, fn(message)
    except Exception:
        return name, None


def _score(result: dict) -> int:
    """Higher = more useful structured answer."""
    if not result:
        return 0
    s = 0
    if result.get("control"):
        s += 50
    props = result.get("proposals") or []
    s += min(30, 10 * len(props))
    reply = (result.get("reply") or "").strip()
    if reply and len(reply) > 8:
        s += 5
    if result.get("source"):
        s += 1
    return s


def _proposal_key(p: dict) -> str:
    at = p.get("alert_type") or ""
    params = p.get("params") or {}
    if at == "weather":
        return f"weather:{(params.get('place_name') or '').lower()}"
    if at == "reminder":
        return f"reminder:{(params.get('message') or p.get('title') or '').lower()[:80]}"
    if at == "keyword":
        return f"keyword:{(params.get('query') or '').lower()}"
    return f"{at}:{p.get('title', '')}".lower()


def _merge(results: list[dict]) -> dict[str, Any] | None:
    usable = [r for r in results if r and (r.get("proposals") or r.get("control") or r.get("reply"))]
    if not usable:
        return None

    # Prefer any clear control (snooze/done)
    controls = [r for r in usable if r.get("control")]
    if controls:
        best_c = max(controls, key=_score)
        out = dict(best_c)
        out["source"] = "ensemble:" + ",".join(
            sorted({str(r.get("source") or "?") for r in usable})
        )
        out["ensemble_count"] = len(usable)
        return out

    # Merge proposals by key; keep highest-score occurrence
    best_by_key: dict[str, tuple[int, dict]] = {}
    replies: list[str] = []
    sources: list[str] = []
    for r in usable:
        sources.append(str(r.get("source") or "?"))
        if r.get("reply"):
            replies.append(str(r["reply"]).strip())
        for p in r.get("proposals") or []:
            if not isinstance(p, dict):
                continue
            k = _proposal_key(p)
            sc = _score({"proposals": [p], "reply": r.get("reply")})
            if k not in best_by_key or sc > best_by_key[k][0]:
                best_by_key[k] = (sc, p)

    proposals = [pair[1] for pair in best_by_key.values()][:6]

    # Pick richest reply among those that produced proposals, else longest
    reply = ""
    if proposals:
        with_props = [r for r in usable if r.get("proposals")]
        if with_props:
            reply = max(with_props, key=_score).get("reply") or ""
    if not reply and replies:
        reply = max(replies, key=len)
    if not reply and proposals:
        lines = ["Here's what I'll set up:"]
        for i, p in enumerate(proposals, 1):
            lines.append(f"{i}. {p.get('reason') or p.get('title')}")
        lines.append("Confirm to save, or describe something else.")
        reply = "\n".join(lines)

    return {
        "reply": reply or "Okay.",
        "proposals": proposals,
        "speak": True,
        "source": "ensemble:" + ",".join(sorted(set(sources))),
        "ensemble_count": len(usable),
    }


def interpret_ensemble(message: str) -> dict[str, Any] | None:
    providers = _providers()
    if not providers:
        return None
    if len(providers) == 1:
        name, fn = providers[0]
        _, result = _run_one(name, fn, message)
        return result

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(providers)) as ex:
        futs = {ex.submit(_run_one, name, fn, message): name for name, fn in providers}
        for fut in as_completed(futs, timeout=35):
            try:
                _name, result = fut.result()
                if result:
                    results.append(result)
            except Exception:
                continue
    return _merge(results)
