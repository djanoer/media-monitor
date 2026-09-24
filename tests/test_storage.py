"""Test repository SQLite: skema, dedup URL, dan pencatatan siklus fetch."""

import sqlite3

from src.storage import repository


def _artikel(url, media="tempo"):
    return {
        "url": url,
        "media": media,
        "title": f"Judul {url}",
        "summary": "ringkasan",
        "link": url,
        "published_at": "2026-09-25T00:00:00Z",
    }


def test_init_db_idempoten(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    repository.init_db(db)  # panggil dua kali tidak error
    with sqlite3.connect(db) as conn:
        tabel = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"articles", "fetch_runs", "fetch_media_log"} <= tabel


def test_insert_dedup_berdasarkan_url(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    baru1 = repository.insert_articles(db, [_artikel("https://a.example/1"),
                                           _artikel("https://a.example/2")])
    assert baru1 == 2
    # masukkan lagi 2 yang sama + 1 baru -> hanya 1 yang dihitung baru
    baru2 = repository.insert_articles(db, [_artikel("https://a.example/1"),
                                           _artikel("https://a.example/2"),
                                           _artikel("https://a.example/3")])
    assert baru2 == 1
    assert repository.count_articles(db) == 3


def test_insert_dedup_lapis_kedua_judul_sama_url_beda(tmp_path):
    # simulasi token Google News berubah: URL beda, judul sama -> tetap dianggap duplikat
    db = tmp_path / "test.db"
    repository.init_db(db)
    a1 = _artikel("https://news.google.com/rss/articles/TOKEN1", media="kompas")
    a1["title"] = "Judul Sama Persis"
    assert repository.insert_articles(db, [a1]) == 1
    a2 = _artikel("https://news.google.com/rss/articles/TOKEN2", media="kompas")
    a2["title"] = "Judul Sama Persis"
    assert repository.insert_articles(db, [a2]) == 0
    # media beda + judul sama = artikel berbeda, tetap masuk
    a3 = _artikel("https://news.google.com/rss/articles/TOKEN3", media="detik")
    a3["title"] = "Judul Sama Persis"
    assert repository.insert_articles(db, [a3]) == 1
    assert repository.count_articles(db) == 2


def test_insert_kosong_tidak_error(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    assert repository.insert_articles(db, []) == 0


def test_pencatatan_run_dan_media(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    run_id = repository.start_run(db)
    repository.log_media(db, run_id, "tempo", "ok", 5, 20)
    repository.log_media(db, run_id, "kompas", "error", 0, 0, "Timeout")
    repository.finish_run(db, run_id)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM fetch_runs WHERE id = ?", (run_id,)).fetchone()
        assert run["finished_at"] is not None
        logs = conn.execute(
            "SELECT * FROM fetch_media_log WHERE run_id = ? ORDER BY media",
            (run_id,)).fetchall()
    assert len(logs) == 2
    assert logs[0]["media"] == "kompas" and logs[0]["status"] == "error"
    assert logs[1]["media"] == "tempo" and logs[1]["new_articles"] == 5
