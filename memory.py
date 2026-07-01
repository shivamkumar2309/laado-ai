"""
memory.py — Persistent SQLite memory system for LAADO.

Replaces the flat JSON file with a proper database that supports:
- Categorized facts (identity, preference, goal, mood, misc)
- Timestamped conversation history (for real recall, not just last N)
- Conversation summarization (so old context isn't lost, just compressed)
- Simple keyword-based recall search (lightweight, no embeddings needed
  for a project this size — keeps it fast and dependency-free)
"""

import sqlite3
import datetime
import os
import threading

DB_FILE = "laado_memory.db"
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        conn = _connect()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,           -- identity | preference | goal | mood | misc
                fact TEXT UNIQUE,
                created_at TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS conversation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,                -- user | assistant
                content TEXT,
                created_at TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT,
                created_at TEXT
            )
        """)

        conn.commit()
        conn.close()


# ═══════════════════════════════════════════════
#  PROFILE (name, title, tone — simple key/value)
# ═══════════════════════════════════════════════
def get_profile() -> dict:
    with _lock:
        conn = _connect()
        rows = conn.execute("SELECT key, value FROM profile").fetchall()
        conn.close()
    profile = {r["key"]: r["value"] for r in rows}
    profile.setdefault("name", "")
    profile.setdefault("title", "Sir")
    profile.setdefault("preferred_tone", "normal")
    return profile


def set_profile_value(key: str, value: str):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO profile (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
        conn.close()


# ═══════════════════════════════════════════════
#  FACTS (categorized, deduplicated)
# ═══════════════════════════════════════════════
def add_fact(fact: str, category: str = "misc"):
    fact = fact.strip()
    if not fact:
        return
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO facts (category, fact, created_at) VALUES (?, ?, ?)",
                (category, fact, datetime.datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def get_facts(limit: int = 20) -> list:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT category, fact FROM facts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
    return [f"[{r['category']}] {r['fact']}" for r in rows]


def search_facts(keyword: str, limit: int = 5) -> list:
    """Lightweight recall — finds facts containing a keyword."""
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT fact FROM facts WHERE fact LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{keyword}%", limit),
        ).fetchall()
        conn.close()
    return [r["fact"] for r in rows]


# ═══════════════════════════════════════════════
#  CONVERSATION LOG (full history, timestamped)
# ═══════════════════════════════════════════════
def log_message(role: str, content: str):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO conversation_log (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()


def get_recent_messages(limit: int = 20) -> list:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT role, content FROM conversation_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
    rows = list(reversed(rows))
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def count_messages() -> int:
    with _lock:
        conn = _connect()
        n = conn.execute("SELECT COUNT(*) AS n FROM conversation_log").fetchone()["n"]
        conn.close()
    return n


# ═══════════════════════════════════════════════
#  SUMMARIES (compressed long-term memory)
# ═══════════════════════════════════════════════
def save_summary(summary: str):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO summaries (summary, created_at) VALUES (?, ?)",
            (summary, datetime.datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()


def get_latest_summary() -> str:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT summary FROM summaries ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
    return row["summary"] if row else ""


def clear_old_messages(keep_last: int = 20):
    """After summarizing, trim the log so it doesn't grow forever."""
    with _lock:
        conn = _connect()
        ids = conn.execute(
            "SELECT id FROM conversation_log ORDER BY id DESC LIMIT ?", (keep_last,)
        ).fetchall()
        if ids:
            min_keep_id = min(r["id"] for r in ids)
            conn.execute("DELETE FROM conversation_log WHERE id < ?", (min_keep_id,))
            conn.commit()
        conn.close()


# Initialize on import
init_db()