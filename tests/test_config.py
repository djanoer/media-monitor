"""Test pemuatan konfigurasi (memakai file config asli proyek)."""

from src.common.config import load_media, load_settings


def test_load_media_sepuluh_media_aktif():
    media = load_media()
    assert len(media) == 10
    names = {m["name"] for m in media}
    assert names == {
        "tempo", "cnn_indonesia", "antara", "republika", "bisnis_indonesia",
        "kompas", "detik", "liputan6", "jawa_pos", "kumparan",
    }


def test_setiap_media_punya_field_wajib():
    for m in load_media():
        assert m["feed"].startswith("http")
        assert m["type"] in ("native", "gnews")


def test_settings_punya_kunci_wajib():
    s = load_settings()
    assert s["fetch"]["interval_hours"] == 1
    assert s["fetch"]["max_articles_per_media"] == 30
    assert s["retention"]["retention_days"] == 30
    assert s["storage"]["db_path"]
