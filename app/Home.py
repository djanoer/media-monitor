"""

Media Monitor - home ala referensi Monitor Indonesia.

Tampilan: bar status fetch, metrik KPI, bar agregat sentimen & risiko,

grid kolom per media (tiap kolom: mini-bar + artikel terbaru + dialog

detail). Hanya memanggil src/storage (+ helper murni app/format &

app/komponen); tidak ada logika bisnis di sini.

"""

from __future__ import annotations

import html as html_mod

import hashlib

import pathlib

import sys

import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from app import format as fmt  # noqa: E402

from app import komponen as kmp  # noqa: E402

from src.common.config import load_media, load_settings  # noqa: E402

from src.processing.risiko import komponen_risiko  # noqa: E402

from src.processing.sentimen import kata_berpengaruh  # noqa: E402

from src.processing.verification import cek_headline  # noqa: E402

from src.storage import repository  # noqa: E402

st.set_page_config(page_title="Media Monitor", layout="wide", page_icon="📰")

st.markdown(kmp.CSS, unsafe_allow_html=True)

st.markdown("""

<style>

.stApp {background:#070c18;

  background-image:

    radial-gradient(600px 400px at 10% 0%, rgba(79,140,255,.16), transparent),

    radial-gradient(500px 380px at 90% 0%, rgba(34,211,238,.10), transparent),

    radial-gradient(700px 500px at 50% 100%, rgba(167,139,250,.08), transparent);}

.stApp, .stApp * {font-family:"Segoe UI", system-ui, -apple-system, Roboto,

  "Helvetica Neue", Arial, sans-serif;}

/* ===== HERO header elegan ===== */

.mm-hero {display:flex; justify-content:space-between; align-items:center;

  flex-wrap:wrap; gap:12px; padding:20px 4px 16px;}

.mm-hero-left {display:flex; align-items:center; gap:14px;}

.mm-live-dot {width:14px; height:14px; border-radius:50%; background:#34d399;

  box-shadow:0 0 14px #34d399; animation:mm-pulse 2.2s ease-in-out infinite;

  flex-shrink:0;}

.mm-live-dot.mm-off {background:#5b6b8c; box-shadow:none; animation:none;}

@keyframes mm-pulse {0%,100%{opacity:1; transform:scale(1);}

  50%{opacity:.55; transform:scale(.85);}}

.mm-hero-title {font-size:31px; font-weight:800; color:#f2f5ff;

  letter-spacing:.3px; line-height:1.1;}

.mm-hero-sub {font-size:10.5px; color:#8ea0c9; letter-spacing:2.6px;

  margin-top:4px;}

.mm-hero-right {text-align:right;}

.mm-hero-upd-label {font-size:9.5px; color:#5b6b8c; letter-spacing:1.6px;

  text-transform:uppercase;}

.mm-hero-upd {font-size:13px; color:#e6ecff; font-weight:600; margin-top:2px;}

.mm-hero-health {font-size:11.5px; color:#8ea0c9; margin-top:5px;

  display:flex; align-items:center; gap:6px; justify-content:flex-end;}

/* ===== kartu KPI ===== */

.mm-kpis {display:grid; grid-template-columns:repeat(3, 1fr); gap:14px;

  margin:4px 0 6px;}

@media (max-width: 900px) {.mm-kpis {grid-template-columns:1fr;}}

.mm-kpi {background:linear-gradient(180deg, #141f42, #0e1730);

  border:1px solid rgba(90,130,255,.18); border-radius:14px;

  padding:16px 18px 14px;}

.mm-kpi-num {font-size:33px; font-weight:800; color:#f2f5ff; line-height:1;}

.mm-kpi-den {font-size:15px; color:#8ea0c9; font-weight:600;}

.mm-kpi-label {font-size:10px; color:#8ea0c9; letter-spacing:1.8px;

  margin-top:6px;}

.mm-kpi-sub {font-size:12px; color:#8ea0c9; margin-top:9px;}

.mm-kpi-sub b {color:#dbe4ff;}

.mm-kpi-bar {display:flex; height:5px; border-radius:3px; overflow:hidden;

  margin-top:9px; background:rgba(255,255,255,.06);}

.mm-kpi-bar span {display:block; height:100%;}

/* ===== judul seksi ===== */

.mm-section {display:flex; align-items:baseline; gap:10px;

  margin:22px 0 12px; padding-top:6px;

  border-top:1px solid rgba(255,255,255,.06);}

.mm-section-title {font-size:17px; font-weight:700; color:#e6ecff;}

.mm-section-sub {font-size:11.5px; color:#5b6b8c;}

/* Tombol expand/collapse sidebar: font ikon Material kadang gagal dimuat

   sehingga muncul teks ligature "keyboard_double_arrow_right".

   Terverifikasi di bundle Streamlit 1.65:

   - sidebar tertutup -> testid ada di <button> (stExpandSidebarButton)

   - sidebar terbuka  -> testid ada di wrapper <div> (stSidebarCollapseButton),

     tombol asli di dalamnya (tetap bisa diklik). */

button[data-testid="stExpandSidebarButton"],

[data-testid="stSidebarCollapseButton"] button {font-size:0 !important;}

button[data-testid="stExpandSidebarButton"] *,

[data-testid="stSidebarCollapseButton"] button * {font-size:0 !important;}

button[data-testid="stExpandSidebarButton"]::after,

[data-testid="stSidebarCollapseButton"] button::after {

  font-size:22px; color:#8ea0c9; line-height:1;}

button[data-testid="stExpandSidebarButton"]::after {content:"»";}

[data-testid="stSidebarCollapseButton"] button::after {content:"«";}

.mm-penjelasan {background:rgba(79,140,255,.10);

  border:1px solid rgba(90,130,255,.25); border-radius:10px;

  padding:10px 12px; margin:8px 0; color:#dbe4ff; font-size:13px;}

/* dialog detail ala modal referensi */

.mm-dlg-head {font-size:14px; color:#e6ecff; margin-bottom:10px;}

.mm-dlg-sep {color:#5b6b8c;}

.mm-dlg-src {color:#7aa5ff; text-decoration:none; font-weight:600;}

.mm-dlg-src:hover {text-decoration:underline;}

.mm-dlg-title {font-size:22px; font-weight:800; color:#f2f5ff;

  line-height:1.3; margin:12px 0 4px;}

/* footer disclaimer ala referensi */

.mm-footer {margin-top:36px; padding:18px 12px 10px;

  border-top:1px solid rgba(255,255,255,.08);

  color:#5b6b8c; font-size:11.5px; text-align:center; line-height:1.7;}

.mm-footer b {color:#8ea0c9;}

.mm-skala {background:rgba(255,255,255,.03);

  border:1px solid rgba(255,255,255,.08); border-radius:10px;

  padding:8px 12px; margin:6px 0; color:#dbe4ff; font-size:13px;}

.mm-skala-aktif {border:1px solid #fbbf24 !important;}

/* Scoped media cards */

[class*="st-key-mm-media-"] {background:linear-gradient(180deg,#111d3c,#0e1730);border:1px solid rgba(90,130,255,.18)!important;border-radius:14px;overflow:hidden;padding:0!important;gap:0!important;box-shadow:0 8px 26px rgba(0,0,0,.35);}

.mi-hdr {margin:0;padding-bottom:6px;background:rgba(255,255,255,.02);}

.mi-hdr-top {display:flex;align-items:center;gap:8px;padding:12px 14px;}

.mi-hdr-dot {width:10px;height:10px;border-radius:50%;flex:none;}

.mi-hdr-name {flex:1;min-width:0;color:#e6ecff;font-size:18px;font-weight:700;letter-spacing:.2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

.mi-hdr-count {flex:none;color:#070c18;font-size:12px;font-weight:800;border-radius:20px;padding:2px 10px;}

.mi-hdr-row {display:flex;align-items:center;justify-content:space-between;gap:8px;margin:5px 12px 2px;font-size:10px;line-height:1.4;letter-spacing:.4px;color:#4f8cff;}

.mi-hdr-row>span:first-child {font-weight:800;}

.mi-hdr-vals {color:#8ea0c9;letter-spacing:0;font-variant-numeric:tabular-nums;white-space:nowrap;}

.mi-hdr-bar {display:flex;height:3px;margin:0 12px;border-radius:3px;overflow:hidden;background:rgba(255,255,255,.07);}

.mi-hdr-bar span {display:block;height:100%;}

[class*="st-key-mm-list-"] {padding:8px!important;border:none!important;border-radius:0!important;background:transparent;gap:8px!important;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.25) transparent;}

[class*="st-key-mm-list-"]::-webkit-scrollbar {width:6px;}

[class*="st-key-mm-list-"]::-webkit-scrollbar-thumb {background:rgba(255,255,255,.25);border-radius:6px;}

[class*="st-key-mm-news-"] {background:rgba(255,255,255,.025);border:1px solid transparent!important;border-left:3px solid #8ea0c9!important;border-radius:10px;padding:9px 11px!important;margin:0!important;gap:4px!important;transition:background .15s ease;}

[class*="st-key-mm-news-tinggi-"] {border-left-color:#fb7185!important;}

[class*="st-key-mm-news-sedang-"] {border-left-color:#fbbf24!important;}

[class*="st-key-mm-news-rendah-"] {border-left-color:#34d399!important;}

[class*="st-key-mm-news-"]:hover {background:rgba(255,255,255,.06);}

.mi-meta {display:flex;align-items:center;gap:8px;margin:0;}

.mi-meta .mi-time {font-size:11px;color:#8ea0c9;white-space:nowrap;}

.mi-meta>div {display:inline-flex;align-items:center;flex-wrap:wrap;gap:5px;}

.mi-meta .mi-badge-sm {margin:0;padding:2px 7px;font-size:11px;font-weight:700;line-height:1.25;}

[class*="st-key-mm-news-"] [data-testid="stButton"] {margin:0!important;}

[class*="st-key-mm-news-"] [data-testid="stButton"]>button {display:block;width:100%;min-height:0;height:auto;margin:0!important;padding:0!important;background:transparent!important;border:none!important;box-shadow:none!important;color:#e6ecff;text-align:left;}

[class*="st-key-mm-news-"] [data-testid="stButton"]>button p {display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;margin:0;font-size:16px!important;font-weight:600;line-height:1.35;text-align:left;}

[class*="st-key-mm-news-"] [data-testid="stButton"]>button:hover {color:#8fb0ff;}

[class*="st-key-mm-news-"] [data-testid="stButton"]>button:focus-visible {outline:2px solid #4f8cff!important;outline-offset:3px;}

@media(max-width:560px){.mi-hdr-name{font-size:14px;}.mi-hdr-row{font-size:9px;}.mi-meta .mi-badge-sm{font-size:9px;}[class*="st-key-mm-news-"] [data-testid="stButton"]>button p{font-size:13px!important;}}

/* ===== Judul artikel: konsolidasi final (pengganti MM_TITLE_FIX_V2..V5) ===== */
[class*="st-key-mm-news-"] {min-width:0!important;}
[class*="st-key-mm-news-"] button {
  display:flex!important;align-items:flex-start!important;justify-content:flex-start!important;
  position:static!important;width:100%!important;max-width:100%!important;
  min-width:0!important;min-height:0!important;height:auto!important;
  padding:0!important;margin:8px 0 0!important;background:transparent!important;
  border:0!important;border-radius:0!important;box-shadow:none!important;
  color:#e6ecff!important;text-align:left!important;white-space:normal!important;transform:none!important;
  font-family:"Segoe UI",system-ui,-apple-system,Arial,sans-serif!important;
  font-size:12px!important;font-weight:500!important;line-height:1.45!important;letter-spacing:normal!important;}
[class*="st-key-mm-news-"] button * {
  font-family:"Segoe UI",system-ui,-apple-system,Arial,sans-serif!important;
  font-size:12px!important;font-weight:500!important;
  line-height:1.45!important;letter-spacing:normal!important;text-align:left!important;}
[class*="st-key-mm-news-"] button [data-testid="stMarkdownContainer"] {
  width:100%!important;min-width:0!important;text-align:left!important;}
[class*="st-key-mm-news-"] button p {
  display:-webkit-box!important;-webkit-box-orient:vertical!important;-webkit-line-clamp:2!important;
  overflow:hidden!important;max-height:2.9em!important;margin:0!important;padding:0!important;
  white-space:normal!important;overflow-wrap:anywhere!important;text-align:left!important;}
[class*="st-key-mm-news-"] button:hover {color:#8fb0ff!important;}
[class*="st-key-mm-news-"] button:focus-visible {outline:2px solid #4f8cff!important;outline-offset:2px!important;}
[class*="st-key-mm-news-"] [data-testid="stButton"] {margin:0!important;padding-top:6px!important;}
.mi-meta {position:static!important;display:flex!important;align-items:center!important;
  gap:5px!important;margin:0!important;line-height:1.25!important;}
.mi-meta .mi-badge-sm {margin:0!important;font-size:9px!important;font-weight:700!important;
  line-height:1.25!important;padding:2px 6px!important;}
@media(max-width:560px){
  [class*="st-key-mm-news-"] button,
  [class*="st-key-mm-news-"] button [data-testid="stMarkdownContainer"],
  [class*="st-key-mm-news-"] button p {font-size:13px!important;}}

/* Ringkas tinggi header nama media */

.mi-hdr-top {

  padding:8px 14px !important;

}

/* Kurangi jarak tambahan V5 */

.mi-hdr {

  margin-bottom:6px !important;

  padding-bottom:4px !important;

}

/* Kurangi ruang atas konten utama */

[data-testid="stMainBlockContainer"] {

  padding-top:3.75rem !important;

}

/* Rapikan spacing header Media Monitor */

.mm-hero {

  margin-top:0 !important;

  padding-top:4px !important;

  padding-bottom:12px !important;

}

/* Jarak tetap antara statistik media dan area scroll artikel */

[class*="st-key-mm-list-"] {

  margin-top:12px !important;

}

/* MM_DETAIL_PROPORTION_V1 */

[role="dialog"]:has(.mm-detail-head) {

 width:min(960px,calc(100vw - 32px))!important;

 max-width:960px!important;max-height:88vh!important;

 overflow-y:auto!important;

 background:linear-gradient(160deg,#152449,#0e1730)!important;

 border:1px solid rgba(90,130,255,.22)!important;

 border-radius:16px!important;

}

.mm-detail-head {display:flex;align-items:center;flex-wrap:wrap;gap:8px;

 color:#8ea0c9;font-size:13px;padding:0 0 12px;margin-bottom:14px;

 border-bottom:1px solid rgba(90,130,255,.18);}

.mm-detail-head b {color:#e6ecff;}

.mm-detail-head a {color:#4f8cff;text-decoration:none;font-weight:600;}

.mm-detail-badges {display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;}

.mm-detail-badges .mi-badge-sm {margin:0;font-size:11px;padding:3px 9px;}

.mm-detail-title {font-size:24px!important;font-weight:700!important;

 color:#e6ecff;line-height:1.3;margin:0 0 14px;overflow-wrap:anywhere;}

.mm-detail-reason {font-size:13px;line-height:1.6;color:#cfe0ff;

 background:rgba(79,140,255,.09);border:1px solid rgba(79,140,255,.22);

 border-radius:10px;padding:10px 12px;margin-bottom:12px;}

.mm-detail-time {color:#8ea0c9;font-size:11px;margin-bottom:18px;}

.mm-detail-body p {font-size:15px!important;line-height:1.75!important;

 color:#dbe6ff;margin:0 0 16px;overflow-wrap:anywhere;}

@media(max-width:560px){.mm-detail-title{font-size:20px!important;}

 .mm-detail-body p{font-size:14px!important;}}

/* MM_DETAIL_CENTER_V2 */

[role="dialog"]:has(.mm-detail-head) {

 position:fixed!important;top:50%!important;left:50%!important;

 right:auto!important;bottom:auto!important;

 transform:translate(-50%,-50%)!important;margin:0!important;

 width:min(960px,calc(100vw - 32px))!important;

 max-height:calc(100dvh - 48px)!important;overflow-y:auto!important;

}

.mm-detail-body p {

 font-size:13px!important;line-height:1.75!important;

 text-align:justify!important;text-align-last:left!important;

 overflow-wrap:break-word!important;word-break:normal!important;

}

.mm-detail-reason {

 font-size:12px!important;line-height:1.65!important;

 text-align:justify!important;text-align-last:left!important;

}

@media(max-width:560px){

 [role="dialog"]:has(.mm-detail-head){

 width:calc(100vw - 24px)!important;max-height:calc(100dvh - 24px)!important;

 }

 .mm-detail-body p{font-size:12px!important;}

}


/* Tooltip judul: gunakan teks singkat, bukan judul lengkap */
</style>

""", unsafe_allow_html=True)

settings = load_settings()

db_path = ROOT / settings["storage"]["db_path"]

if not db_path.exists():

    st.warning(

        "Database belum ada. Jalankan dulu run-all.bat, lalu refresh halaman ini."

    )

    st.stop()

# Pastikan skema terbaru (idempoten; CREATE TABLE IF NOT EXISTS + migrasi).

repository.init_db(db_path)

repository.migrate_analisa(db_path)

repository.migrate_isi_lengkap(db_path)

media_list = load_media()

display = {m["name"]: m["display"] for m in media_list}

warna = {m["name"]: m.get("color", "#8ea0c9") for m in media_list}

names = [m["name"] for m in media_list]

# ---------- hero + kartu KPI ----------

last = repository.get_last_run(db_path)

acuan = (last or {}).get("finished_at") or (last or {}).get("started_at")

menit = fmt.menit_sejak(acuan)

sehat = menit is not None and menit <= 90

total = repository.count_articles(db_path)

baru_24 = repository.count_articles_since(db_path, fmt.iso_mundur(24))

status_media = repository.get_media_last_status(db_path)

ok = sum(1 for v in status_media.values() if v["status"] == "ok")

dist_s = repository.distribusi_sentimen(db_path)

tot_s = sum(dist_s.values())

senti_pct = (round(100 * (dist_s.get("positif", 0) - dist_s.get("negatif", 0))

                   / tot_s) if tot_s else 0)

dist_r = repository.distribusi_risiko(db_path)

tot_r = sum(dist_r.values())

risiko_avg = repository.rata_risiko(db_path)

def _segbar(bagian: list[tuple[int, str]]) -> str:

    tot = sum(n for n, _ in bagian)

    if tot <= 0:

        return ""

    seg = "".join(

        f'<span style="width:{100 * n / tot:.1f}%;background:{w}"></span>'

        for n, w in bagian if n > 0)

    return f'<div class="mm-kpi-bar">{seg}</div>'

_dot = ('<span class="mm-live-dot"></span>' if sehat

        else '<span class="mm-live-dot mm-off"></span>')

if menit is None:

    _health = "Belum ada siklus fetch yang tercatat."

    _upd = "—"

elif sehat:

    _health = f"Scheduler sehat · {fmt.waktu_relatif(acuan)}"

    _upd = fmt.format_wib(acuan)

else:

    _health = f"Scheduler mungkin berhenti · {fmt.waktu_relatif(acuan)}"

    _upd = fmt.format_wib(acuan)

st.markdown(

    f'<div class="mm-hero">'

    f'<div class="mm-hero-left">{_dot}<div>'

    f'<div class="mm-hero-title">Media Monitor</div>'

    f'<div class="mm-hero-sub">PANTAU MEDIA · SENTIMEN &amp; RISIKO</div>'

    f'</div></div>'

    f'<div class="mm-hero-right">'

    f'<div class="mm-hero-upd-label">diperbarui</div>'

    f'<div class="mm-hero-upd">{html_mod.escape(_upd)}</div>'

    f'<div class="mm-hero-health">'

    f'<span class="mm-dot {"mm-ok" if sehat else "mm-err"}"></span>'

    f'{html_mod.escape(_health)}</div>'

    f'</div></div>',

    unsafe_allow_html=True,

)

_sent_tanda = "+" if senti_pct >= 0 else "−"
_emo_s = ("😊" if senti_pct >= 15 else "☹️" if senti_pct <= -15 else "😐")

st.markdown(

    f'<div class="mm-kpis">'

    f'<div class="mm-kpi">'

    f'<div class="mm-kpi-num">📰 {f"{total:,}".replace(",", ".")}</div>'

    f'<div class="mm-kpi-label">TOTAL ARTIKEL</div>'

    f'<div class="mm-kpi-sub"><b>{ok}/{len(names)}</b> media OK · '

    f'<b>{f"{baru_24:,}".replace(",", ".")}</b> dalam 24 jam</div>'

    f'</div>'

    f'<div class="mm-kpi">'

    f'<div class="mm-kpi-num">{_emo_s} {_sent_tanda}{abs(senti_pct)}%</div>'

    f'<div class="mm-kpi-label">SENTIMEN RATA-RATA</div>'

    f'<div class="mm-kpi-sub">P <b>{dist_s.get("positif", 0)}</b> · '

    f'N <b>{dist_s.get("netral", 0)}</b> · '

    f'Ng <b>{dist_s.get("negatif", 0)}</b></div>'

    + _segbar([(dist_s.get("positif", 0), "#34d399"),

               (dist_s.get("netral", 0), "#b6c6f0"),

               (dist_s.get("negatif", 0), "#fb7185")])

    + f'</div>'

    f'<div class="mm-kpi">'

    f'<div class="mm-kpi-num">🛡 {risiko_avg:.0f}'

    f'<span class="mm-kpi-den">/100</span></div>'

    f'<div class="mm-kpi-label">RISIKO RATA-RATA</div>'

    f'<div class="mm-kpi-sub">R <b>{dist_r.get("Rendah", 0)}</b> · '

    f'S <b>{dist_r.get("Sedang", 0)}</b> · '

    f'T <b>{dist_r.get("Tinggi", 0)}</b></div>'

    + _segbar([(dist_r.get("Rendah", 0), "#34d399"),

               (dist_r.get("Sedang", 0), "#fbbf24"),

               (dist_r.get("Tinggi", 0), "#fb7185")])

    + f'</div>'

    f'</div>',

    unsafe_allow_html=True,

)

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

    st.markdown(f'<div class="mm-strip">{"".join(pills)}</div>',

                unsafe_allow_html=True)

# ---------- agregat sentimen & risiko ----------

if dist_s or dist_r:

    b1, b2 = st.columns(2)

    with b1:

        st.markdown(kmp.bar_agregat(

            "Sentimen", tot_s,

            [("positif", dist_s.get("positif", 0), "#34d399"),

             ("netral", dist_s.get("netral", 0), "#b6c6f0"),

             ("negatif", dist_s.get("negatif", 0), "#fb7185")],

        ), unsafe_allow_html=True)

    with b2:

        st.markdown(kmp.bar_agregat(

            "Risiko", tot_r,

            [("Rendah", dist_r.get("Rendah", 0), "#34d399"),

             ("Sedang", dist_r.get("Sedang", 0), "#fbbf24"),

             ("Tinggi", dist_r.get("Tinggi", 0), "#fb7185")],

        ), unsafe_allow_html=True)

# ---------- grid kolom per media ----------

with st.sidebar:

    st.header("Pengaturan")

    per_media = st.slider("Artikel per kolom media", 4, 20, 8)

@st.dialog("Detail artikel", width="large")

def _dialog_artikel(a: dict) -> None:

    media_nm = html_mod.escape(display.get(a["media"], a["media"]))

    url = str(a.get("url") or "")

    url_esc = html_mod.escape(url, quote=True)

    source_link = (

        f'<a href="{url_esc}" target="_blank" rel="noopener noreferrer">Buka sumber ↗</a>'

        if url.lower().startswith(("https://", "http://")) else ""

    )

    st.markdown(

        f'<div class="mm-detail-head"><b>{media_nm}</b>'

        f'<span>·</span>{source_link}</div>', unsafe_allow_html=True)

    if a.get("risiko_skor") is None:

        risk_badge = kmp.pill("Risiko: belum dianalisa", "#6b7280")

    else:

        level = a.get("risiko") or "Rendah"

        risk_badge = kmp.pill(

            f"Risiko: {level} · {_fmt_skor(a.get('risiko_skor'))}",

            kmp.WARNA_RISIKO.get(level, "#8ea0c9"))

    sent = str(a.get("sentimen") or "").strip().lower()

    sent_badge = kmp.pill(

        f"Sentimen: {sent.capitalize()}" if sent else "Sentimen: belum dianalisa",

        kmp.WARNA_SENTIMEN.get(sent, "#6b7280"))

    st.markdown(

        '<div class="mm-detail-badges">' + risk_badge + sent_badge + '</div>',

        unsafe_allow_html=True)

    title = html_mod.escape(a.get("title") or "(tanpa judul)")

    st.markdown(f'<h2 class="mm-detail-title">{title}</h2>', unsafe_allow_html=True)

    st.markdown(

        '<div class="mm-detail-reason">' + html_mod.escape(_teks_ai(a)) + '</div>',

        unsafe_allow_html=True)

    with st.expander("❓ Kenapa label ini?", expanded=False):

        _skala_penjelasan(a)

    st.markdown(

        '<div class="mm-detail-time">Dipublikasikan: '

        + html_mod.escape(fmt.format_wib(a.get("published_at"))) + '</div>',

        unsafe_allow_html=True)

    summary, is_ai = _ringkasan_lokal(a)
    if summary:
        _lbl = "📝 RINGKASAN ✨ AI" if is_ai else "📝 RINGKASAN"
        st.markdown(
            f'<div class="mm-detail-time">{_lbl}</div>'
            '<div class="mm-detail-body"><p>'
            + html_mod.escape(summary) + '</p></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Teks belum cukup untuk dirangkum. Gunakan Buka sumber untuk membaca artikel asli.")

    _dianalisis = _teks_dianalisis_lokal(a)
    st.markdown(
        '<div class="mm-detail-time">🔍 TEKS YANG DIANALISIS</div>'
        '<div class="mm-detail-body"><p>'
        + (html_mod.escape(_dianalisis) if _dianalisis
           else "Hanya judul yang dihitung (ringkasan kosong).")
        + '</p></div>',
        unsafe_allow_html=True,
    )

def _ringkasan_lokal(a: dict) -> tuple[str, bool]:
    """Ringkasan untuk dialog lokal — sama persis dengan versi publish.

    Prioritas: ringkasan AI (cache Groq) bila ada, else ekstraktif
    5 kalimat pertama isi_lengkap maks 900 char.
    Returns: (teks, adalah_ai).
    """
    import re
    ringkasan_ai = (a.get("ringkasan_ai") or "").strip()
    if ringkasan_ai:
        return ringkasan_ai, True
    isi = (a.get("isi_lengkap") or "").strip()
    if not isi:
        return "", False
    kal = [k.strip() for k in re.split(r"(?<=[.!?])\s+", isi) if k.strip()]
    teks = " ".join(kal[:5]).strip()
    if len(teks) > 900:
        teks = teks[:900].rsplit(" ", 1)[0] + "…"
    return teks, False

def _teks_dianalisis_lokal(a: dict) -> str:
    """Teks yang BENAR-BENAR dihitung sistem: summary RSS (judul dihitung
    terpisah). Sama persis dengan _teks_dianalisis di scripts/ekspor_statis.py.
    """
    return fmt.bersihkan_html(a.get("summary") or "").strip()

def _komponen_label(a: dict) -> tuple[str, str, list[tuple[str, float]]]:

    """Hitung bahan penjelasan label: (sentimen, alasan, komponen risiko)."""

    analisa_cfg = settings["analisa"]

    ringkas = kmp.teks_ringkasan_mentah(a, max_len=2000)

    kata = kata_berpengaruh(

        a.get("title") or "", ringkas,

        bobot_judul=float(analisa_cfg.get("bobot_judul", 2.0)))

    sent = a.get("sentimen") or "netral"

    if sent == "positif" and kata["positif"]:

        alasan = ("kata positif "

                  + ", ".join(f"'{w}'" for w in kata["positif"][:5])

                  + " lebih dominan")

    elif sent == "negatif" and kata["negatif"]:

        alasan = ("kata negatif "

                  + ", ".join(f"'{w}'" for w in kata["negatif"][:5])

                  + " lebih dominan")

    else:

        alasan = "tidak ada kata sentimen yang menonjol"

    penanda = settings.get("verification", {}).get("penanda_bombastis", [])

    flags = cek_headline(a.get("title") or "", ringkas, penanda)

    verdicts = _VERDICTS.get(a.get("url"), [])

    komp = komponen_risiko(sent, "bombastis" in flags, verdicts, analisa_cfg)

    return sent, alasan, komp

def _fmt_skor(v) -> str:

    """Format skor numerik; None (belum dianalisa) -> '-'."""

    return f"{v:g}" if isinstance(v, (int, float)) else "-"

def _teks_ai(a: dict) -> str:

    """Kalimat penjelasan ala kotak AI referensi."""

    sent, alasan, komp = _komponen_label(a)

    skor_s = a.get("sentimen_skor")

    bagian = [f"Sentimen {sent} (skor {_fmt_skor(skor_s)}): {alasan}."]

    rincian = "; ".join(

        f"{ket} {'+' if d >= 0 else '−'}{abs(d):g}" for ket, d in komp)

    bagian.append(

        f"Risiko {a.get('risiko')} (skor {_fmt_skor(a.get('risiko_skor'))}/100): "

        f"{rincian}.")

    return " ".join(bagian)

def _skala_penjelasan(a: dict) -> None:

    """Isi expander 'kenapa label ini?' ala referensi Penjelasan Analisis."""

    sent, _, _ = _komponen_label(a)

    lvl = a.get("risiko") or "Rendah"

    tanya = (f"Kenapa berita ini {sent} dengan risiko "

             f"{(a.get('risiko') or 'rendah').lower()}?")

    st.markdown(

        f'<div class="mm-penjelasan"><b>🤖 {html_mod.escape(tanya)}</b>'

        f'<br><b>AI:</b> {html_mod.escape(_teks_ai(a))}</div>',

        unsafe_allow_html=True)

    st.markdown("**🛡 SKALA RISIKO (0–100)**")

    for nama, rentang, ket in [

        ("Rendah", "0–34",

         "Minim potensi dampak buruk atau kerugian berarti; "

         "umumnya kabar biasa/harian."),

        ("Sedang", "35–64",

         "Berpotensi menimbulkan keresahan atau dampak sedang — "

         "perlu diwaspadai."),

        ("Tinggi", "65–100",

         "Isu berbahaya/urgent: bencana, kecelakaan, krisis, "

         "konflik, korupsi besar."),

    ]:

        aktif = ' mm-skala-aktif' if nama == lvl else ''

        border = (f'border-color:{kmp.WARNA_RISIKO.get(nama, "#8ea0c9")}'

                  if nama == lvl else '')

        st.markdown(

            f'<div class="mm-skala{aktif}" style="{border}">'

            f'{kmp.pill(nama, kmp.WARNA_RISIKO.get(nama, "#8ea0c9"))} '

            f'Skor risiko {rentang}. {ket}</div>',

            unsafe_allow_html=True)

    st.markdown("**💬 SKALA SENTIMEN**")

    for nama, ket in [

        ("positif",

         "Nuansa baik lebih dominan (naik, untung, sukses, tumbuh, "

         "menang, capai). Skor sentimen ≥ +2,0."),

        ("netral",

         "Isi berimbang/objektif; tidak condong ke positif maupun "

         "negatif. Skor antara -2,0 sampai +2,0."),

        ("negatif",

         "Nuansa buruk lebih dominan (krisis, korupsi, jatuh, tewas, "

         "bencana, gagal). Skor sentimen ≤ -2,0."),

    ]:

        aktif = ' mm-skala-aktif' if nama == sent else ''

        border = (f'border-color:{kmp.WARNA_SENTIMEN.get(nama, "#8ea0c9")}'

                  if nama == sent else '')

        st.markdown(

            f'<div class="mm-skala{aktif}" style="{border}">'

            f'{kmp.pill(nama.capitalize(), kmp.WARNA_SENTIMEN.get(nama, "#8ea0c9"))} '

            f'{ket}</div>',

            unsafe_allow_html=True)

    st.caption("Estimasi otomatis dari leksikon + sinyal verifikasi; "

               "belum tentu 100% valid.")

dist_pm = repository.distribusi_per_media(db_path)

grid = repository.get_artikel_per_media(db_path, limit_per_media=per_media)

_VERDICTS = repository.get_verdicts_artikel(db_path)

names_grid = [m for m in names if m in grid]

st.markdown(

    f'<div class="mm-section">'

    f'<span class="mm-section-title">Berita per media</span>'

    f'<span class="mm-section-sub">'

    f'{len(names_grid)} media · klik judul untuk detail</span></div>',

    unsafe_allow_html=True,

)

for _r in range(0, len(names_grid), 4):

    _cols = st.columns(4)

    for _col, _name in zip(_cols, names_grid[_r:_r + 4]):

        _media_id = hashlib.md5(_name.encode("utf-8")).hexdigest()[:12]

        with _col:

            with st.container(border=False, key=f"mm-media-{_media_id}", gap=None):

                st.markdown(

                    kmp.header_kartu_minimalis(

                        display[_name], warna[_name],

                        dist_pm.get(_name, {}), len(grid[_name])),

                    unsafe_allow_html=True,

                )

                with st.container(height=360, border=False,

                                  key=f"mm-list-{_media_id}", gap="small"):

                    for _idx, a in enumerate(grid[_name]):

                        _article_id = hashlib.md5(

                            a["url"].encode("utf-8")).hexdigest()[:16]

                        _risk = str(a.get("risiko") or "").strip().lower()

                        if _risk not in {"tinggi", "sedang", "rendah"}:

                            _risk = "unknown"

                        _news_key = (f"mm-news-{_risk}-{_media_id}-"

                                     f"{_article_id}-{_idx}")

                        with st.container(border=False, key=_news_key, gap=None):

                            _badges = []

                            _risiko = a.get("risiko")

                            if _risiko:

                                _badges.append(kmp.pill(

                                    str(_risiko),

                                    kmp.WARNA_RISIKO.get(_risiko, "#8ea0c9")))

                            _sentimen = a.get("sentimen")

                            if _sentimen:

                                _sentimen_key = str(_sentimen).strip().lower()

                                _badges.append(kmp.pill(

                                    _sentimen_key.capitalize(),

                                    kmp.WARNA_SENTIMEN.get(

                                        _sentimen_key, "#8ea0c9")))

                            if _badges:

                                _wkt = html_mod.escape(
                                    fmt.format_wib(a.get("published_at")))

                                st.markdown(

                                    '<div class="mi-meta"><span class="mi-time">'

                                    + _wkt + '</span><div>'

                                    + "".join(_badges) + '</div></div>',

                                    unsafe_allow_html=True,

                                )

                            if st.button(

                                a.get("title") or "(tanpa judul)",

                                key=f"dlg-{_media_id}-{_article_id}-{_idx}",

                                help="Klik untuk baca berita",

                            ):

                                _dialog_artikel(a)

# ---------- footer ----------

st.markdown(

    '<div class="mm-footer">'

    "<b>Disclaimer:</b> Tidak 100% valid, ini hanya berupa ringkasan "

    "otomatis. Gunakan informasi ini dengan bijak. Algoritma berdasarkan "

    "rumus yang saya buat, dan belum tentu valid."

    "</div>",

    unsafe_allow_html=True,

)
