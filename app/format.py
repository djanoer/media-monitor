"""Fungsi format murni untuk tampilan (tanpa streamlit, bisa di-unit-test).

Isi: pembersih HTML ringkasan RSS, konversi waktu UTC -> WITA,
dan format waktu relatif Bahasa Indonesia.
"""

from __future__ import annotations

import datetime
import html
import re

# WITA = UTC+8 tetap, tanpa daylight saving.
WITA_OFFSET = datetime.timedelta(hours=8)

BULAN_ID = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]


def bersihkan_html(teks: str | None) -> str:
    """Buang tag HTML dan entity dari ringkasan RSS.

    Contoh: '<img src="..."/> WNA Malaysia ...' -> 'WNA Malaysia ...'.
    Kembalikan teks polos satu baris.
    """
    if not teks:
        return ""
    s = html.unescape(teks)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(s.split())


def parse_utc(iso: str | None) -> datetime.datetime | None:
    """Parse string ISO -> datetime aware UTC. Kembalikan None bila gagal."""
    if not iso:
        return None
    try:
        dt = datetime.datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def utc_sekarang_iso() -> str:
    """Waktu sekarang sebagai ISO UTC (untuk query count_articles_since)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def iso_mundur(jam: int) -> str:
    """ISO UTC untuk N jam yang lalu."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=jam)
    ).isoformat()


def format_wita(iso: str | None) -> str:
    """'2026-09-25T04:10:00+00:00' -> '25 Sep 2026, 12:10 WITA'."""
    dt = parse_utc(iso)
    if dt is None:
        return "-"
    w = dt + WITA_OFFSET
    return f"{w.day} {BULAN_ID[w.month - 1]} {w.year}, {w:%H:%M} WITA"


def waktu_relatif(
    iso: str | None,
    sekarang_utc: datetime.datetime | None = None,
) -> str:
    """'5 menit lalu' / '2 jam lalu' / '3 hari lalu' dalam Bahasa Indonesia."""
    dt = parse_utc(iso)
    if dt is None:
        return "-"
    now = sekarang_utc or datetime.datetime.now(datetime.timezone.utc)
    detik = max(0, int((now - dt).total_seconds()))
    if detik < 60:
        return "baru saja"
    menit = detik // 60
    if menit < 60:
        return f"{menit} menit lalu"
    jam = menit // 60
    if jam < 24:
        return f"{jam} jam lalu"
    return f"{jam // 24} hari lalu"


def menit_sejak(iso: str | None) -> float | None:
    """Berapa menit berlalu sejak ISO UTC. None bila tidak bisa diparse."""
    dt = parse_utc(iso)
    if dt is None:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now - dt).total_seconds() / 60
