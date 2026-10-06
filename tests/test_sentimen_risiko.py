"""Test sentimen leksikon + skor risiko (tanpa DB, tanpa model)."""

from src.processing.risiko import skor_risiko
from src.processing.sentimen import analisis, skor_teks
from src.storage import repository

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


def _db_analisa(tmp_path):
    import sqlite3
    db = str(tmp_path / "g.db")
    repository.init_db(db)
    repository.migrate_analisa(db)
    conn = sqlite3.connect(db)
    rows = [
        ("u1", "kompas", "T1", "baik bagus sukses", "positif", 4.0, "Rendah", 10.0),
        ("u2", "kompas", "T2", "buruk gagal parah", "negatif", -5.0, "Tinggi", 80.0),
        ("u3", "detik", "T3", "rapat digelar", "netral", 0.0, "Rendah", 20.0),
    ]
    for u, m, t, s, se, ss, r, rs in rows:
        conn.execute(
            "INSERT INTO articles (url, media, title, summary, fetched_at,"
            " sentimen, sentimen_skor, risiko, risiko_skor)"
            " VALUES (?,?,?,?,'x',?,?,?,?)",
            (u, m, t, s, se, ss, r, rs))
    conn.commit()
    conn.close()
    return db


def test_rata_risiko(tmp_path):
    db = _db_analisa(tmp_path)
    assert repository.rata_risiko(db) == round((10 + 80 + 20) / 3, 1)


def test_distribusi_per_media(tmp_path):
    db = _db_analisa(tmp_path)
    d = repository.distribusi_per_media(db)
    assert d["kompas"]["sentimen"] == {"positif": 1, "negatif": 1}
    assert d["kompas"]["risiko"] == {"Rendah": 1, "Tinggi": 1}
    assert d["detik"]["sentimen"] == {"netral": 1}


def test_get_artikel_per_media(tmp_path):
    db = _db_analisa(tmp_path)
    g = repository.get_artikel_per_media(db, limit_per_media=1)
    assert set(g) == {"kompas", "detik"}
    assert len(g["kompas"]) == 1
    assert "risiko" in g["kompas"][0]


def test_header_kartu_minimalis():
    from app import komponen as kmp
    html = kmp.header_kartu_minimalis(
        "Kompas", "#4285f4",
        {"sentimen": {"positif": 1, "netral": 2, "negatif": 3},
         "risiko": {"Rendah": 1, "Sedang": 2, "Tinggi": 3}}, 6)
    assert "Kompas" in html
    assert ">6<" in html  # pil count
    assert "P 1 · N 2 · NG 3" in html  # ringkas sentimen
    assert "R 1 · S 2 · T 3" in html  # ringkas risiko
    assert "?art=" not in html  # tanpa trik hyperlink
    assert html.count("<div") == html.count("</div>")  # seimbang


def test_kata_berpengaruh_negatif():
    from src.processing.sentimen import kata_berpengaruh
    k = kata_berpengaruh(
        "Kebakaran hutan meluas, korban tewas bertambah",
        "Bencana parah, warga panik", 6, 2.0)
    assert "kebakaran" in k["negatif"]
    assert k["positif"] == []


def test_kata_berpengaruh_positif():
    from src.processing.sentimen import kata_berpengaruh
    k = kata_berpengaruh(
        "Presiden apresiasi keberhasilan program", "Sukses luar biasa", 6, 2.0)
    assert "apresiasi" in k["positif"]
    assert k["negatif"] == []


def test_komponen_risiko_urutan_dan_jumlah():
    from src.processing.risiko import komponen_risiko, skor_risiko
    komp = komponen_risiko("negatif", True, ["belum terverifikasi"], CFG)
    ket = [k for k, _ in komp]
    assert ket == ["base", "sentimen negatif", "headline bombastis",
                   "klaim belum terverifikasi"]
    total = max(0.0, min(100.0, round(sum(d for _, d in komp), 1)))
    _, skor = skor_risiko("negatif", True, ["belum terverifikasi"], CFG)
    assert total == skor


def test_komponen_risiko_tidak_ada_verdict():
    from src.processing.risiko import komponen_risiko
    komp = komponen_risiko("netral", False, [], CFG)
    assert [k for k, _ in komp] == ["base", "sentimen netral"]
