"""Unduh isi lengkap artikel yang belum punya (Fase H).

Best-effort: artikel yang gagal unduh ditandai "" agar tidak diulang
tiap siklus; pakai --force untuk mencoba ulang semuanya.

Contoh:
    python scripts/unduh_isi.py --limit 150
    python scripts/unduh_isi.py --limit 50 --force
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common.config import load_settings  # noqa: E402
from src.ingestion.artikel import siklus_unduh_isi  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--force", action="store_true",
                    help="unduh ulang semua (termasuk yang gagal)")
    args = ap.parse_args()

    settings = load_settings()
    cfg = settings.get("unduh_isi", {})
    hasil = siklus_unduh_isi(
        ROOT / settings["storage"]["db_path"],
        limit=args.limit,
        delay_detik=float(cfg.get("delay_detik", 1.0)),
        timeout_detik=int(cfg.get("timeout_detik", 20)),
        force=args.force,
    )
    print(f"total={hasil['total']} ok={hasil['ok']} gagal={hasil['gagal']}")


if __name__ == "__main__":
    main()
