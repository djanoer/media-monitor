"""Entrypoint scheduler Media Monitor.

    python run_scheduler.py         -> jalan terus, fetch tiap interval (APScheduler in-process)
    python run_scheduler.py --once  -> satu siklus fetch lalu keluar (cocok untuk cron/testing)

Dijalankan dari root proyek dengan venv aktif.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.common.logging_setup import setup_logging  # noqa: E402
from src.scheduler.jobs import fetch_cycle, start_scheduler  # noqa: E402

log = logging.getLogger("media_monitor")


def main() -> None:
    parser = argparse.ArgumentParser(description="Media Monitor scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="jalankan satu siklus fetch lalu keluar",
    )
    args = parser.parse_args()
    setup_logging()

    if args.once:
        summary = fetch_cycle()
        ok = sum(1 for v in summary.values() if v["status"] == "ok")
        new_total = sum(v["new"] for v in summary.values())
        log.info("selesai: %d/%d media OK, %d artikel baru", ok, len(summary), new_total)
        print(f"media OK: {ok}/{len(summary)} | artikel baru: {new_total}")
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
