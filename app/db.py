"""Chat storage. Postgres (Neon) in the cloud, SQLite file locally. Same code for both."""
import os
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "sqlite:///chat.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
PK = "INTEGER PRIMARY KEY AUTOINCREMENT" if url.startswith("sqlite") else "SERIAL PRIMARY KEY"


def init():
    with engine.begin() as c:
        c.execute(text(f"""CREATE TABLE IF NOT EXISTS messages(
            id {PK}, session_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        c.execute(text("CREATE INDEX IF NOT EXISTS idx_msg_sid ON messages(session_id, id)"))


def save(sid: str, role: str, content: str):
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages(session_id,role,content) VALUES(:s,:r,:c)"),
                  {"s": sid, "r": role, "c": content})


def history(sid: str):
    with engine.connect() as c:
        rows = c.execute(text("SELECT role,content FROM messages WHERE session_id=:s ORDER BY id"),
                         {"s": sid}).all()
    return [{"role": r, "content": t} for r, t in rows]


def all_messages():
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT session_id,role,content,created_at FROM messages ORDER BY session_id,id")).all()
    return [{"session_id": a, "role": b, "content": d, "created_at": str(e)} for a, b, d, e in rows]
