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
/* kartu kolom media = bordered container, tinggi seragam + scroll */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border:1px solid rgba(90,130,255,.18) !important;
  border-radius:12px !important;
  background:linear-gradient(180deg, #111d3c, #0e1730) !important;
  padding:10px 12px !important;
  height:640px;
  overflow-y:auto;
  scrollbar-width:thin;
  scrollbar-color:rgba(90,130,255,.4) transparent;}
div[data-testid="stVerticalBlockBorderWrapper"]::-webkit-scrollbar {width:6px;}
div[data-testid="stVerticalBlockBorderWrapper"]::-webkit-scrollbar-thumb {
  background:rgba(90,130,255,.4); border-radius:3px;}
/* Tombol sembunyi/tampil sidebar: font ikon Material kadang gagal dimuat
   sehingga muncul teks ligature "keyboard_double_arrow_right".
   Sembunyikan ikon asli, ganti chevron CSS. */
button[data-testid="stSidebarCollapseButton"],
div[data-testid="stSidebarCollapsedControl"] button,
button[data-testid="collapsedControl"] {font-size:0 !important;}
button[data-testid="stSidebarCollapseButton"] span,
button[data-testid="stSidebarCollapseButton"] svg,
div[data-testid="stSidebarCollapsedControl"] button span,
div[data-testid="stSidebarCollapsedControl"] button svg,
button[data-testid="collapsedControl"] span,
button[data-testid="collapsedControl"] svg {display:none !important;}
button[data-testid="stSidebarCollapseButton"]::after,
div[data-testid="stSidebarCollapsedControl"] button::after,
button[data-testid="collapsedControl"]::after {
  content:"»"; font-size:20px; color:#8ea0c9; line-height:1;}
section[data-testid="stSidebar"]
button[data-testid="stSidebarCollapseButton"]::after {content:"«";}
.mm-penjelasan {background:rgba(79,140,255,.10);
  border:1px solid rgba(90,130,255,.25); border-radius:10px;
  padding:10px 12px; margin:8px 0; color:#dbe4ff; font-size:13px;}
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
.mi-item-sum {font-size:11.5px; color:#8ea0c9; line-height:1.5; margin-top:4px;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
  overflow:hidden;}
div[data-testid="stButton"] button {font-size:11px !important;
  padding:2px 8px !important; margin-top:-4px !important;}
</style>
""", unsafe_allow_html=True)

settings = load_settings()
db_path = ROOT / settings["storage"]["db_path"]

st.title("Media Monitor")
st.caption("Pantau media per kolom — klik Detail untuk ringkasan + alasan skor")

if not db_path.exists():
    st.warning(
        "Database belum ada. Jalankan dulu run-all.bat, lalu refresh halaman ini."
    )
    st.stop()

# Pastikan skema terbaru (idempoten; CREATE TABLE IF NOT EXISTS + migrasi).
repository.init_db(db_path)
repository.migrate_analisa(db_path)

media_list = load_media()
display = {m["name"]: m["display"] for m in media_list}
warna = {m["name"]: m.get("color", "#8ea0c9") for m in media_list}
names = [m["name"] for m in media_list]

# ---------- bar status & metrik ----------
last = repository.get_last_run(db_path)
acuan = (last or {}).get("finished_at") or (last or {}).get("started_at")
menit = fmt.menit_sejak(acuan)
sehat = menit is not None and menit <= 90

if menit is None:
    st.info("Belum ada siklus fetch yang tercatat.")
elif sehat:
    st.success(f"Scheduler sehat. Fetch terakhir {fmt.waktu_relatif(acuan)}"
               f" ({fmt.format_wita(acuan)}).")
else:
    st.warning(f"Fetch terakhir {fmt.waktu_relatif(acuan)}"
               f" ({fmt.format_wita(acuan)}). Scheduler mungkin berhenti.")

total = repository.count_articles(db_path)
baru_24 = repository.count_articles_since(db_path, fmt.iso_mundur(24))
status_media = repository.get_media_last_status(db_path)
ok = sum(1 for v in status_media.values() if v["status"] == "ok")

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total artikel", f"{total:,}".replace(",", "."))
k2.metric("24 jam terakhir", f"{baru_24:,}".replace(",", "."))
k3.metric("Media OK", f"{ok}/{len(names)}")
k4.metric("Fetch terakhir", fmt.waktu_relatif(acuan))
dist_s = repository.distribusi_sentimen(db_path)
tot_s = sum(dist_s.values())
senti_pct = (round(100 * (dist_s.get("positif", 0) - dist_s.get("negatif", 0))
                   / tot_s) if tot_s else 0)
k5.metric("Sentimen rata-rata", f"{senti_pct:+d}%".replace("-", "−"))
k6.metric("Risiko rata-rata", f"{repository.rata_risiko(db_path):.0f}/100")

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
dist_r = repository.distribusi_risiko(db_path)
if dist_s or dist_r:
    tot_r = sum(dist_r.values())
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
    col = warna.get(a["media"], "#8ea0c9")
    st.markdown(
        f'<span style="background:{col};color:#111;'
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

    with st.expander("🔍 Kenapa label ini?", expanded=False):
        _penjelasan_label(a)

    ringkas = fmt.bersihkan_html(a.get("summary") or "")
    if ringkas:
        st.markdown("**Ringkasan**")
        st.write(ringkas[:800])
    st.link_button("Buka sumber ↗", a["url"])


def _penjelasan_label(a: dict) -> None:
    """Kotak penjelasan ala modal referensi: alasan + skala."""
    analisa_cfg = settings["analisa"]
    ringkas = fmt.bersihkan_html(a.get("summary") or "")
    kata = kata_berpengaruh(
        a.get("title") or "", ringkas,
        bobot_judul=float(analisa_cfg.get("bobot_judul", 2.0)))
    sent = a.get("sentimen") or "netral"
    skor_s = a.get("sentimen_skor", 0)
    if sent == "positif" and kata["positif"]:
        alasan_s = ("kata positif " + ", ".join(f"'{w}'" for w in kata["positif"][:5])
                    + " lebih dominan")
    elif sent == "negatif" and kata["negatif"]:
        alasan_s = ("kata negatif " + ", ".join(f"'{w}'" for w in kata["negatif"][:5])
                    + " lebih dominan")
    else:
        alasan_s = "tidak ada kata sentimen yang menonjol"

    penanda = settings.get("verifikasi", {}).get("penanda_bombastis", [])
    flags = cek_headline(a.get("title") or "", ringkas, penanda)
    verdicts = _VERDICTS.get(a.get("url"), [])
    komp = komponen_risiko(sent, "bombastis" in flags, verdicts, analisa_cfg)
    rincian = "; ".join(
        f"{ket} {'+' if d >= 0 else '−'}{abs(d):g}" for ket, d in komp)

    st.markdown(
        f'<div class="mm-penjelasan">'
        f'<b>Sentimen {sent}</b> (skor {skor_s}): {html_mod.escape(alasan_s)}.<br>'
        f'<b>Risiko {a.get("risiko")}</b> (skor {a.get("risiko_skor", 0)}/100): '
        f'{html_mod.escape(rincian)}.</div>',
        unsafe_allow_html=True)

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


st.subheader("Berita per media")
dist_pm = repository.distribusi_per_media(db_path)
grid = repository.get_artikel_per_media(db_path, limit_per_media=per_media)
_VERDICTS = repository.get_verdicts_artikel(db_path)
names_grid = [m for m in names if m in grid]

cols = st.columns(4)
for i, name in enumerate(names_grid):
    arts = grid[name]
    d = dist_pm.get(name, {"sentimen": {}, "risiko": {}})
    ds, dr = d["sentimen"], d["risiko"]
    col = warna[name]
    with cols[i % 4]:
        with st.container(border=True):
            st.markdown(
                f'<div class="mi-gridhead">'
                f'<span style="width:9px;height:9px;border-radius:50%;'
                f'display:inline-block;background:{col};'
                f'box-shadow:0 0 8px {col}"></span>'
                f'<span class="mi-gridname">'
                f'{html_mod.escape(display[name])}</span>'
                f'<span class="mi-gridcount" style="background:{col}">'
                f'{len(arts)}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(kmp.bar_agregat(
                "Sentimen", sum(ds.values()),
                [("positif", ds.get("positif", 0), "#34d399"),
                 ("netral", ds.get("netral", 0), "#b6c6f0"),
                 ("negatif", ds.get("negatif", 0), "#fb7185")],
            ), unsafe_allow_html=True)
            st.markdown(kmp.bar_agregat(
                "Risiko", sum(dr.values()),
                [("Rendah", dr.get("Rendah", 0), "#34d399"),
                 ("Sedang", dr.get("Sedang", 0), "#fbbf24"),
                 ("Tinggi", dr.get("Tinggi", 0), "#fb7185")],
            ), unsafe_allow_html=True)
            for a in arts:
                st.markdown(kmp.item_berita_grid(a), unsafe_allow_html=True)
                if st.button("Detail →", key=f"det-{a['url']}",
                             use_container_width=True):
                    _dialog_artikel(a)
