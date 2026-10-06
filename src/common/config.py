"""Pemuatan konfigurasi YAML.

Satu-satunya tempat membaca config/*.yaml (DRY): seluruh kode mengambil
pengaturan lewat fungsi di sini, tidak ada yang membuka file YAML langsung.
"""

from __future__ import annotations

import pathlib

import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def _muat_dotenv() -> None:
    """Muat `.env` di root proyek bila ada (opsional).

    Env var sistem tetap prioritas (override=False): mendukung dua skenario —
    `setx` di laptop utama, file `.env` di laptop kedua. Tanpa python-dotenv
    terinstal -> dilewati diam-diam (lingkungan test/CI).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_ROOT / ".env")


def load_settings(path: pathlib.Path | str | None = None) -> dict:
    """Baca config/settings.yaml -> dict."""
    _muat_dotenv()
    path = pathlib.Path(path) if path else CONFIG_DIR / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_media(path: pathlib.Path | str | None = None) -> list[dict]:
    """Baca config/media.yaml -> daftar media yang aktif saja."""
    path = pathlib.Path(path) if path else CONFIG_DIR / "media.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [m for m in data.get("media", []) if m.get("active", True)]


def load_topics(path: pathlib.Path | str | None = None) -> dict:
    """Baca config/topics.yaml -> dict {nama_topik: spesifikasi keyword}."""
    path = pathlib.Path(path) if path else CONFIG_DIR / "topics.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("topics", {})
