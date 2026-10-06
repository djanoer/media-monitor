"""Utilitas teks murni (tanpa dependensi UI)."""

from __future__ import annotations

import html
import re


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
