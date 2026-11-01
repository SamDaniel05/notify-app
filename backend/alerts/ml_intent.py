"""Lightweight free intent classifier (no GPU, no paid API).

Trained offline on synthetic English phrases for Notify domains.
Synthetic hold-out accuracy is stored in the model JSON — real user text
will be lower; rules remain the source of truth for extraction.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

_MODEL_PATH = Path(__file__).with_name("intent_model.json")


def _tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


@lru_cache(maxsize=1)
def _load():
    if not _MODEL_PATH.exists():
        return None
    with open(_MODEL_PATH, encoding="utf-8") as f:
        return json.load(f)


def classify_intent(text: str, min_conf: float = 0.55) -> dict:
    """Return {intent, confidence, scores} or unknown if weak."""
    model = _load()
    if not model:
        return {"intent": "unknown", "confidence": 0.0, "scores": {}}

    vocab = model["vocab"]
    intents = model["intents"]
    weights = model["weights"]
    toks = _tokenize(text)
    vec = [0.0] * len(vocab)
    for w in toks:
        if w in vocab:
            vec[vocab[w]] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    vec = [x / norm for x in vec]

    scores: dict[str, float] = {}
    for intent in intents:
        w = weights[intent]["w"]
        b = weights[intent]["b"]
        z = sum(wi * xi for wi, xi in zip(w, vec)) + b
        if z < -30:
            p = 0.0
        elif z > 30:
            p = 1.0
        else:
            p = 1.0 / (1.0 + math.exp(-z))
        scores[intent] = p

    best = max(scores, key=scores.get)
    conf = scores[best]
    if conf < min_conf:
        return {"intent": "unknown", "confidence": conf, "scores": scores}
    return {"intent": best, "confidence": conf, "scores": scores}


def model_info() -> dict:
    m = _load()
    if not m:
        return {"loaded": False}
    return {
        "loaded": True,
        "version": m.get("version"),
        "accuracy_synthetic": m.get("accuracy_synthetic"),
        "intents": m.get("intents"),
    }
