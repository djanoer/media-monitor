"""Test unduh isi artikel + cuplikan ringkasan (Fase H, tanpa network)."""

from app import komponen as kmp
from src.ingestion.artikel import ekstrak_isi
from src.storage import repository

HTML = """
<html><head><title>T</title><style>.x{}</style><script>var a=1;</script></head>
<body><nav>menu navigasi situs berita</nav>
<article>
<p>Pendahuluan singkat.</p>
<p>Isi berita utama yang panjang dan menjelaskan peristiwa secara detail
kepada pembaca dengan kalimat yang cukup panjang di sini.</p>
<p>Baca juga: artikel terkait lainnya yang tidak relevan</p>
<p>Paragraf kedua isi berita yang juga panjang dan informatif untuk
pembaca yang ingin memahami konteks peristiwa secara utuh.</p>
</article>
<footer>copyright media</footer>
</body></html>
"""


def test_ekstrak_isi_ambil_paragraf():
    teks = ekstrak_isi(HTML)
    assert "Isi berita utama" in teks
    assert "Paragraf kedua" in teks
    assert "navigasi situs" not in teks
    assert "copyright" not in teks
    assert "Baca juga" not in teks
    assert "Pendahuluan singkat" not in teks  # < 60 karakter


def test_ekstrak_isi_html_rusak():
    assert isinstance(ekstrak_isi("<p>teks tanpa tutup"), str)


def test_mirip_judul():
    assert kmp.mirip_judul("", "Judul Berita")
    assert kmp.mirip_judul("Judul Berita", "Judul Berita")
    assert kmp.mirip_judul("Judul Berita - republika.co.id", "Judul Berita")
    assert not kmp.mirip_judul("Ringkasan asli yang berbeda isinya", "Judul")


def test_cuplikan_prioritas_isi_lengkap():
    r = {"title": "Judul", "summary": "Judul - media.co.id",
         "isi_lengkap": "Kalimat pertama isi. Kalimat kedua isi. "
                        "Kalimat ketiga isi."}
    c = kmp.teks_ringkasan_mentah(r)
    assert "Kalimat pertama" in c and "Kalimat kedua" in c
    assert "Kalimat ketiga" not in c


def test_cuplikan_sembunyikan_duplikat_judul():
    r = {"title": "Judul Berita", "summary": "Judul Berita",
         "isi_lengkap": ""}
    assert kmp.teks_ringkasan_mentah(r) == ""


def test_cuplikan_rss_bagus_tetap_dipakai():
    r = {"title": "Judul", "summary": "Ringkasan asli dari RSS feed",
         "isi_lengkap": ""}
    assert kmp.teks_ringkasan_mentah(r) == "Ringkasan asli dari RSS feed"


def test_migrasi_dan_simpan_isi(tmp_path):
    import sqlite3
    db = tmp_path / "t.db"
    # simulasi DB lama: tabel articles TANPA kolom isi_lengkap
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE articles (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " url TEXT UNIQUE NOT NULL, media TEXT NOT NULL, title TEXT,"
        " published_at TEXT, fetched_at TEXT NOT NULL)")
    conn.execute(
        "INSERT INTO articles (url, media, title, published_at, fetched_at)"
        " VALUES ('u1','kompas','T','2026-10-06T10:00:00','x')")
    conn.commit()
    conn.close()
    assert repository.migrate_isi_lengkap(db) is True
    assert repository.migrate_isi_lengkap(db) is False  # idempoten
    assert repository.artikel_tanpa_isi(db) == ["u1"]
    repository.simpan_isi(db, "u1", "isi berita")
    assert repository.artikel_tanpa_isi(db) == []
    repository.simpan_isi(db, "u1", "")  # gagal unduh: tak diulang
    assert repository.artikel_tanpa_isi(db) == []
