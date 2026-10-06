"""Respon publik per topik: YouTube + Google Trends (Fase D, pilot karhutla).

Jalankan dari root proyek (venv aktif):
    python scripts/respon_publik.py [--topik karhutla]
    python scripts/respon_publik.py --auto     # topik hangat otomatis (Fase I)

Mode --auto: ambil topik manual dari config + N topik terhangat dari judul
artikel 24 jam terakhir, lalu proses satu per satu dengan jeda antar query
Trends + backoff eksponensial bila kena rate-limit (429).

Dijalankan MANUAL dari laptop Bor: double-click respon-publik.bat
(tidak ada scheduler otomatis).

Butuh YOUTUBE_API_KEY di environment untuk bagian YouTube; tanpa itu
bagian YouTube dilewati dan Trends tetap jalan. Butuh pytrends:
    pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from src.common.config import load_settings, load_topics
from src.common import lock as lock_proses
from src.processing import respon_publik, topik_hangat
from src.storage import repository


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}jt"
    if n >= 1_000:
        return f"{n / 1_000:.1f}rb"
    return str(n)


def _ambil_trends_aman(keywords: list[str], rp: dict) -> dict:
    """Ambil Trends dengan retry + backoff bila kena rate-limit.

    ImportError (pytrends belum instal) langsung diteruskan; error lain yang
    bukan rate-limit juga diteruskan tanpa retry.
    """
    maks = rp.get("trends_maks_coba", 3)
    for coba in range(maks):
        try:
            return respon_publik.ambil_trends(
                keywords,
                geo=rp.get("trends_geo", "ID"),
                timeframe=rp.get("trends_timeframe", "today 1-m"),
                jeda_detik=rp.get("trends_jeda_antar_request", 3),
            )
        except ImportError:
            raise
        except Exception as e:
            if (topik_hangat.kena_rate_limit(str(e))
                    and coba < maks - 1):
                tunggu = topik_hangat.hitung_tunggu_429(coba)
                print(f"  Trends kena rate-limit -> tunggu {tunggu}s"
                      f" (coba {coba + 1}/{maks})...")
                time.sleep(tunggu)
            else:
                raise
    raise RuntimeError("Trends gagal setelah retry")  # pragma: no cover


def _proses_topik(
    db_path: str, rp: dict, api_key: str, topik: str, keywords: list[str]
) -> None:
    """Proses satu topik: YouTube lalu Trends, simpan ke DB."""
    print(f"--- topik: {topik} ---")

    # --- YouTube ---
    if not api_key:
        print("YouTube: YOUTUBE_API_KEY tidak diset -> dilewati.")
    else:
        try:
            videos = respon_publik.cari_video_youtube(
                api_key, topik,
                max_results=rp.get("youtube_max_videos", 20),
                region_code=rp.get("youtube_region", "ID"),
            )
        except Exception as e:  # key salah / kuota habis -> lapor, lanjut Trends
            print(f"YouTube: gagal ({e}) -> dilewati.")
            videos = []
        if videos:
            repository.simpan_video_youtube(db_path, topik, videos)
            tot = respon_publik.total_statistik(videos)
            print(f"YouTube ({tot['n_video']} video teratas): "
                  f"{_fmt(tot['total_views'])} views, "
                  f"{_fmt(tot['total_komentar'])} komentar, "
                  f"{_fmt(tot['total_likes'])} likes")

    # --- Google Trends ---
    try:
        tren = _ambil_trends_aman(keywords, rp)
    except ImportError:
        print("Google Trends: pytrends belum terinstal.")
        print("  pip install -r requirements.txt")
        return
    except Exception as e:
        print(f"Google Trends: gagal ({e}) -> topik ini dilewati.")
        return

    n_baris = repository.simpan_trends_harian(db_path, topik, tren)
    repository.simpan_trends_ringkas(db_path, topik, tren)
    ring = respon_publik.ringkasan_trends(tren)
    print(f"Google Trends ({n_baris} baris, keyword: {', '.join(keywords)}):"
          f" minat rata-rata '{ring['keyword_utama']}':"
          f" {ring['minat_rata2']}/100")
    if ring["daerah_teratas"]:
        d = ", ".join(f"{x['daerah']} ({x['skor']})"
                      for x in ring["daerah_teratas"])
        print(f"  daerah teratas: {d}")
    if ring["frasa_naik"]:
        print(f"  frasa naik: {', '.join(ring['frasa_naik'])}")
    print()


def _topik_otomatis(db_path: str, rp: dict) -> list[str]:
    """Topik manual config + N terhangat dari 24 jam terakhir."""
    sejak = (datetime.now(timezone.utc)
             - timedelta(hours=24)).isoformat()
    arts = repository.get_articles_since(db_path, sejak)
    jm = [(a["title"], a["media"]) for a in arts if a.get("title")]
    n_minta = rp.get("topik_otomatis", 5)
    otomatis = topik_hangat.ekstrak_topik(jm, n=n_minta)
    if len(otomatis) < n_minta:
        # Fallback: data 24 jam sepi -> turunkan ambang artikel agar slot
        # terisi; syarat lintas-media tetap dijaga (anti obsesi 1 redaksi).
        otomatis = topik_hangat.ekstrak_topik(
            jm, n=n_minta, min_artikel=2, min_media=2)
    manual = rp.get("topik_manual", [])
    hasil = topik_hangat.gabung_topik(
        manual, otomatis, maks=rp.get("topik_maks_total", 5))
    print(f"Topik otomatis dari {len(jm)} judul 24 jam terakhir:")
    for o in otomatis:
        print(f"  - {o['topik']} ({o['n_artikel']} artikel,"
              f" {o['n_media']} media)")
    return hasil


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topik", default="karhutla",
                    help="topik terdaftar di config/topics.yaml")
    ap.add_argument("--auto", action="store_true",
                    help="topik hangat otomatis + topik manual config")
    args = ap.parse_args()

    settings = load_settings()
    rp = settings.get("respon_publik", {})

    # Satu sync saja: dua --auto bareng = dobel kuota YT + rawan 429 Trends.
    if not lock_proses.minta("respon-publik"):
        print("Sync respons publik sudah berjalan di proses lain. Batal.")
        return 1

    db_path = settings["storage"]["db_path"]
    repository.init_db(db_path)
    api_key = os.environ.get(rp.get("youtube_api_key_env", "YOUTUBE_API_KEY"), "")

    if args.auto:
        daftar = _topik_otomatis(db_path, rp)
        # keyword per topik: topik manual pakai registry, otomatis pakai
        # namanya sendiri sebagai satu keyword Trends.
        topics = load_topics()
    else:
        topics = load_topics()
        if args.topik not in topics:
            print(f"Topik '{args.topik}' tidak dikenal: {list(topics)}")
            return 1
        daftar = [args.topik]

    print(f"=== Respon publik ({len(daftar)} topik) ===\n")
    jeda = rp.get("trends_jeda_detik", 12)
    for i, topik in enumerate(daftar):
        spec = topics.get(topik)
        if spec:
            keywords = spec["high_precision"][: rp.get("trends_keywords", 3)]
        else:
            keywords = [topik]
        _proses_topik(db_path, rp, api_key, topik, keywords)
        if i < len(daftar) - 1 and jeda > 0:
            print(f"  jeda {jeda}s sebelum topik berikutnya...\n")
            time.sleep(jeda)

    print("Selesai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
