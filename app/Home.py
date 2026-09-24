"""Media Monitor - command center (viewer pra-Fase 3).

Tampilan baca-saja: bar status kesehatan fetch, metrik ringkas, grafik per
media, dan feed artikel sebagai kartu. Aturan arsitektur tetap berlaku:
halaman ini hanya memanggil src/storage (+ helper format murni di app/format),
tidak ada logika bisnis di sini.
"""

from __future__ import annotations

import html as html_mod
import pathlib
import sys

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import format as fmt  # noqa: E402
from app import komponen as kmp  # noqa: E402
from src.common.config import load_media, load_settings  # noqa: E402
from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Media Monitor", layout="wide", page_icon="📰")

st.markdown(kmp.CSS, unsafe_allow_html=True)

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]

st.title("Media Monitor")
st.caption("Command center - pantau kesehatan fetch dan artikel terbaru")

if not db_path.exists():
    st.warning(
        "Database belum ada. Jalankan dulu run-all.bat, lalu refresh halaman ini."
    )
    st.stop()

# Pastikan skema terbaru (idempoten; CREATE TABLE IF NOT EXISTS).
repository.init_db(db_path)

media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}
warna = {m["name"]: m.get("color", "#9aa0a6") for m in media_list}
names = [m["name"] for m in media_list]

# ---------- bar status & metrik ----------
last = repository.get_last_run(db_path)
acuan = (last or {}).get("finished_at") or (last or {}).get("started_at")
menit = fmt.menit_sejak(acuan)
sehat = menit is not None and menit <= 90

if menit is None:
    st.info("Belum ada siklus fetch yang tercatat.")
else:
    rel = fmt.waktu_relatif(acuan)
    abs_wita = fmt.format_wita(acuan)
    if sehat:
        st.success(f"Scheduler sehat. Fetch terakhir {rel} ({abs_wita}).")
    else:
        st.warning(
            f"Fetch terakhir {rel} ({abs_wita}). "
            "Scheduler mungkin berhenti, jalankan ulang run-all.bat."
        )

total = repository.count_articles(db_path)
baru_24 = repository.count_articles_since(db_path, fmt.iso_mundur(24))
status_media = repository.get_media_last_status(db_path)
ok = sum(1 for v in status_media.values() if v["status"] == "ok")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total artikel", f"{total:,}".replace(",", "."))
k2.metric("24 jam terakhir", f"{baru_24:,}".replace(",", "."))
k3.metric("Media OK", f"{ok}/{len(names)}")
k4.metric("Fetch terakhir", fmt.waktu_relatif(acuan))

# ---------- strip status per media ----------
if status_media:
    pills = []
    for n in names:
        v = status_media.get(n)
        nama = html_mod.escape(display[n])
        if v is None:
            pills.append(
                f'<span class="mm-pill" title="Belum pernah fetch">'
                f'<span class="mm-dot mm-na"></span>{nama}</span>'
            )
            continue
        dot = "mm-ok" if v["status"] == "ok" else "mm-err"
        tip = html_mod.escape(
            f"Status: {v['status']} | fetch {fmt.waktu_relatif(v['fetched_at'])}"
            + (f" | error: {v['error']}" if v.get("error") else "")
        )
        pills.append(
            f'<span class="mm-pill" title="{tip}">'
            f'<span class="mm-dot {dot}"></span>{nama}</span>'
        )
    st.markdown(f'<div class="mm-strip">{"".join(pills)}</div>', unsafe_allow_html=True)

# ---------- grafik ----------
counts = repository.count_by_media(db_path)
if counts:
    st.subheader("Artikel per media")
    st.bar_chart({display.get(k, k): v for k, v in counts.items()})

# ---------- filter ----------
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

# ---------- feed kartu ----------
st.subheader("Artikel terbaru")
rows = repository.get_latest_articles(
    db_path,
    media=None if pilih == "semua" else pilih,
    keyword=kata.strip() or None,
    limit=batas,
)
st.caption(f"{len(rows)} artikel ditampilkan")

for r in rows:
    st.markdown(kmp.kartu_artikel(r, display, warna), unsafe_allow_html=True)
