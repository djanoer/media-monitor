"""Ekspor statis dashboard ke docs/index.html untuk GitHub Pages.

Jalankan dari root proyek (venv aktif):
    python scripts/ekspor_statis.py [--out docs/index.html]

Membaca DB lokal lalu me-render SATU file HTML mandiri (tanpa dependensi
eksternal): hero + KPI + pil media + bar distribusi + grid berita per media
+ Respons Publik per topik. Alur publikasi: jalankan script -> commit docs/
-> push -> GitHub Pages (source: main, folder /docs) otomatis menayangkan.

Aman diulang-ulang (idempoten): output selalu ditulis ulang penuh.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, ".")

from src.common.config import load_media, load_settings
from src.common.text import bersihkan_html
from src.processing.llm_groq import RateLimitError, ringkas_artikel
from src.processing.risiko import komponen_risiko
from src.processing.sentimen import kata_berpengaruh
from src.processing.verification import cek_headline
from src.storage import repository

WIB = timezone(timedelta(hours=7))
UTC = timezone.utc
WARNA_RISIKO = {"Rendah": "#34d399", "Sedang": "#fbbf24", "Tinggi": "#f87171"}
WARNA_SENTIMEN = {"positif": "#34d399", "netral": "#9aa5c4",
                  "negatif": "#f87171"}
BULAN_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
            "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DISCLAIMER = ("Disclaimer: Tidak 100% valid, ini hanya berupa ringkasan "
              "otomatis. Gunakan informasi ini dengan bijak. Algoritma "
              "berdasarkan rumus yang saya buat, dan belum tentu valid.")


def _esc(s) -> str:
    return html_mod.escape(str(s or ""))


def _ribu(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".")


def _tgl_id(dt: datetime) -> str:
    return (f"{dt.day} {BULAN_ID[dt.month - 1]} {dt.year}, "
            f"{dt.strftime('%H:%M')} WIB")


def _waktu_artikel(iso: str | None) -> str:
    """'2026-10-06T12:00:00+00:00' -> '6 Okt 2026, 19:00 WIB' (pendek: '6 Okt, 19:00')."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    w = dt.astimezone(WIB)
    return f"{w.day} {BULAN_ID[w.month - 1]}, {w.strftime('%H:%M')}"


def _rel_id(ms: float) -> str:
    m = int(ms // 60000)
    if m < 1:
        return "baru saja"
    if m < 60:
        return f"{m} mnt lalu"
    h = m // 60
    if h < 24:
        return f"{h} jam lalu"
    return f"{h // 24} hari lalu"


def _ringkas(teks: str | None, n: int = 140) -> str:
    t = bersihkan_html(teks or "")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def _bar(segs: list[tuple[int, str]], cls: str = "mbar") -> str:
    """Stacked bar horizontal dari [(nilai, warna)]."""
    tot = sum(v for v, _ in segs) or 1
    divs = "".join(
        f'<div style="width:{v / tot * 100:.1f}%;background:{w}"></div>'
        for v, w in segs if v > 0)
    return f'<div class="{cls}">{divs}</div>'


def _badge_risiko(risiko, skor) -> str:
    if skor is None:
        return '<span class="bd b-abu">Risiko: belum dianalisa</span>'
    w = WARNA_RISIKO.get(risiko, "#9aa5c4")
    return (f'<span class="bd" style="background:{w}22;color:{w};'
            f'border:1px solid {w}55">Risiko: {_esc(risiko)} - '
            f'{skor:g}</span>')


def _badge_sentimen(sentimen) -> str:
    if not sentimen:
        return '<span class="bd b-abu">Sentimen: belum dianalisa</span>'
    w = WARNA_SENTIMEN.get(sentimen, "#9aa5c4")
    return (f'<span class="bd" style="background:{w}22;color:{w};'
            f'border:1px solid {w}55">Sentimen: {_esc(sentimen).capitalize()}'
            f'</span>')


def _fmt_skor(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) else "-"


def _kalimat_awal(a: dict, max_kalimat: int, max_len: int) -> str:
    """Ambil N kalimat pertama isi_lengkap untuk ringkasan baca.

    '' bila isi belum diunduh (pemanggil menyembunyikan seksi).
    """
    isi = (a.get("isi_lengkap") or "").strip()
    if not isi:
        return ""
    kal = [k.strip() for k in re.split(r"(?<=[.!?])\s+", isi) if k.strip()]
    teks = " ".join(kal[:max_kalimat]).strip()
    if len(teks) > max_len:
        teks = teks[:max_len].rsplit(" ", 1)[0] + "…"
    return teks


def _teks_dianalisis(a: dict) -> str:
    """Teks yang BENAR-BENAR dihitung sistem (sama persis dgn siklus_analisa
    di src/processing/analisa.py): judul + summary RSS, bukan isi_lengkap.
    """
    return bersihkan_html(a.get("summary") or "").strip()


def _skala_risiko_html(lvl: str) -> str:
    """Baris skala risiko ala referensi Penjelasan Analisis."""
    rows = []
    for nama, rentang, ket in [
            ("Rendah", "0–34",
             "Minim potensi dampak buruk atau kerugian berarti; "
             "umumnya kabar biasa/harian."),
            ("Sedang", "35–64",
             "Berpotensi menimbulkan keresahan atau dampak sedang — "
             "perlu diwaspadai."),
            ("Tinggi", "65–100",
             "Isu berbahaya/urgent: bencana, kecelakaan, krisis, "
             "konflik, korupsi besar.")]:
        w = WARNA_RISIKO.get(nama, "#9aa5c4")
        on = ' style="border-color:%s"' % w if nama == lvl else ""
        rows.append(
            f'<div class="skala{" on" if nama == lvl else ""}"{on}>'
            f'<span class="bd" style="background:{w}22;color:{w};'
            f'border:1px solid {w}55">{nama}</span> '
            f'Skor risiko {rentang}. {_esc(ket)}</div>')
    return "".join(rows)


def _skala_sentimen_html(sent: str) -> str:
    """Baris skala sentimen ala referensi Penjelasan Analisis."""
    rows = []
    for nama, ket in [
            ("positif",
             "Nuansa baik lebih dominan (naik, untung, sukses, tumbuh, "
             "menang, capai). Skor sentimen ≥ +2,0."),
            ("netral",
             "Isi berimbang/objektif; tidak condong ke positif maupun "
             "negatif. Skor antara -2,0 sampai +2,0."),
            ("negatif",
             "Nuansa buruk lebih dominan (krisis, korupsi, jatuh, tewas, "
             "bencana, gagal). Skor sentimen ≤ -2,0.")]:
        w = WARNA_SENTIMEN.get(nama, "#9aa5c4")
        on = ' style="border-color:%s"' % w if nama == sent else ""
        rows.append(
            f'<div class="skala{" on" if nama == sent else ""}"{on}>'
            f'<span class="bd" style="background:{w}22;color:{w};'
            f'border:1px solid {w}55">{nama.capitalize()}</span> '
            f'{_esc(ket)}</div>')
    return "".join(rows)


def _isi_ringkasan_ai(db_path, settings: dict) -> int:
    """Isi cache ringkasan_ai via API OpenAI-compatible untuk artikel terbaru.

    Provider: TOPTOOLS_API_KEY (prioritas) atau GROQ_API_KEY (fallback).
    Best-effort: tanpa key / gagal / 429 -> berhenti diam-diam, ekspor tetap
    jalan dengan ringkasan ekstraktif. Kembalikan jumlah yg berhasil.
    """
    cfg = settings.get("ringkasan_ai") or {}
    if not cfg.get("aktif", True):
        return 0
    from src.processing.llm_groq import (
        API_URL_GROQ, API_URL_TOPTOOLS, MODEL_DEFAULT_TOPTOOLS,
    )
    api_key = os.environ.get("TOPTOOLS_API_KEY", "").strip()
    api_url = os.environ.get("TOPTOOLS_API_URL", "").strip() or API_URL_TOPTOOLS
    env_model = os.environ.get("TOPTOOLS_MODEL", "").strip() or MODEL_DEFAULT_TOPTOOLS
    if api_key:
        provider = "Top Tools AI"
    else:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        api_url = API_URL_GROQ
        env_model = ""
        provider = "Groq"
    if not api_key:
        print("Ringkasan AI dilewati (tidak ada API key)", flush=True)
        return 0
    print(f"Ringkasan AI via {provider}...", flush=True)
    repository.migrate_ringkasan_ai(db_path)
    maks_umur = int(cfg.get("maks_umur_jam", 24))
    antre = repository.artikel_tanpa_ringkasan_ai(
        db_path, limit=int(cfg.get("maks_artikel", 30)),
        maks_umur_jam=maks_umur)
    if not antre:
        return 0
    jeda = float(cfg.get("jeda_detik", 3))
    model = env_model or cfg.get("model", "qwen/qwen3.8-27b")
    max_tokens = int(cfg.get("max_tokens", 300))
    max_retry = int(cfg.get("retry_429", 3))
    tunggu_awal = float(cfg.get("tunggu_awal_detik", 60))
    tunggu_maks = float(cfg.get("tunggu_maks_detik", 300))
    total = len(antre)
    print(f"Mengisi ringkasan AI ({total} artikel)...", flush=True)
    n = 0
    for a in antre:
        # Percobaan bertahap: 429 -> tunggu (60, 120, 240 dtk...) lalu coba
        # lagi artikel yg sama; gagal lain -> berhenti, lanjut ekspor berikut.
        teks = None
        tunggu = tunggu_awal
        for attempt in range(max_retry + 1):
            try:
                teks = ringkas_artikel(
                    a.get("title") or "", a.get("isi_lengkap") or "",
                    api_key, model=model, max_tokens=max_tokens,
                    api_url=api_url)
                break
            except RateLimitError:
                if attempt >= max_retry:
                    print(f"  429 {max_retry + 1}x beruntun, berhenti "
                          f"({n}/{total})", flush=True)
                    return n
                print(f"  429 -> tunggu {tunggu:g} dtk lalu coba lagi",
                      flush=True)
                time.sleep(tunggu)
                tunggu = min(tunggu * 2, tunggu_maks)
        if not teks:
            break
        repository.simpan_ringkasan_ai(db_path, a["url"], teks)
        n += 1
        if n % 5 == 0 or n == total:
            print(f"  ringkasan AI: {n}/{total}", flush=True)
        time.sleep(jeda)
    return n


def _detail_artikel(a: dict, settings: dict, verdicts: dict,
                    display: str) -> dict:
    """Bahan modal detail artikel (precompute, ala dialog lokal)."""
    analisa_cfg = settings.get("analisa", {})
    judul = a.get("title") or ""
    # Teks yang benar-benar dihitung (sinkron dgn siklus_analisa):
    # judul + summary RSS.
    ringkas = _teks_dianalisis(a)
    kata = kata_berpengaruh(
        judul, ringkas,
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
    flags = cek_headline(judul, ringkas, penanda)
    komp = komponen_risiko(sent, "bombastis" in flags,
                           verdicts.get(a.get("url"), []), analisa_cfg)
    rincian = "; ".join(
        f"{ket} {'+' if d >= 0 else '−'}{abs(d):g}" for ket, d in komp)
    ai = (f"Sentimen {sent} (skor {_fmt_skor(a.get('sentimen_skor'))}): "
          f"{alasan}. Risiko {a.get('risiko') or '-'} "
          f"(skor {_fmt_skor(a.get('risiko_skor'))}/100): {rincian}.")

    lvl = a.get("risiko") or "Rendah"
    # Skala ala referensi "Penjelasan Analisis" (Bor).
    tanya = (f"Kenapa berita ini {sent} dengan risiko "
             f"{(a.get('risiko') or 'rendah').lower()}?")
    why = (f'<div class="mai"><b>🤖 {_esc(tanya)}</b><br>AI: {_esc(ai)}</div>'
           f'<div class="skhead">🛡 SKALA RISIKO (0–100)</div>'
           + _skala_risiko_html(lvl) +
           f'<div class="skhead">💬 SKALA SENTIMEN</div>'
           + _skala_sentimen_html(sent))

    # Ringkasan baca: ringkasan AI (cache) bila ada, else ekstraktif min 3 kalimat.
    ringkasan_ai = (a.get("ringkasan_ai") or "").strip()
    ringkasan = ringkasan_ai or _kalimat_awal(a, max_kalimat=5, max_len=900)
    return {
        "media": display,
        "url": a.get("url") or "",
        "title": a.get("title") or "(tanpa judul)",
        "badge_r": _badge_risiko(a.get("risiko"), a.get("risiko_skor")),
        "badge_s": _badge_sentimen(a.get("sentimen")),
        "ai": ai,
        "why": why,
        "pub": a.get("published_at") or "",
        "ringkasan": [ringkasan] if ringkasan else [],
        "ringkasan_ai": bool(ringkasan_ai),
        "dianalisis": [ringkas] if ringkas else [],
    }


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


def _metrik(db_path, media_list: list[dict]) -> dict:
    """Kumpulkan semua angka hero/KPI dari DB (testable)."""
    repository.init_db(db_path)
    total = sum(repository.count_by_media(db_path).values())
    status = repository.get_media_last_status(db_path)
    ok = sum(1 for m in media_list
             if status.get(m["name"], {}).get("status") == "ok")
    sejak = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    d24 = repository.count_articles_since(db_path, sejak)
    dist_s = repository.distribusi_sentimen(db_path)
    ps, nt, ng = (dist_s.get("positif", 0), dist_s.get("netral", 0),
                  dist_s.get("negatif", 0))
    avg_s = round((ps - ng) / total * 100) if total else 0
    kat_s = ("Positif" if avg_s >= 15 else
             "Negatif" if avg_s <= -15 else "Netral")
    dist_r = repository.distribusi_risiko(db_path)
    rr, rs, rt = (dist_r.get("Rendah", 0), dist_r.get("Sedang", 0),
                  dist_r.get("Tinggi", 0))
    avg_r = repository.rata_risiko(db_path)
    kat_r = ("Tinggi" if avg_r >= 55 else
             "Sedang" if avg_r >= 22 else "Rendah")
    repository.migrate_isi_lengkap(db_path)
    repository.migrate_ringkasan_ai(db_path)
    nm = len(media_list)
    ok_isi = repository.count_isi_lengkap(db_path)
    last = repository.get_last_run(db_path)
    umur_ms, sehat = None, "unknown"
    if last and last.get("finished_at"):
        fin = datetime.fromisoformat(last["finished_at"])
        if fin.tzinfo is None:
            fin = fin.replace(tzinfo=UTC)
        umur_ms = (datetime.now(UTC) - fin).total_seconds() * 1000
        sehat = ("ok" if umur_ms <= 2 * 3600 * 1000
                 else "waspada" if umur_ms <= 24 * 3600 * 1000
                 else "mati")
    return {
        "total": total, "ok": ok, "n_media": len(media_list), "d24": d24,
        "ps": ps, "nt": nt, "ng": ng, "avg_s": avg_s, "kat_s": kat_s,
        "rr": rr, "rs": rs, "rt": rt, "avg_r": avg_r, "kat_r": kat_r,
        "nm": nm, "ok_isi": ok_isi,
        "umur_ms": umur_ms, "sehat": sehat,
        "status": status,
    }


def _kartu_media(m: dict, items: list[tuple[int, dict]]) -> str:
    rows = []
    for idx, a in items:
        wr = WARNA_RISIKO.get(a.get("risiko"), "#2a3352") \
            if a.get("risiko_skor") is not None else "#2a3352"
        wkt = _waktu_artikel(a.get("published_at"))
        wkt_html = f'<div class="wkt">{_esc(wkt)}</div>' if wkt else ""
        rows.append(
            f'<div class="item" style="border-left:3px solid {wr}">'
            f'{wkt_html}'
            f'<button class="tlink" data-i="{idx}">'
            f'{_esc(a["title"])}</button>'
            f'<div class="sum">{_esc(_ringkas(a.get("summary")))}</div>'
            '<div class="bds">'
            f'{wkt_html}'
            f'{_badge_risiko(a.get("risiko"), a.get("risiko_skor"))}'
            f'{_badge_sentimen(a.get("sentimen"))}'
            '</div></div>'
        )
    return (
        f'<section class="card">'
        f'<header><span class="dot" style="background:{m["color"]}"></span>'
        f'<b>{_esc(m["display"])}</b>'
        f'<span class="cnt">{len(items)} berita</span></header>'
        f'<div class="items">{"".join(rows) or "<div class=muted>kosong</div>"}</div>'
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
        f'<div class="kpi"><div class="v">{_ribu(tot_v)}</div>'
        f'<div class="l">views YouTube</div></div>'
        f'<div class="kpi"><div class="v">{_ribu(tot_k)}</div>'
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
body{background:#0a0f1e;color:#e6ebf5;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;padding:0 20px 48px}
.wrap{max-width:1280px;margin:0 auto}
.hero{padding:32px 4px 20px;display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px}
.hero h1{margin:2px 0 6px;font-size:2.4rem;font-weight:800;display:flex;align-items:center;gap:14px}
.hero .tag{color:#8ea0c9;letter-spacing:3px;font-size:.75rem}
.hright{text-align:right}
.hright .dlab{color:#8ea0c9;letter-spacing:3px;font-size:.7rem}
.hright .dval{font-size:1.05rem;font-weight:700;margin:2px 0}
.hright .dval .relt{color:#9ca3af;font-weight:400;font-size:.85rem}
.sched{font-size:.85rem;color:#9ca3af;display:flex;align-items:center;gap:8px;justify-content:flex-end}
.sdot{width:9px;height:9px;border-radius:50%;display:inline-block}
.pulse{animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 #34d39966}70%{box-shadow:0 0 0 9px transparent}100%{box-shadow:0 0 0 0 transparent}}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:4px 0 18px}
@media(max-width:800px){
.kpis{grid-template-columns:1fr}
.hero{flex-direction:column;align-items:stretch;padding:24px 4px 12px}
.hero h1{font-size:1.9rem}
.hright{text-align:left;background:#0d1326;border:1px solid #1e2745;border-radius:12px;padding:12px 14px}
.sched{justify-content:flex-start}
}
.kpi{background:#131a30;border:1px solid #1e2745;border-radius:16px;padding:20px 22px}
.kpi .v{font-size:2.2rem;font-weight:800}
.kpi .v .per{font-size:1.1rem;color:#8ea0c9;font-weight:600}
.kpi .l{font-size:.72rem;color:#8ea0c9;letter-spacing:2px;margin:2px 0 8px}
.kpi .s{font-size:.85rem;color:#c6d2e8;margin-bottom:10px}
.kpi .s b{color:#e6ebf5}
.kpi-btn{font:inherit;color:inherit;text-align:left;cursor:pointer}
.kpi-btn:hover{border-color:#33406b;transform:translateY(-2px)}
.mbar{display:flex;height:8px;border-radius:4px;overflow:hidden;background:#232c4d}
.mbar div{height:100%}
.dist{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:8px}
.dist>div{background:#101737;border:1px solid #1e2745;border-radius:12px;padding:16px}
@media(max-width:800px){.dist{grid-template-columns:1fr}}
.dhead{font-size:.72rem;color:#8ea0c9;letter-spacing:2px;margin-bottom:8px}
.legend{display:flex;gap:16px;font-size:.82rem;color:#c6d2e8;margin-bottom:8px;flex-wrap:wrap}
.legend i{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
.dbar{display:flex;height:8px;border-radius:4px;overflow:hidden;background:#232c4d}
.dbar div{height:100%}
h2.sec{margin:30px 0 14px;font-size:1.15rem;display:flex;align-items:center;gap:10px}
h2.sec::before{content:"";width:4px;height:1.2em;background:linear-gradient(#4dabf7,#9775fa);border-radius:2px}
.topnav{position:sticky;top:0;z-index:10;background:#0a0f1ee6;backdrop-filter:blur(8px);padding:10px 4px;display:flex;gap:18px;border-bottom:1px solid #1e2745;margin:0 -20px;padding-left:24px}
.topnav a{color:#9ca3af;text-decoration:none;font-size:.85rem;font-weight:600}
.topnav a:hover{color:#7dd3fc}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media(max-width:1200px){.grid{grid-template-columns:repeat(3,1fr);}}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr);}}
@media(max-width:600px){.grid{grid-template-columns:1fr;}}
.card{background:#0d1326;border:1px solid #1e2745;border-radius:14px;overflow:hidden;display:flex;flex-direction:column;transition:transform .15s ease,border-color .15s ease}
.card:hover{transform:translateY(-3px);border-color:#33406b}
.card header{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #1e2745}
.dot{width:10px;height:10px;border-radius:50%}
.cnt{margin-left:auto;color:#9ca3af;font-size:.75rem}
.items{max-height:380px;overflow-y:auto;padding:6px 12px}
.item{padding:10px 4px 10px 10px;border-bottom:1px solid #16202f;border-radius:0 6px 6px 0}
.item:last-child{border-bottom:none}
.item .t{font-weight:600;color:#e6ebf5;text-decoration:none;font-size:.92rem}
.item .t:hover{color:#7dd3fc}
.item .sum{color:#9ca3af;font-size:.8rem;margin:4px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bds{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px;align-items:center}
.item .wkt{font-size:.72rem;color:#8ea0c9;margin-bottom:2px}
.bd{font-size:.7rem;padding:2px 8px;border-radius:20px}
.b-abu{background:#1f2937;color:#9ca3af;border:1px solid #374151}
.muted{color:#6b7280;font-size:.8rem}
.topik{background:#0d1326;border:1px solid #1e2745;border-radius:14px;padding:18px;margin-bottom:16px}
.topik h3{margin:0 0 4px;font-size:1.3rem;text-transform:capitalize}
.topik .cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:8px}
@media(max-width:800px){.topik .cols{grid-template-columns:1fr}}
.topik h4{margin:12px 0 6px;color:#9ca3af;font-size:.85rem}
.topik .kpis{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.topik .kpi{padding:12px 16px}
.topik .kpi .v{font-size:1.5rem}
.bar{display:flex;align-items:center;gap:8px;font-size:.8rem;margin:4px 0}
.bar span{width:130px;color:#c6d2e8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .track{flex:1;background:#232c4d;border-radius:4px;height:8px}
.bar .fill{background:#4dabf7;border-radius:4px;height:8px}
.bar b{width:36px;text-align:right}
ul{margin:4px 0;padding-left:18px;font-size:.85rem;color:#c6d2e8}
.tlink{background:none;border:none;padding:0;font:inherit;font-weight:600;color:#e6ebf5;text-align:left;cursor:pointer;font-size:.92rem;line-height:1.4}
.tlink:hover{color:#7dd3fc}
.mback{position:fixed;inset:0;background:#04060cd9;z-index:50;display:none;align-items:center;justify-content:center;padding:20px}
.mback.open{display:flex}
.modal{background:#131a30;border:1px solid #2a3352;border-radius:16px;max-width:760px;width:100%;max-height:88vh;overflow-y:auto;padding:22px 26px;position:relative}
.mx{position:absolute;top:12px;right:12px;width:32px;height:32px;border-radius:8px;border:1px solid #2a3352;background:#1a2240;color:#9ca3af;font-size:1rem;cursor:pointer}
.mx:hover{color:#e6ebf5;border-color:#3b4a7a}
.mhead{font-size:.9rem;color:#9ca3af;margin-bottom:10px;padding-right:36px}
.mhead b{color:#e6ebf5}
.mhead a{color:#7dd3fc;text-decoration:none;font-weight:600}
.mbadges{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.mwhy{background:none;border:none;color:#7dd3fc;font-size:.85rem;cursor:pointer;padding:4px 0;font-weight:600}
.mwhybody{margin:8px 0}
.mtitle{font-size:1.4rem;font-weight:700;margin:10px 0;line-height:1.35}
.mai{background:#1a2240;border:1px solid #2a3a66;border-radius:10px;padding:12px 14px;margin:12px 0;font-size:.9rem;line-height:1.6;color:#c6d2e8}
.mpub{color:#6b7280;font-size:.8rem;margin-bottom:12px}
.misi p{margin:0 0 14px;line-height:1.7;color:#dbe3f5;font-size:.82rem;text-align:justify}
.mseclbl{font-size:.72rem;letter-spacing:2px;color:#8ea0c9;margin:16px 0 6px}
.mring p{margin:0 0 10px;line-height:1.7;color:#dbe3f5;font-size:.92rem;text-align:justify}
.skala{border:1px solid #2a3352;border-radius:8px;padding:8px 12px;margin:6px 0;font-size:.85rem;color:#c6d2e8}
.skala.on{border-width:2px}
.skala b{color:#e6ebf5}
.skhead{font-weight:700;color:#7dd3fc;letter-spacing:1px;font-size:.82rem;margin:14px 0 4px}
footer{margin-top:36px;padding-top:16px;border-top:1px solid #1e2745;color:#6b7280;font-size:.8rem;text-align:center}
a{color:#7dd3fc}
"""


def _tanda_persen(v: int) -> str:
    if v > 0:
        return f"+{v}%"
    if v < 0:
        return f"−{abs(v)}%"
    return "0%"


def ekspor(db_path, out_path: Path, settings: dict,
           media_list: list[dict]) -> dict:
    """Render docs/index.html dari DB. Kembalikan statistik."""
    n_hapus = repository.hapus_artikel_lama(
        db_path, hari=int(settings.get("storage", {}).get("retensi_hari", 30)))
    if n_hapus:
        print(f"Retensi: {n_hapus} artikel >30 hari dihapus", flush=True)
    m = _metrik(db_path, media_list)
    n_ai = _isi_ringkasan_ai(db_path, settings)
    per_media = repository.get_artikel_per_media(db_path, limit_per_media=10)
    topiks = repository.daftar_topik_respon(db_path)

    now = datetime.now(WIB)
    now_iso = now.isoformat()

    # Kesehatan scheduler
    sehat_cfg = {"ok": ("#34d399", "Scheduler sehat", True),
                 "waspada": ("#fbbf24", "Siklus terakhir", False),
                 "mati": ("#6b7280", "Scheduler tidak aktif", False),
                 "unknown": ("#6b7280", "Belum ada siklus tercatat", False)}
    w_sch, teks_sch, pulse = sehat_cfg[m["sehat"]]
    rel_sch = (f" · {_rel_id(m['umur_ms'])}" if m["umur_ms"] is not None
               else "")

    emo_s = {"Positif": "😊", "Netral": "😐", "Negatif": "☹️"}.get(
        m["kat_s"], "😐")
    kpi1 = (
        f'<button class="kpi kpi-btn" id="kpi-total"><div class="v">📰 {_ribu(m["total"])}</div>'
        f'<div class="l">TOTAL ARTIKEL</div>'
        f'<div class="s"><b>{m["ok"]}/{m["n_media"]}</b> media OK · '
        f'<b>{_ribu(m["d24"])}</b> dalam 24 jam</div></button>')
    kpi2 = (
        f'<button class="kpi kpi-btn" id="kpi-sentimen"><div class="v">{emo_s} {_tanda_persen(m["avg_s"])}</div>'
        f'<div class="l">SENTIMEN RATA-RATA</div>'
        f'<div class="s">P {_ribu(m["ps"])} · N {_ribu(m["nt"])} · '
        f'Ng {_ribu(m["ng"])}</div>'
        f'{_bar([(m["ps"], WARNA_SENTIMEN["positif"]), (m["nt"], WARNA_SENTIMEN["netral"]), (m["ng"], WARNA_SENTIMEN["negatif"])])}</button>')
    kpi3 = (
        f'<button class="kpi kpi-btn" id="kpi-risiko"><div class="v">🛡 {m["avg_r"]:g}<span class="per">/100</span></div>'
        f'<div class="l">RISIKO RATA-RATA</div>'
        f'<div class="s">R {_ribu(m["rr"])} · S {_ribu(m["rs"])} · '
        f'T {_ribu(m["rt"])}</div>'
        f'{_bar([(m["rr"], WARNA_RISIKO["Rendah"]), (m["rs"], WARNA_RISIKO["Sedang"]), (m["rt"], WARNA_RISIKO["Tinggi"])])}</button>')

    # ---- modal "Kartu Statistik · Penjelasan" untuk tiap KPI ----
    gagal_isi = m["total"] - m["ok_isi"]
    pct_isi = round(m["ok_isi"] / m["total"] * 100) if m["total"] else 0
    stat_total = (
        f'<div class="mtitle">📰 Total Berita: {_ribu(m["total"])} · '
        f'{_ribu(m["nm"])} media</div>'
        f'<div class="mai"><b>📌 Apa maksudnya?</b><br>'
        f'Jumlah seluruh item berita yang berhasil dikumpulkan dari '
        f'<b>{_ribu(m["nm"])} sumber RSS</b> pada pemantauan ini '
        f'(berita terbaru dari tiap sumber).</div>'
        f'<div class="mai"><b>🤖 Soal sukses/gagal unduh isi</b><br>'
        f'Dari {_ribu(m["total"])} berita: <b>{_ribu(m["ok_isi"])}</b> ✅ '
        f'berhasil diunduh isi lengkapnya ({pct_isi}%); '
        f'<b>{_ribu(gagal_isi)}</b> ❌ gagal (mis. situs memblokir / '
        f'timeout) sehingga memakai <b>ringkasan/deskripsi dari RSS</b> '
        f'sebagai gantinya — berita tetap muncul di daftar.</div>')
    ps_pct = round(m["ps"] / m["total"] * 100) if m["total"] else 0
    ng_pct = round(m["ng"] / m["total"] * 100) if m["total"] else 0
    stat_sentimen = (
        f'<div class="mtitle">{emo_s} Sentimen Rata-rata: '
        f'{_tanda_persen(m["avg_s"])} · {m["kat_s"]}</div>'
        f'<div class="mai"><b>📌 Apa maksudnya?</b><br>'
        f'Selisih persentase berita positif dikurangi negatif dari '
        f'<b>{_ribu(m["total"])} berita</b>. '
        f'{_tanda_persen(m["avg_s"])} berarti kecenderungan seluruh '
        f'berita saat ini {m["kat_s"].lower()}.</div>'
        f'<div class="mai"><b>🤖 Kenapa nilainya '
        f'{_tanda_persen(m["avg_s"])}?</b><br>'
        f'Tiap berita dilabeli positif/netral/negatif dari perbandingan '
        f'kata positif vs negatif pada judul/isi (<b>leksikon</b>). '
        f'Nilai kartu ini = % positif − % negatif '
        f'({ps_pct}% − {ng_pct}%).<br>'
        f'Rincian semua berita:<br>'
        f'<span class="legend">'
        f'<span><i style="background:{WARNA_SENTIMEN["positif"]}"></i>'
        f'P {_ribu(m["ps"])}</span>'
        f'<span><i style="background:{WARNA_SENTIMEN["netral"]}"></i>'
        f'N {_ribu(m["nt"])}</span>'
        f'<span><i style="background:{WARNA_SENTIMEN["negatif"]}"></i>'
        f'Ng {_ribu(m["ng"])}</span></span></div>'
        f'<div class="skhead">💬 SKALA SENTIMEN</div>'
        f'{_skala_sentimen_html(m["kat_s"].lower())}'
        f'<div class="mai">💡 Baris yang disorot = kategori rata-rata '
        f'saat ini. Ini estimasi otomatis & <b>belum tentu 100% '
        f'valid</b>.</div>')
    stat_risiko = (
        f'<div class="mtitle">🛡 Risiko Rata-rata: {m["avg_r"]:g}/100 · '
        f'{m["kat_r"]}</div>'
        f'<div class="mai"><b>📌 Apa maksudnya?</b><br>'
        f'Rata-rata skor risiko dari <b>{_ribu(m["total"])} berita</b> '
        f'yang dipantau, dalam skala <b>0–100</b>. Makin tinggi angkanya, '
        f'makin banyak berita yang mengandung isu berisiko (bencana, '
        f'krisis, korupsi, kecelakaan, konflik, dsb).</div>'
        f'<div class="mai"><b>🤖 Kenapa nilainya {m["avg_r"]:g}/100?</b><br>'
        f'Tiap berita diberi <b>risk_score</b>: dihitung dari kata '
        f'negatif & kata berisiko pada judul/isi lewat <b>leksikon</b>. '
        f'Nilai di kartu ini = rata-rata dari {_ribu(m["total"])} skor '
        f'tsb.<br>Rincian semua berita:<br>'
        f'<span class="legend">'
        f'<span><i style="background:{WARNA_RISIKO["Rendah"]}"></i>'
        f'Rendah {_ribu(m["rr"])}</span>'
        f'<span><i style="background:{WARNA_RISIKO["Sedang"]}"></i>'
        f'Sedang {_ribu(m["rs"])}</span>'
        f'<span><i style="background:{WARNA_RISIKO["Tinggi"]}"></i>'
        f'Tinggi {_ribu(m["rt"])}</span></span></div>'
        f'<div class="skhead">🛡 SKALA RISIKO (0–100)</div>'
        f'{_skala_risiko_html(m["kat_r"])}'
        f'<div class="mai">💡 Baris yang disorot = kategori rata-rata '
        f'saat ini. Ini estimasi otomatis dan <b>belum tentu 100% valid'
        f'</b> — dipakai untuk memantau kecenderungan berita.</div>')
    stat_modals = "".join(
        f'<div class="mback" id="{mid}"><div class="modal" role="dialog" '
        f'aria-modal="true"><button class="mx" aria-label="Tutup">✕</button>'
        f'<div class="mhead"><b>Kartu Statistik</b><span> · Penjelasan</span>'
        f'</div>{body}</div></div>'
        for mid, body in [("mstat-t", stat_total),
                          ("mstat-s", stat_sentimen),
                          ("mstat-r", stat_risiko)])

    dist = (
        f'<div class="dist"><div>'
        f'<div class="dhead">SENTIMEN · {_ribu(m["total"])} BERITA</div>'
        f'<div class="legend">'
        f'<span><i style="background:{WARNA_SENTIMEN["positif"]}"></i>positif {_ribu(m["ps"])}</span>'
        f'<span><i style="background:{WARNA_SENTIMEN["netral"]}"></i>netral {_ribu(m["nt"])}</span>'
        f'<span><i style="background:{WARNA_SENTIMEN["negatif"]}"></i>negatif {_ribu(m["ng"])}</span>'
        f'</div>'
        f'{_bar([(m["ps"], WARNA_SENTIMEN["positif"]), (m["nt"], WARNA_SENTIMEN["netral"]), (m["ng"], WARNA_SENTIMEN["negatif"])], cls="dbar")}'
        f'</div><div>'
        f'<div class="dhead">RISIKO · {_ribu(m["total"])} BERITA</div>'
        f'<div class="legend">'
        f'<span><i style="background:{WARNA_RISIKO["Rendah"]}"></i>Rendah {_ribu(m["rr"])}</span>'
        f'<span><i style="background:{WARNA_RISIKO["Sedang"]}"></i>Sedang {_ribu(m["rs"])}</span>'
        f'<span><i style="background:{WARNA_RISIKO["Tinggi"]}"></i>Tinggi {_ribu(m["rt"])}</span>'
        f'</div>'
        f'{_bar([(m["rr"], WARNA_RISIKO["Rendah"]), (m["rs"], WARNA_RISIKO["Sedang"]), (m["rt"], WARNA_RISIKO["Tinggi"])], cls="dbar")}'
        f'</div></div>')

    verdicts = repository.get_verdicts_artikel(db_path)
    disp = {x["name"]: x["display"] for x in media_list}
    details: list[dict] = []
    kartu = []
    for x in media_list:
        items = []
        for a in per_media.get(x["name"], []):
            details.append(_detail_artikel(
                a, settings, verdicts, disp.get(x["name"], x["name"])))
            items.append((len(details) - 1, a))
        kartu.append(_kartu_media(x, items))
    cards = "".join(kartu)
    seksis = "".join(_seksi_topik(db_path, t) for t in topiks)
    adata = json.dumps(details, ensure_ascii=False).replace("</", "<\\/")

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
<div><h1><span class="sdot pulse" style="background:#34d399;width:16px;height:16px"></span>Media Monitor</h1><div class="tag">PANTAU MEDIA · SENTIMEN & RISIKO</div></div>
<div class="hright">
<div class="dlab">DIPERBARUI</div>
<div class="dval" data-ts="{now_iso}"><span class="t">{_tgl_id(now)}</span> <span class="relt"></span></div>
<div class="sched"><span class="sdot{' pulse' if pulse else ''}" style="background:{w_sch}"></span><span>{teks_sch}{rel_sch}</span></div>
</div>
</div>
<div class="kpis">{kpi1}{kpi2}{kpi3}</div>
{dist}
<nav class="topnav"><a href="#berita">📰 Berita per media</a><a href="#respons">📊 Respons Publik</a></nav>
<h2 class="sec" id="berita">Berita per media</h2>
<div class="grid">{cards}</div>
<h2 class="sec" id="respons">Respons Publik</h2>
{seksis or '<div class="muted">Belum ada data respons publik.</div>'}
<footer>{_esc(DISCLAIMER)}</footer>
</div>
<div class="mback" id="mback"><div class="modal" role="dialog" aria-modal="true">
<button class="mx" id="mx" aria-label="Tutup">✕</button>
<div class="mhead"><b id="m-media"></b><span> · — · </span><a id="m-src" href="#" target="_blank" rel="noopener">Buka sumber ↗</a></div>
<div class="mbadges" id="m-badges"></div>
<button class="mwhy" id="mwhy">❓ kenapa label ini?</button>
<div class="mwhybody" id="mwhybody" hidden></div>
<div class="mtitle" id="m-title"></div>
<div class="mai" id="m-ai"></div>
<div class="mpub" id="m-pub"></div>
<div class="mseclbl">📝 RINGKASAN</div><div class="mring" id="m-ring"></div>
<div class="mseclbl">🔍 TEKS YANG DIANALISIS</div><div class="misi" id="m-isi"></div>
</div></div>
{stat_modals}
<script type="application/json" id="adata">{adata}</script>
<script>
(function(){{
document.querySelectorAll('[data-ts]').forEach(function(el){{
var ts=new Date(el.dataset.ts).getTime();
function tick(){{var age=Date.now()-ts;
var r=el.querySelector('.relt');if(!r)return;
r.textContent='('+rel(age)+')';}}
function rel(ms){{var m=Math.floor(ms/60000);if(m<1)return'baru saja';
if(m<60)return m+' mnt lalu';var h=Math.floor(m/60);
if(h<24)return h+' jam lalu';return Math.floor(h/24)+' hari lalu';}}
tick();setInterval(tick,60000);
}});
}})();
// ---- modal detail artikel ----
(function(){{
var DATA=JSON.parse(document.getElementById('adata').textContent);
var back=document.getElementById('mback');
function esc(s){{var d=document.createElement('div');d.textContent=s;return d.innerHTML;}}
function openM(i){{var d=DATA[i];if(!d)return;
document.getElementById('m-media').textContent=d.media;
var src=document.getElementById('m-src');src.href=d.url;
document.getElementById('m-badges').innerHTML=d.badge_r+' '+d.badge_s;
document.getElementById('m-title').textContent=d.title;
document.getElementById('m-ai').innerHTML='<b>AI:</b> '+esc(d.ai);
document.getElementById('mwhybody').innerHTML=d.why;
document.getElementById('mwhybody').hidden=true;
document.getElementById('m-pub').textContent=d.pub?('Dipublikasikan: '+d.pub):'';
var rg=document.getElementById('m-ring');
rg.innerHTML=d.ringkasan.map(function(p){{return '<p>'+esc(p)+'</p>';}}).join('');
var rgl=rg.previousElementSibling;rgl.style.display=rg.style.display=d.ringkasan.length?'':'none';
rgl.textContent=d.ringkasan_ai?'📝 RINGKASAN ✨ AI':'📝 RINGKASAN';
var an=document.getElementById('m-isi');
an.innerHTML=d.dianalisis.map(function(p){{return '<p>'+esc(p)+'</p>';}}).join('')||'<p class="muted">Hanya judul yang dihitung (ringkasan kosong).</p>';
back.classList.add('open');document.body.style.overflow='hidden';}}
document.querySelectorAll('.tlink').forEach(function(b){{
b.addEventListener('click',function(){{openM(+b.dataset.i);}});}});
document.getElementById('mwhy').addEventListener('click',function(){{
var wb=document.getElementById('mwhybody');wb.hidden=!wb.hidden;}});
function closeAll(){{document.querySelectorAll('.mback.open').forEach(function(b){{b.classList.remove('open');}});document.body.style.overflow='';}}
function openModal(id){{document.getElementById(id).classList.add('open');document.body.style.overflow='hidden';}}
document.querySelectorAll('.mback').forEach(function(back){{
var x=back.querySelector('.mx');if(x)x.addEventListener('click',closeAll);
back.addEventListener('click',function(e){{if(e.target===back)closeAll();}});}});
document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeAll();}});
[['kpi-total','mstat-t'],['kpi-sentimen','mstat-s'],['kpi-risiko','mstat-r']].forEach(function(p){{
var b=document.getElementById(p[0]);if(b)b.addEventListener('click',function(){{openModal(p[1]);}});}});
}})();
</script>
</body></html>
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
