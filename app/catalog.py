"""Verified product catalog + keyword retrieval, so only relevant items reach the LLM."""
import json
import re
from pathlib import Path

PRODUCTS = json.loads((Path(__file__).parent.parent / "catalog.json").read_text("utf-8"))["products"]

# Customer words -> words that appear in product names/categories/descriptions.
SYNONYMS = {
    "frying": ["oil", "groundnut", "sunflower"], "fry": ["oil", "groundnut", "sunflower"],
    "cooking": ["oil", "flour", "spices"], "oil": ["oil", "cold", "pressed"],
    "sweetener": ["honey", "jaggery", "sugar", "shakkar"], "sweet": ["honey", "jaggery", "chikki", "sweetener"],
    "sugar": ["jaggery", "honey", "shakkar", "sweetener"], "sugarfree": ["millet", "flour"],
    "diabetic": ["millet", "ragi", "low", "gi", "foxtail", "quinoa"],
    "protein": ["dal", "chana", "rajma", "moong", "peanut", "quinoa", "pulses", "masoor"],
    "pulses": ["dal", "chana", "rajma", "moong", "masoor", "beans"], "lentils": ["dal", "masoor", "moong"],
    "breakfast": ["poha", "oats", "flakes", "cereals", "millet", "puffed"],
    "snack": ["snacks", "chikki", "murukku", "mixture", "peanut", "puffed", "bar"],
    "snacks": ["snacks", "chikki", "murukku", "mixture", "peanut", "puffed", "bar"],
    "healthy": ["super", "food", "millet", "seeds", "quinoa"], "superfood": ["super", "food", "seeds", "powder"],
    "gluten": ["gluten", "millet", "ragi", "bajra", "quinoa", "foxtail"], "glutenfree": ["gluten", "millet", "ragi", "bajra", "quinoa"],
    "roti": ["flour", "atta", "bajra", "ragi", "wheat"], "chapati": ["flour", "atta", "wheat"],
    "rice": ["rice", "poha", "puffed", "brown"], "grains": ["rice", "millet", "cereals", "quinoa"],
    "spice": ["spices", "powder", "seed", "pepper", "cumin"], "masala": ["spices", "powder", "masala"],
    "weight": ["millet", "quinoa", "seeds", "low", "gi"], "gift": ["honey", "chikki", "snacks", "oil"],
    "tea": ["tea", "honey", "jaggery"], "kids": ["chikki", "snacks", "honey", "bar"],
}
STOP = {"i", "a", "an", "the", "for", "of", "and", "or", "to", "my", "me", "in", "on", "with", "is", "are", "need",
        "want", "some", "any", "please", "budget", "rupees", "family", "month", "monthly", "under", "about", "can", "you"}


def _tok(s: str):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _expand(query: str):
    words = {w for w in _tok(query) if w not in STOP}
    for w in list(words):
        key = w.rstrip("s") if w.rstrip("s") in SYNONYMS else w
        words |= set(SYNONYMS.get(key, []))
    return words


def _blob(p):
    return (_tok(p["name"]), _tok(str(p.get("category", ""))), _tok(str(p.get("description", ""))))


INDEX = [(p, *_blob(p)) for p in PRODUCTS]


def search(query: str, k: int = 12):
    q = _expand(query)
    scored = []
    for p, name, cat, desc in INDEX:
        score = 3 * len(q & name) + 2 * len(q & cat) + len(q & desc)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:k]]
