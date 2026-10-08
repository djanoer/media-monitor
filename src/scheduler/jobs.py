"""Siklus fetch + penjadwalan.

fetch_cycle() adalah logika murni satu putaran fetch: bisa dipanggil oleh
APScheduler in-process maupun lewat cron (via run_scheduler.py --once).
Satu media gagal tidak menggagalkan seluruh siklus.
"""

from __future__ import annotations

import logging
import time

from apscheduler.schedulers.blocking import BlockingScheduler

from src.common.config import load_media, load_settings
from src.common.http_client import HttpClient
from src.ingestion.artikel import siklus_unduh_isi
from src.ingestion.fetcher import fetch_media
from src.processing.analisa import siklus_analisa
from src.storage import repository

log = logging.getLogger("media_monitor")


def fetch_cycle(
    settings: dict | None = None,
    media_list: list[dict] | None = None,
) -> dict[str, dict]:
    """Satu putaran fetch semua media aktif. Kembalikan ringkasan per media."""
    settings = settings or load_settings()
    media_list = media_list if media_list is not None else load_media()

    fetch_cfg = settings.get("fetch", {})
    db_path = settings["storage"]["db_path"]
    delay = fetch_cfg.get("delay_between_media_seconds", 3)
    max_items = fetch_cfg.get("max_articles_per_media")

    repository.init_db(db_path)
    client = HttpClient(
        user_agent=fetch_cfg.get("user_agent", "MediaMonitor/0.1"),
        timeout_seconds=fetch_cfg.get("timeout_seconds", 20),
    )

    run_id = repository.start_run(db_path)
    summary: dict[str, dict] = {}
    try:
        for i, media in enumerate(media_list):
            name = media["name"]
            if i > 0:
                time.sleep(delay)  # jeda antar media, hindari rate-limit
            try:
                articles = fetch_media(media, client, max_items=max_items)
                new_count = repository.insert_articles(db_path, articles)
                status, error = "ok", None
            except Exception as exc:
                articles, new_count = [], 0
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                log.warning("fetch %s gagal: %s", name, error)
            repository.log_media(
                db_path, run_id, name, status, new_count, len(articles), error
            )
            summary[name] = {
                "status": status,
                "new": new_count,
                "total": len(articles),
                "error": error,
            }
            log.info(
                "media=%s status=%s baru=%d total=%d",
                name, status, new_count, len(articles),
            )
    finally:
        repository.finish_run(db_path, run_id)
    # Pengayaan best-effort: unduh isi artikel yang belum punya, agar
    # ringkasan di dashboard bukan sekadar judul (Fase H). Gagal di sini
    # tidak menggagalkan siklus fetch.
    try:
        cfg_isi = settings.get("unduh_isi", {})
        if cfg_isi.get("aktif", True):
            siklus_unduh_isi(
                db_path,
                limit=int(cfg_isi.get("limit_per_siklus", 150)),
                delay_detik=float(cfg_isi.get("delay_detik", 1.0)),
                timeout_detik=int(cfg_isi.get("timeout_detik", 20)),
                hanya_tampil=cfg_isi.get("hanya_tampil", True),
                tampil_per_media=int(cfg_isi.get("tampil_per_media", 10)),
            )
    except Exception as exc:
        log.warning("unduh isi artikel gagal: %s", exc)
    # Analisa sentimen + risiko otomatis (Fase F -> full otomatis).
    # Komputasi lokal murni (tanpa API/kuota); best-effort seperti unduh isi.
    try:
        cfg_analisa = settings.get("analisa", {})
        if cfg_analisa.get("otomatis", True):
            hasil = siklus_analisa(
                db_path, settings,
                limit=int(cfg_analisa.get("limit_per_siklus", 500)),
            )
            if hasil["n"]:
                log.info("analisa otomatis: %d artikel, risiko=%s",
                         hasil["n"], hasil["risiko"])
    except Exception as exc:
        log.warning("analisa otomatis gagal: %s", exc)
    return summary


def start_scheduler() -> None:
    """Jalankan scheduler APScheduler in-process: fetch tiap interval jam."""
    settings = load_settings()
    interval = settings["fetch"].get("interval_hours", 1)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        fetch_cycle,
        "interval",
        hours=interval,
        id="fetch_cycle",
        coalesce=True,       # siklus tertinggal digabung, tidak menumpuk
        max_instances=1,     # tidak ada dua siklus berjalan bersamaan
        misfire_grace_time=600,
    )
    log.info("scheduler mulai: fetch tiap %d jam", interval)
    try:
        fetch_cycle(settings)  # satu siklus langsung saat start
    except Exception as exc:  # fetch awal gagal != scheduler mati
        log.warning("fetch awal gagal, scheduler tetap jalan: %s", exc)
    scheduler.start()
