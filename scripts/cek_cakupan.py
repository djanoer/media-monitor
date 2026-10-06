"""Cek cakupan topik di korpus (Fase A).

Jalankan dari root proyek di laptop (DB ada di data/media_monitor.db):
    python scripts/cek_cakupan.py [nama_topik]

Read-only: tidak menulis apa pun ke DB. Keluarkan laporan:
total artikel di jendela retensi, hit topik, hit per media, tren harian,
sampel judul untuk spot check presisi manual, dan verdict GO/NO-GO Fase B.

Kriteria GO (Fase A, topik karhutla): >=30 artikel dan >=5 media meliput
dalam 30 hari terakhir. Angka ini bisa diubah via argumen --min-artikel
dan --min-media.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import random
import sys

sys.path.insert(0, ".")

from src.common.config import load_settings, load_topics
from src.processing.topic_matcher import match_topic, teks_artikel
from src.storage import repository


def _sejak_iso(hari: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=hari)
    ).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Cek cakupan topik di korpus.")
    ap.add_argument("topik", nargs="?", default="karhutla")
    ap.add_argument("--min-artikel", type=int, default=30)
    ap.add_argument("--min-media", type=int, default=5)
    ap.add_argument("--sampel", type=int, default=20,
                    help="jumlah judul sampel untuk spot check manual")
    args = ap.parse_args()

    topics = load_topics()
    if args.topik not in topics:
        print(f"Topik '{args.topik}' tidak ada di config/topics.yaml: "
              f"{sorted(topics)}")
        return 2
    spec = topics[args.topik]

    settings = load_settings()
    db_path = settings["storage"]["db_path"]
    hari = settings["retention"]["retention_days"]

    repository.init_db(db_path)  # aman: hanya buat tabel bila belum ada
    artikel = repository.get_articles_since(db_path, _sejak_iso(hari))
    cocok = [a for a in artikel if match_topic(teks_artikel(a), spec)]

    per_media = collections.Counter(a["media"] for a in cocok)
    per_hari = collections.Counter(
        (a.get("published_at") or "?")[:10] for a in cocok
    )

    print(f"=== Cakupan topik '{args.topik}' ({hari} hari terakhir) ===")
    print(f"Total artikel di korpus : {len(artikel)}")
    print(f"Hit topik               : {len(cocok)}")
    print(f"Media meliput           : {len(per_media)}")
    print("\n-- per media --")
    for media, n in per_media.most_common():
        print(f"  {media:20s} {n}")
    print("\n-- 14 hari terakhir --")
    for tgl in sorted(per_hari)[-14:]:
        print(f"  {tgl}  {per_hari[tgl]}")

    print(f"\n-- sampel {args.sampel} judul untuk spot check manual --")
    for a in random.sample(cocok, min(args.sampel, len(cocok))):
        print(f"  [{a['media']}] {a['title']}")

    go_artikel = len(cocok) >= args.min_artikel
    go_media = len(per_media) >= args.min_media
    print("\n=== VERDICT ===")
    print(f"Artikel >= {args.min_artikel}: {'YA' if go_artikel else 'TIDAK'}")
    print(f"Media   >= {args.min_media}: {'YA' if go_media else 'TIDAK'}")
    if go_artikel and go_media:
        print("GO Fase B. Spot check manual tetap wajib sebelum lanjut.")
        return 0
    print("NO-GO: korpus kurang. Opsi: tambah media daerah "
          "(mis. Tribun Pekanbaru, Antara Riau) atau perlebar keyword.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
