"""Test ekstraksi klaim rule-based (tanpa model, tanpa DB)."""

from src.processing.claim_extraction import extract_claims, split_sentences


def test_judul_selalu_jadi_klaim():
    klaim = extract_claims({"title": "Karhutla melanda Riau", "summary": ""})
    assert klaim == [{"claim_text": "Karhutla melanda Riau",
                      "claim_type": "headline"}]


def test_kalimat_berangka_dari_ringkasan_diambil():
    klaim = extract_claims({
        "title": "Karhutla melanda Riau",
        "summary": "BPBD mencatat 479,48 hektare lahan terbakar di Batang Hari. "
                   "Api masih belum padam.",
    })
    teks = [k["claim_text"] for k in klaim]
    assert "Karhutla melanda Riau" in teks
    assert "BPBD mencatat 479,48 hektare lahan terbakar di Batang Hari." in teks
    # kalimat tanpa angka diabaikan
    assert not any("belum padam" in t for t in teks)


def test_batas_maks_kalimat_dan_panjang_minimum():
    ringkasan = ("Luas 10 hektare terbakar. Korban 5 orang dirawat. "
                 "Kerugian 2 miliar rupiah. Tim 100 personel dikerahkan.")
    klaim = extract_claims({"title": "T", "summary": ringkasan},
                           max_sentences=2, min_length=20)
    assert len(klaim) == 3  # 1 judul + 2 kalimat
    klaim_pendek = extract_claims({"title": "T", "summary": "Ada 5 korban."},
                                  min_length=20)
    assert len(klaim_pendek) == 1  # cuma judul


def test_duplikat_persis_dengan_judul_dilewati():
    klaim = extract_claims({
        "title": "Luas 10 hektare terbakar",
        "summary": "Luas 10 hektare terbakar. Korban 2 orang dirawat.",
    })
    teks = [k["claim_text"] for k in klaim]
    assert teks.count("Luas 10 hektare terbakar") == 1
    assert "Korban 2 orang dirawat." in teks


def test_tanpa_judul_tanpa_klaim():
    assert extract_claims({"title": "", "summary": ""}) == []
    assert extract_claims({}) == []


def test_split_sentences():
    assert split_sentences("Satu. Dua! Tiga?") == ["Satu.", "Dua!", "Tiga?"]
