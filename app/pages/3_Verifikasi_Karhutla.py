"""Verifikasi Karhutla: sinyal verifikasi klaim + respon publik (Fase E).

Desain mengikuti referensi "Monitor Indonesia" (Bor, 6 Okt 2026):
tema gelap, KPI cards, badge verdict berwarna, kartu cluster dengan
border kiri sesuai verdict.

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

from src.common.config import load_media, load_settings  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Verifikasi Karhutla", layout="wide",
                   page_icon="✅")

# ---------- tema gelap ala Monitor Indonesia ----------
st.markdown("""
<style>
.stApp {background:#0a0e1a;}
.mi-kpi {border:1px solid rgba(255,255,255,0.09); border-radius:12px;
  padding:14px 18px; background:rgba(255,255,255,0.02); margin-bottom:6px;}
.mi-kpi-num {font-size:30px; font-weight:800; color:#fff; line-height:1.1;}
.mi-kpi-label {font-size:11px; color:#9aa0a6; text-transform:uppercase;
  letter-spacing:1px; margin-top:2px;}
.mi-kpi-sub {font-size:12px; color:#9aa0a6; margin-top:4px;}
.mi-col {border:1px solid rgba(255,255,255,0.09); border-radius:12px;
  padding:0; background:rgba(255,255,255,0.02); margin-bottom:14px;
  overflow:hidden;}
.mi-col-head {padding:12px 16px; border-bottom:1px solid
  rgba(255,255,255,0.08); display:flex; align-items:center; gap:10px;}
.mi-col-title {font-size:15px; font-weight:700; color:#fff;}
.mi-count {margin-left:auto; font-size:11px; font-weight:700; color:#111;
  background:#9aa0a6; border-radius:20px; padding:2px 10px;}
.mi-badge {font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px;
  white-space:nowrap; color:#111;}
.mi-item {border-left:3px solid #9aa0a6; padding:10px 14px;
  border-bottom:1px solid rgba(255,255,255,0.05);}
.mi-item:last-child {border-bottom:none;}
.mi-item-title {font-size:14px; color:#e8eaed; line-height:1.45; margin-top:6px;}
.mi-meta {font-size:11px; color:#9aa0a6; margin-top:4px;}
.mi-head {display:flex; align-items:baseline; justify-content:space-between;}
.mi-updated {font-size:12px; color:#9aa0a6; text-align:right;}
</style>
""", unsafe_allow_html=True)

WARNA_VERDICT = {
    "terkoroborasi": "#3DDC84",
    "satu sumber kredibel": "#FFD43B",
    "belum terverifikasi": "#FF6B6B",
}

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]
TOPIK = "karhutla"

# ---------- header ----------
hc1, hc2 = st.columns([3, 1])
with hc1:
    st.title("Verifikasi Karhutla")
    st.caption("Sinyal verifikasi klaim lintas media + respon publik"
               " — bukan vonis hoax")
with hc2:
    st.markdown('<div class="mi-updated">pilot: karhutla</div>',
                unsafe_allow_html=True)

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

# ---------- KPI cards ----------
n_klaim = sum(c["size"] for c in clusters)
n_korob = sum(1 for c in clusters if c.get("verdict") == "terkoroborasi")
skor_list = [c.get("score") for c in clusters
             if isinstance(c.get("score"), (int, float))]
skor_rata = round(sum(skor_list) / len(skor_list), 1) if skor_list else 0
tot_views = sum(v.get("view_count", 0) for v in videos)
rata_tren = (round(sum(r["skor"] for r in harian) / len(harian), 1)
             if harian else 0)
terakhir = max((c.get("computed_at") or "" for c in clusters), default="")


def _kpi(num: str, label: str, sub: str) -> str:
    return (
        f'<div class="mi-kpi"><div class="mi-kpi-num">{num}</div>'
        f'<div class="mi-kpi-label">{label}</div>'
        f'<div class="mi-kpi-sub">{sub}</div></div>'
    )


c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(_kpi(f"{len(clusters)}", "cluster klaim",
                     f"{n_klaim} klaim"), unsafe_allow_html=True)
with c2:
    st.markdown(_kpi(f"{n_korob}", "terkoroborasi",
                     "skor ≥ 80"), unsafe_allow_html=True)
with c3:
    st.markdown(_kpi(f"{skor_rata}", "skor rata-rata",
                     "skala 0–100"), unsafe_allow_html=True)
with c4:
    st.markdown(_kpi(f"{tot_views:,}".replace(",", "."),
                     "views youtube", "20 video teratas"),
                unsafe_allow_html=True)
with c5:
    st.markdown(_kpi(f"{rata_tren}", "minat trends",
                     "rata-rata /100"), unsafe_allow_html=True)

if terakhir:
    st.caption(f"Verifikasi terakhir: {terakhir[:16].replace('T', ' ')}")

# ---------- grid cluster ala kolom media ----------
st.subheader("Sinyal verifikasi")


def _kartu_cluster(c: dict) -> str:
    skor = c.get("score")
    verdict = c.get("verdict") or "-"
    col = WARNA_VERDICT.get(verdict, "#9aa0a6")
    try:
        rincian = json.loads(c.get("tier_breakdown") or "{}")
        per_tier = ", ".join(
            f"{v}×T{k}" for k, v in rincian.get("per_tier", {}).items()
        )
    except (TypeError, ValueError):
        per_tier = "-"
    try:
        flags = json.loads(c.get("headline_flags") or "[]")
    except (TypeError, ValueError):
        flags = []
    badge = (f'<span class="mi-badge" style="background:{col}">'
             f'{html_mod.escape(verdict)}</span>')
    head = (
        f'<div class="mi-col-head"><span class="mi-dot" style="width:8px;'
        f'height:8px;border-radius:50%;display:inline-block;'
        f'background:{col}"></span>'
        f'<span class="mi-col-title">Cluster #{c["id"]}</span>{badge}'
        f'<span class="mi-count">{c["size"]} klaim</span></div>'
    )
    items = []
    for k in c["claims"]:
        media = html_mod.escape(display.get(k["media"], k["media"]))
        teks = html_mod.escape(k["claim_text"][:170])
        items.append(
            f'<div class="mi-item" style="border-left-color:{col}">'
            f'<span class="mi-badge" style="background:#3a4356;color:#e8eaed">'
            f'{media}</span>'
            f'<div class="mi-item-title">{teks}</div></div>'
        )
    meta = (f'<div class="mi-item"><div class="mi-meta">skor {skor}'
            f' · {html_mod.escape(per_tier)}'
            + (f' · ⚠ {html_mod.escape(", ".join(flags))}' if flags else '')
            + '</div></div>')
    return f'<div class="mi-col">{head}{"".join(items)}{meta}</div>'


cols = st.columns(3)
for i, c in enumerate(clusters):
    with cols[i % 3]:
        st.markdown(_kartu_cluster(c), unsafe_allow_html=True)

# ---------- minat publik ----------
st.subheader("Minat publik")
if harian:
    t1, t2 = st.columns([2, 1])
    with t1:
        st.caption("Google Trends — skor minat harian")
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
    st.info("Belum ada data Trends. Jalankan scripts/respon_publik.py.")

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
