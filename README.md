# 24 Mantra Advisory Sales Agent

## Architecture (all free)
```
Browser (HTML chat, session id in localStorage)
   |  HTTPS
FastAPI + uvicorn on Render (free)  --->  Gemini API (free)  --fallback-->  Groq API (free)
   |  every user/assistant message saved
Neon Postgres (free)  <---  /admin?key=...  (transcripts + CSV download)
```
Unlike a hosted Gemini page, every message passes through *your* server, so you own the history.

## 1. Free accounts / keys
- Gemini key: https://aistudio.google.com/apikey
- (optional fallback) Groq key: https://console.groq.com/keys
- Neon Postgres: https://neon.tech -> new project -> copy connection string -> `DATABASE_URL`
- GitHub account (Render deploys from a repo)

## 2. Run locally
    python -m venv .venv; .venv\Scripts\activate
    pip install -r requirements.txt
    $env:GEMINI_API_KEY="xxx"; $env:ADMIN_KEY="secret"
    uvicorn app.main:app --reload
Open http://localhost:8000 . Without DATABASE_URL it uses a local SQLite file (chat.db).

## 3. Deploy on Render
1. Push this folder to GitHub.
2. Render -> New -> Blueprint (reads render.yaml) or Web Service: build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set env vars: DATABASE_URL, GEMINI_API_KEY, (GROQ_API_KEY), ADMIN_KEY.
4. Share `https://<name>.onrender.com`.
5. Free tier sleeps when idle: add a free UptimeRobot monitor on `/health` every 5 min.

## Reading chat history
`https://<name>.onrender.com/admin?key=<ADMIN_KEY>` (grouped by visitor) and `/admin/export.csv?key=...`.
Neon's SQL console also works: `SELECT * FROM messages;`

## Before the demo
- Fill catalog.json with verified products/prices/links from 24mantraorganic.com.
- Run `python tests/guardrails.py https://<name>.onrender.com` and keep the output for your report.
- The page tells visitors chats are stored; keep that notice.
