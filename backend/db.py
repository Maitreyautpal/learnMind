"""SQLite storage: users, materials, chunks, questions, responses, mastery, history.

Every write goes through connect(): the block is one transaction, committed
when it succeeds and rolled back if anything raises.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,              -- pdf | notes | youtube
    source TEXT,                     -- file name or URL
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_sec REAL,                  -- YouTube chunks only
    end_sec REAL,
    embed_model TEXT,
    embedding BLOB
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    chunk_id INTEGER,
    concept TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,           -- JSON list of 4 strings
    correct_idx INTEGER NOT NULL,
    explanation TEXT,
    difficulty_est REAL NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    concept TEXT NOT NULL,
    selected_idx INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    interaction_no INTEGER NOT NULL,
    mastery_before REAL NOT NULL,
    mastery_after REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mastery (
    user_id INTEGER NOT NULL,
    concept TEXT NOT NULL,
    p_know REAL NOT NULL,
    attempts INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    last_interaction_no INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, concept)
);
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chunks_user ON chunks(user_id);
CREATE INDEX IF NOT EXISTS ix_questions_user ON questions(user_id, concept);
CREATE INDEX IF NOT EXISTS ix_responses_user ON responses(user_id, concept);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def log_event(conn, user_id: int, event: str, detail: str = "") -> None:
    conn.execute("INSERT INTO history(user_id,event,detail,created_at) VALUES (?,?,?,?)",
                 (user_id, event, detail, now()))


# ---------------------------------------------------------------- users
def get_or_create_user(name: str) -> dict:
    name = name.strip()
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
        if row is None:
            cur = c.execute("INSERT INTO users(name,created_at) VALUES (?,?)", (name, now()))
            row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
            log_event(c, row["id"], "user_created", name)
        return dict(row)


def list_users() -> list:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users ORDER BY name")]


def get_user(user_id: int) -> Optional[dict]:
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


# ------------------------------------------------------------ materials
def add_material(user_id: int, title: str, kind: str, source: str,
                 chunks: Iterable[dict]) -> int:
    """Insert a material and its chunks in one transaction."""
    chunks = list(chunks)
    with connect() as c:
        cur = c.execute(
            "INSERT INTO materials(user_id,title,kind,source,created_at) VALUES (?,?,?,?,?)",
            (user_id, title, kind, source, now()))
        mid = cur.lastrowid
        c.executemany(
            "INSERT INTO chunks(material_id,user_id,idx,text,start_sec,end_sec) VALUES (?,?,?,?,?,?)",
            [(mid, user_id, i, ch["text"], ch.get("start_sec"), ch.get("end_sec"))
             for i, ch in enumerate(chunks)])
        log_event(c, user_id, "material_added", f"{kind}: {title} ({len(chunks)} chunks)")
        return mid


def list_materials(user_id: int) -> list:
    with connect() as c:
        rows = c.execute("""
            SELECT m.*,
                   (SELECT COUNT(*) FROM chunks   WHERE material_id=m.id) AS n_chunks,
                   (SELECT COUNT(*) FROM questions WHERE material_id=m.id) AS n_questions
            FROM materials m WHERE m.user_id=? ORDER BY m.id DESC""", (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["concepts"] = [x["concept"] for x in c.execute(
                "SELECT DISTINCT concept FROM questions WHERE material_id=? ORDER BY concept", (r["id"],))]
            out.append(d)
        return out


def get_material(material_id: int) -> Optional[dict]:
    with connect() as c:
        row = c.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        return dict(row) if row else None


def delete_material(user_id: int, material_id: int) -> bool:
    with connect() as c:
        row = c.execute("SELECT title FROM materials WHERE id=? AND user_id=?",
                        (material_id, user_id)).fetchone()
        if row is None:
            return False
        c.execute("DELETE FROM materials WHERE id=?", (material_id,))
        log_event(c, user_id, "material_deleted", row["title"])
        return True


# --------------------------------------------------------------- chunks
def get_chunks(user_id: int, material_id: Optional[int] = None) -> list:
    sql = """SELECT ch.*, m.title AS material_title, m.kind AS kind, m.source AS source
             FROM chunks ch JOIN materials m ON m.id = ch.material_id
             WHERE ch.user_id=?"""
    args = [user_id]
    if material_id is not None:
        sql += " AND ch.material_id=?"
        args.append(material_id)
    sql += " ORDER BY ch.material_id, ch.idx"
    with connect() as c:
        return [dict(r) for r in c.execute(sql, args)]


def update_embeddings(rows: Iterable[tuple]) -> None:
    """rows: (chunk_id, embed_model, blob)"""
    with connect() as c:
        c.executemany("UPDATE chunks SET embed_model=?, embedding=? WHERE id=?",
                      [(m, b, i) for i, m, b in rows])


# ------------------------------------------------------------ questions
def add_question(user_id: int, material_id: int, chunk_id: Optional[int], concept: str,
                 question: str, options: list, correct_idx: int, explanation: str,
                 difficulty_est: float) -> Optional[int]:
    with connect() as c:
        dup = c.execute("SELECT 1 FROM questions WHERE user_id=? AND material_id=? AND question=?",
                        (user_id, material_id, question)).fetchone()
        if dup:
            return None
        cur = c.execute(
            """INSERT INTO questions(user_id,material_id,chunk_id,concept,question,options,
               correct_idx,explanation,difficulty_est,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (user_id, material_id, chunk_id, concept, question, json.dumps(options),
             correct_idx, explanation, difficulty_est, now()))
        return cur.lastrowid


def get_question(question_id: int) -> Optional[dict]:
    with connect() as c:
        row = c.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["options"] = json.loads(d["options"])
        return d


def existing_concepts(user_id: int, material_id: Optional[int] = None) -> list:
    sql, args = "SELECT DISTINCT concept FROM questions WHERE user_id=?", [user_id]
    if material_id is not None:
        sql += " AND material_id=?"
        args.append(material_id)
    with connect() as c:
        return [r["concept"] for r in c.execute(sql, args)]


def unattempted_questions(user_id: int, concept: Optional[str] = None,
                          material_id: Optional[int] = None) -> list:
    sql = """SELECT q.* FROM questions q
             WHERE q.user_id=? AND q.id NOT IN
                   (SELECT question_id FROM responses WHERE user_id=?)"""
    args = [user_id, user_id]
    if concept:
        sql += " AND q.concept=?"
        args.append(concept)
    if material_id is not None:
        sql += " AND q.material_id=?"
        args.append(material_id)
    with connect() as c:
        out = []
        for r in c.execute(sql, args):
            d = dict(r)
            d["options"] = json.loads(d["options"])
            out.append(d)
        return out
