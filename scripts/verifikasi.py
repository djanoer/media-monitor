"""Verifikasi cluster klaim (Fase C).

Jalankan dari root proyek (venv aktif), setelah ekstraksi klaim:
    python scripts/verifikasi.py

Untuk tiap cluster di DB:
1. Skor koroborasi dari tier media unik anggotanya.
2. Verdict: terkoroborasi / satu sumber kredibel / belum terverifikasi.
3. Flag headline bombastis per klaim anggota.

Hasil disimpan ke tabel claim_clusters. Idempoten: run ulang menimpa
hasil sebelumnya (computed_at dicatat).
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from src.common.config import load_media, load_settings
from src.processing.verification import (
    cek_headline,
    skor_koroborasi,
    verdict,
)
from src.storage import repository


def main() -> int:
    settings = load_settings()
    ver = settings.get("verification", {})
    db_path = settings["storage"]["db_path"]

    tier_per_media = {m["name"]: m.get("tier", 3) for m in load_media()}
    bobot = {int(k): float(v) for k, v in
             ver.get("tier_weights", {1: 1.0, 2: 0.7, 3: 0.4}).items()}
    ambang_kuat = ver.get("ambang_terkoroborasi", 80)
    ambang_cukup = ver.get("ambang_satu_sumber", 50)
    penanda = ver.get("penanda_bombastis", [])

    repository.init_db(db_path)
    tambah = repository.migrate_verifikasi(db_path)
    if tambah:
        print(f"Migrasi: kolom {tambah} ditambahkan ke claim_clusters.")

    clusters = repository.get_clusters(db_path)
    if not clusters:
        print("Belum ada cluster. Jalankan scripts/ekstrak_klaim.py dulu.")
        return 0

    # ringkasan per URL untuk cek headline-vs-isi
    import datetime
    sejak = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=settings["retention"]["retention_days"]))
    ringkasan_per_url = {
        a["url"]: (a.get("summary") or "")
        for a in repository.get_articles_since(db_path, sejak.isoformat())
    }

    print(f"Verifikasi {len(clusters)} cluster...\n")
    for cl in clusters:
        medias = [k["media"] for k in cl["claims"]]
        skor, rincian = skor_koroborasi(medias, tier_per_media, bobot)
        label = verdict(skor, ambang_kuat, ambang_cukup)
        semua_flag: set[str] = set()
        for k in cl["claims"]:
            semua_flag.update(cek_headline(
                k["claim_text"],
                ringkasan_per_url.get(k["article_url"], ""),
                penanda,
            ))
        repository.save_verifikasi(db_path, cl["id"], {
            "score": skor,
            "verdict": label,
            "tier_breakdown": json.dumps(rincian),
            "headline_flags": json.dumps(sorted(semua_flag)),
        })
        print(f"cluster #{cl['id']} ({cl['size']} klaim)"
              f" [{', '.join(sorted(set(medias)))}]")
        print(f"  skor {skor} -> {label}"
              + (f" | flag: {sorted(semua_flag)}" if semua_flag else ""))
        top = cl["claims"][0]["claim_text"]
        print(f"  cth: {top[:95]}")
    print("\nSelesai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
