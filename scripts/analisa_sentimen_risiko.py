"""Analisa sentimen + risiko per artikel (Fase F).

Jalankan dari root proyek (venv aktif):
    python scripts/analisa_sentimen_risiko.py [--force] [--limit N]

Tanpa --force hanya memproses artikel yang belum dianalisa.
Rumus risiko memakai sinyal verifikasi (Fase C): lihat
src/processing/risiko.py.

Sejak revisi full-otomatis, analisa juga jalan sendiri di akhir tiap
siklus scheduler (config analisa.otomatis); script ini untuk kebutuhan
manual (mis. --force).
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from src.common.config import load_settings
from src.processing.analisa import siklus_analisa
from src.storage import repository


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="analisa ulang semua artikel")
    ap.add_argument("--limit", type=int, default=0,
                    help="batasi jumlah artikel (0 = semua)")
    args = ap.parse_args()

    settings = load_settings()
    db_path = settings["storage"]["db_path"]

    repository.init_db(db_path)
    hasil = siklus_analisa(db_path, settings,
                           limit=args.limit, force=args.force)
    if not hasil["n"]:
        print("Tidak ada artikel yang perlu dianalisa.")
        return 0

    print(f"Dianalisa: {hasil['n']} artikel")
    print("Sentimen:", ", ".join(
        f"{k}={v}" for k, v in sorted(hasil["sentimen"].items())))
    print("Risiko:", ", ".join(
        f"{k}={v}" for k, v in sorted(hasil["risiko"].items())))
    print("Selesai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
