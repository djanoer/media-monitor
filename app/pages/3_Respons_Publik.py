"""Respons Publik — sisi berita (15 media) vs sisi publik (YouTube + Trends).

Topik: manual dari config + otomatis dari judul 24 jam terakhir
(scripts/respon_publik.py --auto, 2x sehari). Halaman ini read-only.
"""

from __future__ import annotations

import html as html_mod
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.config import load_media, load_settings  # noqa: E402
from src.processing import respon_publik  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Respons Publik", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
.mi-topic-head { font-size: 1.6rem; font-weight: 700; margin: 0.2rem 0 0.6rem; }
.mi-kpi { background: #111827; border: 1px solid #1f2937; border-radius: 10px;
          padding: 0.7rem 1rem; }
.mi-kpi .v { font-size: 1.4rem; font-weight: 700; }
.mi-kpi .l { font-size: 0.75rem; color: #9ca3af; }
.mi-news { border-left: 3px solid #4DABF7; padding: 0.35rem 0.7rem;
           margin-bottom: 0.55rem; background: #0d1526; border-radius: 0 8px 8px 0; }
.mi-news .t { font-weight: 600; font-size: 0.92rem; }
.mi-news .m { font-size: 0.75rem; color: #9ca3af; }
.mi-news a { color: #7dd3fc; text-decoration: none; }
</style>
""", unsafe_allow_html=True)

settings = load_settings()
db_path = Path(settings["storage"]["db_path"])
media_cfg = {m["name"]: m for m in load_media()}

st.title("Respons Publik")
st.caption("Satu topik, dua sisi: apa yang diberitakan 15 media vs"
           " bagaimana publik merespons (YouTube + Google Trends).")

if not db_path.exists():
    st.warning("Database belum ada. Jalankan dulu run-all.bat.")
    st.stop()

topik_list = repository.daftar_topik_respon(db_path)
if not topik_list:
    st.info("Belum ada data respons publik."
            " Jalankan: python scripts/respon_publik.py --auto")
    st.stop()

topik = st.selectbox("Topik", topik_list, index=0)

# ---------- sisi berita ----------
berita = repository.get_artikel_keyword(db_path, topik, limit=8)

# ---------- sisi publik ----------
videos = repository.get_youtube_videos(db_path, topik, limit=10)
harian = repository.get_trends_harian(db_path, topik)
ringkas = repository.get_trends_ringkas_terbaru(db_path, topik)
tot = respon_publik.total_statistik(videos) if videos else None
ring = (respon_publik.ringkasan_trends(
    {"keywords": [topik], "minat_harian":
     [{"tanggal": r["tanggal"], topik: r["skor"]} for r in harian],
     "per_daerah": ringkas["per_daerah"] if ringkas else [],
     "terkait": ringkas["terkait"] if ringkas else {}})
    if harian else None)

st.markdown(f'<div class="mi-topic-head">{html_mod.escape(topik)}</div>',
            unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="mi-kpi"><div class="v">{len(berita)}</div>'
                '<div class="l">berita terkait</div></div>',
                unsafe_allow_html=True)
with k2:
    v = f'{tot["total_views"]:,}' .replace(",", ".") if tot else "-"
    st.markdown(f'<div class="mi-kpi"><div class="v">{v}</div>'
                '<div class="l">views YouTube</div></div>',
                unsafe_allow_html=True)
with k3:
    v = f'{tot["total_komentar"]:,}' .replace(",", ".") if tot else "-"
    st.markdown(f'<div class="mi-kpi"><div class="v">{v}</div>'
                '<div class="l">komentar</div></div>',
                unsafe_allow_html=True)
with k4:
    v = f'{ring["minat_rata2"]}/100' if ring else "-"
    st.markdown(f'<div class="mi-kpi"><div class="v">{v}</div>'
                '<div class="l">minat Trends rata-rata</div></div>',
                unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Berita dari media")
    if berita:
        for b in berita:
            m = media_cfg.get(b["media"], {})
            disp = m.get("display", b["media"])
            tgl = (b.get("published_at") or "")[:10]
            st.markdown(
                f'<div class="mi-news"><div class="t">'
                f'<a href="{html_mod.escape(b["url"])}" target="_blank">'
                f'{html_mod.escape(b["title"])}</a></div>'
                f'<div class="m">{html_mod.escape(disp)}'
                f'{f" · {tgl}" if tgl else ""}</div></div>',
                unsafe_allow_html=True)
    else:
        st.info("Tidak ada berita mengandung topik ini.")
with c2:
    st.subheader("Video YouTube teratas")
    if videos:
        st.dataframe(
            [{"Judul": v["title"][:70], "Channel": v["channel"],
              "Views": v["view_count"], "Komentar": v["comment_count"],
              "Likes": v["like_count"]} for v in videos],
            use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data YouTube untuk topik ini.")

st.subheader("Minat pencarian (Google Trends)")
if harian:
    t1, t2 = st.columns([2, 1])
    with t1:
        st.caption("Skor minat harian")
        pivot: dict[str, dict[str, int]] = {}
        for r in harian:
            pivot.setdefault(r["tanggal"], {})[r["keyword"]] = r["skor"]
        st.line_chart(pivot)
    with t2:
        st.caption("Daerah dengan minat tertinggi")
        if ringkas and ringkas["per_daerah"]:
            daerah = ringkas["per_daerah"][:8]
            kw0 = next((k for k in daerah[0] if k != "daerah"), None)
            if kw0:
                st.bar_chart({d["daerah"]: d.get(kw0, 0) for d in daerah})
        st.caption("Frasa terkait yang naik")
        naik = []
        if ringkas:
            for v in ringkas["terkait"].values():
                naik += [q["query"] for q in v.get("rising", [])[:5]]
        for q in naik[:8]:
            st.markdown(f"- {html_mod.escape(q)}")
else:
    st.info("Belum ada data Trends untuk topik ini.")

st.divider()
st.caption("Disclaimer: Tidak 100% valid, ini hanya berupa ringkasan otomatis."
           " Gunakan informasi ini dengan bijak. Algoritma berdasarkan rumus"
           " yang saya buat, dan belum tentu valid.")
