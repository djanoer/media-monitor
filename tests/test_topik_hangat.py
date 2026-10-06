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
