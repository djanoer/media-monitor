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
    """Simpan artikel; yang sudah ada dilewati (dedup).

    Dua lapis dedup:
    1. URL sudah ada -> skip (kunci utama).
    2. Pasangan (media, judul) sudah ada -> skip. Ini antisipasi token URL
       Google News yang bisa berubah antar siklus, sementara judul artikel stabil.

    Kembalikan jumlah artikel BARU yang masuk.
    """
    if not articles:
        return 0
    now = _utcnow()
    with _connect(db_path) as conn:
        # lapis 1: URL
        ph = ",".join("?" for _ in articles)
        existing_urls = {
            r[0]
            for r in conn.execute(
                f"SELECT url FROM articles WHERE url IN ({ph})",
                [a["url"] for a in articles],
            )
        }
        candidates = [a for a in articles if a["url"] not in existing_urls]

        # lapis 2: (media, judul)
        pairs = {
            (a["media"], a.get("title") or "")
            for a in candidates
            if (a.get("title") or "").strip()
        }
        existing_pairs: set[tuple[str, str]] = set()
        if pairs:
            ph2 = ",".join("(?,?)" for _ in pairs)
            params = [x for p in pairs for x in p]
            existing_pairs = {
                (r[0], r[1])
                for r in conn.execute(
                    f"SELECT media, title FROM articles WHERE (media, title) IN ({ph2})",
                    params,
                )
            }

        fresh: list[dict] = []
        seen_pairs = set(existing_pairs)
        for a in candidates:
            title = (a.get("title") or "").strip()
            key = (a["media"], a.get("title") or "")
            if title and key in seen_pairs:
                continue
            seen_pairs.add(key)
            fresh.append(a)

        if not fresh:
            return 0
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
            for a in fresh
        ]
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


def count_by_media(db_path: str | pathlib.Path) -> dict[str, int]:
    """Jumlah artikel per media (read-only, untuk viewer/dashboard)."""
    with _connect(db_path) as conn:
        return {
            r["media"]: r["n"]
            for r in conn.execute("SELECT media, COUNT(*) AS n FROM articles GROUP BY media")
        }


def get_latest_articles(
    db_path: str | pathlib.Path,
    media: str | None = None,
    keyword: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Ambil artikel terbaru (read-only, untuk viewer/dashboard).

    Urut berdasarkan published_at menurun; yang tanpa tanggal di akhir.
    keyword dicocokkan ke judul/ringkasan (LIKE, case-insensitive ASCII).
    """
    with _connect(db_path) as conn:
        sql = (
            "SELECT url, media, title, summary, published_at, fetched_at"
            " FROM articles"
        )
        clauses: list[str] = []
        params: list = []
        if media:
            clauses.append("media = ?")
            params.append(media)
        if keyword:
            clauses.append("(title LIKE ? OR summary LIKE ?)")
            params += [f"%{keyword}%", f"%{keyword}%"]
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY published_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(sql, params)]
