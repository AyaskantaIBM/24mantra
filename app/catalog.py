"""Verified product catalog + simple keyword retrieval, so only relevant items reach the LLM."""
import json
import re
from pathlib import Path

PRODUCTS = json.loads((Path(__file__).parent.parent / "catalog.json").read_text("utf-8"))["products"]


def _tok(s: str):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def search(query: str, k: int = 12):
    q = _tok(query)
    scored = []
    for p in PRODUCTS:
        blob = _tok(" ".join(str(v) for v in p.values() if v))
        score = len(q & blob)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:k]]
