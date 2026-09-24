"""Media Monitor - viewer sementara (pra-Fase 3).

Halaman baca-saja: daftar artikel terbaru + filter media + pencarian kata kunci.
Sengaja minimal; struktur ini yang akan berkembang menjadi dashboard Fase 3.
Aturan arsitektur tetap berlaku: halaman ini hanya memanggil src/storage,
tidak ada logika bisnis di sini.
"""

from __future__ import annotations

import pathlib
import sys

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common.config import load_media, load_settings  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Media Monitor", layout="wide")

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]

st.title("Media Monitor")
st.caption("Viewer sementara - daftar artikel yang sudah terkumpul")

if not db_path.exists():
    st.warning(
        "Database belum ada. Jalankan dulu scheduler (run-application.bat) "
        "atau uji satu siklus (uji-sekali.bat), lalu refresh halaman ini."
    )
    st.stop()

media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}
names = [m["name"] for m in media_list]

with st.sidebar:
    st.header("Filter")
    opsi = ["semua"] + names
    pilih = st.selectbox(
        "Media",
        opsi,
        format_func=lambda n: "Semua media" if n == "semua" else display[n],
    )
    kata = st.text_input("Kata kunci", placeholder="mis. timnas, BBM, rupiah")
    batas = st.slider("Jumlah artikel", 20, 500, 100)

counts = repository.count_by_media(db_path)
if counts:
    st.subheader("Artikel per media")
    st.bar_chart({display.get(k, k): v for k, v in counts.items()})

st.subheader("Artikel terbaru")
rows = repository.get_latest_articles(
    db_path,
    media=None if pilih == "semua" else pilih,
    keyword=kata.strip() or None,
    limit=batas,
)
st.caption(f"{len(rows)} artikel ditampilkan")

for r in rows:
    judul = (r["title"] or "(tanpa judul)").strip()
    st.markdown(f"**[{judul}]({r['url']})**")
    waktu = r["published_at"] or "-"
    st.caption(f"{display.get(r['media'], r['media'])} | {waktu}")
    if (r["summary"] or "").strip():
        st.write(r["summary"][:300])
    st.divider()
