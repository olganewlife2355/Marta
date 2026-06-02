"""
SQLite storage with MD5-based deduplication for collected job posts.
"""

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class Storage:
    """SQLite-backed storage for job posts with deduplication."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS posts (
        id          TEXT PRIMARY KEY,
        source      TEXT NOT NULL,
        title       TEXT,
        company     TEXT,
        url         TEXT,
        date        TEXT,
        salary      TEXT,
        location    TEXT,
        skills      TEXT,   -- JSON list
        description TEXT,
        raw         TEXT,
        extra       TEXT,   -- JSON for source-specific fields
        notified    INTEGER DEFAULT 0,
        created_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS companies (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT UNIQUE NOT NULL,
        telegram    TEXT,
        linkedin    TEXT,
        instagram   TEXT,
        dou         TEXT,
        threads     TEXT,
        created_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS reports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        type        TEXT NOT NULL,   -- 'daily' or 'weekly'
        content     TEXT NOT NULL,
        format      TEXT NOT NULL,   -- 'text' or 'html'
        created_at  TEXT NOT NULL,
        filepath    TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_posts_source ON posts (source);
    CREATE INDEX IF NOT EXISTS idx_posts_notified ON posts (notified);
    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts (created_at);
    """

    def __init__(self, db_path: str):
        """
        Initialize storage.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)
        logger.info("Storage initialized at %s", self.db_path)

    def _compute_hash(self, post: Dict) -> str:
        """Compute stable MD5 hash for a post based on URL + title."""
        raw = f"{post.get('url', '')}:{post.get('title', '')}"
        return hashlib.md5(raw.encode()).hexdigest()

    def save_post(self, post: Dict) -> bool:
        """
        Save a post to the database. Skips duplicates.

        Args:
            post: Post dict with fields from collectors.

        Returns:
            True if inserted (new), False if already existed.
        """
        post_id = post.get("id") or self._compute_hash(post)
        now = datetime.utcnow().isoformat()

        # Extract known fields; put rest in extra
        known_fields = {"id", "source", "title", "company", "url", "date",
                        "salary", "location", "skills", "description", "raw"}
        extra = {k: v for k, v in post.items() if k not in known_fields}

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO posts
                        (id, source, title, company, url, date, salary,
                         location, skills, description, raw, extra, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post_id,
                        post.get("source", ""),
                        post.get("title", ""),
                        post.get("company", ""),
                        post.get("url", ""),
                        post.get("date", ""),
                        post.get("salary", ""),
                        post.get("location", ""),
                        json.dumps(post.get("skills", [])),
                        post.get("description", ""),
                        post.get("raw", ""),
                        json.dumps(extra),
                        now,
                    ),
                )
                inserted = conn.execute(
                    "SELECT changes() AS c"
                ).fetchone()["c"]
            return bool(inserted)
        except Exception as exc:
            logger.error("Error saving post %s: %s", post_id, exc)
            return False

    def save_posts(self, posts: List[Dict]) -> Tuple[int, int]:
        """
        Save multiple posts.

        Returns:
            Tuple of (new_count, duplicate_count).
        """
        new_count = 0
        dup_count = 0
        for post in posts:
            if self.save_post(post):
                new_count += 1
            else:
                dup_count += 1
        logger.info("Saved %d new posts, %d duplicates skipped", new_count, dup_count)
        return new_count, dup_count

    def get_new_posts(self, limit: int = 100) -> List[Dict]:
        """
        Retrieve posts that haven't been notified yet.

        Args:
            limit: Max number of posts to return.

        Returns:
            List of post dicts.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM posts
                WHERE notified = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def mark_notified(self, post_ids: List[str]):
        """Mark posts as notified."""
        if not post_ids:
            return
        placeholders = ",".join("?" * len(post_ids))
        with self._connect() as conn:
            conn.execute(
                f"UPDATE posts SET notified = 1 WHERE id IN ({placeholders})",
                post_ids,
            )
        logger.info("Marked %d posts as notified", len(post_ids))

    def get_posts_since(self, since: datetime, source: Optional[str] = None) -> List[Dict]:
        """
        Get posts created since a given datetime.

        Args:
            since: Datetime threshold.
            source: Optional source filter.

        Returns:
            List of post dicts.
        """
        query = "SELECT * FROM posts WHERE created_at >= ?"
        params: list = [since.isoformat()]
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> Dict:
        """
        Return basic statistics about stored posts.

        Returns:
            Dict with counts by source, total, unnotified, etc.
        """
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"]
            unnotified = conn.execute(
                "SELECT COUNT(*) AS c FROM posts WHERE notified = 0"
            ).fetchone()["c"]
            by_source = conn.execute(
                "SELECT source, COUNT(*) AS c FROM posts GROUP BY source"
            ).fetchall()
            by_company = conn.execute(
                "SELECT company, COUNT(*) AS c FROM posts GROUP BY company ORDER BY c DESC LIMIT 10"
            ).fetchall()

        return {
            "total": total,
            "unnotified": unnotified,
            "by_source": {r["source"]: r["c"] for r in by_source},
            "top_companies": {r["company"]: r["c"] for r in by_company},
        }

    def save_report(self, report_type: str, content: str, fmt: str, filepath: Optional[str] = None):
        """
        Save a generated report to the reports table.

        Args:
            report_type: 'daily' or 'weekly'.
            content: Report content.
            fmt: 'text' or 'html'.
            filepath: Optional path where report was also saved to disk.
        """
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reports (type, content, format, created_at, filepath) VALUES (?, ?, ?, ?, ?)",
                (report_type, content, fmt, now, filepath),
            )
        logger.info("Saved %s %s report to database", report_type, fmt)

    def upsert_company(self, company: Dict):
        """Insert or update a company record."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO companies (name, telegram, linkedin, instagram, dou, threads, created_at)
                VALUES (:name, :telegram, :linkedin, :instagram, :dou, :threads, :created_at)
                ON CONFLICT(name) DO UPDATE SET
                    telegram  = excluded.telegram,
                    linkedin  = excluded.linkedin,
                    instagram = excluded.instagram,
                    dou       = excluded.dou,
                    threads   = excluded.threads
                """,
                {
                    "name": company.get("name", ""),
                    "telegram": company.get("telegram", ""),
                    "linkedin": company.get("linkedin", ""),
                    "instagram": company.get("instagram", ""),
                    "dou": company.get("dou", ""),
                    "threads": company.get("threads", ""),
                    "created_at": now,
                },
            )

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert a sqlite3.Row to a plain dict, deserializing JSON fields."""
        d = dict(row)
        for field in ("skills", "extra"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
