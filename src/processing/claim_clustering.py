"""Pengelompokan klaim dengan embedding + union-find.

Klaim dengan cosine similarity >= threshold dianggap "klaim yang sama
dilaporkan media berbeda" -> satu cluster (sinyal koroborasi).

Desain:
- encode_claims(): satu-satunya tempat memuat sentence-transformers.
  Model dan prefix terpusat di sini agar konsisten.
- group_similar(): murni Python (tanpa numpy/torch) supaya bisa diuji
  dengan embedding palsu tanpa mengunduh model.
"""

from __future__ import annotations

import math


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def group_similar(
    embeddings: list[list[float]], threshold: float = 0.80
) -> list[list[int]]:
    """Kelompokkan indeks embedding yang saling mirip (union-find).

    Kembalikan daftar cluster, tiap cluster = daftar indeks.
    Urut dari cluster terbesar; indeks di dalam cluster urut menaik.
    """
    n = len(embeddings)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(embeddings[i], embeddings[j]) >= threshold:
                union(i, j)

    kelompok: dict[int, list[int]] = {}
    for i in range(n):
        kelompok.setdefault(find(i), []).append(i)
    hasil = sorted(kelompok.values(), key=len, reverse=True)
    return hasil


def encode_claims(
    texts: list[str], model_name: str
) -> list[list[float]]:
    """Encode teks klaim jadi embedding (butuh sentence-transformers).

    Import dilakukan di dalam fungsi agar modul tetap bisa diimpor
    (dan diuji) di lingkungan tanpa torch.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    # e5: tugas simetris -> prefix sama untuk semua teks.
    vecs = model.encode(
        [f"passage: {t}" for t in texts], normalize_embeddings=True
    )
    return [list(map(float, v)) for v in vecs]
