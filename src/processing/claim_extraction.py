"""Ekstraksi klaim rule-based (tanpa ML).

Aturan:
- Setiap artikel -> 1 klaim utama dari judul (claim_type='headline').
- Kalimat kunci dari ringkasan: kalimat yang mengandung angka
  (klaim kuantitatif: luas lahan, jumlah korban, dsb.), panjang minimum
  claim_min_length, maks claim_max_sentences per artikel, dan tidak
  duplikat dengan judul.

Deterministik dan mudah diuji. Fase lanjutan boleh menambah aturan
(neraca klaim kutipan, dsb.) tanpa mengubah kontrak fungsi ini.
"""

from __future__ import annotations

import re

from src.common.text import bersihkan_html

_PEMECAH_KALIMAT = re.compile(r"(?<=[.!?])\s+")
_ANGKA = re.compile(r"\d")


def split_sentences(teks: str) -> list[str]:
    """Pecah teks jadi kalimat (aturan sederhana, cukup untuk ringkasan)."""
    return [k.strip() for k in _PEMECAH_KALIMAT.split(teks or "") if k.strip()]


def extract_claims(
    artikel: dict,
    max_sentences: int = 3,
    min_length: int = 20,
) -> list[dict]:
    """Ekstrak klaim dari satu artikel -> list {claim_text, claim_type}.

    Selalu kembalikan klaim judul bila ada; kalimat kunci diambil dari
    ringkasan bila memenuhi syarat.
    """
    klaim: list[dict] = []
    judul = (artikel.get("title") or "").strip()
    if judul:
        klaim.append({"claim_text": judul, "claim_type": "headline"})

    terlihat = {judul.lower()}
    diambil = 0
    # Ringkasan RSS mentah mengandung tag HTML (<img>, <a href>) yang URL-nya
    # mengandung angka -> wajib dibersihkan dulu agar tidak jadi klaim sampah.
    ringkasan_bersih = bersihkan_html(artikel.get("summary"))
    for kalimat in split_sentences(ringkasan_bersih):
        if diambil >= max_sentences:
            break
        if len(kalimat) < min_length:
            continue
        if not _ANGKA.search(kalimat):
            continue
        kunci = kalimat.lower()
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        klaim.append({"claim_text": kalimat, "claim_type": "sentence"})
        diambil += 1
    return klaim
