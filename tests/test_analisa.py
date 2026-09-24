"""Test analisa teks murni (app/analisa.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import analisa

STOP = frozenset({"yang", "dan", "di", "ke", "dari"})


def test_kata_terkait():
    judul = [
        "Rupiah menguat terhadap dolar AS",
        "Rupiah melemah, dolar menguat tajam",
        "Harga BBM naik, rupiah tertekan",
    ]
    hasil = dict(analisa.kata_terkait(judul, "rupiah", STOP, top_n=10))
    assert "menguat" in hasil and hasil["menguat"] == 2
    assert "dolar" in hasil and hasil["dolar"] == 2
    # keyword itu sendiri dan stopwords tidak ikut
    assert "rupiah" not in hasil
    assert "yang" not in hasil and "dan" not in hasil
    # token pendek dibuang
    assert "as" not in hasil


def test_kata_terkait_kosong():
    assert analisa.kata_terkait([], "rupiah", STOP) == []
    # keyword tidak ada di judul -> semua kata non-stopword dihitung (urutan tie bebas)
    assert dict(analisa.kata_terkait(["Rupiah menguat"], "bbm", STOP)) == {
        "rupiah": 1,
        "menguat": 1,
    }
