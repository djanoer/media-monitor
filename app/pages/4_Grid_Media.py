"""Grid Media: kolom per media ala referensi Monitor Indonesia (Fase G).

Tiap kolom: header (dot warna + nama + jumlah), mini-bar sentimen &
risiko, daftar artikel terbaru dengan badge. Klik "Detail" membuka
dialog berisi ringkasan + alasan skor + tautan sumber.

Hanya membaca src/storage (+ helper murni app/format & app/komponen);
tidak ada logika bisnis di halaman ini.
"""

from __future__ import annotations

import html as html_mod
import pathlib
import sys

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import format as fmt  # noqa: E402
from app import komponen as kmp  # noqa: E402
from src.common.config import load_media, load_settings  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Grid Media", layout="wide", page_icon="🗞️")
st.markdown(kmp.CSS, unsafe_allow_html=True)
# pakai tema gelap yang sama dengan halaman Verifikasi
st.markdown("""
<style>
.stApp {background:#070c18;}
.stApp, .stApp * {font-family:"Segoe UI", system-ui, -apple-system, Roboto,
  "Helvetica Neue", Arial, sans-serif;}
.mi-gridcol {border:1px solid rgba(90,130,255,.18); border-radius:12px;
  background:linear-gradient(180deg, #111d3c, #0e1730);
  margin-bottom:14px; overflow:hidden;}
.mi-gridhead {padding:12px 16px; border-bottom:1px solid rgba(255,255,255,.08);
  display:flex; align-items:center; gap:8px;}
.mi-gridname {font-size:15px; font-weight:700; color:#e6ecff;}
.mi-gridcount {margin-left:auto; font-size:11px; font-weight:700; color:#070c18;
  border-radius:20px; padding:2px 10px;}
.mi-gridbars {padding:8px 16px 0;}
.mi-griditems {padding:4px 6px 10px; max-height:520px; overflow-y:auto;}
.mi-detailbtn button {font-size:11px !important; padding:2px 10px !important;}
</style>
""", unsafe_allow_html=True)

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]

st.title("Grid Media")
st.caption("Kolom per media ala Monitor Indonesia — klik Detail untuk"
           " ringkasan + alasan skor")

if not db_path.exists():
    st.warning("Database belum ada. Jalankan dulu run-all.bat.")
    st.stop()

repository.init_db(db_path)
repository.migrate_analisa(db_path)

media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}
warna = {m["name"]: m.get("color", "#8ea0c9") for m in media_list}

with st.sidebar:
    st.header("Pengaturan")
    per_media = st.slider("Artikel per kolom media", 4, 20, 8)


@st.dialog("Detail artikel", width="large")
def _dialog_artikel(a: dict) -> None:
    col = warna.get(a["media"], "#8ea0c9")
    st.markdown(
        f'<span class="mi-badge-sm" style="background:{col};color:#111;'
        f'font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px">'
        f'{html_mod.escape(display.get(a["media"], a["media"]))}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f"### {a['title'] or '(tanpa judul)'}")
    baris = []
    if a.get("sentimen"):
        baris.append(kmp.pill(
            f"Sentimen: {a['sentimen']} ({a.get('sentimen_skor', 0)})",
            kmp.WARNA_SENTIMEN.get(a["sentimen"], "#8ea0c9")))
    if a.get("risiko"):
        baris.append(kmp.pill(
            f"Risiko: {a['risiko']} ({a.get('risiko_skor', 0)}/100)",
            kmp.WARNA_RISIKO.get(a["risiko"], "#8ea0c9")))
    if baris:
        st.markdown(" ".join(baris), unsafe_allow_html=True)
    st.caption(f"Dipublikasikan: {fmt.format_wita(a.get('published_at'))}")
    ringkas = fmt.bersihkan_html(a.get("summary") or "")
    if ringkas:
        st.markdown("**Ringkasan**")
        st.write(ringkas[:800])
    st.link_button("Buka sumber ↗", a["url"])


dist = repository.distribusi_per_media(db_path)
grid = repository.get_artikel_per_media(db_path, limit_per_media=per_media)
names = [m["name"] for m in media_list if m["name"] in grid]

cols = st.columns(4)
for i, name in enumerate(names):
    arts = grid[name]
    d = dist.get(name, {"sentimen": {}, "risiko": {}})
    ds, dr = d["sentimen"], d["risiko"]
    tot = len(arts)
    col = warna[name]
    with cols[i % 4]:
        st.markdown(
            f'<div class="mi-gridcol">'
            f'<div class="mi-gridhead">'
            f'<span style="width:9px;height:9px;border-radius:50%;'
            f'display:inline-block;background:{col};'
            f'box-shadow:0 0 8px {col}"></span>'
            f'<span class="mi-gridname">{html_mod.escape(display[name])}</span>'
            f'<span class="mi-gridcount" style="background:{col}">'
            f'{tot}</span></div>'
            f'<div class="mi-gridbars">'
            f'{kmp.bar_agregat("Sentimen", sum(ds.values()), [("positif", ds.get("positif", 0), "#34d399"), ("netral", ds.get("netral", 0), "#b6c6f0"), ("negatif", ds.get("negatif", 0), "#fb7185")])}'
            f'{kmp.bar_agregat("Risiko", sum(dr.values()), [("Rendah", dr.get("Rendah", 0), "#34d399"), ("Sedang", dr.get("Sedang", 0), "#fbbf24"), ("Tinggi", dr.get("Tinggi", 0), "#fb7185")])}'
            f'</div>'
            f'<div class="mi-griditems">',
            unsafe_allow_html=True,
        )
        for a in arts:
            st.markdown(kmp.item_berita_grid(a), unsafe_allow_html=True)
            st.markdown('<div class="mi-detailbtn">', unsafe_allow_html=True)
            if st.button("Detail →", key=f"det-{a['url']}",
                         use_container_width=True):
                _dialog_artikel(a)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)
