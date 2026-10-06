"""Ekspor statis dashboard ke docs/index.html untuk GitHub Pages.

Jalankan dari root proyek (venv aktif):
    python scripts/ekspor_statis.py [--out docs/index.html]

Membaca DB lokal lalu me-render SATU file HTML mandiri (tanpa JS, tanpa
dependensi eksternal): grid 15 media + KPI + Respons Publik per topik.
Alur publikasi: jalankan script -> commit docs/ -> push -> GitHub Pages
(source: main, folder /docs) otomatis menayangkan.

Aman diulang-ulang (idempoten): output selalu ditulis ulang penuh.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, ".")

from src.common.config import load_media, load_settings
from src.common.text import bersihkan_html
from src.storage import repository

WIB = timezone(timedelta(hours=7))
WARNA_RISIKO = {"Rendah": "#40c057", "Sedang": "#fab005", "Tinggi": "#fa5252"}
WARNA_SENTIMEN = {"positif": "#40c057", "netral": "#8ea0c9",
                  "negatif": "#fa5252"}
DISCLAIMER = ("Disclaimer: Tidak 100% valid, ini hanya berupa ringkasan "
              "otomatis. Gunakan informasi ini dengan bijak. Algoritma "
              "berdasarkan rumus yang saya buat, dan belum tentu valid.")


def _esc(s) -> str:
    return html_mod.escape(str(s or ""))


def _ringkas(teks: str | None, n: int = 140) -> str:
    t = bersihkan_html(teks or "")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def _badge_risiko(risiko, skor) -> str:
    if skor is None:
        return '<span class="bd b-abu">Risiko: belum dianalisa</span>'
    w = WARNA_RISIKO.get(risiko, "#8ea0c9")
    return (f'<span class="bd" style="background:{w}22;color:{w};'
            f'border:1px solid {w}55">Risiko: {_esc(risiko)} - '
            f'{skor:g}</span>')


def _badge_sentimen(sentimen) -> str:
    if not sentimen:
        return '<span class="bd b-abu">Sentimen: belum dianalisa</span>'
    w = WARNA_SENTIMEN.get(sentimen, "#8ea0c9")
    return (f'<span class="bd" style="background:{w}22;color:{w};'
            f'border:1px solid {w}55">Sentimen: {_esc(sentimen).capitalize()}'
            f'</span>')


def _sparkline(harian: list[dict], w: int = 280, h: int = 56) -> str:
    """Sparkline SVG dari skor minat harian (rata-rata semua keyword)."""
    by_tgl: dict[str, list[float]] = {}
    for r in harian:
        by_tgl.setdefault(r["tanggal"], []).append(r["skor"])
    tgls = sorted(by_tgl)
    if len(tgls) < 2:
        return '<div class="muted">data tren belum cukup</div>'
    vals = [sum(by_tgl[t]) / len(by_tgl[t]) for t in tgls]
    vmax = max(vals) or 1
    pts = []
    for i, v in enumerate(vals):
        x = i / (len(vals) - 1) * (w - 4) + 2
        y = h - 4 - (v / vmax) * (h - 10)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<polyline points="{" ".join(pts)}" fill="none" '
        f'stroke="#4dabf7" stroke-width="2"/></svg>'
        f'<div class="muted">minat rata-rata {sum(vals)/len(vals):.0f}/100 · '
        f'puncak {max(vals):.0f}</div>'
    )


def _kartu_media(m: dict, arts: list[dict]) -> str:
    items = []
    for a in arts:
        items.append(
            '<div class="item">'
            f'<a class="t" href="{_esc(a["url"])}" target="_blank" '
            f'rel="noopener">{_esc(a["title"])}</a>'
            f'<div class="sum">{_esc(_ringkas(a.get("summary")))}</div>'
            '<div class="bds">'
            f'{_badge_risiko(a.get("risiko"), a.get("risiko_skor"))}'
            f'{_badge_sentimen(a.get("sentimen"))}'
            '</div></div>'
        )
    return (
        f'<section class="card">'
        f'<header><span class="dot" style="background:{m["color"]}"></span>'
        f'<b>{_esc(m["display"])}</b>'
        f'<span class="cnt">{len(arts)} berita</span></header>'
        f'<div class="items">{"".join(items) or "<div class=muted>kosong</div>"}</div>'
        f'</section>'
    )


def _seksi_topik(db_path, topik: str) -> str:
    videos = repository.get_youtube_videos(db_path, topik, limit=5)
    harian = repository.get_trends_harian(db_path, topik)
    ringkas = repository.get_trends_ringkas_terbaru(db_path, topik)
    tot_v = sum(v["view_count"] for v in videos)
    tot_k = sum(v["comment_count"] for v in videos)
    vids = "".join(
        f'<div class="item"><div class="t">{_esc(v["title"][:80])}</div>'
        f'<div class="muted">{_esc(v["channel"])} · '
        f'{v["view_count"]:,} views · {v["comment_count"]:,} komentar</div></div>'
        for v in videos
    )
    daerah = ""
    if ringkas and ringkas["per_daerah"]:
        top_d = ringkas["per_daerah"][:5]
        kw0 = next((k for k in top_d[0] if k != "daerah"), None)
        if kw0:
            maks = max((d.get(kw0, 0) for d in top_d), default=1) or 1
            daerah = "".join(
                f'<div class="bar"><span>{_esc(d["daerah"])}</span>'
                f'<div class="track"><div class="fill" '
                f'style="width:{d.get(kw0, 0)/maks*100:.0f}%"></div></div>'
                f'<b>{d.get(kw0, 0)}</b></div>'
                for d in top_d
            )
    frasa = []
    if ringkas:
        for v in ringkas["terkait"].values():
            frasa += [q["query"] for q in v.get("rising", [])[:5]]
    return (
        f'<section class="topik" id="t-{_esc(topik)}">'
        f'<h3>{_esc(topik)}</h3>'
        f'<div class="kpis">'
        f'<div class="kpi"><div class="v">{tot_v:,}</div>'
        f'<div class="l">views YouTube</div></div>'
        f'<div class="kpi"><div class="v">{tot_k:,}</div>'
        f'<div class="l">komentar</div></div>'
        f'<div class="kpi"><div class="v">{len(videos)}</div>'
        f'<div class="l">video teratas</div></div>'
        f'</div>'
        f'<div class="cols"><div><h4>Video teratas</h4>{vids or "<div class=muted>kosong</div>"}</div>'
        f'<div><h4>Minat pencarian</h4>{_sparkline(harian)}'
        f'<h4>Daerah teratas</h4>{daerah or "<div class=muted>kosong</div>"}'
        f'<h4>Frasa naik</h4><ul>{"".join(f"<li>{_esc(q)}</li>" for q in frasa[:8]) or "<li class=muted>kosong</li>"}</ul>'
        f'</div></div></section>'
    )


CSS = """
*{box-sizing:border-box}
body{background:#0a0e1a;color:#e6ebf5;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;padding:0 16px 40px}
.wrap{max-width:1280px;margin:0 auto}
.hero{padding:28px 4px 8px;display:flex;justify-content:space-between;align-items:end;flex-wrap:wrap;gap:8px}
.hero h1{margin:0;font-size:2rem}
.hero .tag{color:#8ea0c9;letter-spacing:2px;font-size:.75rem}
.hero .upd{color:#9ca3af;font-size:.85rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.kpi{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:12px 16px}
.kpi .v{font-size:1.5rem;font-weight:700}
.kpi .l{font-size:.75rem;color:#9ca3af}
h2.sec{margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid #1f2937}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:#0d1526;border:1px solid #1f2937;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card header{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #1f2937}
.dot{width:10px;height:10px;border-radius:50%}
.cnt{margin-left:auto;color:#9ca3af;font-size:.75rem}
.items{max-height:380px;overflow-y:auto;padding:6px 12px}
.item{padding:10px 4px;border-bottom:1px solid #16202f}
.item:last-child{border-bottom:none}
.item .t{font-weight:600;color:#e6ebf5;text-decoration:none;font-size:.92rem}
.item .t:hover{color:#7dd3fc}
.item .sum{color:#9ca3af;font-size:.8rem;margin:4px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bds{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.bd{font-size:.7rem;padding:2px 8px;border-radius:20px}
.b-abu{background:#1f2937;color:#9ca3af;border:1px solid #374151}
.muted{color:#6b7280;font-size:.8rem}
.topik{background:#0d1526;border:1px solid #1f2937;border-radius:12px;padding:18px;margin-bottom:16px}
.topik h3{margin:0 0 4px;font-size:1.3rem;text-transform:capitalize}
.topik .cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:8px}
@media(max-width:800px){.topik .cols{grid-template-columns:1fr}}
.topik h4{margin:12px 0 6px;color:#9ca3af;font-size:.85rem}
.bar{display:flex;align-items:center;gap:8px;font-size:.8rem;margin:4px 0}
.bar span{width:130px;color:#c6d2e8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .track{flex:1;background:#1f2937;border-radius:4px;height:8px}
.bar .fill{background:#4dabf7;border-radius:4px;height:8px}
.bar b{width:36px;text-align:right}
ul{margin:4px 0;padding-left:18px;font-size:.85rem;color:#c6d2e8}
footer{margin-top:32px;padding-top:16px;border-top:1px solid #1f2937;color:#6b7280;font-size:.8rem;text-align:center}
a{color:#7dd3fc}
"""


def _kpi(nilai, label) -> str:
    return (f'<div class="kpi"><div class="v">{nilai}</div>'
            f'<div class="l">{label}</div></div>')


def ekspor(db_path, out_path: Path, settings: dict,
           media_list: list[dict]) -> dict:
    """Render docs/index.html dari DB. Kembalikan statistik."""
    repository.init_db(db_path)
    per_media = repository.get_artikel_per_media(db_path, limit_per_media=8)
    dist_s = repository.distribusi_sentimen(db_path)
    dist_r = repository.distribusi_risiko(db_path)
    total = sum(repository.count_by_media(db_path).values())
    status = repository.get_media_last_status(db_path)
    ok = sum(1 for m in media_list
             if status.get(m["name"], {}).get("status") == "ok")
    topiks = repository.daftar_topik_respon(db_path)

    now = datetime.now(WIB).strftime("%d %b %Y %H:%M WIB")
    kpis = "".join([
        _kpi(f"{total:,}".replace(",", "."), "total artikel"),
        _kpi(f"{ok}/{len(media_list)}", "media OK"),
        _kpi(f"{dist_s.get('positif', 0)}/{dist_s.get('netral', 0)}/"
             f"{dist_s.get('negatif', 0)}", "sentimen +/n/−"),
        _kpi(f"{repository.rata_risiko(db_path):g}/100", "risiko rata-rata"),
    ])
    cards = "".join(
        _kartu_media(m, per_media.get(m["name"], []))
        for m in media_list
    )
    seksis = "".join(_seksi_topik(db_path, t) for t in topiks)

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Media Monitor — Pantau Media, Sentimen & Risiko</title>
<style>{CSS}</style>
</head>
<body><div class="wrap">
<div class="hero">
<div><div class="tag">PANTAU MEDIA · SENTIMEN & RISIKO</div><h1>Media Monitor</h1></div>
<div class="upd">Diperbarui: {now} · ekspor statis</div>
</div>
<div class="kpis">{kpis}</div>
<h2 class="sec">Berita per media</h2>
<div class="grid">{cards}</div>
<h2 class="sec">Respons Publik</h2>
{seksis or '<div class="muted">Belum ada data respons publik.</div>'}
<footer>{_esc(DISCLAIMER)}</footer>
</div></body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {"file": str(out_path), "size": len(html),
            "media": len(media_list), "topik": len(topiks)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/index.html")
    args = ap.parse_args()
    settings = load_settings()
    db_path = settings["storage"]["db_path"]
    if not Path(db_path).exists():
        print(f"Database tidak ada: {db_path}")
        return 1
    stats = ekspor(db_path, Path(args.out), settings, load_media())
    print(f"Diekspor: {stats['file']} ({stats['size']:,} bytes, "
          f"{stats['media']} media, {stats['topik']} topik)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
