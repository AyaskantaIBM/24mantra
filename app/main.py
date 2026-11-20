import csv
import hmac
import html
import io
import json
import os
import re
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import catalog, db, llm

OPENING = ("Welcome to the 24 Mantra Organic Shopping Advisor! I can help you find and compare organic "
           "groceries based on your needs and budget. What are you shopping for today?")

SYSTEM = """You are an AI sales advisor in a SIMULATED sales interaction for 24 Mantra Organic (https://24mantraorganic.com/). You are NOT an officially authorised company representative; say so if asked.
Goal: help customers discover, evaluate and consider buying suitable products. Be friendly, persuasive, conversational and concise.
Rules:
1. Understand needs (shopping requirements, preferences, household size, dietary restrictions, intended use, budget). Ask only for what is missing.
2. Screen products using explicit criteria (category, preference, suitability, quantity, budget).
3. Compare options using clearly stated factors. Separate VERIFIED information (the catalog excerpt below) from assumptions. NEVER invent products, prices, stock, discounts, certifications or nutritional claims. You cannot browse the site; if something is not in the catalog, say it is unverified and ask the customer to confirm on https://24mantraorganic.com/.
4. Recommend 2-3 products or combinations, with advantages and limitations of each.
5. Encourage purchase of matching products. Give an official link only if it is in the catalog (otherwise the homepage) and explain the customer completes checkout on the website themselves. Suggest complementary items gently.
6. The customer decides. Never finalise a basket, place an order, or simulate checkout.
Format: short paragraphs or bullets; markdown links allowed."""

app = FastAPI(title="24 Mantra Advisor")
db.init()

# ---- simple in-memory rate limit (protects free LLM quota) ----
HITS: dict[str, deque] = defaultdict(deque)
LIMIT, WINDOW = int(os.getenv("RATE_LIMIT", "15")), 60


def rate_limit(key: str):
    now, q = time.time(), HITS[key]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(429, "Too many messages, please wait a minute.")
    q.append(now)


SID = re.compile(r"^[\w-]{8,64}$")


class ChatIn(BaseModel):
    sid: str
    message: str


@app.get("/health")
def health():
    return {"ok": True}  # ping this with UptimeRobot to avoid free-tier sleep


@app.get("/api/history")
def get_history(sid: str):
    if not SID.match(sid):
        raise HTTPException(400, "bad sid")
    h = db.history(sid)
    if not h:
        db.save(sid, "assistant", OPENING)
        h = [{"role": "assistant", "content": OPENING}]
    return h


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    msg = body.message.strip()
    if not SID.match(body.sid) or not msg or len(msg) > 2000:
        raise HTTPException(400, "bad request")
    ip = (request.headers.get("x-forwarded-for") or request.client.host).split(",")[0]
    rate_limit(ip)
    rate_limit("sid:" + body.sid)
    db.save(body.sid, "user", msg)
    hist = db.history(body.sid)[-30:]
    found = catalog.search(" ".join(m["content"] for m in hist if m["role"] == "user")[-600:])
    ctx = "VERIFIED CATALOG EXCERPT (JSON): " + json.dumps(found, ensure_ascii=False)
    try:
        reply = await llm.complete([{"role": "system", "content": SYSTEM + "\n\n" + ctx}] + hist)
    except Exception as e:
        print("LLM error:", e)
        raise HTTPException(502, "The advisor is busy right now. Please try again shortly.")
    db.save(body.sid, "assistant", reply)
    return {"reply": reply}


# ---- admin: readable transcripts + CSV export ----
def check_admin(key: str):
    k = os.getenv("ADMIN_KEY", "")
    if not k or not hmac.compare_digest(key.encode(), k.encode()):
        raise HTTPException(401, "unauthorized")


@app.get("/admin", response_class=HTMLResponse)
def admin(key: str = ""):
    check_admin(key)
    sessions: dict[str, list] = {}
    for m in db.all_messages():
        sessions.setdefault(m["session_id"], []).append(m)
    out = [f"<h2>{len(sessions)} conversations</h2><p><a href='/admin/export.csv?key={html.escape(key)}'>Download CSV</a></p>"]
    for sid, ms in sessions.items():
        out.append(f"<details><summary><b>{html.escape(sid[:8])}</b> — {len(ms)} msgs — {ms[0]['created_at']}</summary>")
        for m in ms:
            out.append(f"<p><b>{m['role']}</b> <small>{m['created_at']}</small><br>{html.escape(m['content'])}</p>")
        out.append("</details>")
    return "<body style='font-family:system-ui;max-width:800px;margin:auto'>" + "".join(out)


@app.get("/admin/export.csv")
def export(key: str = ""):
    check_admin(key)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["session_id", "role", "content", "created_at"])
    w.writeheader()
    w.writerows(db.all_messages())
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=chats.csv"})


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "public", html=True), name="static")
