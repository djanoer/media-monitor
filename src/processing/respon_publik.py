"""Respon publik per topik: YouTube Data API + Google Trends (Fase D).

Pilot: karhutla. Hasil disimpan ke DB (youtube_videos, trends_harian,
trends_ringkas) untuk dipakai halaman "Respon Publik" di Fase E.

YouTube butuh YOUTUBE_API_KEY di environment (jangan taruh di config/repo).
Tanpa key -> cari_video_youtube() raise ValueError; skrip melewati bagian
YouTube dan tetap menjalankan Trends (tidak butuh key).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

YT_API = "https://www.googleapis.com/youtube/v3"


def _yt_get(api_key: str, path: str, params: dict) -> dict:
    q = dict(params)
    q["key"] = api_key
    url = f"{YT_API}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"YouTube API error {e.code}: {body[:200]}") from e


def cari_video_youtube(
    api_key: str,
    query: str,
    max_results: int = 20,
    region_code: str = "ID",
) -> list[dict]:
    """Cari video teratas + statistiknya. Urut viewCount (paling ditonton)."""
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY kosong")
    s = _yt_get(api_key, "/search", {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max_results, 50),
        "regionCode": region_code,
        "order": "viewCount",
    })
    ids = [
        it["id"]["videoId"]
        for it in s.get("items", [])
        if it.get("id", {}).get("videoId")
    ]
    if not ids:
        return []
    v = _yt_get(api_key, "/videos", {
        "part": "snippet,statistics",
        "id": ",".join(ids),
    })
    hasil = []
    for it in v.get("items", []):
        sn, st = it.get("snippet", {}), it.get("statistics", {})
        hasil.append({
            "video_id": it["id"],
            "title": sn.get("title", ""),
            "channel": sn.get("channelTitle", ""),
            "published_at": sn.get("publishedAt"),
            "view_count": int(st.get("viewCount", 0) or 0),
            "like_count": int(st.get("likeCount", 0) or 0),
            "comment_count": int(st.get("commentCount", 0) or 0),
        })
    return hasil


def video_teratas(videos: list[dict], n: int = 5) -> list[dict]:
    """N video dengan views terbanyak."""
    return sorted(videos, key=lambda v: v.get("view_count", 0),
                  reverse=True)[:n]


def total_statistik(videos: list[dict]) -> dict:
    """Agregat KPI untuk laporan."""
    return {
        "n_video": len(videos),
        "total_views": sum(v.get("view_count", 0) for v in videos),
        "total_komentar": sum(v.get("comment_count", 0) for v in videos),
        "total_likes": sum(v.get("like_count", 0) for v in videos),
    }


def ambil_trends(
    keywords: list[str],
    geo: str = "ID",
    timeframe: str = "today 1-m",
) -> dict:
    """Ambil Google Trends: minat harian, per daerah, frasa terkait.

    Lazy import pytrends supaya test/unit tidak butuh instalasinya.
    tz=480 -> WITA (UTC+8).
    """
    from pytrends.request import TrendReq

    pt = TrendReq(hl="id", tz=480)
    pt.build_payload(keywords, geo=geo, timeframe=timeframe)

    minat = pt.interest_over_time()
    minat_harian = []
    if not minat.empty:
        for idx, row in minat.iterrows():
            rec = {"tanggal": idx.strftime("%Y-%m-%d")}
            for kw in keywords:
                try:
                    rec[kw] = int(row[kw])
                except (KeyError, TypeError, ValueError):
                    rec[kw] = 0
            minat_harian.append(rec)

    daerah = pt.interest_by_region(resolution="COUNTRY", inc_low_vol=True)
    per_daerah = []
    if not daerah.empty:
        df = daerah.reset_index()
        for _, row in df.iterrows():
            rec = {"daerah": str(row["geoName"])}
            for kw in keywords:
                try:
                    rec[kw] = int(row[kw])
                except (KeyError, TypeError, ValueError):
                    rec[kw] = 0
            per_daerah.append(rec)
        per_daerah.sort(key=lambda r: r.get(keywords[0], 0), reverse=True)

    terkait_raw = pt.related_queries()
    terkait = {}
    for kw, v in terkait_raw.items():
        t = {}
        for arah in ("top", "rising"):
            df = (v or {}).get(arah)
            t[arah] = (
                df[["query", "value"]].to_dict(orient="records")
                if df is not None and not df.empty else []
            )
        terkait[kw] = t

    return {
        "keywords": keywords,
        "minat_harian": minat_harian,
        "per_daerah": per_daerah,
        "terkait": terkait,
    }


def ringkasan_trends(tren: dict) -> dict:
    """KPI ringkas dari hasil ambil_trends (pure, untuk laporan/UI)."""
    keywords = tren.get("keywords", [])
    utama = keywords[0] if keywords else None
    harian = tren.get("minat_harian", [])
    rata = (
        round(sum(r.get(utama, 0) for r in harian) / len(harian), 1)
        if harian and utama else 0.0
    )
    puncak = max(harian, key=lambda r: r.get(utama, 0), default=None)
    return {
        "keyword_utama": utama,
        "minat_rata2": rata,
        "puncak": (
            {"tanggal": puncak["tanggal"], "skor": puncak.get(utama, 0)}
            if puncak else None
        ),
        "daerah_teratas": [
            {"daerah": r["daerah"], "skor": r.get(utama, 0)}
            for r in tren.get("per_daerah", [])[:5]
        ],
        "frasa_naik": [
            q["query"]
            for q in (tren.get("terkait", {}).get(utama, {}).get("rising", [])[:5])
        ],
    }
