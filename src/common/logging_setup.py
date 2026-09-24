"""Konfigurasi logging: tulis ke logs/ sekaligus tampil di console."""

from __future__ import annotations

import logging
import pathlib
import sys

from src.common.config import PROJECT_ROOT


def setup_logging(
    name: str = "media_monitor",
    log_file: pathlib.Path | str | None = None,
) -> logging.Logger:
    log_file = pathlib.Path(log_file) if log_file else PROJECT_ROOT / "logs" / "fetch.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:  # sudah dikonfigurasi sebelumnya
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
