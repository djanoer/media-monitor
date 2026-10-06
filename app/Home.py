"""Media Monitor - home ala referensi Monitor Indonesia.

Tampilan: bar status fetch, metrik KPI, bar agregat sentimen & risiko,
grid kolom per media (tiap kolom: mini-bar + artikel terbaru + dialog
detail). Hanya memanggil src/storage (+ helper murni app/format &
app/komponen); tidak ada logika bisnis di sini.
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
.mi-card {border:1px solid rgba(90,130,255,.18); border-radius:12px;
  background:linear-gradient(180deg, #111d3c, #0e1730);
  padding:10px 12px; height:640px; display:flex; flex-direction:column;
  margin-bottom:28px;}
.mi-card-items {overflow-y:auto; flex:1; min-height:0;
  scrollbar-width:thin; scrollbar-color:rgba(90,130,255,.4) transparent;}
.mi-card-items::-webkit-scrollbar {width:6px;}
.mi-card-items::-webkit-scrollbar-thumb {
  background:rgba(90,130,255,.4); border-radius:3px;}
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
.mi-gridhead {display:flex; align-items:center; gap:8px;
  padding:6px 2px 12px; border-bottom:1px solid rgba(255,255,255,.08);
  margin-bottom:4px;}
.mi-gridname {font-size:15px; font-weight:700; color:#e6ecff;
  letter-spacing:.2px;}
.mi-gridcount {margin-left:auto; font-size:11px; font-weight:700; color:#070c18;
  border-radius:20px; padding:2px 10px;}
/* item berita di dalam kartu kolom */
.mi-item {background:rgba(255,255,255,.025); border-radius:9px;
  border-left:3px solid #8ea0c9; padding:8px 12px; margin:8px 0;}
.mi-item-title {font-size:13px; font-weight:600; color:#e6ecff;
  line-height:1.35; margin-top:6px;}
/* judul sebagai hyperlink real -> buka dialog detail */
a.mi-judul {font-size:13px; font-weight:600; color:#e6ecff;
  line-height:1.35; margin-top:6px; display:block; text-decoration:none;}
a.mi-judul:hover {color:#8fb0ff; text-decoration:underline;}
.mi-item-sum {font-size:11.5px; color:#8ea0c9; line-height:1.5; margin-top:4px;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
  overflow:hidden;}
div[data-testid="stButton"] button {font-size:11px !important;
  padding:2px 8px !important; margin-top:-4px !important;}
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
    _upd = fmt.format_wita(acuan)
else:
    _health = f"Scheduler mungkin berhenti · {fmt.waktu_relatif(acuan)}"
    _upd = fmt.format_wita(acuan)

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
st.markdown(
    f'<div class="mm-kpis">'
    f'<div class="mm-kpi">'
    f'<div class="mm-kpi-num">{f"{total:,}".replace(",", ".")}</div>'
    f'<div class="mm-kpi-label">TOTAL ARTIKEL</div>'
    f'<div class="mm-kpi-sub"><b>{ok}/{len(names)}</b> media OK · '
    f'<b>{f"{baru_24:,}".replace(",", ".")}</b> dalam 24 jam</div>'
    f'</div>'
    f'<div class="mm-kpi">'
    f'<div class="mm-kpi-num">{_sent_tanda}{abs(senti_pct)}%</div>'
    f'<div class="mm-kpi-label">SENTIMEN RATA-RATA</div>'
    f'<div class="mm-kpi-sub">P <b>{dist_s.get("positif", 0)}</b> · '
    f'N <b>{dist_s.get("netral", 0)}</b> · '
    f'Ng <b>{dist_s.get("negatif", 0)}</b></div>'
    + _segbar([(dist_s.get("positif", 0), "#34d399"),
               (dist_s.get("netral", 0), "#b6c6f0"),
               (dist_s.get("negatif", 0), "#fb7185")])
    + f'</div>'
    f'<div class="mm-kpi">'
    f'<div class="mm-kpi-num">{risiko_avg:.0f}'
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
    # Header ala referensi: media · — · Buka sumber ↗
    media_nm = html_mod.escape(display.get(a["media"], a["media"]))
    url_esc = html_mod.escape(a["url"], quote=True)
    st.markdown(
        f'<div class="mm-dlg-head"><b>{media_nm}</b>'
        f'<span class="mm-dlg-sep"> · — · </span>'
        f'<a class="mm-dlg-src" href="{url_esc}" target="_blank">'
        f'Buka sumber ↗</a></div>',
        unsafe_allow_html=True,
    )
    # Badge format referensi: "Risiko: Sedang - 50", "Sentimen: Netral".
    # Artikel yang belum dianalisa (skor NULL) tampil apa adanya, bukan crash.
    if a.get("risiko_skor") is None:
        pill_risiko = kmp.pill("Risiko: belum dianalisa", "#6b7280")
    else:
        lvl = a.get("risiko") or "Rendah"
        pill_risiko = kmp.pill(
            f"Risiko: {lvl} - {_fmt_skor(a.get('risiko_skor'))}",
            kmp.WARNA_RISIKO.get(a.get("risiko"), "#8ea0c9"))
    if a.get("sentimen") is None:
        pill_sentimen = kmp.pill("Sentimen: belum dianalisa", "#6b7280")
    else:
        pill_sentimen = kmp.pill(
            f"Sentimen: {(a.get('sentimen') or 'netral').capitalize()}",
            "#b6c6f0")
    st.markdown(pill_risiko + " " + pill_sentimen, unsafe_allow_html=True)
    with st.expander("❓ kenapa label ini?", expanded=False):
        _skala_penjelasan(a)

    st.markdown(
        f"<div class='mm-dlg-title'>"
        f"{html_mod.escape(a['title'] or '(tanpa judul)')}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="mm-penjelasan"><b>AI:</b> '
        f'{html_mod.escape(_teks_ai(a))}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Dipublikasikan: {fmt.format_wita(a.get('published_at'))}")

    isi = (a.get("isi_lengkap") or "").strip()
    if isi:
        for _pg in isi.split("\n\n"):
            _pg = _pg.strip()
            if _pg:
                st.write(_pg)
    else:
        _sum = fmt.bersihkan_html(a.get("summary") or "").strip()
        if _sum and not kmp.mirip_judul(_sum, a.get("title")):
            st.write(_sum)


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
    penanda = settings.get("verifikasi", {}).get("penanda_bombastis", [])
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
    """Skala risiko & sentimen ala modal 'Penjelasan Analisis' referensi."""
    analisa_cfg = settings["analisa"]
    sent, _, _ = _komponen_label(a)
    t_tinggi = float(analisa_cfg.get("ambang_risiko_tinggi", 65))
    t_sedang = float(analisa_cfg.get("ambang_risiko_sedang", 35))
    lvl = a.get("risiko") or "Rendah"
    st.markdown("**🛡 SKALA RISIKO (0–100)**")
    for nama, lo, hi, ket in [
        ("Rendah", 0, t_sedang - 1,
         "Minim potensi dampak buruk; umumnya kabar biasa/harian."),
        ("Sedang", t_sedang, t_tinggi - 1,
         "Berpotensi menimbulkan keresahan atau dampak sedang — perlu diwaspadai."),
        ("Tinggi", t_tinggi, 100,
         "Isu berbahaya/urgent: bencana, kecelakaan, krisis, konflik; "
         "atau klaim belum terverifikasi + headline bombastis."),
    ]:
        aktif = ' mm-skala-aktif' if nama == lvl else ''
        border = (f'border-color:{kmp.WARNA_RISIKO.get(nama, "#8ea0c9")}'
                  if nama == lvl else '')
        st.markdown(
            f'<div class="mm-skala{aktif}" style="{border}">'
            f'{kmp.pill(nama, kmp.WARNA_RISIKO.get(nama, "#8ea0c9"))} '
            f'Skor {lo:g}–{hi:g}. {ket}</div>',
            unsafe_allow_html=True)

    amb = float(analisa_cfg.get("ambang_sentimen", 2.0))
    st.markdown("**💬 SKALA SENTIMEN**")
    for nama, ket in [
        ("positif", f"Nuansa baik lebih dominan. Skor sentimen ≥ +{amb:g}."),
        ("netral",
         f"Isi berimbang/objektif; tidak condong. Skor antara −{amb:g} "
         f"sampai +{amb:g}."),
        ("negatif", f"Nuansa buruk lebih dominan. Skor sentimen ≤ −{amb:g}."),
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

# Dialog detail via hyperlink judul (?art=<url>): buka saat param ada,
# bersihkan setelah ditutup agar refresh tak membuka lagi.
_art_param = st.query_params.get("art")
if _art_param:
    _target = next(
        (a for arts in grid.values() for a in arts if a["url"] == _art_param),
        None)
    if _target is not None:
        _dialog_artikel(_target)
    st.query_params.clear()

for _r in range(0, len(names_grid), 4):
    _cols = st.columns(4)
    for _col, _name in zip(_cols, names_grid[_r:_r + 4]):
        with _col:
            st.markdown(
                kmp.kartu_media_grid(
                    _name, display[_name], warna[_name],
                    dist_pm.get(_name, {}), grid[_name]),
                unsafe_allow_html=True)

# ---------- footer ----------
st.markdown(
    '<div class="mm-footer">'
    "<b>Disclaimer:</b> Tidak 100% valid, ini hanya berupa ringkasan "
    "otomatis. Gunakan informasi ini dengan bijak. Algoritma berdasarkan "
    "rumus yang saya buat, dan belum tentu valid."
    "</div>",
    unsafe_allow_html=True,
)
