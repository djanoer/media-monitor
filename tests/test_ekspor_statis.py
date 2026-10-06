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
    # modal detail: tombol judul + data JSON + markup modal
    assert 'class="tlink" data-i="0"' in html
    assert 'id="adata"' in html and 'id="mback"' in html
    assert "kenapa label ini?" in html and "Buka sumber" in html
    # tiga kartu KPI bisa diklik -> modal Kartu Statistik
    for mid in ["kpi-total", "kpi-sentimen", "kpi-risiko",
                "mstat-t", "mstat-s", "mstat-r"]:
        assert f'id="{mid}"' in html, mid
    assert html.count("Kartu Statistik") >= 3
    assert "Apa maksudnya?" in html and "SKALA SENTIMEN" in html
    assert "SKALA RISIKO (0–100)" in html
    # ringkasan (min 3 kalimat) + teks yang dianalisis di modal artikel
    assert "📝 RINGKASAN" in html and "🔍 TEKS YANG DIANALISIS" in html
    assert 'id="m-ring"' in html
    # emoji KPI + kartu distribusi
    assert "📰" in html and "😐" in html and "🛡" in html
    assert ".dist>div{background" in html.replace(" ", "")
    import json as _json
    data = _json.loads(html.split('id="adata">')[1].split("</script>")[0]
                       .replace("<\\/", "</"))
    assert len(data) == 8 and data[0]["media"] == "Tempo"  # limit 8/media
    assert data[0]["ai"].startswith("Sentimen negatif")  # id DESC
    assert "SKALA RISIKO" in data[0]["why"]


def test_detail_artikel_tanpa_analisa(tmp_path):
    db = tmp_path / "d.db"
    repository.init_db(db)
    repository.insert_articles(db, [{"url": "u9", "media": "tempo",
                                     "title": "Judul", "summary": "",
                                     "link": "u9",
                                     "published_at": "2026-10-06T10:00:00Z"}])
    a = {"url": "u9", "media": "tempo", "title": "Judul", "summary": "",
         "isi_lengkap": "", "published_at": "2026-10-06T10:00:00Z",
         "sentimen": None, "sentimen_skor": None,
         "risiko": None, "risiko_skor": None}
    d = eks._detail_artikel(a, {}, {}, "Tempo")
    assert "belum dianalisa" in d["badge_r"]
    assert d["dianalisis"] == [] and d["title"] == "Judul"


def test_kalimat_awal_dan_teks_dianalisis():
    isi = ("Satu. Dua! Tiga? Empat. Lima. Enam tidak ikut.")
    a = {"title": "Banjir", "summary": "<p>Ringkasan RSS banjir.</p>",
         "isi_lengkap": isi}
    r = eks._kalimat_awal(a, max_kalimat=5, max_len=900)
    assert "Lima." in r and "Enam" not in r
    assert eks._kalimat_awal({"title": "T", "isi_lengkap": ""}, 5, 900) == ""
    # teks yang benar-benar dihitung = summary RSS (bersih HTML)
    assert eks._teks_dianalisis(a) == "Ringkasan RSS banjir."
    d = eks._detail_artikel(
        dict(a, url="u", media="tempo", sentimen="negatif",
             sentimen_skor=-3.0, risiko="Tinggi", risiko_skor=80.0),
        {"analisa": {}, "verification": {}}, {}, "Tempo")
    assert d["dianalisis"] == ["Ringkasan RSS banjir."]
    assert len(d["ringkasan"]) == 1 and "Lima." in d["ringkasan"][0]
    # kata berpengaruh kini dari summary (yg dihitung), bukan isi_lengkap
    assert "banjir" in d["ai"].lower()
