"""Ekstraksi klaim + dedup semantik (Fase B).

Jalankan dari root proyek (venv aktif):
    python scripts/ekstrak_klaim.py [--topik karhutla] [--threshold 0.80]

Alur:
1. Ambil artikel topik dari korpus (matcher Fase A, read-only).
2. Ekstrak klaim per artikel (judul + kalimat kunci berangka).
3. Encode klaim dengan embedding (sentence-transformers; unduh model
   sekali di run pertama, butuh koneksi internet).
4. Kelompokkan klaim sejenis (union-find, cosine >= threshold).
5. Simpan klaim + cluster ke DB, cetak laporan.

Idempoten: klaim yang sudah ada dilewati (UNIQUE article_url+claim_text).
Cluster baru dibuat tiap run; cluster lama tidak dihapus (audit trail).
"""

from __future__ import annotations

import argparse
import datetime
import sys

sys.path.insert(0, ".")

from src.common.config import load_settings, load_topics
from src.processing.claim_clustering import encode_claims, group_similar
from src.processing.claim_extraction import extract_claims
from src.processing.topic_matcher import match_topic, teks_artikel
from src.storage import repository


def _sejak_iso(hari: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=hari)
    ).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Ekstraksi klaim + cluster (Fase B).")
    ap.add_argument("--topik", default="karhutla")
    ap.add_argument("--threshold", type=float, default=None,
                    help="override verification.similarity_threshold")
    ap.add_argument("--hari", type=int, default=None,
                    help="jendela hari (default: retention_days)")
    ap.add_argument("--reset", action="store_true",
                    help="hapus SEMUA klaim+cluster dulu (run ulang bersih)")
    args = ap.parse_args()

    topics = load_topics()
    if args.topik not in topics:
        print(f"Topik '{args.topik}' tidak ada di config/topics.yaml")
        return 2
    spec = topics[args.topik]

    settings = load_settings()
    ver = settings.get("verification", {})
    threshold = args.threshold if args.threshold is not None else ver.get(
        "similarity_threshold", 0.80)
    max_sent = ver.get("claim_max_sentences", 3)
    min_len = ver.get("claim_min_length", 20)
    hari = args.hari or settings["retention"]["retention_days"]
    db_path = settings["storage"]["db_path"]
    model_name = settings["clustering"]["embedding_model"]

    repository.init_db(db_path)
    if args.reset:
        n_klaim, n_cluster = repository.reset_claims(db_path)
        print(f"RESET: {n_klaim} klaim + {n_cluster} cluster dihapus.")
    artikel = repository.get_articles_since(db_path, _sejak_iso(hari))
    cocok = [a for a in artikel if match_topic(teks_artikel(a), spec)]
    print(f"Artikel topik '{args.topik}': {len(cocok)} dari {len(artikel)}")

    # 1-2. Ekstrak klaim
    semua: list[dict] = []
    for a in cocok:
        for k in extract_claims(a, max_sentences=max_sent, min_length=min_len):
            semua.append({
                "article_url": a["url"],
                "media": a["media"],
                "claim_text": k["claim_text"],
                "claim_type": k["claim_type"],
                "published_at": a.get("published_at"),
            })
    if not semua:
        print("Tidak ada klaim terekstrak. Berhenti.")
        return 0
    ids = repository.insert_claims(db_path, semua)
    print(f"Klaim terekstrak: {len(semua)} ({len(set(ids))} unik di DB)")

    # 3. Embedding (hanya klaim unik yang baru diproses di run ini disederhanakan:
    #    encode semua klaim unik agar cluster konsisten)
    teks_unik: list[str] = []
    id_unik: list[int] = []
    terlihat = set()
    for cid, k in zip(ids, semua):
        if k["claim_text"] not in terlihat:
            terlihat.add(k["claim_text"])
            teks_unik.append(k["claim_text"])
            id_unik.append(cid)
    print(f"Encode {len(teks_unik)} klaim unik ({model_name})...")
    try:
        embeddings = encode_claims(teks_unik, model_name)
    except ImportError:
        print("ERROR: sentence-transformers belum terinstal di venv ini.")
        return 3

    # 4-5. Cluster + simpan, lalu cetak dari DB (sumber kebenaran)
    groups_idx = group_similar(embeddings, threshold=threshold)
    groups = [[id_unik[i] for i in g] for g in groups_idx]
    cids = repository.save_clusters(db_path, groups)
    print(f"\n=== {len(cids)} cluster (threshold {threshold}) ===")
    for cl in repository.get_clusters(db_path)[-len(cids):]:
        print(f"\n-- cluster #{cl['id']} ({cl['size']} klaim) --")
        for k in cl["claims"][:6]:
            print(f"   [{k['media']}] ({k['claim_type']}) "
                  f"{k['claim_text'][:100]}")
    print("\nSelesai. Cluster lama tidak dihapus (audit trail).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
