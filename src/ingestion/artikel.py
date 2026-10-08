"""Unduh isi lengkap artikel berita (Fase H).

Banyak feed RSS mengisi deskripsi hanya dengan judul (atau kosong),
sehingga ringkasan di dashboard hanya mengulang judul. Modul ini
mengunduh halaman artikel dan mengekstrak teks utama dengan heuristik
sederhana (stdlib saja, tanpa dependensi baru):

- abaikan script/style/nav/header/footer/aside/form/noscript
- kumpulkan teks tiap <p> dengan panjang >= 60 karakter
- buang paragraf boilerplate (iklan, subscribe, baca juga, dsb.)
- gabung, batasi ~4000 karakter

Best-effort: gagal unduh/parse -> kembalikan "" (kolom tetap NULL).
"""

from __future__ import annotations

import logging
import re
import urllib.request
from html.parser import HTMLParser

log = logging.getLogger("media_monitor")

SKIP_TAGS = frozenset({
    "script", "style", "nav", "header", "footer", "aside",
    "form", "noscript", "iframe", "button", "select",
})

BOILERPLATE = re.compile(
    r"baca juga|advertisement|berlangganan|subscribe|ikuti kami|"
    r"download aplikasi|unduh aplikasi|copyright|hak cipta|"
    r"all rights reserved|klik di sini untuk|share this|bagikan artikel",
    re.IGNORECASE,
)

_PUTIH = re.compile(r"\s+")


class _Ekstraktor(HTMLParser):
    """Kumpulkan teks paragraf isi artikel."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._dalam_p = False
        self._buf: list[str] = []
        self.paragraf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag == "p" and not self._skip:
            self._dalam_p = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag == "p" and self._dalam_p:
            self._dalam_p = False
            teks = _PUTIH.sub(" ", "".join(self._buf)).strip()
            self._buf = []
            if len(teks) >= 60 and not BOILERPLATE.search(teks):
                self.paragraf.append(teks)

    def handle_data(self, data: str) -> None:
        if self._dalam_p and not self._skip:
            self._buf.append(data)


def ekstrak_isi(html: str, maks_karakter: int = 4000) -> str:
    """Ekstrak teks utama dari HTML halaman artikel."""
    eks = _Ekstraktor()
    try:
        eks.feed(html)
    except Exception as exc:  # HTML rusak: pakai yang terkumpul
        log.debug("parse HTML gagal parsial: %s", exc)
    teks = "\n\n".join(eks.paragraf)
    return teks[:maks_karakter].strip()


def unduh_isi(
    url: str,
    timeout_detik: int = 20,
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0 Safari/537.36",
) -> str:
    """Unduh + ekstrak isi artikel. Gagal -> "" (best-effort)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=timeout_detik) as resp:
            if resp.status != 200:
                return ""
            charset = resp.headers.get_content_charset() or "utf-8"
            mentah = resp.read(2_000_000).decode(charset, errors="replace")
    except Exception as exc:
        log.debug("unduh %s gagal: %s", url, exc)
        return ""
    return ekstrak_isi(mentah)


def siklus_unduh_isi(
    db_path,
    limit: int = 150,
    delay_detik: float = 1.0,
    timeout_detik: int = 20,
    force: bool = False,
    hanya_tampil: bool = True,
    tampil_per_media: int = 10,
) -> dict[str, int]:
    """Unduh isi artikel yang belum punya. Kembalikan statistik.

    Best-effort: satu artikel gagal tidak menghentikan yang lain.
    Artikel yang gagal unduh ditandai "" agar tidak diulang tiap siklus
    (kecuali force=True).

    hanya_tampil=True: prioritaskan artikel tampil di dashboard.
    """
    import time

    from src.storage import repository

    repository.migrate_isi_lengkap(db_path)
    if force:
        urls = [r["url"] for r in _semua_url(db_path, limit)]
    else:
        urls = repository.artikel_tanpa_isi(
            db_path, limit, hanya_tampil=hanya_tampil,
            tampil_per_media=tampil_per_media)
    ok = gagal = 0
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(delay_detik)  # sopan ke server media
        isi = unduh_isi(url, timeout_detik=timeout_detik)
        repository.simpan_isi(db_path, url, isi)
        if isi:
            ok += 1
        else:
            gagal += 1
    log.info("unduh isi: %d ok, %d gagal dari %d", ok, gagal, len(urls))
    return {"total": len(urls), "ok": ok, "gagal": gagal}


def _semua_url(db_path, limit: int) -> list[dict]:
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(
            "SELECT url FROM articles ORDER BY published_at DESC, id DESC"
            " LIMIT ?", (limit,)))
    finally:
        conn.close()
