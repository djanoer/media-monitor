#!/usr/bin/env python3
"""Kirim ringkasan berita harian via Telegram. 0 token Muse.

Dibaca dari DB media-monitor (ringkasan AI yang sudah ada).
Dijalankan dari pipeline atau manual:
    python scripts/telegram_ringkasan.py [--test]

Butuh di .env:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import os
import sqlite3
import sys
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "data", "media_monitor.db")

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
         "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def tgl_id(dt: datetime) -> str:
    return f"{dt.day} {BULAN[dt.month-1]} {dt.year}"


def esc_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ambil_berita(limit_geo: int = 3, limit_tek: int = 3) -> tuple[list[dict], list[dict]]:
    """Return (geopolitik, teknologi): masing-masing list dict artikel."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    kw_geo = ["geopolitik", "geopolitics", "diplomasi", "diplomacy", "konflik",
              "conflict", "perang", "war", "nato", "pbb", "asean",
              "tiongkok", "china", "amerika", "russia", "rusia", "ukraina",
              "ukraine", "timur tengah", "middle east", "taiwan", "korea",
              "nuklir", "nuclear", "sanksi", "sanction", "perbatasan", "border"]
    kw_tek = ["teknologi", "technology", "tech", "kecerdasan buatan",
              "artificial intelligence", "startup", "digital", "siber", "cyber",
              "semikonduktor", "semiconductor", "chip", "5g", "satelit",
              "satellite", "roket", "rocket", "luar angkasa", "space",
              "robot", "drone", "quantum", "kuantum", "blockchain", "kripto",
              "crypto", "openai", "google", "microsoft", "apple", "nvidia",
              "tesla", "spacex", "gadget", "smartphone", "internet"]

    def cari(kw_list: list[str], limit: int) -> list[dict]:
        like = " OR ".join(["(lower(title) LIKE ? OR lower(ringkasan_ai) LIKE ?)"] * len(kw_list))
        params = []
        for kw in kw_list:
            params += [f"%{kw}%", f"%{kw}%"]
        rows = con.execute(f"""
            SELECT title, url, media, published_at, ringkasan_ai, sentimen, risiko
            FROM articles
            WHERE published_at >= datetime('now', '-24 hours')
              AND ({like})
            ORDER BY
                CASE WHEN ringkasan_ai IS NOT NULL AND ringkasan_ai != '' THEN 0 ELSE 1 END,
                published_at DESC
            LIMIT ?
        """, (*params, limit)).fetchall()
        return [dict(r) for r in rows]

    geo = cari(kw_geo, limit_geo)
    tek = cari(kw_tek, limit_tek)
    con.close()
    return geo, tek


def format_pesan(geo: list[dict], tek: list[dict]) -> str:
    """Format: Header, Icon+Topik, 1-3, Icon+Topik, 1-3, Footer."""
    now = datetime.now(WIB)
    lines = [
        f"📰 <b>RINGKASAN BERITA</b>",
        f"📅 {tgl_id(now)}",
        "",
        f"🌍 <b>GEOPOLITIK</b>",
    ]
    lines += _format_seksi(geo)
    lines += ["", f"💻 <b>TEKNOLOGI</b>"]
    lines += _format_seksi(tek)
    lines.append("")
    lines.append("—")
    lines.append("")
    lines.append("🔗 <a href=\"https://djanoer.github.io/media-monitor/\">Media Monitor</a>")
    lines.append("")
    lines.append("<i>Disusun otomatis dari Media Monitor</i>")
    return "\n".join(lines)


def _format_seksi(berita: list[dict]) -> list[str]:
    out = [""]
    for i, b in enumerate(berita, 1):
        judul = esc_html(b["title"] or "(tanpa judul)")
        url = b["url"] or ""
        media = esc_html(b.get("media") or "")
        ringkasan = esc_html(b.get("ringkasan_ai") or "").strip()
        if len(ringkasan) > 300:
            ringkasan = ringkasan[:297] + "..."
        out.append(f"<b>{i}. {media} - <a href=\"{url}\">{judul}</a></b>")
        if ringkasan:
            out.append(f"   {ringkasan}")
        out.append(f"   🔗 <a href=\"{url}\">Baca selengkapnya</a>")
        out.append("")
    return out


def kirim(token: str, chat_id: str, teks: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": teks,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}", file=sys.stderr)
        return False


def main():
    # Muat .env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    envf = os.path.join(root, ".env")
    if os.path.exists(envf):
        for line in open(envf):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset", file=sys.stderr)
        sys.exit(1)

    test = "--test" in sys.argv
    if test:
        geo, tek = ambil_berita(limit_geo=2, limit_tek=2)
    else:
        geo, tek = ambil_berita(limit_geo=3, limit_tek=3)
    if not geo and not tek:
        print("Tidak ada berita 24 jam terakhir")
        sys.exit(0)

    pesan = format_pesan(geo, tek)
    if test:
        print("=== PREVIEW ===")
        print(pesan[:1500])
        print("===============")
    ok = kirim(token, chat_id, pesan)
    print("Terkirim" if ok else "GAGAL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
