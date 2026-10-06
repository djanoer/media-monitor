"""Analisa sentimen + risiko per artikel (Fase F).

Jalankan dari root proyek (venv aktif):
    python scripts/analisa_sentimen_risiko.py [--force] [--limit N]

Tanpa --force hanya memproses artikel yang belum dianalisa.
Rumus risiko memakai sinyal verifikasi (Fase C): lihat
src/processing/risiko.py.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from src.common.config import load_settings
from src.common.text import bersihkan_html
from src.processing.risiko import skor_risiko
from src.processing.sentimen import analisis
from src.processing.verification import cek_headline
from src.storage import repository


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="analisa ulang semua artikel")
    ap.add_argument("--limit", type=int, default=0,
                    help="batasi jumlah artikel (0 = semua)")
    args = ap.parse_args()

    settings = load_settings()
    cfg = settings.get("analisa", {})
    ver = settings.get("verification", {})
    db_path = settings["storage"]["db_path"]
    penanda = ver.get("penanda_bombastis", [])

    repository.init_db(db_path)
    tambah = repository.migrate_analisa(db_path)
    if tambah:
        print(f"Migrasi: kolom {tambah} ditambahkan ke articles.")

    artikel = repository.get_artikel_untuk_analisa(
        db_path, force=args.force, limit=args.limit)
    if not artikel:
        print("Tidak ada artikel yang perlu dianalisa.")
        return 0

    verdicts = repository.get_verdicts_artikel(db_path)
    n = 0
    dist_s: dict[str, int] = {}
    dist_r: dict[str, int] = {}
    for a in artikel:
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
        repository.simpan_analisa(db_path, a["url"], label, skor, level, rskor)
        dist_s[label] = dist_s.get(label, 0) + 1
        dist_r[level] = dist_r.get(level, 0) + 1
        n += 1

    print(f"Dianalisa: {n} artikel")
    print("Sentimen:", ", ".join(f"{k}={v}" for k, v in sorted(dist_s.items())))
    print("Risiko:", ", ".join(f"{k}={v}" for k, v in sorted(dist_r.items())))
    print("Selesai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
