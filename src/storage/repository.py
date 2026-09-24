"""Repository SQLite: satu-satunya modul yang berisi SQL.

Tabel:
- articles: artikel unik per URL (dedup via UNIQUE constraint).
- fetch_runs: satu baris per siklus fetch.
- fetch_media_log: hasil per media per siklus (dipakai halaman status Fase 4).
"""

from __future__ import annotations

import datetime
import pathlib
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    media TEXT NOT NULL,
    title TEXT,
    summary TEXT,
    link TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_media ON articles(media);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS fetch_media_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
    media TEXT NOT NULL,
    status TEXT NOT NULL,
    new_articles INTEGER NOT NULL DEFAULT 0,
    total_entries INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fetch_media_log_run ON fetch_media_log(run_id);
"""


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _connect(db_path: str | pathlib.Path) -> sqlite3.Connection:
    db_path = pathlib.Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | pathlib.Path) -> None:
    """Buat tabel bila belum ada. Aman dipanggil berulang."""
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_articles(db_path: str | pathlib.Path, articles: list[dict]) -> int:
    """Simpan artikel; URL yang sudah ada dilewati (dedup).

    Kembalikan jumlah artikel BARU yang masuk.
    """
    if not articles:
        return 0
    now = _utcnow()
    rows = [
        (
            a["url"],
            a["media"],
            a.get("title"),
            a.get("summary"),
            a.get("link"),
            a.get("published_at"),
            now,
        )
        for a in articles
    ]
    with _connect(db_path) as conn:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO articles"
            " (url, media, title, summary, link, published_at, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        return conn.total_changes - before


def start_run(db_path: str | pathlib.Path) -> int:
    """Catat awal siklus fetch, kembalikan run_id."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO fetch_runs (started_at) VALUES (?)", (_utcnow(),)
        )
        return cur.lastrowid


def finish_run(db_path: str | pathlib.Path, run_id: int) -> None:
    """Catat akhir siklus fetch."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE fetch_runs SET finished_at = ? WHERE id = ?",
            (_utcnow(), run_id),
        )


def log_media(
    db_path: str | pathlib.Path,
    run_id: int,
    media: str,
    status: str,
    new_articles: int,
    total_entries: int,
    error: str | None = None,
) -> None:
    """Catat hasil fetch satu media dalam satu siklus."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO fetch_media_log"
            " (run_id, media, status, new_articles, total_entries, error, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, media, status, new_articles, total_entries, error, _utcnow()),
        )


def count_articles(db_path: str | pathlib.Path) -> int:
    """Jumlah total artikel di DB (helper diagnostik)."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM articles").fetchone()
        return row["n"]
