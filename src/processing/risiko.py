"""Skor risiko per artikel (Fase F, 0-100).

Keunggulan vs referensi: risiko tidak hanya dari nada teks, tapi dari
sinyal verifikasi kita sendiri:
- klaim terkoroborasi (multi-sumber independen) -> risiko TURUN
- klaim belum terverifikasi (satu sumber lemah) -> risiko NAIK
- headline bombastis -> risiko NAIK

Rumus (semua angka configurable di settings.yaml -> analisa):
    risiko = base
           + (negatif: +w_neg | netral: +w_net | positif: +0)
           + (bombastis: +w_bomb)
           + (ada verdict belum_terverifikasi: +w_unver
              elif ada verdict terkoroborasi: +w_korob)  # w_korob negatif
    clamp 0-100.

Level: >= ambang_tinggi -> "Tinggi"; >= ambang_sedang -> "Sedang";
       else "Rendah".
"""

from __future__ import annotations


def skor_risiko(
    sentimen: str,
    bombastis: bool,
    verdicts: list[str],
    cfg: dict,
) -> tuple[str, float]:
    """Kembalikan (level, skor). verdicts = verdict cluster klaim artikel."""
    risiko = float(cfg.get("risiko_base", 20))
    if sentimen == "negatif":
        risiko += float(cfg.get("risiko_negatif", 35))
    elif sentimen == "netral":
        risiko += float(cfg.get("risiko_netral", 10))
    if bombastis:
        risiko += float(cfg.get("risiko_bombastis", 20))
    if any(v == "belum terverifikasi" for v in verdicts):
        risiko += float(cfg.get("risiko_belum_terverifikasi", 15))
    elif any(v == "terkoroborasi" for v in verdicts):
        risiko += float(cfg.get("risiko_terkoroborasi", -15))
    risiko = max(0.0, min(100.0, round(risiko, 1)))
    if risiko >= float(cfg.get("ambang_risiko_tinggi", 65)):
        level = "Tinggi"
    elif risiko >= float(cfg.get("ambang_risiko_sedang", 35)):
        level = "Sedang"
    else:
        level = "Rendah"
    return level, risiko
