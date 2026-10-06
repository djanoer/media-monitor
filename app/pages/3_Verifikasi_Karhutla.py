"""Verifikasi Karhutla: sinyal verifikasi klaim + respon publik (Fase E).

Hanya membaca src/storage (+ helper murni app/format); tidak ada logika
bisnis di halaman ini. Data diisi oleh scripts/ekstrak_klaim.py,
scripts/verifikasi.py, dan scripts/respon_publik.py.
"""

from __future__ import annotations

import html as html_mod
import json
import pathlib
import sys

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import komponen as kmp  # noqa: E402
from src.common.config import load_media, load_settings  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Verifikasi Karhutla", layout="wide",
                   page_icon="✅")
st.markdown(kmp.CSS, unsafe_allow_html=True)

WARNA_VERDICT = {
    "terkoroborasi": "#3DDC84",
    "satu sumber kredibel": "#FFD43B",
    "belum terverifikasi": "#FF6B6B",
}

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]
TOPIK = "karhutla"

st.title("Verifikasi Karhutla")
st.caption("Sinyal verifikasi klaim lintas media + respon publik"
           " (bukan vonis hoax)")

if not db_path.exists():
    st.warning("Database belum ada. Jalankan dulu run-all.bat.")
    st.stop()

repository.init_db(db_path)

media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}

clusters = repository.get_clusters(db_path)
videos = repository.get_youtube_videos(db_path, TOPIK, limit=20)
harian = repository.get_trends_harian(db_path, TOPIK)
ringkas = repository.get_trends_ringkas_terbaru(db_path, TOPIK)

if not clusters:
    st.info("Belum ada cluster klaim. Jalankan scripts/ekstrak_klaim.py"
            " lalu scripts/verifikasi.py.")
    st.stop()

# ---------- KPI ----------
n_klaim = sum(c["size"] for c in clusters)
n_korob = sum(1 for c in clusters if c.get("verdict") == "terkoroborasi")
tot_views = sum(v.get("view_count", 0) for v in videos)
rata_tren = (
    round(sum(r["skor"] for r in harian) / len(harian), 1) if harian else 0
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Cluster klaim", len(clusters))
k2.metric("Total klaim", n_klaim)
k3.metric("Terkoroborasi", n_korob)
k4.metric("Views YouTube (20 video)", f"{tot_views:,}".replace(",", "."))
k5.metric("Minat Trends rata-rata", f"{rata_tren}/100")

# ---------- sinyal verifikasi ----------
st.subheader("Sinyal verifikasi per cluster")
for c in clusters:
    skor = c.get("score")
    verdict = c.get("verdict") or "-"
    col = WARNA_VERDICT.get(verdict, "#9aa0a6")
    try:
        rincian = json.loads(c.get("tier_breakdown") or "{}")
        per_tier = ", ".join(
            f"{v} media Tier {k}" for k, v in rincian.get("per_tier", {}).items()
        )
    except (TypeError, ValueError):
        per_tier = "-"
    try:
        flags = json.loads(c.get("headline_flags") or "[]")
    except (TypeError, ValueError):
        flags = []

    badge = (f'<span class="mm-badge" style="background:{col}">'
             f'{html_mod.escape(verdict)}</span>')
    judul = (f'<div class="mm-title">{badge}'
             f' <span class="mm-time">skor {skor}</span>'
             f' <span class="mm-time">{html_mod.escape(per_tier)}</span>'
             + (f' <span class="mm-time">⚠ {", ".join(map(html_mod.escape, flags))}'
                f'</span>' if flags else '')
             + '</div>')
    anggota = "".join(
        f'<div class="mm-summary">[{html_mod.escape(display.get(k["media"], k["media"]))}]'
        f' {html_mod.escape(k["claim_text"][:160])}</div>'
        for k in c["claims"]
    )
    st.markdown(f'<div class="mm-card">{judul}{anggota}</div>',
                unsafe_allow_html=True)

# ---------- minat publik ----------
st.subheader("Minat publik (Google Trends)")
if harian:
    pivot: dict[str, dict[str, int]] = {}
    for r in harian:
        pivot.setdefault(r["tanggal"], {})[r["keyword"]] = r["skor"]
    st.line_chart(pivot)
else:
    st.info("Belum ada data Trends. Jalankan scripts/respon_publik.py.")

if ringkas:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Daerah dengan minat tertinggi**")
        daerah = ringkas["per_daerah"][:8]
        if daerah:
            kw0 = next((k for k in daerah[0] if k != "daerah"), None)
            st.bar_chart({d["daerah"]: d.get(kw0, 0) for d in daerah} if kw0
                         else {})
    with c2:
        st.markdown("**Frasa terkait yang naik**")
        naik = []
        for v in ringkas["terkait"].values():
            naik += [q["query"] for q in v.get("rising", [])[:5]]
        if naik:
            st.markdown("\n".join(f"- {html_mod.escape(q)}" for q in naik[:10]))
        else:
            st.caption("Belum ada frasa naik.")

# ---------- YouTube ----------
st.subheader("Video YouTube teratas")
if videos:
    st.dataframe(
        [
            {
                "Judul": v["title"],
                "Channel": v["channel"],
                "Views": v["view_count"],
                "Komentar": v["comment_count"],
                "Likes": v["like_count"],
            }
            for v in videos[:10]
        ],
        use_container_width=True,
    )
else:
    st.info("Belum ada data YouTube. Jalankan scripts/respon_publik.py"
            " dengan YOUTUBE_API_KEY.")
