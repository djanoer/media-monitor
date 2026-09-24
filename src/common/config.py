"""Pemuatan konfigurasi YAML.

Satu-satunya tempat membaca config/*.yaml (DRY): seluruh kode mengambil
pengaturan lewat fungsi di sini, tidak ada yang membuka file YAML langsung.
"""

from __future__ import annotations

import pathlib

import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def load_settings(path: pathlib.Path | str | None = None) -> dict:
    """Baca config/settings.yaml -> dict."""
    path = pathlib.Path(path) if path else CONFIG_DIR / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_media(path: pathlib.Path | str | None = None) -> list[dict]:
    """Baca config/media.yaml -> daftar media yang aktif saja."""
    path = pathlib.Path(path) if path else CONFIG_DIR / "media.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [m for m in data.get("media", []) if m.get("active", True)]
