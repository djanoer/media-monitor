"""Test sentimen leksikon + skor risiko (tanpa DB, tanpa model)."""

from src.processing.risiko import skor_risiko
from src.processing.sentimen import analisis, skor_teks

CFG = {
    "risiko_base": 20, "risiko_negatif": 35, "risiko_netral": 10,
    "risiko_bombastis": 20, "risiko_belum_terverifikasi": 15,
    "risiko_terkoroborasi": -15,
    "ambang_risiko_tinggi": 65, "ambang_risiko_sedang": 35,
}


def test_positif_jelas():
    label, skor = analisis(
        "Presiden apresiasi keberhasilan program bantuan",
        "Pemerintah bangga atas prestasi luar biasa ini", 2.0, 2.0)
    assert label == "positif" and skor > 0


def test_negatif_jelas():
    label, skor = analisis(
        "Kebakaran hutan meluas, korban tewas bertambah",
        "Bencana parah, warga panik dan mengungsi", 2.0, 2.0)
    assert label == "negatif" and skor < 0


def test_netral_sinyal_lemah():
    label, _ = analisis("Rapat koordinasi digelar hari ini",
                        "Acara berlangsung di ruang rapat utama", 2.0, 2.0)
    assert label == "netral"


def test_negasi_membalik():
    # "tidak baik" -> negatif; "tidak buruk" -> positif
    assert skor_teks("pelayanan tidak baik") < 0
    assert skor_teks("kondisi tidak buruk") > 0


def test_penguat_mengalikan():
    assert skor_teks("sangat bagus") > skor_teks("bagus")


def test_bobot_judul():
    # kata positif hanya di judul, bobot 2 -> lolos ambang
    label, _ = analisis("sukses besar", "", 2.0, 2.0)
    assert label == "positif"
    label2, _ = analisis("sukses besar", "", 3.0, 1.0)
    assert label2 == "netral"


def test_risiko_dasar_netral():
    level, skor = skor_risiko("netral", False, [], CFG)
    assert (level, skor) == ("Rendah", 30.0)  # 20 + 10


def test_risiko_negatif_bombastis_tak_terverifikasi():
    level, skor = skor_risiko(
        "negatif", True, ["belum terverifikasi"], CFG)
    assert skor == 20 + 35 + 20 + 15 == 90.0
    assert level == "Tinggi"


def test_risiko_turun_bila_terkoroborasi():
    _, s1 = skor_risiko("negatif", False, ["terkoroborasi"], CFG)
    _, s2 = skor_risiko("negatif", False, [], CFG)
    assert s1 == s2 - 15


def test_risiko_clamp_dan_level():
    level, skor = skor_risiko("negatif", True,
                              ["belum terverifikasi", "terkoroborasi"], CFG)
    assert skor <= 100.0
    # campur: unverified menang atas koroborasi (elif)
    assert skor == 90.0 and level == "Tinggi"
    lvl, sk = skor_risiko("positif", False, ["terkoroborasi"], CFG)
    assert (lvl, sk) == ("Rendah", 5.0)


def test_risiko_sedang():
    level, skor = skor_risiko("negatif", False, [], CFG)
    assert (level, skor) == ("Sedang", 55.0)
