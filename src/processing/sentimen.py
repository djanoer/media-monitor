"""Analisis sentimen berbasis leksikon Bahasa Indonesia (Fase F).

Skor = jumlah bobot kata positif dikurangi kata negatif pada judul
(bobot ganda, configurable) + ringkasan. Negasi ("tidak baik")
membalik polaritas; penguat ("sangat") mengalikan 1.5.

Label: |skor| >= ambang -> positif/negatif; else netral.
Baseline: netral bila sinyal lemah (seperti referensi: mayoritas netral).
"""

from __future__ import annotations

import re

from src.processing.leksikon_sentimen import INTENSIF, NEGASI, NEGATIF, POSITIF

_TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)?")


def tokenisasi(teks: str) -> list[str]:
    """Token kata lowercase; buang angka & simbol."""
    return _TOKEN.findall((teks or "").lower())


def skor_teks(
    teks: str,
    bobot: float = 1.0,
) -> float:
    """Skor sentimen satu teks (positif > 0)."""
    tokens = tokenisasi(teks)
    skor = 0.0
    for i, tok in enumerate(tokens):
        if tok in POSITIF:
            val = 1.0
        elif tok in NEGATIF:
            val = -1.0
        else:
            continue
        jendela = tokens[max(0, i - 2):i]
        if any(t in NEGASI for t in jendela):
            val = -val
        if any(t in INTENSIF for t in jendela):
            val *= 1.5
        skor += val * bobot
    return round(skor, 2)


def analisis(
    judul: str,
    ringkasan: str,
    ambang: float = 2.0,
    bobot_judul: float = 2.0,
) -> tuple[str, float]:
    """Kembalikan (label, skor). Label: positif/netral/negatif."""
    skor = skor_teks(judul, bobot_judul) + skor_teks(ringkasan or "", 1.0)
    skor = round(skor, 2)
    if skor >= ambang:
        return "positif", skor
    if skor <= -ambang:
        return "negatif", skor
    return "netral", skor


def kata_berpengaruh(
    judul: str,
    ringkasan: str,
    n: int = 6,
    bobot_judul: float = 2.0,
) -> dict[str, list[str]]:
    """Kata sentimen paling berpengaruh (untuk penjelasan label).

    Kembalikan {"positif": [...], "negatif": [...]} — kata unik diurutkan
    berdasarkan kontribusi bobot absolut terbesar.
    """
    kontribusi: dict[str, float] = {}

    def _hitung(teks: str, bobot: float) -> None:
        tokens = tokenisasi(teks)
        for i, tok in enumerate(tokens):
            if tok in POSITIF:
                val = 1.0
            elif tok in NEGATIF:
                val = -1.0
            else:
                continue
            jendela = tokens[max(0, i - 2):i]
            if any(t in NEGASI for t in jendela):
                val = -val
            if any(t in INTENSIF for t in jendela):
                val *= 1.5
            kontribusi[tok] = kontribusi.get(tok, 0.0) + val * bobot

    _hitung(judul, bobot_judul)
    _hitung(ringkasan or "", 1.0)
    urut = sorted(kontribusi.items(), key=lambda kv: -abs(kv[1]))
    pos = [k for k, v in urut if v > 0][:n]
    neg = [k for k, v in urut if v < 0][:n]
    return {"positif": pos, "negatif": neg}
