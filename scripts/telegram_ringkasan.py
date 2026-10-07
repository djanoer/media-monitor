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


def ambil_berita(limit: int = 10) -> list[dict]:
    """Ambil berita 24 jam terakhir: prioritaskan geopolitik & teknologi,
    lalu yang ada ringkasan AI."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # Keyword geopolitik & teknologi (ID + EN)
    kw_geo = ["geopolitik", "geopolitics", "diplomasi", "diplomacy", "konflik",
              "conflict", "perang", "war", "nato", "pbb", "un ", "asean",
              "tiongkok", "china", "amerika", "russia", "rusia", "ukraina",
              "ukraine", "timur tengah", "middle east", "taiwan", "korea",
              "nuklir", "nuclear", "sanksi", "sanction", "perbatasan", "border"]
    kw_tek = ["teknologi", "technology", "tech", "ai ", "kecerdasan buatan",
              "artificial intelligence", "startup", "digital", "siber", "cyber",
              "semikonduktor", "semiconductor", "chip", "5g", "satelit",
              "satellite", "roket", "rocket", "luar angkasa", "space",
              "robot", "drone", "quantum", "kuantum", "blockchain", "kripto",
              "crypto", "openai", "google", "microsoft", "apple", "nvidia",
              "tesla", "spacex", "gadget", "smartphone", "laptop", "internet"]
    semua_kw = kw_geo + kw_tek
    like_clause = " OR ".join(["(lower(title) LIKE ? OR lower(ringkasan_ai) LIKE ?)"] * len(semua_kw))
    params = []
    for kw in semua_kw:
        params += [f"%{kw}%", f"%{kw}%"]

    # Ambil yang match topik dulu
    rows = con.execute(f"""
        SELECT title, url, media, published_at, ringkasan_ai, sentimen, risiko
        FROM articles
        WHERE published_at >= datetime('now', '-24 hours')
          AND ({like_clause})
        ORDER BY
            CASE WHEN ringkasan_ai IS NOT NULL AND ringkasan_ai != '' THEN 0 ELSE 1 END,
            published_at DESC
        LIMIT ?
    """, (*params, limit)).fetchall()

    # Kalau kurang dari limit, tambah berita umum terbaru
    if len(rows) < limit:
        sisa = limit - len(rows)
        urls_ada = {r["url"] for r in rows}
        rows2 = con.execute("""
            SELECT title, url, media, published_at, ringkasan_ai, sentimen, risiko
            FROM articles
            WHERE published_at >= datetime('now', '-24 hours')
            ORDER BY published_at DESC
            LIMIT ?
        """, (sisa * 3,)).fetchall()
        for r in rows2:
            if r["url"] not in urls_ada and len(rows) < limit:
                rows.append(r)
                urls_ada.add(r["url"])

    con.close()
    return [dict(r) for r in rows]


def format_pesan(berita: list[dict]) -> str:
    """Format pesan elegan dengan judul klikable."""
    now = datetime.now(WIB)
    lines = [
        f"📰 <b>RINGKASAN BERITA</b>",
        f"📅 {tgl_id(now)} · Geopolitik & Teknologi",
        "",
    ]
    for i, b in enumerate(berita, 1):
        judul = esc_html(b["title"] or "(tanpa judul)")
        url = b["url"] or ""
        media = esc_html(b.get("media") or "")
        ringkasan = esc_html(b.get("ringkasan_ai") or "").strip()
        # Potong ringkasan agar tidak terlalu panjang
        if len(ringkasan) > 300:
            ringkasan = ringkasan[:297] + "..."

        # Format: Nama Media - Judul (klikable)
        lines.append(f"<b>{i}. {media} - <a href=\"{url}\">{judul}</a></b>")
        if ringkasan:
            lines.append(f"   {ringkasan}")
        lines.append(f"   🔗 <a href=\"{url}\">Baca selengkapnya</a>")
        lines.append("")
    lines.append("—")
    lines.append("🔗 <a href=\"https://djanoer.github.io/media-monitor/\">Dashboard lengkap</a>")
    lines.append("<i>Disusun otomatis oleh Media Monitor</i>")
    return "\n".join(lines)


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
    berita = ambil_berita(limit=5 if test else 10)
    if not berita:
        print("Tidak ada berita 24 jam terakhir")
        sys.exit(0)

    pesan = format_pesan(berita)
    if test:
        print("=== PREVIEW ===")
        print(pesan[:1500])
        print("===============")
    ok = kirim(token, chat_id, pesan)
    print("Terkirim" if ok else "GAGAL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
