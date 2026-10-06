"""Siklus analisa sentimen + risiko per artikel (Fase F).

Dipakai dua tempat:
- scripts/analisa_sentimen_risiko.py (manual)
- fetch_cycle() di src/scheduler/jobs.py (otomatis tiap jam -> full otomatis)

Komputasi lokal murni (leksikon + rumus); tanpa API/kuota sehingga aman
dijalankan tiap siklus. Best-effort: satu artikel gagal tidak menghentikan
yang lain; fungsi tak pernah raise untuk data normal.
"""

from __future__ import annotations

import logging

from src.common.text import bersihkan_html
from src.processing.risiko import skor_risiko
from src.processing.sentimen import analisis
from src.processing.verification import cek_headline
from src.storage import repository

log = logging.getLogger("media_monitor")


def siklus_analisa(
    db_path,
    settings: dict,
    limit: int = 0,
    force: bool = False,
) -> dict:
    """Analisa artikel yang belum dianalisa (semua bila force=True).

    Kembalikan {"n": jumlah, "sentimen": {label: n}, "risiko": {level: n}}.
    Idempoten: tanpa force, artikel yang sudah berlabel dilewati.
    """
    cfg = settings.get("analisa", {})
    ver = settings.get("verification", {})
    penanda = ver.get("penanda_bombastis", [])

    repository.migrate_analisa(db_path)
    artikel = repository.get_artikel_untuk_analisa(
        db_path, force=force, limit=limit)
    verdicts = repository.get_verdicts_artikel(db_path)

    dist_s: dict[str, int] = {}
    dist_r: dict[str, int] = {}
    n = 0
    for a in artikel:
        try:
            judul = a["title"] or ""
            ringkas = bersihkan_html(a.get("summary") or "")
            label, skor = analisis(
                judul, ringkas,
                ambang=cfg.get("ambang_sentimen", 2.0),
                bobot_judul=cfg.get("bobot_judul", 2.0),
            )
            bombastis = bool(cek_headline(judul, ringkas, penanda))
            level, rskor = skor_risiko(
                label, bombastis, verdicts.get(a["url"], []), cfg)
            repository.simpan_analisa(
                db_path, a["url"], label, skor, level, rskor)
        except Exception as exc:  # satu artikel gagal != siklus gagal
            log.warning("analisa %s gagal: %s", a.get("url"), exc)
            continue
        dist_s[label] = dist_s.get(label, 0) + 1
        dist_r[level] = dist_r.get(level, 0) + 1
        n += 1
    return {"n": n, "sentimen": dist_s, "risiko": dist_r}
