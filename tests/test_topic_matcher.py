"""Test pencocokan topik karhutla (memakai config/topics.yaml asli proyek)."""

from src.common.config import load_topics
from src.processing.topic_matcher import match_topic, match_topics, teks_artikel


def _spec():
    return load_topics()["karhutla"]


def test_load_topics_memuat_karhutla():
    topics = load_topics()
    assert "karhutla" in topics
    spec = topics["karhutla"]
    for kunci in ("high_precision", "contextual", "context_words", "exclude"):
        assert spec[kunci], kunci


def test_high_precision_langsung_tag():
    for judul in [
        "Karhutla melanda Riau, 200 hektare hangus",
        "Titik panas terpantau 120 di Sumatera",
        "Kabut asap selimuti Palembang",
        "Manggala Agni padamkan api di gambut",
        # konstruksi pasif yang umum di berita
        "BPBD: Luas lahan terbakar di Batang Hari capai 479,48 hektare",
        "Hutan terbakar di kawasan TN",
        "Titik api terpantau di tiga kabupaten",
    ]:
        assert match_topic(judul, _spec()), judul


def test_contextual_butuh_kata_konteks():
    assert match_topic("Kebakaran melanda hutan lindung", _spec())
    assert match_topic("Kebakaran hanguskan 50 hektare lahan gambut", _spec())
    # kata umum tanpa konteks -> bukan karhutla
    assert not match_topic("Kebakaran melanda kawasan industri", _spec())
    assert not match_topic("Hotspot wifi gratis di 10 desa", _spec())


def test_exclude_menang_atas_yang_lain():
    for judul in [
        "Kebakaran rumah di Jakarta",
        "Kebakaran mobil di tol Cipali",
        "Kebakaran pasar induk dini hari",
        # exclude menang walau ada kata konteks
        "Kebakaran rumah di dekat hutan lindung",
    ]:
        assert not match_topic(judul, _spec()), judul


def test_bukan_berita_karhutla():
    assert not match_topic("Harga cabai rawit naik di pasar induk", _spec())
    assert not match_topic("", _spec())


def test_match_topics_kembalikan_nama_topik():
    topics = load_topics()
    assert match_topics("Karhutla di Kalimantan", topics) == ["karhutla"]
    assert match_topics("Harga cabai naik", topics) == []


def test_teks_artikel_gabung_judul_ringkasan():
    artikel = {"title": "Judul", "summary": "Ringkasan"}
    teks = teks_artikel(artikel)
    assert "Judul" in teks and "Ringkasan" in teks
    # konteks boleh datang dari ringkasan, bukan cuma judul
    assert match_topic(
        teks_artikel({"title": "Kebakaran besar", "summary": "Api melalap hutan lindung"}),
        _spec(),
    )
