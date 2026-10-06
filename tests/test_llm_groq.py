"""Test klien Groq (mocked) dan pengisian cache ringkasan_ai di exporter."""

import io
import json
import os
from unittest import mock

from src.processing import llm_groq
from src.storage import repository


def _resp_ok(payload):
    m = mock.MagicMock()
    m.read.return_value = json.dumps(payload).encode()
    m.__enter__.return_value = m
    return m


def test_ringkas_artikel_sukses():
    payload = {"choices": [{"message": {"content": "Ringkasan tiga kalimat."}}]}
    with mock.patch("urllib.request.urlopen",
                    return_value=_resp_ok(payload)):
        out = llm_groq.ringkas_artikel("Judul", "Isi berita.", "key123")
    assert out == "Ringkasan tiga kalimat."


def test_ringkas_artikel_gagal_none():
    import urllib.error
    with mock.patch("urllib.request.urlopen",
                    side_effect=TimeoutError("timeout")):
        assert llm_groq.ringkas_artikel("J", "Isi", "key") is None
    # HTTP 429 -> RateLimitError (layak retry), bukan None
    err429 = urllib.error.HTTPError("http://x", 429, "Too Many Requests",
                                    {}, io.BytesIO(b""))
    with mock.patch("urllib.request.urlopen", side_effect=err429):
        try:
            llm_groq.ringkas_artikel("J", "Isi", "key")
            assert False, "harusnya raise"
        except llm_groq.RateLimitError:
            pass
    # HTTP lain (401) -> None, tidak retry
    err401 = urllib.error.HTTPError("http://x", 401, "Unauthorized",
                                    {}, io.BytesIO(b""))
    with mock.patch("urllib.request.urlopen", side_effect=err401):
        assert llm_groq.ringkas_artikel("J", "Isi", "key") is None
    # tanpa key / tanpa isi -> None tanpa panggil API
    assert llm_groq.ringkas_artikel("J", "Isi", "") is None
    assert llm_groq.ringkas_artikel("J", "", "key") is None


def test_isi_ringkasan_ai_tanpa_key(tmp_path):
    from scripts import ekspor_statis as eks
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("GROQ_API_KEY", None)
        assert eks._isi_ringkasan_ai(db, {"ringkasan_ai": {"aktif": True}}) == 0


def test_isi_ringkasan_ai_retry_429_bertahap(tmp_path):
    from scripts import ekspor_statis as eks
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    repository.migrate_isi_lengkap(db)
    arts = [{"url": f"u{i}", "media": "tempo", "title": f"T{i}",
             "summary": "s", "link": f"u{i}",
             "published_at": "2026-10-06T10:00:00Z"} for i in range(2)]
    repository.insert_articles(db, arts)
    for i in range(2):
        repository.simpan_isi(db, f"u{i}", f"Isi lengkap artikel {i}.")
    calls = {"n": 0}

    def fake_ringkas(judul, isi, api_key, **kw):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise eks.RateLimitError("429")
        return "Ringkasan AI."

    tidur = []
    cfg = {"ringkasan_ai": {"aktif": True, "maks_artikel": 30,
                            "maks_umur_jam": 24 * 365, "jeda_detik": 0,
                            "max_tokens": 300, "model": "m",
                            "retry_429": 3, "tunggu_awal_detik": 60,
                            "tunggu_maks_detik": 300}}
    with mock.patch.dict(os.environ, {"GROQ_API_KEY": "k"}), \
         mock.patch("scripts.ekspor_statis.ringkas_artikel", fake_ringkas), \
         mock.patch("scripts.ekspor_statis.time.sleep",
                    side_effect=lambda s: tidur.append(s)):
        n = eks._isi_ringkasan_ai(db, cfg)
    assert n == 2  # 429 2x -> backoff -> sukses, lanjut artikel ke-2
    assert tidur[:2] == [60, 120]  # backoff bertahap
    assert repository.artikel_tanpa_ringkasan_ai(
        db, 10, maks_umur_jam=24 * 365) == []


def test_isi_ringkasan_ai_menyerah_setelah_max_retry(tmp_path):
    from scripts import ekspor_statis as eks
    db = str(tmp_path / "t.db")
    repository.init_db(db)
    repository.migrate_isi_lengkap(db)
    arts = [{"url": "u0", "media": "tempo", "title": "T0",
             "summary": "s", "link": "u0",
             "published_at": "2026-10-06T10:00:00Z"}]
    repository.insert_articles(db, arts)
    repository.simpan_isi(db, "u0", "Isi lengkap.")

    def selalu_429(judul, isi, api_key, **kw):
        raise eks.RateLimitError("429")

    cfg = {"ringkasan_ai": {"aktif": True, "maks_artikel": 30,
                            "maks_umur_jam": 24 * 365, "jeda_detik": 0,
                            "max_tokens": 300, "model": "m",
                            "retry_429": 2, "tunggu_awal_detik": 60,
                            "tunggu_maks_detik": 300}}
    with mock.patch.dict(os.environ, {"GROQ_API_KEY": "k"}), \
         mock.patch("scripts.ekspor_statis.ringkas_artikel", selalu_429), \
         mock.patch("scripts.ekspor_statis.time.sleep"):
        n = eks._isi_ringkasan_ai(db, cfg)
    assert n == 0  # 3x 429 -> berhenti, coba ekspor berikutnya


def test_detail_prioritaskan_ringkasan_ai():
    from scripts import ekspor_statis as eks
    a = {"url": "u", "media": "tempo", "title": "Judul",
         "summary": "Ringkasan RSS.",
         "isi_lengkap": "Satu. Dua. Tiga. Empat.",
         "ringkasan_ai": "Ringkasan AI tiga kalimat.",
         "published_at": "", "sentimen": "netral", "sentimen_skor": 0.0,
         "risiko": "Rendah", "risiko_skor": 20.0}
    d = eks._detail_artikel(a, {"analisa": {}, "verification": {}}, {}, "Tempo")
    assert d["ringkasan"] == ["Ringkasan AI tiga kalimat."]
    assert d["ringkasan_ai"] is True
