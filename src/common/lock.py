"""Kunci proses (file lock): cegah dua proses sama jalan bersamaan.

Skenario: Bor double-click all-in-one.bat dua kali -> dua scheduler fetch
bareng (dobel kerja + rebutan DB) atau dua sync --auto bareng (dobel kuota
YouTube + rawan 429 Trends). Dengan kunci ini, proses kedua batal dengan
pesan yang jelas.

Kunci basi (laptop crash / window ditutup paksa sehingga atexit tak jalan)
diambil alih otomatis: dicek apakah PID pemilik masih hidup.
"""

from __future__ import annotations

import atexit
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
_DIR = ROOT / "data"

_kunci_aktif: pathlib.Path | None = None


def _pid_hidup(pid: int) -> bool:
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=15,
            )
            return str(pid) in r.stdout
        except Exception:
            return True  # gagal cek -> anggap hidup (tolak start ganda)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _lepas() -> None:
    global _kunci_aktif
    if _kunci_aktif is not None:
        try:
            _kunci_aktif.unlink(missing_ok=True)
        except OSError:
            pass
        _kunci_aktif = None


def minta(nama: str) -> bool:
    """Minta kunci `nama`. True bila dapat (dilepas otomatis saat keluar),
    False bila proses lain dengan kunci yang sama masih hidup."""
    global _kunci_aktif
    _DIR.mkdir(parents=True, exist_ok=True)
    path = _DIR / f"{nama}.lock"
    if path.exists():
        try:
            pid_lama = int(path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            pid_lama = 0
        if pid_lama and _pid_hidup(pid_lama):
            return False
        # Kunci basi -> ambil alih.
    try:
        path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return False
    _kunci_aktif = path
    atexit.register(_lepas)
    return True


def lepas() -> None:
    """Lepas kunci yang sedang dipegang (umumnya via atexit otomatis)."""
    _lepas()
