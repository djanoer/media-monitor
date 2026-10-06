"""Pencocokan topik berbasis keyword, config-driven tanpa ML.

Aturan per topik (spesifikasi dari config/topics.yaml), dievaluasi berurutan:
1. exclude: bila ada frasa exclude yang cocok -> BUKAN topik, berhenti.
2. high_precision: bila ada frasa yang cocok -> topik.
3. contextual: bila ada kata contextual yang cocok DAN minimal satu
   context_words muncul di teks yang sama -> topik.

Pencocokan case-insensitive dengan batas kata agar "asap" tidak cocok
dengan "berasap-asap" dsb. Tanpa ML: cepat, deterministik, mudah diuji.
"""

from __future__ import annotations

import re

# Cache pola regex per frasa agar tidak dikompilasi ulang tiap artikel.
_POLA_CACHE: dict[str, re.Pattern] = {}


def _pola(frasa: str) -> re.Pattern:
    if frasa not in _POLA_CACHE:
        _POLA_CACHE[frasa] = re.compile(r"\b" + re.escape(frasa) + r"\b", re.IGNORECASE)
    return _POLA_CACHE[frasa]


def _cocok(teks: str, frasa_daftar: list[str]) -> bool:
    return any(_pola(f).search(teks) for f in frasa_daftar)


def match_topic(teks: str, spec: dict) -> bool:
    """True bila teks masuk topik sesuai spec keyword-nya."""
    teks = teks or ""
    if _cocok(teks, spec.get("exclude", [])):
        return False
    if _cocok(teks, spec.get("high_precision", [])):
        return True
    if _cocok(teks, spec.get("contextual", [])):
        return _cocok(teks, spec.get("context_words", []))
    return False


def match_topics(teks: str, topics: dict) -> list[str]:
    """Kembalikan daftar nama topik yang cocok untuk teks ini."""
    return [nama for nama, spec in topics.items() if match_topic(teks, spec or {})]


def teks_artikel(artikel: dict) -> str:
    """Gabung judul + ringkasan jadi satu teks untuk pencocokan."""
    judul = (artikel.get("title") or "").strip()
    ringkasan = (artikel.get("summary") or "").strip()
    return f"{judul}\n{ringkasan}".strip()
