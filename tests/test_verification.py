"""Test skor koroborasi + cek headline (tanpa model, tanpa DB)."""

from src.processing.verification import (
    bobot_media,
    cek_headline,
    skor_koroborasi,
    verdict,
)

TIER = {"kompas": 1, "detik": 1, "kumparan": 2, "blog_x": 3}
BOBOT = {1: 1.0, 2: 0.7, 3: 0.4}
PENANDA = ["darurat", "heboh", "!"]


def test_dua_tier1_skor_100_terkoroborasi():
    skor, rincian = skor_koroborasi(["kompas", "detik"], TIER, BOBOT)
    assert skor == 100.0
    assert rincian["per_tier"] == {"1": 2}
    assert verdict(skor, 80, 50) == "terkoroborasi"


def test_satu_tier1_skor_50_satu_sumber():
    skor, _ = skor_koroborasi(["kompas"], TIER, BOBOT)
    assert skor == 50.0
    assert verdict(skor, 80, 50) == "satu sumber kredibel"


def test_media_sama_dua_klaim_dihitung_sekali():
    skor_dua = skor_koroborasi(["kompas", "kompas"], TIER, BOBOT)[0]
    skor_satu = skor_koroborasi(["kompas"], TIER, BOBOT)[0]
    assert skor_dua == skor_satu == 50.0


def test_tier2_dan_tier3():
    skor, _ = skor_koroborasi(["kumparan"], TIER, BOBOT)
    assert skor == 35.0
    assert verdict(skor, 80, 50) == "belum terverifikasi"
    skor3, _ = skor_koroborasi(["blog_x"], TIER, BOBOT)
    assert skor3 == 20.0


def test_media_tak_dikenal_jatuh_ke_tier3():
    assert bobot_media("media_asing", TIER, BOBOT) == 0.4


def test_kombinasi_tier1_tier2():
    skor, rincian = skor_koroborasi(["kompas", "kumparan"], TIER, BOBOT)
    assert skor == 85.0  # (1.0+0.7)/2*100
    assert verdict(skor, 80, 50) == "terkoroborasi"


def test_headline_bombastis():
    assert cek_headline("Darurat! Karhutla melanda", "isi panjang " * 20,
                        PENANDA) == ["bombastis"]
    assert cek_headline("Karhutla melanda Riau", "isi", PENANDA) == []


def test_bombastis_tak_didukung_bila_ringkasan_kosong():
    flags = cek_headline("Heboh kebakaran!", "", PENANDA)
    assert flags == ["bombastis", "bombastis tak didukung"]
