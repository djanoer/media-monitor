"""Test clustering klaim dengan embedding palsu (tanpa unduh model)."""

import math

from src.processing.claim_clustering import _cosine, group_similar


def _vektor(sudut_derajat: float) -> list[float]:
    r = math.radians(sudut_derajat)
    return [math.cos(r), math.sin(r)]


def test_cosine_identik_satu_berbeda_nol():
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert abs(_cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_klaster_bpgmn_terpisah_dari_yang_lain():
    # 3 klaim searah (satu event), 1 klaim jauh berbeda
    emb = [_vektor(0), _vektor(5), _vektor(8), _vektor(90)]
    clusters = group_similar(emb, threshold=0.80)
    assert len(clusters) == 2
    assert clusters[0] == [0, 1, 2]  # terbesar dulu
    assert clusters[1] == [3]


def test_threshold_ketat_memisahkan_semua():
    emb = [_vektor(0), _vektor(30), _vektor(60)]
    clusters = group_similar(emb, threshold=0.99)
    assert len(clusters) == 3


def test_transitif_melalui_perantara():
    # A~B dan B~C tapi A!~C langsung -> tetap satu cluster (union-find)
    emb = [_vektor(0), _vektor(20), _vektor(40)]
    clusters = group_similar(emb, threshold=0.80)
    assert len(clusters) == 1
    assert clusters[0] == [0, 1, 2]


def test_kosong():
    assert group_similar([], threshold=0.80) == []
