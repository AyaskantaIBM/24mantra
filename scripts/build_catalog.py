"""Build catalog.json from the public 24mantraorganic.com product sitemap + per-product .js endpoints.
Run:  python scripts/build_catalog.py      (polite: ~1 request per 0.7s, ~60 products)
Re-run before a demo to refresh prices/availability. Snapshot date is stored in the file."""
import html
import json
import re
import time
from datetime import date
from pathlib import Path

import httpx

BASE = "https://24mantraorganic.com"
HEAD = {"User-Agent": "Mozilla/5.0 (university class project; catalog snapshot)"}
OUT = Path(__file__).parent.parent / "catalog.json"


def text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def get(c, url, tries=4):
    for i in range(tries):
        r = c.get(url)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 20)))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"rate limited: {url}")


with httpx.Client(headers=HEAD, timeout=30, follow_redirects=True) as c:
    index = get(c, f"{BASE}/sitemap.xml").text
    prod_maps = [html.unescape(u) for u in re.findall(r"<loc>([^<]*sitemap_products[^<]*)</loc>", index)]
    handles = []
    for m in prod_maps:
        handles += re.findall(r"<loc>%s/products/([^<]+)</loc>" % re.escape(BASE), get(c, m).text)
    print(len(handles), "products found")

    products = []
    for h in dict.fromkeys(handles):
        try:
            d = get(c, f"{BASE}/products/{h}.js").json()
        except Exception as e:
            print("skip", h, e)
            continue
        products.append({
            "name": d["title"],
            "category": ", ".join(d.get("tags") or []) or d.get("type") or "",
            "variants": [{"size": v["title"], "price_inr": v["price"] / 100, "in_stock": v["available"]}
                         for v in d["variants"]],
            "description": text(d["description"])[:350],
            "url": f"{BASE}/products/{h}",
        })
        print("ok", d["title"])
        time.sleep(0.7)

OUT.write_text(json.dumps({"_note": f"Snapshot from {BASE} on {date.today()}. Prices in INR; stock may change.",
                           "products": products}, ensure_ascii=False, indent=1), "utf-8")
print("wrote", len(products), "products ->", OUT)
