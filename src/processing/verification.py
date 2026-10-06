"""Skor koroborasi + sinyal verifikasi per cluster klaim (Fase C).

Skor koroborasi (0-100):
    skor = min(100, round(100 * total_bobot / 2.0))
total_bobot = jumlah bobot tier untuk tiap media UNIK di cluster.
2.0 (dua sumber Tier 1) -> 100. Media yang sama dihitung sekali walau
muncul di banyak klaim: koroborasi = banyaknya sumber independen.

Verdict:
- skor >= ambang_terkoroborasi -> "terkoroborasi"
- skor >= ambang_satu_sumber    -> "satu sumber kredibel"
- di bawah itu                  -> "belum terverifikasi"

Cek headline: flag "bombastis" bila judul mengandung penanda bombastis
dari config. Sinyal sederhana, bukan vonis.
"""

from __future__ import annotations

import re


def bobot_media(media: str, tier_per_media: dict, bobot_per_tier: dict) -> float:
    """Bobot kredibilitas satu media; media tak dikenal -> tier 3."""
    tier = tier_per_media.get(media, 3)
    try:
        tier = int(tier)
    except (TypeError, ValueError):
        tier = 3
    return float(bobot_per_tier.get(tier, bobot_per_tier.get(3, 0.4)))


def skor_koroborasi(
    media_anggota: list[str],
    tier_per_media: dict,
    bobot_per_tier: dict,
) -> tuple[float, dict]:
    """Hitung skor + rincian per tier. Kembalikan (skor, rincian)."""
    unik = set(media_anggota)
    per_tier: dict[int, int] = {}
    total = 0.0
    for m in unik:
        tier = tier_per_media.get(m, 3)
        try:
            tier = int(tier)
        except (TypeError, ValueError):
            tier = 3
        per_tier[tier] = per_tier.get(tier, 0) + 1
        total += float(bobot_per_tier.get(tier, bobot_per_tier.get(3, 0.4)))
    skor = min(100.0, round(100.0 * total / 2.0, 1))
    rincian = {
        "media_unik": sorted(unik),
        "per_tier": {str(k): v for k, v in sorted(per_tier.items())},
        "total_bobot": round(total, 2),
    }
    return skor, rincian


def verdict(skor: float, ambang_terkoroborasi: float, ambang_satu_sumber: float) -> str:
    """Label verdict berdasarkan skor."""
    if skor >= ambang_terkoroborasi:
        return "terkoroborasi"
    if skor >= ambang_satu_sumber:
        return "satu sumber kredibel"
    return "belum terverifikasi"


def _pola_bombastis(penanda: list[str]) -> list[re.Pattern]:
    return [re.compile(re.escape(p), re.IGNORECASE) for p in penanda]


def cek_headline(
    judul: str, ringkasan: str, penanda: list[str]
) -> list[str]:
    """Flag headline: ['bombastis'] bila judul mengandung penanda.

    'bombastis tak didukung' bila juga ringkasannya kosong/sangat pendek
    (< 50 karakter): judul heboh tapi isi tidak menjelaskan apa-apa.
    """
    flags: list[str] = []
    judul = judul or ""
    if any(p.search(judul) for p in _pola_bombastis(penanda or [])):
        flags.append("bombastis")
        if len((ringkasan or "").strip()) < 50:
            flags.append("bombastis tak didukung")
    return flags
