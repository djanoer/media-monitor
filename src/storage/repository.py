"""Repository SQLite: satu-satunya modul yang berisi SQL.

Tabel:
- articles: artikel unik per URL (dedup via UNIQUE constraint).
- fetch_runs: satu baris per siklus fetch.
- fetch_media_log: hasil per media per siklus (dipakai halaman status Fase 4).
"""

from __future__ import annotations

import datetime
import json
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

CREATE TABLE IF NOT EXISTS keyword_watchlist (
    keyword TEXT PRIMARY KEY COLLATE NOCASE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Fase B: klaim yang diekstrak dari artikel (satu artikel bisa banyak klaim).
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_url TEXT NOT NULL,
    media TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    published_at TEXT,
    extracted_at TEXT NOT NULL,
    cluster_id INTEGER,
    UNIQUE(article_url, claim_text)
);
CREATE INDEX IF NOT EXISTS idx_claims_cluster ON claims(cluster_id);

-- Fase B: cluster klaim sejenis (sinyal koroborasi lintas media).
-- Kolom score/verdict/dst diisi Fase C (verifikasi).
CREATE TABLE IF NOT EXISTS claim_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    size INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    score REAL,
    verdict TEXT,
    tier_breakdown TEXT,
    headline_flags TEXT,
    computed_at TEXT
);
"""

_SCHEMA_FASE_D = """
-- Fase D: respon publik (YouTube + Google Trends), pilot karhutla.
CREATE TABLE IF NOT EXISTS youtube_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topik TEXT NOT NULL,
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    channel TEXT,
    published_at TEXT,
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    fetched_at TEXT NOT NULL,
    UNIQUE(topik, video_id)
);
CREATE TABLE IF NOT EXISTS trends_harian (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topik TEXT NOT NULL,
    keyword TEXT NOT NULL,
    tanggal TEXT NOT NULL,
    skor INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(topik, keyword, tanggal)
);
CREATE TABLE IF NOT EXISTS trends_ringkas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topik TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    per_daerah TEXT,
    terkait TEXT
);
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
        conn.executescript(_SCHEMA_FASE_D)


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


def get_last_run(db_path: str | pathlib.Path) -> dict | None:
    """Siklus fetch terakhir (started_at, finished_at) atau None bila belum ada."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT started_at, finished_at FROM fetch_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def count_articles_since(db_path: str | pathlib.Path, since_iso: str) -> int:
    """Jumlah artikel dengan fetched_at >= since_iso (string ISO UTC)."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM articles WHERE fetched_at >= ?", (since_iso,)
        ).fetchone()
        return row["n"]


def get_articles_since(
    db_path: str | pathlib.Path, since_iso: str, limit: int = 50000
) -> list[dict]:
    """Ambil artikel dengan fetched_at >= since_iso (read-only).

    Dipakai skrip analisa offline (mis. cek cakupan topik): kembalikan
    url, media, title, summary, published_at. Urut dari yang terlama.
    """
    with _connect(db_path) as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT url, media, title, summary, published_at"
                " FROM articles WHERE fetched_at >= ?"
                " ORDER BY fetched_at ASC LIMIT ?",
                (since_iso, limit),
            )
        ]


def get_media_last_status(db_path: str | pathlib.Path) -> dict[str, dict]:
    """Status fetch terakhir per media.

    Kembalikan {media: {status, new_articles, total_entries, error, fetched_at}}.
    Dipakai bar status command center.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT media, status, new_articles, total_entries, error, fetched_at"
            " FROM fetch_media_log"
            " WHERE id IN (SELECT MAX(id) FROM fetch_media_log GROUP BY media)"
        )
        return {r["media"]: dict(r) for r in rows}


def _like_aman(keyword: str) -> str:
    r"""Escape karakter khusus LIKE (%, _, \) lalu bungkus dengan %...%."""
    aman = (
        keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{aman}%"


def _klausa_keyword(keyword: str) -> tuple[str, list]:
    """Klausa WHERE + params untuk pencarian keyword di judul/ringkasan."""
    pola = _like_aman(keyword)
    return "(title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\')", [pola, pola]


def count_by_day_keyword(
    db_path: str | pathlib.Path, keyword: str
) -> dict[str, int]:
    """Jumlah artikel per hari (YYYY-MM-DD dari published_at) untuk keyword.

    Artikel tanpa published_at tidak masuk tren (asumsi tercatat).
    """
    klausa, params = _klausa_keyword(keyword)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT substr(published_at, 1, 10) AS tgl, COUNT(*) AS n"
            " FROM articles"
            f" WHERE published_at IS NOT NULL AND {klausa}"
            " GROUP BY tgl ORDER BY tgl",
            params,
        )
        return {r["tgl"]: r["n"] for r in rows}


def count_by_media_keyword(
    db_path: str | pathlib.Path, keyword: str
) -> dict[str, int]:
    """Jumlah artikel per media untuk keyword."""
    klausa, params = _klausa_keyword(keyword)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT media, COUNT(*) AS n FROM articles"
            f" WHERE {klausa} GROUP BY media",
            params,
        )
        return {r["media"]: r["n"] for r in rows}


def get_titles_keyword(
    db_path: str | pathlib.Path, keyword: str, limit: int = 2000
) -> list[str]:
    """Judul-judul artikel yang mengandung keyword (untuk analisa kata terkait)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT title FROM articles WHERE title LIKE ? ESCAPE '\\' LIMIT ?",
            (_like_aman(keyword), limit),
        )
        return [r["title"] for r in rows if r["title"]]


def get_watchlist(db_path: str | pathlib.Path) -> list[str]:
    """Daftar keyword/hashtag yang dipantau, urut waktu ditambahkan."""
    with _connect(db_path) as conn:
        return [
            r["keyword"]
            for r in conn.execute(
                "SELECT keyword FROM keyword_watchlist"
                " WHERE active = 1 ORDER BY created_at"
            )
        ]


def add_keyword(db_path: str | pathlib.Path, keyword: str) -> bool:
    """Tambah keyword ke watchlist. False bila kosong/duplikat (case-insensitive)."""
    kw = (keyword or "").strip()
    if not kw:
        return False
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO keyword_watchlist (keyword, active, created_at)"
            " VALUES (?, 1, ?)",
            (kw, _utcnow()),
        )
        return cur.rowcount == 1


def remove_keyword(db_path: str | pathlib.Path, keyword: str) -> bool:
    """Hapus keyword dari watchlist. False bila tidak ada."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM keyword_watchlist WHERE keyword = ?",
            ((keyword or "").strip(),),
        )
        return cur.rowcount == 1


def count_matrix(
    db_path: str | pathlib.Path, keywords: list[str]
) -> dict[str, dict[str, int]]:
    """Matriks liputan: {keyword: {media: jumlah_artikel}}.

    Dipakai untuk komparasi antar media: isu apa yang paling dibahas siapa.
    """
    return {kw: count_by_media_keyword(db_path, kw) for kw in keywords}


def insert_claims(
    db_path: str | pathlib.Path, claims: list[dict]
) -> list[int]:
    """Simpan klaim; (article_url, claim_text) yang sudah ada dilewati.

    Kembalikan id klaim untuk tiap input (yang sudah ada -> id lama).
    """
    if not claims:
        return []
    now = _utcnow()
    ids: list[int] = []
    with _connect(db_path) as conn:
        for c in claims:
            conn.execute(
                "INSERT OR IGNORE INTO claims"
                " (article_url, media, claim_text, claim_type,"
                "  published_at, extracted_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    c["article_url"],
                    c["media"],
                    c["claim_text"],
                    c["claim_type"],
                    c.get("published_at"),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT id FROM claims WHERE article_url = ? AND claim_text = ?",
                (c["article_url"], c["claim_text"]),
            ).fetchone()
            ids.append(row["id"])
    return ids


def save_clusters(
    db_path: str | pathlib.Path, groups: list[list[int]]
) -> list[int]:
    """Simpan cluster klaim; update claims.cluster_id. Kembalikan id cluster.

    groups: daftar cluster, tiap cluster = daftar id klaim.
    """
    if not groups:
        return []
    now = _utcnow()
    cluster_ids: list[int] = []
    with _connect(db_path) as conn:
        for g in groups:
            cur = conn.execute(
                "INSERT INTO claim_clusters (size, created_at) VALUES (?, ?)",
                (len(g), now),
            )
            cid = cur.lastrowid
            conn.executemany(
                "UPDATE claims SET cluster_id = ? WHERE id = ?",
                [(cid, claim_id) for claim_id in g],
            )
            cluster_ids.append(cid)
    return cluster_ids


def get_clusters(
    db_path: str | pathlib.Path,
) -> list[dict]:
    """Ambil semua cluster + klaim anggotanya (read-only, untuk laporan/UI)."""
    with _connect(db_path) as conn:
        clusters = [
            dict(r)
            for r in conn.execute(
                "SELECT id, size, created_at, score, verdict,"
                " tier_breakdown, headline_flags, computed_at"
                " FROM claim_clusters ORDER BY size DESC"
            )
        ]
        for cl in clusters:
            cl["claims"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT id, media, claim_text, claim_type, article_url"
                    " FROM claims WHERE cluster_id = ? ORDER BY id",
                    (cl["id"],),
                )
            ]
    return clusters


def count_claims(db_path: str | pathlib.Path) -> int:
    """Jumlah total klaim di DB (helper diagnostik)."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM claims").fetchone()
        return row["n"]


def reset_claims(db_path: str | pathlib.Path) -> tuple[int, int]:
    """Hapus SEMUA klaim + cluster. Dipakai untuk run ulang bersih.

    Kembalikan (jumlah_klaim_dihapus, jumlah_cluster_dihapus).
    Hanya dipanggil eksplisit via flag --reset; bukan bagian run normal.
    """
    with _connect(db_path) as conn:
        n_klaim = conn.execute("SELECT COUNT(*) AS n FROM claims").fetchone()["n"]
        n_cluster = conn.execute(
            "SELECT COUNT(*) AS n FROM claim_clusters"
        ).fetchone()["n"]
        conn.execute("DELETE FROM claims")
        conn.execute("DELETE FROM claim_clusters")
        return n_klaim, n_cluster


_KOLOM_VERIFIKASI = [
    ("score", "REAL"),
    ("verdict", "TEXT"),
    ("tier_breakdown", "TEXT"),
    ("headline_flags", "TEXT"),
    ("computed_at", "TEXT"),
]


def migrate_verifikasi(db_path: str | pathlib.Path) -> list[str]:
    """Tambah kolom verifikasi ke claim_clusters bila belum ada (idempoten).

    Dibutuhkan karena DB yang dibuat sebelum Fase C belum punya kolom ini.
    Kembalikan daftar kolom yang ditambahkan.
    """
    ditambah: list[str] = []
    with _connect(db_path) as conn:
        ada = {r[1] for r in conn.execute("PRAGMA table_info(claim_clusters)")}
        for nama, tipe in _KOLOM_VERIFIKASI:
            if nama not in ada:
                # nama & tipe konstanta internal, aman dari injeksi
                conn.execute(f"ALTER TABLE claim_clusters ADD COLUMN {nama} {tipe}")
                ditambah.append(nama)
    return ditambah


def save_verifikasi(
    db_path: str | pathlib.Path, cluster_id: int, hasil: dict
) -> None:
    """Simpan hasil verifikasi satu cluster (skor, verdict, flag)."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE claim_clusters SET score = ?, verdict = ?,"
            " tier_breakdown = ?, headline_flags = ?, computed_at = ?"
            " WHERE id = ?",
            (
                hasil.get("score"),
                hasil.get("verdict"),
                hasil.get("tier_breakdown"),
                hasil.get("headline_flags"),
                _utcnow(),
                cluster_id,
            ),
        )


def simpan_video_youtube(
    db_path: str | pathlib.Path, topik: str, videos: list[dict]
) -> int:
    """Simpan/refresh video YouTube per topik. Kembalikan jumlah tersimpan."""
    now = _utcnow()
    n = 0
    with _connect(db_path) as conn:
        for v in videos:
            conn.execute(
                "INSERT INTO youtube_videos"
                " (topik, video_id, title, channel, published_at,"
                "  view_count, like_count, comment_count, fetched_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(topik, video_id) DO UPDATE SET"
                "  title=excluded.title, channel=excluded.channel,"
                "  view_count=excluded.view_count, like_count=excluded.like_count,"
                "  comment_count=excluded.comment_count,"
                "  fetched_at=excluded.fetched_at",
                (
                    topik, v["video_id"], v.get("title", ""),
                    v.get("channel"), v.get("published_at"),
                    v.get("view_count", 0), v.get("like_count", 0),
                    v.get("comment_count", 0), now,
                ),
            )
            n += 1
    return n


def simpan_trends_harian(
    db_path: str | pathlib.Path, topik: str, tren: dict
) -> int:
    """Simpan skor minat harian per keyword. Kembalikan jumlah baris."""
    now = _utcnow()
    n = 0
    with _connect(db_path) as conn:
        for rec in tren.get("minat_harian", []):
            for kw in tren.get("keywords", []):
                conn.execute(
                    "INSERT INTO trends_harian"
                    " (topik, keyword, tanggal, skor, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT(topik, keyword, tanggal) DO UPDATE SET"
                    "  skor=excluded.skor, fetched_at=excluded.fetched_at",
                    (topik, kw, rec["tanggal"], rec.get(kw, 0), now),
                )
                n += 1
    return n


def simpan_trends_ringkas(
    db_path: str | pathlib.Path, topik: str, tren: dict
) -> None:
    """Simpan per-daerah + frasa terkait sebagai JSON (satu baris per run)."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO trends_ringkas"
            " (topik, fetched_at, per_daerah, terkait) VALUES (?, ?, ?, ?)",
            (
                topik,
                _utcnow(),
                json.dumps(tren.get("per_daerah", [])),
                json.dumps(tren.get("terkait", {})),
            ),
        )
