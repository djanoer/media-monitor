"""Test fetcher generik dengan feed RSS contoh (tanpa akses jaringan)."""

import time

import pytest

from src.ingestion.fetcher import fetch_media, normalize_entry

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Contoh Feed</title>
<item>
  <title>Berita Pertama</title>
  <link>https://contoh.example/berita-1</link>
  <description>Ringkasan pertama</description>
  <pubDate>Thu, 25 Sep 2026 08:00:00 +0700</pubDate>
</item>
<item>
  <title>Berita Kedua</title>
  <link>https://contoh.example/berita-2</link>
  <description>Ringkasan kedua</description>
</item>
<item>
  <title>Berita Pertama (duplikat link)</title>
  <link>https://contoh.example/berita-1</link>
  <description>duplikat</description>
</item>
</channel>
</rss>
"""


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content


class FakeClient:
    """Pengganti HttpClient tanpa jaringan."""

    def __init__(self, resolve_map=None):
        self.resolve_map = resolve_map or {}

    def get(self, url):
        return FakeResponse(SAMPLE_RSS.encode("utf-8"))

    def resolve_final_url(self, url):
        return self.resolve_map.get(url, url)


def test_fetch_media_native_normalisasi_dan_dedup():
    media = {"name": "tempo", "feed": "https://x.example/rss", "type": "native"}
    hasil = fetch_media(media, FakeClient())
    assert len(hasil) == 2  # duplikat link hanya dihitung sekali
    urls = {a["url"] for a in hasil}
    assert urls == {"https://contoh.example/berita-1", "https://contoh.example/berita-2"}
    pertama = next(a for a in hasil if a["url"].endswith("berita-1"))
    assert pertama["media"] == "tempo"
    assert pertama["title"] == "Berita Pertama"
    assert pertama["summary"] == "Ringkasan pertama"
    assert pertama["link"] == "https://contoh.example/berita-1"
    assert pertama["published_at"] is not None  # pubDate ter-parse


def test_fetch_media_gnews_resolve_ke_url_asli():
    media = {"name": "kompas", "feed": "https://news.google.com/rss", "type": "gnews"}
    client = FakeClient(resolve_map={
        "https://contoh.example/berita-1": "https://www.kompas.com/artikel-asli-1",
        "https://contoh.example/berita-2": "https://www.kompas.com/artikel-asli-2",
    })
    hasil = fetch_media(media, client)
    urls = {a["url"] for a in hasil}
    assert urls == {"https://www.kompas.com/artikel-asli-1",
                    "https://www.kompas.com/artikel-asli-2"}
    # link mentah tetap disimpan untuk audit
    assert all(a["link"].startswith("https://contoh.example/") for a in hasil)


def test_feed_kosong_memicu_error():
    class EmptyClient(FakeClient):
        def get(self, url):
            return FakeResponse(b"<rss version='2.0'><channel></channel></rss>")

    media = {"name": "rusak", "feed": "https://x.example/rss", "type": "native"}
    with pytest.raises(ValueError):
        fetch_media(media, EmptyClient())


def test_normalize_entry_tanpa_tanggal():
    entry = {"title": "  Judul  ", "link": "https://x.example/1"}
    hasil = normalize_entry("antara", entry, "https://x.example/1")
    assert hasil["title"] == "Judul"
    assert hasil["summary"] == ""
    assert hasil["published_at"] is None


def test_normalize_entry_dengan_struct_time():
    entry = {"title": "T", "link": "https://x.example/1",
             "published_parsed": time.struct_time((2026, 9, 25, 1, 0, 0, 0, 0, 0))}
    hasil = normalize_entry("antara", entry, "https://x.example/1")
    assert hasil["published_at"] == "2026-09-25T01:00:00Z"
