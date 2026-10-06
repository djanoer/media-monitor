"""Test Fase I: ekstraksi topik hangat + util rate-limit."""

import sys

sys.path.insert(0, ".")

from src.processing import topik_hangat
from src.storage import repository


def _jm():
    # (judul, media): "kebakaran hutan" di 3 media x 3 artikel
    data = []
    for media in ("kompas", "detik", "tempo"):
        for i in range(3):
            data.append(
                (f"Kebakaran hutan meluas di Kalimantan, titik api bertambah {i}",
                 media))
    # noise satu media saja (tidak lolos min_media)
    for i in range(4):
        data.append((f"Harga cabai naik di pasar induk {i}", "kompas"))
    return data


def test_ekstrak_topik_temukan_bigram_lintas_media():
    top = topik_hangat.ekstrak_topik(_jm(), n=3)
    nama = [t["topik"] for t in top]
    assert "kebakaran hutan" in nama
    info = next(t for t in top if t["topik"] == "kebakaran hutan")
    assert info["n_artikel"] >= 9
    assert info["n_media"] == 3


def test_ekstrak_topik_tolak_satu_media():
    top = topik_hangat.ekstrak_topik(_jm(), n=5)
    nama = [t["topik"] for t in top]
    assert not any("cabai" in t for t in nama)


def test_ekstrak_topik_stopword_dibuang():
    data = [(f"Resmi: yang dan di ke dari untuk {i}", "kompas")
            for i in range(5)]
    data += [(f"Presiden umumkan ibu kota baru tahap {i}", m)
             for m in ("kompas", "detik") for i in range(3)]
    top = topik_hangat.ekstrak_topik(data, n=3)
    nama = " ".join(t["topik"] for t in top)
    assert "resmi" not in nama.split()


def test_gabung_topik_manual_dulu_dedup_maks():
    oto = [{"topik": "kebakaran hutan"}, {"topik": "karhutla"},
           {"topik": "banjir bandang"}]
    hasil = topik_hangat.gabung_topik(["karhutla"], oto, maks=3)
    assert hasil[0] == "karhutla"          # manual prioritas
    assert hasil.count("karhutla") == 1    # dedup
    assert len(hasil) == 3                 # maks


def test_hitung_tunggu_429_backoff():
    assert topik_hangat.hitung_tunggu_429(0) == 60
    assert topik_hangat.hitung_tunggu_429(1) == 120
    assert topik_hangat.hitung_tunggu_429(2) == 240


def test_kena_rate_limit():
    assert topik_hangat.kena_rate_limit("HTTP Error 429: Too Many Requests")
    assert topik_hangat.kena_rate_limit("429 unknown")
    assert not topik_hangat.kena_rate_limit("connection timeout")
    assert not topik_hangat.kena_rate_limit("")


def test_repo_artikel_keyword_dan_daftar_topik(tmp_path):
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    repository.insert_articles(db, [
        {"url": "u1", "media": "kompas", "title": "Kebakaran hutan meluas",
         "summary": "ringkasan", "published_at": "2026-10-06T10:00:00",
         "fetched_at": "2026-10-06T10:05:00"},
        {"url": "u2", "media": "detik", "title": "Harga cabai naik",
         "summary": "ringkasan", "published_at": "2026-10-06T11:00:00",
         "fetched_at": "2026-10-06T11:05:00"},
    ])
    arts = repository.get_artikel_keyword(db, "kebakaran hutan")
    assert len(arts) == 1 and arts[0]["media"] == "kompas"

    repository.simpan_video_youtube(db, "kebakaran hutan",
                                   [{"video_id": "v1", "title": "t",
                                     "channel": "c", "published_at": None,
                                     "view_count": 10, "like_count": 1,
                                     "comment_count": 0}])
    assert repository.daftar_topik_respon(db) == ["kebakaran hutan"]


def test_ekstrak_topik_buang_fragmen_domain():
    # Regresi bug 6 Okt 2026: topik "com" lolos dari judul berisi alamat situs.
    data = [(f"Info lengkap kunjungi okezone.com dan kompas.com {i}", m)
            for m in ("kompas", "detik") for i in range(5)]
    top = topik_hangat.ekstrak_topik(data, n=3)
    for t in top:
        assert "com" not in t["topik"].split()
        assert "www" not in t["topik"].split()


def test_hapus_topik(tmp_path):
    import sys
    sys.path.insert(0, ".")
    from scripts.bersihkan_topik import hapus_topik
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    repository.simpan_video_youtube(db, "com",
                                   [{"video_id": "v1", "title": "t",
                                     "channel": "c", "published_at": None,
                                     "view_count": 1, "like_count": 0,
                                     "comment_count": 0}])
    hitung = hapus_topik(db, "com", jalan=False)
    assert hitung["youtube_videos"] == 1
    assert repository.daftar_topik_respon(db) == ["com"]  # belum dihapus
    hapus_topik(db, "com", jalan=True)
    assert repository.daftar_topik_respon(db) == []


def test_ekstrak_topik_fallback_ambang_rendah():
    # Data sepi: strict (min_artikel=3) tidak penuh, relaxed (2) mengisi.
    data = [(f"Topik unik pagi ini {i}", m)
            for m in ("kompas", "detik") for i in range(2)]
    strict = topik_hangat.ekstrak_topik(data, n=5, min_artikel=3, min_media=2)
    relaxed = topik_hangat.ekstrak_topik(data, n=5, min_artikel=2, min_media=2)
    assert len(relaxed) >= len(strict)
    assert len(relaxed) > 0


def test_ambil_trends_jeda_antar_request(monkeypatch):
    """Jeda disebar di antara 4 request (anti burst -> 429)."""
    import sys
    import types

    class _DF:
        empty = True

    class _FakeTrendReq:
        def __init__(self, *a, **k):
            self.calls = []

        def build_payload(self, *a, **k):
            self.calls.append("payload")

        def interest_over_time(self):
            self.calls.append("iot")
            return _DF()

        def interest_by_region(self, *a, **k):
            self.calls.append("ibr")
            return _DF()

        def related_queries(self):
            self.calls.append("rq")
            return {}

    fake_req = types.ModuleType("pytrends.request")
    fake_req.TrendReq = _FakeTrendReq
    fake_pkg = types.ModuleType("pytrends")
    fake_pkg.request = fake_req
    monkeypatch.setitem(sys.modules, "pytrends", fake_pkg)
    monkeypatch.setitem(sys.modules, "pytrends.request", fake_req)

    tidur = []
    monkeypatch.setattr("time.sleep", lambda s: tidur.append(s))

    from src.processing import respon_publik
    respon_publik.ambil_trends(["x"], jeda_detik=3)
    # 3 jeda: setelah payload, iot, ibr (rq terakhir tanpa jeda)
    assert tidur == [3, 3, 3]

    # tanpa jeda -> tidak tidur sama sekali
    tidur.clear()
    respon_publik.ambil_trends(["x"], jeda_detik=0)
    assert tidur == []


def test_lock_minta_dua_kali_ditolak(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, ".")
    from src.common import lock as lk
    monkeypatch.setattr(lk, "_DIR", tmp_path)
    assert lk.minta("uji") is True
    assert lk.minta("uji") is False   # proses sendiri masih hidup
    lk.lepas()
    assert lk.minta("uji") is True   # sesudah dilepas bisa lagi
    lk.lepas()


def test_lock_basi_diambil_alih(tmp_path, monkeypatch):
    import subprocess
    import sys
    sys.path.insert(0, ".")
    from src.common import lock as lk
    monkeypatch.setattr(lk, "_DIR", tmp_path)
    # PID yang sudah pasti mati (proses langsung keluar)
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    (tmp_path / "uji2.lock").write_text(str(p.pid))
    assert lk.minta("uji2") is True  # kunci basi -> ambil alih
    lk.lepas()


def _db_analisa(tmp_path):
    import sys
    sys.path.insert(0, ".")
    from src.storage import repository
    db = str(tmp_path / "a.db")
    repository.init_db(db)
    repository.insert_articles(db, [
        {"url": "u1", "media": "kompas",
         "title": "Bencana banjir bandang melanda, warga mengungsi",
         "summary": "banjir besar merendam puluhan rumah",
         "published_at": "2026-10-06T10:00:00",
         "fetched_at": "2026-10-06T10:05:00"},
        {"url": "u2", "media": "detik",
         "title": "Festival meriah sukses besar, pengunjung senang",
         "summary": "acara berjalan lancar dan menggembirakan",
         "published_at": "2026-10-06T11:00:00",
         "fetched_at": "2026-10-06T11:05:00"},
    ])
    return db


def test_siklus_analisa_idempoten(tmp_path):
    import sys
    sys.path.insert(0, ".")
    from src.processing.analisa import siklus_analisa
    from src.storage import repository
    db = _db_analisa(tmp_path)
    settings = {"analisa": {}, "verification": {"penanda_bombastis": []}}
    h1 = siklus_analisa(db, settings)
    assert h1["n"] == 2
    assert sum(h1["sentimen"].values()) == 2
    arts = repository.get_artikel_keyword(db, "banjir")
    assert arts[0]["sentimen"] == "negatif"
    assert arts[0]["risiko"] in ("Rendah", "Sedang", "Tinggi")
    h2 = siklus_analisa(db, settings)   # tanpa force -> tak ada yang baru
    assert h2["n"] == 0
    h3 = siklus_analisa(db, settings, force=True)
    assert h3["n"] == 2


def test_fetch_cycle_hook_analisa(tmp_path, monkeypatch):
    import sys
    import types
    sys.path.insert(0, ".")
    # jobs.py butuh apscheduler (ada di laptop, tak ada di VM test)
    fake_sched = types.ModuleType("apscheduler.schedulers.blocking")
    fake_sched.BlockingScheduler = object
    fake_pkg = types.ModuleType("apscheduler.schedulers")
    fake_root = types.ModuleType("apscheduler")
    monkeypatch.setitem(sys.modules, "apscheduler", fake_root)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers", fake_pkg)
    monkeypatch.setitem(sys.modules,
                        "apscheduler.schedulers.blocking", fake_sched)
    from src.scheduler.jobs import fetch_cycle
    from src.storage import repository
    db = _db_analisa(tmp_path)
    settings = {
        "storage": {"db_path": db},
        "fetch": {"delay_between_media_seconds": 0, "timeout_seconds": 5},
        "unduh_isi": {"aktif": False},
        "analisa": {"otomatis": True, "limit_per_siklus": 500},
        "verification": {"penanda_bombastis": []},
    }
    summary = fetch_cycle(settings, media_list=[])
    assert summary == {}
    arts = repository.get_artikel_keyword(db, "banjir")
    assert arts[0]["sentimen"] is not None  # hook analisa jalan


def test_start_run_tutup_siklus_terputus(tmp_path):
    import sys
    sys.path.insert(0, ".")
    from src.storage import repository
    db = str(tmp_path / "r.db")
    repository.init_db(db)
    rid = repository.start_run(db)          # simulasi siklus terputus
    assert repository.get_last_run(db)["finished_at"] is None
    rid2 = repository.start_run(db)         # start baru -> tutup yang lama
    assert rid2 != rid
    assert repository.get_last_run(db)["finished_at"] is None  # yg baru
    import sqlite3
    n_terbuka = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM fetch_runs WHERE finished_at IS NULL").fetchone()[0]
    assert n_terbuka == 1  # hanya siklus berjalan yang terbuka


def test_ekspor_statis_html(tmp_path):
    import sys
    sys.path.insert(0, ".")
    from scripts.ekspor_statis import ekspor
    from src.storage import repository
    db = str(tmp_path / "e.db")
    repository.init_db(db)
    repository.insert_articles(db, [
        {"url": "u1", "media": "kompas",
         "title": "Judul berita <b>penting</b>",
         "summary": "ringkasan berita", "published_at": "2026-10-06T10:00:00",
         "fetched_at": "2026-10-06T10:05:00"},
    ])
    repository.simpan_video_youtube(db, "banjir",
                                   [{"video_id": "v1", "title": "Video banjir",
                                     "channel": "ch", "published_at": None,
                                     "view_count": 100, "like_count": 5,
                                     "comment_count": 2}])
    media = [{"name": "kompas", "display": "Kompas", "color": "#9775FA"}]
    out = tmp_path / "docs" / "index.html"
    stats = ekspor(db, out, {"storage": {"db_path": db}}, media)
    html = out.read_text(encoding="utf-8")
    assert stats["media"] == 1 and stats["topik"] == 1
    assert "Kompas" in html and "Judul berita" in html
    assert "<b>penting</b>" not in html  # di-escape
    assert "banjir" in html and "Video banjir" in html
    assert "WIB" in html and "Disclaimer" in html
