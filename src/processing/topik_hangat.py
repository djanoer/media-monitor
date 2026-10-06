"""Topik hangat otomatis dari judul artikel 24 jam terakhir (Fase I).

Dipakai scripts/respon_publik.py --auto: topik terhangat menjadi query
YouTube + Google Trends tanpa intervensi manual.

Murni (pure functions) supaya gampang di-test; tanpa dependensi UI.
"""

from __future__ import annotations

import re

# Kata pengisi khas judul berita Indonesia — dibuang agar topik bermakna.
STOPWORDS_ID = frozenset(
    """
    yang dan di ke dari untuk dengan pada adalah ini itu sebagai dalam oleh
    atau juga tidak tak akan telah sudah saat agar karena namun tapi serta
    para sang sebuah seorang antara atas bawah depan belakang samping tengah
    sekitar hampir sangat lebih paling kurang bisa dapat harus wajib perlu
    ingin mau jadi menjadi ada ialah yaitu yakni jika kalau bila meski
    walaupun meskipun sedangkan sementara lalu kemudian kini kembali lagi
    pun saja hanya cuma bahwa berapa bagaimana kapan dimana kemana mengapa
    kenapa apa siapa tersebut the of in to a an vs via
    resmi baru viral heboh bikin ungkap minta kata ujar tegas sebut klaim
    soal terkait usai pasca jelang simak cek catat profil fakta kronologi
    bocoran sorotan potret momen detik detikcom
    com net org co id www http https html htm
    """.split()
)

_KATA = re.compile(r"[a-z0-9]+")


def _kata_bermakna(judul: str) -> list[str]:
    """Tokenisasi judul -> kata bermakna (lowercase, >=3 huruf, bukan stopword)."""
    return [
        w for w in _KATA.findall(judul.lower())
        if len(w) >= 3 and w not in STOPWORDS_ID
    ]


def ekstrak_topik(
    judul_media: list[tuple[str, str]],
    n: int = 3,
    min_artikel: int = 3,
    min_media: int = 2,
) -> list[dict]:
    """Ekstrak N topik terhangat dari daftar (judul, media).

    Kandidat = bigram kata bermakna yang muncul di >= min_artikel judul
    dari >= min_media media berbeda (sinyal lintas-media, bukan obsesi
    satu redaksi). Unigram hanya jadi cadangan bila bigram kurang.

    Kembalikan [{"topik", "n_artikel", "n_media"}], urut skor tertinggi.
    """
    bigram: dict[str, set[int]] = {}
    bigram_media: dict[str, set[str]] = {}
    unigram: dict[str, set[int]] = {}
    unigram_media: dict[str, set[str]] = {}

    for i, (judul, media) in enumerate(judul_media):
        kata = _kata_bermakna(judul)
        for w in set(kata):
            unigram.setdefault(w, set()).add(i)
            unigram_media.setdefault(w, set()).add(media)
        for a, b in zip(kata, kata[1:]):
            bg = f"{a} {b}"
            bigram.setdefault(bg, set()).add(i)
            bigram_media.setdefault(bg, set()).add(media)

    kandidat: list[tuple[float, dict]] = []
    for bg, idxs in bigram.items():
        n_art, n_med = len(idxs), len(bigram_media[bg])
        if n_art >= min_artikel and n_med >= min_media:
            kandidat.append(
                (n_art * 2.0 + n_med,
                 {"topik": bg, "n_artikel": n_art, "n_media": n_med}))
    # Unigram cadangan: bar lebih tinggi, skor lebih rendah dari bigram.
    for w, idxs in unigram.items():
        n_art, n_med = len(idxs), len(unigram_media[w])
        if n_art >= min_artikel * 2 and n_med >= min_media:
            kandidat.append(
                (n_art * 1.0 + n_med,
                 {"topik": w, "n_artikel": n_art, "n_media": n_med}))

    kandidat.sort(key=lambda k: k[0], reverse=True)
    hasil, terpakai = [], set()
    for _, info in kandidat:
        # Lewati unigram yang sudah terwakili bigram terpilih.
        if " " not in info["topik"] and any(
                info["topik"] in t for t in terpakai):
            continue
        hasil.append(info)
        terpakai.add(info["topik"])
        if len(hasil) >= n:
            break
    return hasil


def gabung_topik(
    manual: list[str], otomatis: list[dict], maks: int = 5
) -> list[str]:
    """Gabung topik manual (prioritas) + otomatis, dedup, batasi maks."""
    hasil: list[str] = []
    for t in list(manual) + [o["topik"] for o in otomatis]:
        t = t.strip()
        if t and t.lower() not in {h.lower() for h in hasil}:
            hasil.append(t)
        if len(hasil) >= maks:
            break
    return hasil


def hitung_tunggu_429(coba_ke: int) -> int:
    """Backoff eksponensial (detik) bila Trends kena rate-limit: 60, 120, 240."""
    return 60 * (2 ** max(0, coba_ke))


def kena_rate_limit(pesan_error: str) -> bool:
    """Deteksi 429 / Too Many Requests dari pesan exception pytrends."""
    p = (pesan_error or "").lower()
    return "429" in p or "too many requests" in p
