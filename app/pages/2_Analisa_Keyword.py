"""Analisa Keyword: watchlist, analisa mendalam per keyword, matriks liputan.

- Watchlist keyword/hashtag tersimpan di database (bukan ketik manual).
- Matriks liputan (keyword x media): siapa membahas isu apa, seberapa banyak.
- Analisa mendalam: tren harian, perbandingan media, kata terkait, daftar artikel.
- Pro/kontra/netral BUKAN bagian halaman ini (butuh klasifikasi stance, Fase 2).
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st
from Sastrawi.StopWordRemover.StopWordRemoverFactory import (
    StopWordRemoverFactory,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import analisa  # noqa: E402
from app import komponen as kmp  # noqa: E402
from src.common.config import load_media, load_settings  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Analisa Keyword", layout="wide", page_icon="🔍")
st.markdown(kmp.CSS, unsafe_allow_html=True)

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]

st.title("Analisa Keyword")
st.caption("Pantau isu yang dipantau dan bandingkan liputan antar media")

if not db_path.exists():
    st.warning("Database belum ada. Jalankan dulu run-all.bat.")
    st.stop()

# Pastikan skema terbaru (idempoten; CREATE TABLE IF NOT EXISTS).
repository.init_db(db_path)


@st.cache_resource
def _stopwords() -> frozenset:
    return frozenset(StopWordRemoverFactory().get_stop_words())


media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}
warna = {m["name"]: m.get("color", "#9aa0a6") for m in media_list}
names = [m["name"] for m in media_list]

# ---------- watchlist ----------
st.subheader("Watchlist keyword")
with st.form("tambah_keyword", clear_on_submit=True):
    baru = st.text_input(
        "Keyword/hashtag baru", placeholder="mis. timnas, BBM, #kabinetmerahputih"
    )
    if st.form_submit_button("Tambah"):
        if repository.add_keyword(db_path, baru):
            st.success(f'"{baru.strip()}" masuk watchlist.')
            st.rerun()
        else:
            st.warning("Keyword kosong atau sudah ada di watchlist.")

watch = repository.get_watchlist(db_path)
if not watch:
    st.info("Watchlist masih kosong. Tambahkan keyword di atas untuk mulai.")
    st.stop()

kolom = st.columns(4)
for i, kw in enumerate(watch):
    with kolom[i % 4]:
        c1, c2 = st.columns([4, 1])
        c1.write(f"`{kw}`")
        if c2.button("✕", key=f"hapus_{kw}", help=f"Hapus {kw}"):
            repository.remove_keyword(db_path, kw)
            st.rerun()

st.divider()

# ---------- analisa mendalam ----------
keyword = st.selectbox("Pilih keyword untuk analisa mendalam", watch)

tren = repository.count_by_day_keyword(db_path, keyword)
per_media = repository.count_by_media_keyword(db_path, keyword)

st.subheader(f'Analisa: "{keyword}"')
if not tren and not per_media:
    st.info(f'Belum ada artikel yang mengandung "{keyword}".')
else:
    total = sum(per_media.values())
    tgl = sorted(tren)
    rentang = f"{tgl[0]} s.d. {tgl[-1]}" if tgl else "-"
    m1, m2, m3 = st.columns(3)
    m1.metric("Total artikel", f"{total:,}".replace(",", "."))
    m2.metric("Rentang tanggal", rentang)
    m3.metric("Media terlibat", f"{len(per_media)}/{len(names)}")

    st.write("**Tren volume pemberitaan**")
    if tren:
        st.line_chart(tren)
        st.caption("Per hari (published_at). Artikel tanpa tanggal tidak masuk grafik.")
    else:
        st.caption("Tidak ada data bertanggal untuk keyword ini.")

    st.write("**Perbandingan antar media**")
    if per_media:
        st.bar_chart({display.get(k, k): v for k, v in per_media.items()})

    st.write("**Kata yang sering muncul bersama**")
    judul_list = repository.get_titles_keyword(db_path, keyword)
    terkait = analisa.kata_terkait(judul_list, keyword, _stopwords(), top_n=15)
    if terkait:
        st.bar_chart(dict(terkait))
        st.caption(f"Dihitung dari {len(judul_list)} judul, stopwords dibuang.")
    else:
        st.caption("Tidak ada kata terkait yang signifikan.")

    st.write("**Artikel terkait**")
    batas = st.slider("Jumlah artikel", 10, 200, 50)
    rows = repository.get_latest_articles(db_path, keyword=keyword, limit=batas)
    st.caption(f"{len(rows)} artikel, keyword di-highlight kuning")
    for r in rows:
        st.markdown(
            kmp.kartu_artikel(r, display, warna, keyword=keyword),
            unsafe_allow_html=True,
        )

st.divider()

# ---------- matriks liputan ----------
st.subheader("Matriks liputan: keyword × media")
matriks = repository.count_matrix(db_path, watch)
tabel: dict[str, list] = {"Keyword": watch}
for n in names:
    tabel[display[n]] = [matriks[kw].get(n, 0) for kw in watch]
st.dataframe(tabel, use_container_width=True, hide_index=True)
st.caption(
    "Angka = jumlah artikel. Baca per baris: isu paling ramai dibahas media mana. "
    "Baca per kolom: media paling fokus ke isu apa."
)

# ---------- isu terhangat per media ----------
st.subheader("Isu terhangat per media")
m_media, m_isu, m_n = [], [], []
for n in names:
    peringkat = sorted(
        ((matriks[kw].get(n, 0), kw) for kw in watch), reverse=True
    )
    top_n, top_kw = peringkat[0]
    m_media.append(display[n])
    m_isu.append(top_kw if top_n else "-")
    m_n.append(top_n)
st.dataframe(
    {"Media": m_media, "Isu terhangat": m_isu, "Artikel": m_n},
    use_container_width=True,
    hide_index=True,
)
