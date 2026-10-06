"""Respon publik per topik: YouTube + Google Trends (Fase D, pilot karhutla).

Jalankan dari root proyek (venv aktif):
    python scripts/respon_publik.py [--topik karhutla]

Butuh YOUTUBE_API_KEY di environment untuk bagian YouTube; tanpa itu
bagian YouTube dilewati dan Trends tetap jalan. Butuh pytrends:
    pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, ".")

from src.common.config import load_settings, load_topics
from src.processing import respon_publik
from src.storage import repository


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}jt"
    if n >= 1_000:
        return f"{n / 1_000:.1f}rb"
    return str(n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topik", default="karhutla")
    args = ap.parse_args()

    settings = load_settings()
    rp = settings.get("respon_publik", {})
    db_path = settings["storage"]["db_path"]
    topics = load_topics()
    if args.topik not in topics:
        print(f"Topik '{args.topik}' tidak dikenal: {list(topics)}")
        return 1
    spec = topics[args.topik]
    keywords = spec["high_precision"][: rp.get("trends_keywords", 3)]

    repository.init_db(db_path)
    print(f"=== Respon publik: {args.topik} ===\n")

    # --- YouTube ---
    api_key = os.environ.get(rp.get("youtube_api_key_env", "YOUTUBE_API_KEY"), "")
    if not api_key:
        print("YouTube: YOUTUBE_API_KEY tidak diset -> dilewati.\n")
    else:
        try:
            videos = respon_publik.cari_video_youtube(
                api_key, args.topik,
                max_results=rp.get("youtube_max_videos", 20),
                region_code=rp.get("youtube_region", "ID"),
            )
        except Exception as e:  # key salah / kuota habis -> lapor, lanjut Trends
            print(f"YouTube: gagal ({e}) -> dilewati.\n")
            videos = []
        if videos:
            repository.simpan_video_youtube(db_path, args.topik, videos)
            tot = respon_publik.total_statistik(videos)
            print(f"YouTube ({tot['n_video']} video teratas): "
                  f"{_fmt(tot['total_views'])} views, "
                  f"{_fmt(tot['total_komentar'])} komentar, "
                  f"{_fmt(tot['total_likes'])} likes")
            for i, v in enumerate(respon_publik.video_teratas(videos), 1):
                print(f"  {i}. [{_fmt(v['view_count'])} views]"
                      f" {v['title'][:80]} - {v['channel']}")
            print()

    # --- Google Trends ---
    try:
        tren = respon_publik.ambil_trends(
            keywords,
            geo=rp.get("trends_geo", "ID"),
            timeframe=rp.get("trends_timeframe", "today 1-m"),
        )
    except ImportError:
        print("Google Trends: pytrends belum terinstal.")
        print("  pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"Google Trends: gagal ({e}).")
        return 1

    n_baris = repository.simpan_trends_harian(db_path, args.topik, tren)
    repository.simpan_trends_ringkas(db_path, args.topik, tren)
    ring = respon_publik.ringkasan_trends(tren)
    print(f"Google Trends ({n_baris} baris tersimpan,"
          f" keyword: {', '.join(keywords)}):")
    print(f"  minat rata-rata '{ring['keyword_utama']}':"
          f" {ring['minat_rata2']}/100")
    if ring["puncak"]:
        print(f"  puncak: {ring['puncak']['tanggal']}"
              f" (skor {ring['puncak']['skor']})")
    if ring["daerah_teratas"]:
        d = ", ".join(f"{x['daerah']} ({x['skor']})"
                       for x in ring["daerah_teratas"])
        print(f"  daerah teratas: {d}")
    if ring["frasa_naik"]:
        print(f"  frasa naik: {', '.join(ring['frasa_naik'])}")
    print("\nSelesai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
