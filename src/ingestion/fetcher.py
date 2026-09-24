"""Satu fetcher generik untuk semua media.

Perbedaan antar media (URL feed, native vs Google News) hanya dibaca dari
config/media.yaml. Tidak boleh ada percabangan khusus nama media di sini.
"""

from __future__ import annotations

import calendar
import time

import feedparser

from src.common.http_client import HttpClient


def _to_iso(entry: dict) -> str | None:
    """published_parsed feedparser -> string ISO UTC. Tidak ada tanggal -> None."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(calendar.timegm(parsed)))
    except (ValueError, OverflowError, OSError):
        return None


def normalize_entry(media_name: str, entry: dict, final_url: str) -> dict:
    """Seragamkan satu item feed menjadi dict artikel siap simpan."""
    return {
        "url": final_url,  # URL kanonis artikel; kunci dedup
        "media": media_name,
        "title": (entry.get("title") or "").strip(),
        "summary": (entry.get("summary") or entry.get("description") or "").strip(),
        "link": entry.get("link") or "",  # link mentah dari feed
        "published_at": _to_iso(entry),
    }


def fetch_media(
    media: dict,
    client: HttpClient,
    max_items: int | None = None,
) -> list[dict]:
    """Ambil satu feed, kembalikan daftar artikel ternormalisasi.

    - Feed diambil via HttpClient (retry, timeout, user-agent konsisten),
      lalu di-parse dari kontennya (feedparser tidak melakukan HTTP sendiri).
    - Untuk type 'gnews', link news.google.com di-resolve ke URL artikel asli.
    - Duplikat URL dalam satu batch hanya diambil sekali.
    - max_items membatasi item terbaru yang diproses (feed terurut terbaru dulu).
    """
    name = media["name"]
    resp = client.get(media["feed"])
    parsed = feedparser.parse(resp.content)
    if not parsed.entries:
        detail = parsed.bozo_exception if parsed.bozo else "tidak ada item"
        raise ValueError(f"feed {name} tidak menghasilkan item: {detail}")

    seen: dict[str, dict] = {}
    entries = parsed.entries[:max_items] if max_items else parsed.entries
    for entry in entries:
        raw_link = (entry.get("link") or "").strip()
        if not raw_link:
            continue
        if media.get("type") == "gnews":
            final_url = client.resolve_final_url(raw_link)
        else:
            final_url = raw_link
        if final_url in seen:
            continue
        seen[final_url] = normalize_entry(name, entry, final_url)
    return list(seen.values())
