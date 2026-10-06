"""Bersihkan data respons publik untuk satu topik sampah/arsip.

Contoh: topik "com" yang lolos dari ekstraksi otomatis (bug, sudah diperbaiki
di src/processing/topik_hangat.py).

Jalankan dari root proyek (venv aktif):
    python scripts/bersihkan_topik.py --topik com         # tampilkan dulu
    python scripts/bersihkan_topik.py --topik com --ya    # hapus beneran
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from src.common.config import load_settings
from src.storage import repository


def hapus_topik(db_path: str, topik: str, jalan: bool = False) -> dict:
    """Hitung (dan bila jalan=True, hapus) baris per tabel untuk topik."""
    hasil = {}
    with repository._connect(db_path) as conn:
        for tabel in ("youtube_videos", "trends_harian", "trends_ringkas"):
            n = conn.execute(
                f"SELECT COUNT(*) AS n FROM {tabel} WHERE topik = ?",
                (topik,),
            ).fetchone()["n"]
            hasil[tabel] = n
            if jalan and n:
                conn.execute(f"DELETE FROM {tabel} WHERE topik = ?", (topik,))
    return hasil


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topik", required=True)
    ap.add_argument("--ya", action="store_true",
                    help="hapus beneran (tanpa ini hanya tampilkan jumlah)")
    args = ap.parse_args()

    db_path = load_settings()["storage"]["db_path"]
    repository.init_db(db_path)
    hasil = hapus_topik(db_path, args.topik, jalan=args.ya)
    total = sum(hasil.values())
    mode = "DIHAPUS" if args.ya else "akan dihapus (tambah --ya utk eksekusi)"
    for tabel, n in hasil.items():
        print(f"  {tabel}: {n} baris {mode}")
    print(f"Total: {total} baris.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
