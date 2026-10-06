"""Test respon publik: logika murni + penyimpanan (tanpa network/API)."""

import pytest

from src.processing import respon_publik
from src.storage import repository


VIDEOS = [
    {"video_id": "a", "title": "A", "channel": "C1", "published_at": "x",
     "view_count": 100, "like_count": 10, "comment_count": 5},
    {"video_id": "b", "title": "B", "channel": "C2", "published_at": "x",
     "view_count": 500, "like_count": 50, "comment_count": 25},
    {"video_id": "c", "title": "C", "channel": "C3", "published_at": "x",
     "view_count": 300, "like_count": 30, "comment_count": 15},
]


def test_video_teratas_urut_views():
    top = respon_publik.video_teratas(VIDEOS, n=2)
    assert [v["video_id"] for v in top] == ["b", "c"]


def test_total_statistik():
    tot = respon_publik.total_statistik(VIDEOS)
    assert tot == {"n_video": 3, "total_views": 900,
                   "total_komentar": 45, "total_likes": 90}


def test_total_statistik_kosong():
    tot = respon_publik.total_statistik([])
    assert tot["n_video"] == 0 and tot["total_views"] == 0


def test_tanpa_api_key_raise():
    with pytest.raises(ValueError):
        respon_publik.cari_video_youtube("", "karhutla")


def test_ringkasan_trends():
    tren = {
        "keywords": ["karhutla"],
        "minat_harian": [
            {"tanggal": "2026-10-01", "karhutla": 40},
            {"tanggal": "2026-10-02", "karhutla": 80},
        ],
        "per_daerah": [
            {"daerah": "Riau", "karhutla": 100},
            {"daerah": "Jawa Barat", "karhutla": 30},
        ],
        "terkait": {"karhutla": {
            "top": [], "rising": [{"query": "titik panas", "value": 120}]}},
    }
    r = respon_publik.ringkasan_trends(tren)
    assert r["minat_rata2"] == 60.0
    assert r["puncak"] == {"tanggal": "2026-10-02", "skor": 80}
    assert r["daerah_teratas"][0] == {"daerah": "Riau", "skor": 100}
    assert r["frasa_naik"] == ["titik panas"]


def test_ringkasan_trends_kosong():
    r = respon_publik.ringkasan_trends(
        {"keywords": ["karhutla"], "minat_harian": [],
         "per_daerah": [], "terkait": {}})
    assert r["minat_rata2"] == 0.0 and r["puncak"] is None


def test_simpan_video_youtube(tmp_path):
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    assert repository.simpan_video_youtube(db, "karhutla", VIDEOS) == 3
    # run ulang: upsert, tetap 3 baris unik
    assert repository.simpan_video_youtube(db, "karhutla", VIDEOS) == 3
    import sqlite3
    n = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM youtube_videos").fetchone()[0]
    assert n == 3


def test_simpan_trends(tmp_path):
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    tren = {
        "keywords": ["karhutla"],
        "minat_harian": [{"tanggal": "2026-10-01", "karhutla": 40}],
        "per_daerah": [{"daerah": "Riau", "karhutla": 100}],
        "terkait": {"karhutla": {"top": [], "rising": []}},
    }
    assert repository.simpan_trends_harian(db, "karhutla", tren) == 1
    repository.simpan_trends_ringkas(db, "karhutla", tren)
    import sqlite3
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM trends_harian").fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM trends_ringkas").fetchone()[0] == 1
