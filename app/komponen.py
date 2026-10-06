"""Komponen tampilan bersama (kartu artikel, CSS, sorot keyword).

Dipakai Home.py dan halaman-halaman di app/pages/ agar tidak duplikasi HTML.
Fungsi di sini hanya merangkai string; tidak ada logika bisnis.
"""

from __future__ import annotations

import html as html_mod
import re

from app import format as fmt

CSS = """
<style>
.mm-card {border:1px solid rgba(255,255,255,0.09); border-radius:10px;
  padding:12px 16px; margin-bottom:10px; background:rgba(255,255,255,0.02);}
.mm-badge {color:#111; font-size:11px; font-weight:700; padding:2px 10px;
  border-radius:20px; white-space:nowrap;}
.mm-time {color:#9aa0a6; font-size:12px; margin-left:8px;}
.mm-title {font-size:16px; font-weight:600; margin:8px 0 4px; line-height:1.4;}
.mm-title a {color:#e8eaed; text-decoration:none;}
.mm-title a:hover {text-decoration:underline;}
.mm-summary {color:#9aa0a6; font-size:13px; line-height:1.55;}
.mm-strip {display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 16px;}
.mm-pill {display:inline-flex; align-items:center; gap:6px; font-size:12px;
  color:#e8eaed; border:1px solid rgba(255,255,255,0.12); border-radius:20px;
  padding:4px 12px;}
.mm-dot {width:8px; height:8px; border-radius:50%; display:inline-block;}
.mm-ok {background:#3DDC84;} .mm-err {background:#FF6B6B;} .mm-na {background:#6c757d;}
mark {background:#FFD43B; color:#111; border-radius:3px; padding:0 2px;}
.mi-badge-sm {font-size:8.5px; font-weight:700; padding:2px 8px; border-radius:20px;
  white-space:nowrap; color:#111; margin-left:6px;}
.mi-segbar {display:flex; height:4px; border-radius:2px; overflow:hidden;
  margin:4px 0 12px; background:rgba(255,255,255,0.06);}
.mi-segbar span {display:block; height:100%;}
.mi-seglabel {font-size:10px; color:#8ea0c9; text-transform:uppercase;
  letter-spacing:.8px; margin-top:12px;}
</style>
"""

# Warna badge exact dari referensi Monitor Indonesia.
WARNA_SENTIMEN = {"positif": "#34d399", "netral": "#b6c6f0",
                  "negatif": "#fb7185"}
WARNA_RISIKO = {"Tinggi": "#fb7185", "Sedang": "#fbbf24", "Rendah": "#34d399"}


def pill(teks: str, warna: str) -> str:
    """Pill badge kecil."""
    return (f'<span class="mi-badge-sm" style="background:{warna}">'
            f'{html_mod.escape(teks)}</span>')


def bar_agregat(
    judul: str, total: int, bagian: list[tuple[str, int, str]]
) -> str:
    """Bar tersegmen proporsional + legend, ala referensi Monitor Indonesia.

    bagian: list (label, jumlah, warna).
    """
    seg = "".join(
        f'<span style="width:{100 * n / total:.1f}%;background:{w}"'
        f' title="{html_mod.escape(lb)}: {n}"></span>'
        for lb, n, w in bagian if n > 0
    ) if total > 0 else ""
    leg = " &nbsp; ".join(
        f'<span style="color:{w}">●</span> {html_mod.escape(lb)} {n}'
        for lb, n, w in bagian
    )
    return (
        f'<div class="mi-seglabel">{html_mod.escape(judul)}'
        f' · {total} berita</div>'
        f'<div style="font-size:10px;color:#8ea0c9">{leg}</div>'
        f'<div class="mi-segbar">{seg}</div>'
    )


def pills_artikel(r: dict) -> str:
    """Baris badge risiko + sentimen untuk satu artikel."""
    isi = '<div>'
    if r.get("risiko"):
        isi += pill(r["risiko"], WARNA_RISIKO.get(r["risiko"], "#8ea0c9"))
    if r.get("sentimen"):
        isi += pill(r["sentimen"],
                    WARNA_SENTIMEN.get(r["sentimen"], "#8ea0c9"))
    return isi + '</div>'


def mirip_judul(ringkasan: str | None, judul: str | None) -> bool:
    """True bila ringkasan kosong atau hanya mengulang judul.

    Banyak feed RSS mengisi deskripsi dengan judul (+ embel-embel
    seperti " - media.co.id"); itu bukan ringkasan sungguhan.
    """
    r = (ringkasan or "").strip().lower()
    j = (judul or "").strip().lower()
    if not r:
        return True
    if r == j:
        return True
    # pola "judul - nama media" / "judul | media"
    if r.startswith(j) and len(r) <= len(j) + 40:
        return True
    return False


def teks_ringkasan_mentah(r: dict, max_len: int = 140) -> str:
    """Teks ringkasan artikel TANPA escape (untuk komputasi/internal).

    Prioritas: isi_lengkap hasil unduhan (2 kalimat pertama) ->
    ringkasan RSS (bila bukan duplikat judul) -> "".
    """
    isi = (r.get("isi_lengkap") or "").strip()
    if isi:
        kalimat = re.split(r"(?<=[.!?])\s+", isi)
        teks = " ".join(kalimat[:2]).strip()
    else:
        teks = fmt.bersihkan_html(r.get("summary") or "").strip()
        if mirip_judul(teks, r.get("title")):
            return ""
    if len(teks) > max_len:
        teks = teks[:max_len].rsplit(" ", 1)[0] + "…"
    return teks


def cuplikan(r: dict, max_len: int = 140) -> str:
    """Teks tampil untuk ringkasan artikel (sudah di-escape)."""
    return html_mod.escape(teks_ringkasan_mentah(r, max_len))


def buka_kartu_media(
    name: str, display_name: str, color: str,
    dist: dict, n_arts: int,
) -> str:
    """HTML pembuka kartu kolom media: header + mini-bar + div scroll.

    Daftar artikel di-render oleh pemanggil sebagai st.button native per
    judul (dialog langsung, tanpa trik ?art=), lalu tutup_kartu_media().
    """
    ds = (dist or {}).get("sentimen", {})
    dr = (dist or {}).get("risiko", {})
    tot_s, tot_r = sum(ds.values()), sum(dr.values())
    nama = html_mod.escape(display_name)
    return (
        f'<div class="mi-card" id="card-{name}">'
        f'<div class="mi-gridhead">'
        f'<span style="width:9px;height:9px;border-radius:50%;'
        f'display:inline-block;background:{color};'
        f'box-shadow:0 0 8px {color}"></span>'
        f'<span class="mi-gridname">{nama}</span>'
        f'<span class="mi-gridcount" style="background:{color}">'
        f'{n_arts}</span></div>'
        f'{bar_agregat("Sentimen", tot_s, [("positif", ds.get("positif", 0), "#34d399"), ("netral", ds.get("netral", 0), "#b6c6f0"), ("negatif", ds.get("negatif", 0), "#fb7185")])}'
        f'{bar_agregat("Risiko", tot_r, [("Rendah", dr.get("Rendah", 0), "#34d399"), ("Sedang", dr.get("Sedang", 0), "#fbbf24"), ("Tinggi", dr.get("Tinggi", 0), "#fb7185")])}'
        f'<div class="mi-card-items">'
    )


def tutup_kartu_media() -> str:
    """Penutup div scroll + div kartu (pasangan buka_kartu_media)."""
    return "</div></div>"


def buka_item_artikel(a: dict) -> str:
    """HTML pembuka satu item berita: box + pills (tanpa judul).

    Judul di-render pemanggil sebagai st.button native agar klik langsung
    membuka dialog tanpa navigasi ?art=.
    """
    col = WARNA_RISIKO.get(a.get("risiko"), "#8ea0c9")
    return (
        f'<div class="mi-item" style="border-left-color:{col}">'
        f'{pills_artikel(a)}'
    )


def tutup_item_artikel(a: dict) -> str:
    """Cuplikan ringkasan + penutup div item (pasangan buka_item_artikel)."""
    cuplik = cuplikan(a)
    sum_html = (f'<div class="mi-item-sum">{cuplik}</div>'
                if cuplik else "")
    return f"{sum_html}</div>"


def kartu_media_grid(
    name: str, display_name: str, color: str,
    dist: dict, arts: list[dict],
) -> str:
    """Satu kartu kolom media utuh (satu blok HTML).

    CATATAN: tidak lagi dipakai Home.py (sudah pakai st.button native per
    judul). Disimpan untuk kompatibilitas test; judul berupa span biasa.
    """
    items = []
    for a in arts:
        judul = html_mod.escape(a.get("title") or "(tanpa judul)")
        items.append(
            f"{buka_item_artikel(a)}"
            f'<span class="mi-judul">{judul}</span>'
            f"{tutup_item_artikel(a)}")
    gabung = "".join(items)
    return (
        f"{buka_kartu_media(name, display_name, color, dist, len(arts))}"
        f"{gabung}"
        f"{tutup_kartu_media()}"
    )


def sorot(teks_escaped: str, keyword: str | None) -> str:
    """Bungkus kemunculan keyword dengan <mark>. Terima teks yang SUDAH di-escape."""
    if not keyword or not teks_escaped:
        return teks_escaped
    pola = re.compile(re.escape(html_mod.escape(keyword)), re.IGNORECASE)
    return pola.sub(lambda m: f"<mark>{m.group(0)}</mark>", teks_escaped)


def kartu_artikel(
    r: dict,
    display: dict[str, str],
    warna: dict[str, str],
    keyword: str | None = None,
) -> str:
    """Satu kartu artikel sebagai string HTML (sudah aman dari injeksi HTML)."""
    judul = sorot(html_mod.escape((r["title"] or "(tanpa judul)").strip()), keyword)
    ringkas = sorot(html_mod.escape(fmt.bersihkan_html(r["summary"])[:280]), keyword)
    url = html_mod.escape(r["url"], quote=True)
    badge = html_mod.escape(display.get(r["media"], r["media"]))
    col = warna.get(r["media"], "#9aa0a6")
    pub = r["published_at"]
    isi = (
        f'<div class="mm-card">'
        f'<div><span class="mm-badge" style="background:{col}">{badge}</span>'
        f'<span class="mm-time" title="{html_mod.escape(fmt.format_wita(pub))}">'
        f"{html_mod.escape(fmt.waktu_relatif(pub))}</span>"
    )
    if r.get("sentimen"):
        isi += pill(r["sentimen"],
                    WARNA_SENTIMEN.get(r["sentimen"], "#8ea0c9"))
    if r.get("risiko"):
        isi += pill(r["risiko"], WARNA_RISIKO.get(r["risiko"], "#8ea0c9"))
    isi += "</div>"
    isi += (f'<div class="mm-title"><a href="{url}" target="_blank">{judul}</a>'
            f"</div>")
    if ringkas:
        isi += f'<div class="mm-summary">{ringkas}</div>'
    return isi + "</div>"
