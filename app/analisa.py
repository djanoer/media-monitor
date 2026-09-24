"""Analisa teks murni untuk halaman Analisa Keyword (tanpa streamlit).

Isi: hitung kata yang sering muncul bersama sebuah keyword dari
kumpulan judul artikel. Stopwords Bahasa Indonesia dari Sastrawi.
"""

from __future__ import annotations

import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]+")


def tokenisasi(judul: str) -> list[str]:
    """Judul -> token alfanumerik lowercase."""
    return TOKEN.findall(judul.lower())


def kata_terkait(
    daftar_judul: list[str],
    keyword: str,
    stopwords: set[str] | frozenset,
    top_n: int = 15,
) -> list[tuple[str, int]]:
    """Kata tersering yang muncul bersama keyword (di luar keyword itu sendiri).

    Buang stopwords dan token pendek (<=2 huruf). Kembalikan
    [(kata, jumlah), ...] terurut menurun.
    """
    kunci = {t for t in tokenisasi(keyword)}
    hitung: Counter[str] = Counter()
    for judul in daftar_judul:
        for tok in set(tokenisasi(judul)):
            if len(tok) <= 2 or tok in kunci or tok in stopwords:
                continue
            hitung[tok] += 1
    return hitung.most_common(top_n)
