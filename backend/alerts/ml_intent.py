"""Free intent models: neural mean-pool MLP (exported) — no paid API."""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

_MODEL_PATH = Path(__file__).with_name("intent_model.json")
_EMB_PATH = Path(__file__).with_name("intent_emb.json")


def _tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


@lru_cache(maxsize=1)
def _load():
    if not _MODEL_PATH.exists():
        return None
    with open(_MODEL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") == "torch_meanpool_mlp" and "emb" not in data and _EMB_PATH.exists():
        with open(_EMB_PATH, encoding="utf-8") as f:
            data["emb"] = json.load(f)
    return data


def _softmax(xs: list[float]) -> list[float]:
    m = max(xs) if xs else 0.0
    ex = [math.exp(x - m) for x in xs]
    s = sum(ex) or 1.0
    return [e / s for e in ex]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def classify_intent(text: str, min_conf: float = 0.55) -> dict:
    model = _load()
    if not model:
        return {"intent": "unknown", "confidence": 0.0, "scores": {}}

    if model.get("type") == "torch_meanpool_mlp":
        stoi = model["stoi"]
        maxlen = int(model.get("maxlen") or 24)
        ids = [stoi.get(w, 0) for w in _tokenize(text)][:maxlen]
        ids += [0] * (maxlen - len(ids))
        emb = model.get("emb")
        if not emb:
            return {"intent": "unknown", "confidence": 0.0, "scores": {}, "model": "nn-missing-emb"}
        dim = len(emb[0])
        acc = [0.0] * dim
        n = 0
        for i in ids:
            if i == 0:
                continue
            row = emb[i]
            for d in range(dim):
                acc[d] += row[d]
            n += 1
        pooled = [0.0] * dim if n == 0 else [x / n for x in acc]
        w0, b0 = model["fc0_w"], model["fc0_b"]
        h = [max(0.0, _dot(row, pooled) + b0[i]) for i, row in enumerate(w0)]
        w3, b3 = model["fc3_w"], model["fc3_b"]
        logits = [_dot(row, h) + b3[i] for i, row in enumerate(w3)]
        probs = _softmax(logits)
        intents = model["intents"]
        best_i = max(range(len(probs)), key=lambda i: probs[i])
        conf = probs[best_i]
        scores = {intents[i]: probs[i] for i in range(len(intents))}
        intent = intents[best_i] if conf >= min_conf else "unknown"
        return {"intent": intent, "confidence": conf, "scores": scores, "model": "nn"}

    return {"intent": "unknown", "confidence": 0.0, "scores": {}, "model": "unsupported"}


def model_info() -> dict:
    m = _load()
    if not m:
        return {"loaded": False}
    return {
        "loaded": True,
        "type": m.get("type"),
        "accuracy_synthetic": m.get("accuracy_synthetic"),
        "intents": m.get("intents"),
        "has_emb": bool(m.get("emb")),
    }
