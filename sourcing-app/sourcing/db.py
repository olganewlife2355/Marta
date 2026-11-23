"""SQLite storage. One local file, no server."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("SOURCING_DB", Path(__file__).resolve().parent.parent / "data" / "sourcing.db"))

STATUSES = [
    "Новий",
    "Інвайт надіслано",
    "Конект",
    "Відповів",
    "Теплий",
    "Not now",
    "В процесі",
    "Найнятий",
    "Не підходить",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    jd TEXT NOT NULL DEFAULT '',
    kickoff TEXT NOT NULL DEFAULT '',
    scorecard_json TEXT,
    weights_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    linkedin_url TEXT UNIQUE,
    current_title TEXT DEFAULT '',
    current_company TEXT DEFAULT '',
    start_date TEXT DEFAULT '',
    tenure_text TEXT DEFAULT '',
    location TEXT DEFAULT '',
    email TEXT DEFAULT '',
    profile_text TEXT DEFAULT '',
    source TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pipeline (
    vacancy_id INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'Новий',
    score INTEGER,
    assessment_json TEXT,
    next_touch TEXT,
    notes TEXT DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (vacancy_id, candidate_id)
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# --- vacancies ---

def add_vacancy(conn, title: str, jd: str, kickoff: str) -> int:
    cur = conn.execute(
        "INSERT INTO vacancies (title, jd, kickoff, created_at) VALUES (?, ?, ?, ?)",
        (title, jd, kickoff, now()),
    )
    conn.commit()
    return cur.lastrowid


def update_vacancy(conn, vacancy_id: int, **fields) -> None:
    for key in ("scorecard", "weights"):
        if key in fields:
            fields[f"{key}_json"] = json.dumps(fields.pop(key), ensure_ascii=False)
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE vacancies SET {cols} WHERE id = ?", (*fields.values(), vacancy_id))
    conn.commit()


def list_vacancies(conn) -> list[dict]:
    return [_vacancy(r) for r in conn.execute("SELECT * FROM vacancies ORDER BY id DESC")]


def get_vacancy(conn, vacancy_id: int) -> dict:
    r = conn.execute("SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()
    return _vacancy(r) if r else None


def delete_vacancy(conn, vacancy_id: int) -> None:
    conn.execute("DELETE FROM vacancies WHERE id = ?", (vacancy_id,))
    conn.commit()


def _vacancy(r) -> dict:
    d = dict(r)
    d["scorecard"] = json.loads(d.pop("scorecard_json") or "null")
    d["weights"] = json.loads(d.pop("weights_json") or "null")
    return d


# --- candidates ---

CANDIDATE_FIELDS = [
    "full_name", "linkedin_url", "current_title", "current_company", "start_date",
    "tenure_text", "location", "email", "profile_text", "source",
]


def upsert_candidate(conn, data: dict) -> int:
    """Insert a candidate or update the existing one with the same LinkedIn URL."""
    row = {k: (str(data.get(k) or "").strip()) for k in CANDIDATE_FIELDS}
    row["linkedin_url"] = row["linkedin_url"].rstrip("/") or None
    existing = None
    if row["linkedin_url"]:
        existing = conn.execute("SELECT id FROM candidates WHERE linkedin_url = ?", (row["linkedin_url"],)).fetchone()
    if existing:
        updates = {k: v for k, v in row.items() if v and k != "linkedin_url"}
        if updates:
            cols = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE candidates SET {cols} WHERE id = ?", (*updates.values(), existing["id"]))
        conn.commit()
        return existing["id"]
    cols = ", ".join(CANDIDATE_FIELDS + ["created_at"])
    marks = ", ".join("?" for _ in range(len(CANDIDATE_FIELDS) + 1))
    cur = conn.execute(f"INSERT INTO candidates ({cols}) VALUES ({marks})", (*[row[k] for k in CANDIDATE_FIELDS], now()))
    conn.commit()
    return cur.lastrowid


def get_candidate(conn, candidate_id: int) -> dict:
    r = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    return dict(r) if r else None


# --- pipeline ---

def attach(conn, vacancy_id: int, candidate_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO pipeline (vacancy_id, candidate_id, updated_at) VALUES (?, ?, ?)",
        (vacancy_id, candidate_id, now()),
    )
    conn.commit()


def update_pipeline(conn, vacancy_id: int, candidate_id: int, **fields) -> None:
    if "assessment" in fields:
        fields["assessment_json"] = json.dumps(fields.pop("assessment"), ensure_ascii=False)
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE pipeline SET {cols} WHERE vacancy_id = ? AND candidate_id = ?",
        (*fields.values(), vacancy_id, candidate_id),
    )
    conn.commit()


def pipeline_rows(conn, vacancy_id: int | None = None) -> list[dict]:
    sql = """
        SELECT p.*, c.*, v.title AS vacancy_title
        FROM pipeline p
        JOIN candidates c ON c.id = p.candidate_id
        JOIN vacancies v ON v.id = p.vacancy_id
    """
    params: tuple = ()
    if vacancy_id is not None:
        sql += " WHERE p.vacancy_id = ?"
        params = (vacancy_id,)
    rows = []
    for r in conn.execute(sql + " ORDER BY p.score DESC NULLS LAST, c.full_name", params):
        d = dict(r)
        d["assessment"] = json.loads(d.pop("assessment_json") or "null")
        rows.append(d)
    return rows
