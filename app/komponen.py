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
</style>
"""


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
        f"{html_mod.escape(fmt.waktu_relatif(pub))}</span></div>"
        f'<div class="mm-title"><a href="{url}" target="_blank">{judul}</a></div>'
    )
    if ringkas:
        isi += f'<div class="mm-summary">{ringkas}</div>'
    return isi + "</div>"
