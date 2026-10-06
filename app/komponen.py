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


def item_berita_grid(r: dict, max_judul: int = 110,
                      max_ringkas: int = 130) -> str:
    """Satu item berita untuk grid kolom media (ala referensi).

    Border kiri berwarna sesuai level risiko; badge sentimen + risiko;
    judul + cuplikan ringkasan di bawahnya.
    """
    col = WARNA_RISIKO.get(r.get("risiko"), "#8ea0c9")
    judul = html_mod.escape((r.get("title") or "(tanpa judul)")[:max_judul])
    sum_mentah = fmt.bersihkan_html(r.get("summary") or "").strip()
    ringkas = html_mod.escape(sum_mentah[:max_ringkas])
    if len(sum_mentah) > max_ringkas:
        ringkas += "…"
    isi = (f'<div class="mi-item" style="border-left-color:{col}">'
           f'<div>')
    if r.get("risiko"):
        isi += pill(r["risiko"], WARNA_RISIKO.get(r["risiko"], "#8ea0c9"))
    if r.get("sentimen"):
        isi += pill(r["sentimen"],
                    WARNA_SENTIMEN.get(r["sentimen"], "#8ea0c9"))
    isi += f'</div><div class="mi-item-title">{judul}</div>'
    if ringkas:
        isi += f'<div class="mi-item-sum">{ringkas}</div>'
    isi += '</div>'
    return isi


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
