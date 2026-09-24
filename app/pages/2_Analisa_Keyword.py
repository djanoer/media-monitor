"""Analisa Keyword: tren volume, perbandingan media, kata terkait, daftar artikel.

Murni SQL + hitung kata (tanpa ML). Artikel tanpa published_at tidak masuk
grafik tren. Sentimen & klasterisasi otomatis bukan bagian halaman ini
(jatah Fase 2/5).
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
st.caption("Tren volume, perbandingan media, dan kata terkait dari sebuah isu")

if not db_path.exists():
    st.warning("Database belum ada. Jalankan dulu run-all.bat.")
    st.stop()


@st.cache_resource
def _stopwords() -> frozenset:
    return frozenset(StopWordRemoverFactory().get_stop_words())


media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}
warna = {m["name"]: m.get("color", "#9aa0a6") for m in media_list}

keyword = st.text_input("Keyword", placeholder="mis. timnas, BBM, rupiah").strip()

if not keyword:
    st.info("Ketik sebuah keyword untuk memulai analisa.")
    st.stop()
if len(keyword) < 3:
    st.info("Keyword minimal 3 karakter.")
    st.stop()

tren = repository.count_by_day_keyword(db_path, keyword)
per_media = repository.count_by_media_keyword(db_path, keyword)

if not tren and not per_media:
    st.info(f'Tidak ada artikel yang mengandung "{keyword}".')
    st.stop()

# ---------- metrik ----------
total = sum(per_media.values())
tgl = sorted(tren)
rentang = f"{tgl[0]} s.d. {tgl[-1]}" if tgl else "-"
m1, m2, m3 = st.columns(3)
m1.metric("Total artikel", f"{total:,}".replace(",", "."))
m2.metric("Rentang tanggal", rentang)
m3.metric("Media terlibat", f"{len(per_media)}/{len(media_list)}")

# ---------- tren harian ----------
st.subheader("Tren volume pemberitaan")
if tren:
    st.line_chart(tren)
    st.caption(
        "Jumlah artikel per hari berdasarkan published_at. "
        "Artikel tanpa tanggal tidak masuk grafik."
    )
else:
    st.caption("Tidak ada data bertanggal untuk keyword ini.")

# ---------- per media ----------
st.subheader("Perbandingan antar media")
if per_media:
    st.bar_chart({display.get(k, k): v for k, v in per_media.items()})

# ---------- kata terkait ----------
st.subheader("Kata yang sering muncul bersama")
judul_list = repository.get_titles_keyword(db_path, keyword)
terkait = analisa.kata_terkait(judul_list, keyword, _stopwords(), top_n=15)
if terkait:
    st.bar_chart(dict(terkait))
    st.caption(
        f"Dihitung dari {len(judul_list)} judul, stopwords Bahasa Indonesia dibuang."
    )
else:
    st.caption("Tidak ada kata terkait yang signifikan.")

# ---------- daftar artikel ----------
st.subheader("Artikel terkait")
batas = st.slider("Jumlah artikel", 10, 200, 50)
rows = repository.get_latest_articles(db_path, keyword=keyword, limit=batas)
st.caption(f"{len(rows)} artikel ditampilkan, keyword di-highlight kuning")
for r in rows:
    st.markdown(
        kmp.kartu_artikel(r, display, warna, keyword=keyword),
        unsafe_allow_html=True,
    )
