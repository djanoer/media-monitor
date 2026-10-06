"""Test exporter statis: helper format + agregat metrik hero/KPI."""

import sys

sys.path.insert(0, ".")

from scripts import ekspor_statis as eks
from src.storage import repository

MEDIA = [{"name": "tempo", "display": "Tempo", "color": "#ff0000"},
         {"name": "cnn", "display": "CNN", "color": "#00ff00"}]


def _db_isi(tmp_path):
    db = tmp_path / "test.db"
    repository.init_db(db)
    arts = [{"url": f"https://a.example/{i}", "media": "tempo",
             "title": f"Judul {i}", "summary": "ringkasan",
             "link": f"https://a.example/{i}",
             "published_at": "2026-10-06T00:00:00Z"}
            for i in range(10)]
    repository.insert_articles(db, arts)
    for i in range(3):  # positif / Rendah
        repository.simpan_analisa(db, f"https://a.example/{i}",
                                  "positif", 1.0, "Rendah", 20.0)
    for i in range(3, 8):  # netral / Sedang
        repository.simpan_analisa(db, f"https://a.example/{i}",
                                  "netral", 0.0, "Sedang", 50.0)
    for i in range(8, 10):  # negatif / Tinggi
        repository.simpan_analisa(db, f"https://a.example/{i}",
                                  "negatif", -1.0, "Tinggi", 80.0)
    run_id = repository.start_run(db)
    repository.log_media(db, run_id, "tempo", "ok", 10, 10)
    repository.finish_run(db, run_id)
    return db


def test_metrik_agregat(tmp_path):
    db = _db_isi(tmp_path)
    m = eks._metrik(db, MEDIA)
    assert m["total"] == 10
    assert (m["ps"], m["nt"], m["ng"]) == (3, 5, 2)
    assert m["avg_s"] == 10  # (3-2)/10*100
    assert (m["rr"], m["rs"], m["rt"]) == (3, 5, 2)
    assert m["avg_r"] == 47.0
    assert m["ok"] == 1 and m["n_media"] == 2
    assert m["d24"] == 10
    assert m["sehat"] == "ok" and m["umur_ms"] is not None


def test_metrik_db_kosong(tmp_path):
    db = tmp_path / "kosong.db"
    m = eks._metrik(db, MEDIA)
    assert m["total"] == 0 and m["avg_s"] == 0
    assert m["sehat"] == "unknown" and m["umur_ms"] is None


def test_tanda_persen():
    assert eks._tanda_persen(5) == "+5%"
    assert eks._tanda_persen(-2) == "−2%"
    assert eks._tanda_persen(0) == "0%"


def test_bar_proporsi():
    html = eks._bar([(3, "#a"), (5, "#b"), (2, "#c")])
    assert 'width:30.0%' in html and 'width:50.0%' in html
    assert 'width:20.0%' in html
    assert eks._bar([(0, "#a")]) == '<div class="mbar"></div>'


def test_ekspor_html_memuat_semua_seksi(tmp_path):
    db = _db_isi(tmp_path)
    out = tmp_path / "index.html"
    stats = eks.ekspor(db, out, {}, MEDIA)
    html = out.read_text(encoding="utf-8")
    for penanda in ["Media Monitor", "DIPERBARUI", "TOTAL ARTIKEL",
                    "SENTIMEN RATA-RATA", "RISIKO RATA-RATA",
                    "Scheduler sehat", "Tempo", "CNN",
                    "Berita per media", "Respons Publik",
                    "data-ts", "Disclaimer"]:
        assert penanda in html, penanda
    assert stats["media"] == 2
