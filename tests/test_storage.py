"""Test repository SQLite: skema, dedup URL, dan pencatatan siklus fetch."""

import datetime
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


def test_get_latest_articles_filter_dan_urut(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    a1 = _artikel("https://a.example/1", media="tempo")
    a1.update(title="Rupiah menguat", published_at="2026-09-25T02:00:00Z")
    a2 = _artikel("https://a.example/2", media="kompas")
    a2.update(title="Timnas menang", published_at="2026-09-25T03:00:00Z")
    a3 = _artikel("https://a.example/3", media="tempo")
    a3.update(title="Rupiah melemah", published_at="2026-09-25T01:00:00Z")
    assert repository.insert_articles(db, [a1, a2, a3]) == 3

    semua = repository.get_latest_articles(db)
    assert [r["title"] for r in semua] == ["Timnas menang", "Rupiah menguat", "Rupiah melemah"]

    tempo = repository.get_latest_articles(db, media="tempo")
    assert {r["title"] for r in tempo} == {"Rupiah menguat", "Rupiah melemah"}

    cari = repository.get_latest_articles(db, keyword="rupiah")
    assert {r["title"] for r in cari} == {"Rupiah menguat", "Rupiah melemah"}

    satu = repository.get_latest_articles(db, limit=1)
    assert len(satu) == 1 and satu[0]["title"] == "Timnas menang"


def test_count_by_media(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    repository.insert_articles(db, [_artikel("https://a.example/1", media="tempo"),
                                   _artikel("https://a.example/2", media="tempo"),
                                   _artikel("https://a.example/3", media="kompas")])
    assert repository.count_by_media(db) == {"tempo": 2, "kompas": 1}


def test_get_last_run_dan_status_media(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    assert repository.get_last_run(db) is None

    run1 = repository.start_run(db)
    repository.log_media(db, run1, "tempo", "ok", 5, 30, None)
    repository.finish_run(db, run1)
    last = repository.get_last_run(db)
    assert last["started_at"] and last["finished_at"]

    run2 = repository.start_run(db)
    repository.log_media(db, run2, "tempo", "error", 0, 0, "timeout")
    st = repository.get_media_last_status(db)
    assert st["tempo"]["status"] == "error"
    assert st["tempo"]["error"] == "timeout"


def test_count_articles_since(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    repository.insert_articles(db, [_artikel("https://a.example/1")])
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert repository.count_articles_since(db, now) >= 0
    lama = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=25)).isoformat()
    assert repository.count_articles_since(db, lama) == 1


def _artikel_berkeyword(url, media, title, published_at):
    a = _artikel(url, media=media)
    a.update(title=title, published_at=published_at)
    return a


def test_keyword_tren_media_judul(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    data = [
        _artikel_berkeyword("https://a.example/1", "tempo", "Rupiah menguat",
                            "2026-09-24T01:00:00+00:00"),
        _artikel_berkeyword("https://a.example/2", "tempo", "Rupiah melemah",
                            "2026-09-24T02:00:00+00:00"),
        _artikel_berkeyword("https://a.example/3", "kompas", "Dolar dan rupiah",
                            "2026-09-25T01:00:00+00:00"),
        _artikel_berkeyword("https://a.example/4", "kompas", "Cuaca cerah",
                            "2026-09-25T02:00:00+00:00"),
    ]
    assert repository.insert_articles(db, data) == 4

    tren = repository.count_by_day_keyword(db, "rupiah")
    assert tren == {"2026-09-24": 2, "2026-09-25": 1}

    per_media = repository.count_by_media_keyword(db, "rupiah")
    assert per_media == {"tempo": 2, "kompas": 1}

    judul = repository.get_titles_keyword(db, "rupiah")
    assert len(judul) == 3

    assert repository.count_by_day_keyword(db, "tidakada") == {}


def test_watchlist_tambah_hapus(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    assert repository.get_watchlist(db) == []

    assert repository.add_keyword(db, " timnas ") is True
    assert repository.add_keyword(db, "TIMNAS") is False  # duplikat case-insensitive
    assert repository.add_keyword(db, "   ") is False
    assert repository.get_watchlist(db) == ["timnas"]

    assert repository.remove_keyword(db, "timnas") is True
    assert repository.remove_keyword(db, "timnas") is False
    assert repository.get_watchlist(db) == []


def test_count_matrix(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    data = [
        _artikel_berkeyword("https://a.example/1", "tempo", "Rupiah menguat",
                            "2026-09-24T01:00:00+00:00"),
        _artikel_berkeyword("https://a.example/2", "kompas", "Rupiah melemah",
                            "2026-09-24T02:00:00+00:00"),
        _artikel_berkeyword("https://a.example/3", "kompas", "Timnas menang",
                            "2026-09-25T01:00:00+00:00"),
    ]
    assert repository.insert_articles(db, data) == 3
    matriks = repository.count_matrix(db, ["rupiah", "timnas"])
    assert matriks["rupiah"] == {"tempo": 1, "kompas": 1}
    assert matriks["timnas"] == {"kompas": 1}
    assert matriks["timnas"].get("tempo", 0) == 0


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
