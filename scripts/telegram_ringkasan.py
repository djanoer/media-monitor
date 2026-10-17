#!/usr/bin/env python3
"""Kirim ringkasan berita harian via Telegram. 0 token Muse.

Dibaca dari DB media-monitor (ringkasan AI yang sudah ada).
Dijalankan dari pipeline atau manual:
    python scripts/telegram_ringkasan.py [--test]

Butuh di .env:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

WIB = timezone(timedelta(hours=7))
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "data", "media_monitor.db")

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
         "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def tgl_id(dt: datetime) -> str:
    return f"{dt.day} {BULAN[dt.month-1]} {dt.year}"


def esc_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def norm_url(u: str) -> str:
    """Normalisasi URL untuk dedup lintas topik.

    Lowercase, tanpa fragment, tanpa trailing slash, tanpa www.,
    dan tanpa parameter tracking (utm_*, fbclid, gclid, ...).
    """
    u = (u or "").strip()
    if not u:
        return ""
    try:
        p = urlparse(u.lower())
        q = [(k, v) for k, v in parse_qsl(p.query)
             if not k.startswith("utm_") and k not in _TRACKING_PARAMS]
        netloc = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme, netloc, path, "", urlencode(q), ""))
    except Exception:
        return u.lower().rstrip("/")


def buang_duplikat(daftar: list[dict], seen: set[str]) -> list[dict]:
    """Buang artikel yang URL-nya sudah ada di `seen` (preservasi urutan)."""
    hasil = []
    for a in daftar:
        u = norm_url(a.get("url"))
        if u and u not in seen:
            seen.add(u)
            hasil.append(a)
    return hasil


def ambil_berita(limit_geo: int = 3, limit_tek: int = 3):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT title, url, media, published_at, ringkasan_ai FROM articles WHERE published_at >= datetime('now', '-24 hours') ORDER BY published_at DESC LIMIT 400")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    geo_kw = ["geopolitik","diplomasi","konflik","perang","nato","pbb","asean","tiongkok","china","amerika","rusia","ukraina","timur tengah","taiwan","korea","nuklir","sanksi","perbatasan","militer","gaza","israel","iran","pemilu amerika"]
    tek_kw = ["teknologi","kecerdasan buatan","artificial intelligence","startup","siber","semikonduktor","chip","5g","satelit","roket","luar angkasa","robot","drone","kuantum","blockchain","kripto","openai","google","microsoft","apple","nvidia","tesla","spacex","gadget","smartphone","internet","aplikasi","data"]
    def skor_artikel(art, kws):
        judul = (art.get("title") or "").lower()
        ringkasan = (art.get("ringkasan_ai") or "").lower()
        sk_judul = set()
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", judul, re.IGNORECASE):
                sk_judul.add(kw)
        sk_ring = set()
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", ringkasan, re.IGNORECASE):
                sk_ring.add(kw)
        return 3 * len(sk_judul) + 1 * len(sk_ring)
    geo_kandidat = []
    for art in rows:
        s = skor_artikel(art, geo_kw)
        if s >= 3:
            geo_kandidat.append((s, art.get("published_at") or "", art))
    geo_kandidat.sort(key=lambda x: (x[0], x[1]), reverse=True)
    geo = buang_duplikat([x[2] for x in geo_kandidat], set())[:limit_geo]
    geo_urls = set(norm_url(a.get("url") or "") for a in geo)
    tek_kandidat = []
    for art in rows:
        if norm_url(art.get("url") or "") in geo_urls:
            continue
        s = skor_artikel(art, tek_kw)
        if s >= 3:
            tek_kandidat.append((s, art.get("published_at") or "", art))
    tek_kandidat.sort(key=lambda x: (x[0], x[1]), reverse=True)
    tek = buang_duplikat([x[2] for x in tek_kandidat], set())[:limit_tek]
    return geo, tek


def ambil_terpanas(limit: int = 5) -> list[dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    q = """
    SELECT title, url, media, published_at, ringkasan_ai
    FROM articles
    WHERE published_at >= datetime('now', '-24 hours')
    ORDER BY published_at DESC
    LIMIT 1500
    """
    rows = conn.execute(q).fetchall()
    conn.close()
    art_list = [dict(r) for r in rows]
    stop = {"yang","dan","di","ke","dari","ini","itu","untuk","dengan","pada","adalah","akan","jadi","usai","kata","tak","tidak","ada","juga","oleh","saat","bilang","com","www","https","hari"}
    freq = {}
    art_tokens = []
    for a in art_list:
        judul = a.get('title') or ''
        toks = set()
        for w in re.findall(r"[a-z0-9]+", judul.lower()):
            if len(w) > 2 and w not in stop:
                toks.add(w)
        art_tokens.append(toks)
        for t in toks:
            freq[t] = freq.get(t, 0) + 1
    max_art = len(art_list)
    threshold = max(3, int(0.1 * max_art))
    klaster = []
    for i, toks in enumerate(art_tokens):
        placed = False
        for k in klaster:
            kt = k['tokens']
            inter = len(toks & kt)
            union = len(toks | kt)
            jacc = inter / union if union else 0
            if jacc >= 0.45:
                k['articles'].append(i)
                k['media'].add(art_list[i]['media'])
                pa = art_list[i].get('published_at') or ''
                if pa > (k['latest_pub'] or ''):
                    k['latest_pub'] = pa
                placed = True
                break
        if not placed:
            klaster.append({
                'tokens': set(toks),
                'articles': [i],
                'media': {art_list[i]['media']},
                'latest_pub': art_list[i].get('published_at') or ''
            })
    klaster.sort(key=lambda k: (
        -len(k['media']),
        -len(k['articles']),
        k['latest_pub']
    ), reverse=False)
    klaster.sort(key=lambda k: (
        len(k['media']),
        len(k['articles']),
        k['latest_pub']
    ), reverse=True)
    selected = []
    khas_sets = []
    for k in klaster:
        if len(selected) >= limit:
            break
        khas = set()
        for t in k['tokens']:
            if freq.get(t, 0) <= threshold:
                khas.add(t)
        flag = False
        for s in khas_sets:
            if len(khas & s) >= 2:
                flag = True
                break
        if flag:
            continue
        khas_sets.append(khas)
        selected.append(k)
    out = []
    for k in selected:
        art_idx = k['articles']
        rep = None
        for ai in art_idx:
            a = art_list[ai]
            if (a.get('ringkasan_ai') or '').strip():
                rep = a
                break
        if rep is None:
            best = min(art_idx, key=lambda i: art_list[i].get('published_at') or '')
            rep = art_list[best]
        d = dict(rep)
        d['jumlah_media'] = len(k['media'])
        d['daftar_media'] = sorted(k['media'])
        d['jumlah_artikel'] = len(art_idx)
        out.append(d)
    return out


def _format_terpanas(berita: list[dict]) -> list[str]:
    out = [""]
    for i, b in enumerate(berita, 1):
        judul = esc_html(b.get('judul') or b.get('title') or '')
        media = esc_html(b.get('media') or '')
        url = norm_url(b.get('url') or '')
        out.append(f"<b>{i}. {media} - <a href=\"{url}\">{judul}</a></b>")
        ringkasan = (b.get('ringkasan_ai') or '').strip()
        if ringkasan:
            r = ringkasan[:297]
            if len(ringkasan) > 300:
                last100 = r[-100:]
                idx = last100.find('. ')
                if idx >= 0:
                    r = r[:len(r)-100+idx+1].rstrip()
                else:
                    sp = r.rfind(' ')
                    if sp > 0:
                        r = r[:sp]
                    r += '…'
            out.append(f"   {r}")
        media_list = [esc_html(m) for m in b.get('daftar_media', [])]
        out.append(f"   🔥 Diliput {b.get('jumlah_media',0)} media ({b.get('jumlah_artikel',0)} artikel): {', '.join(media_list)}")
        out.append(f"   🔗 <a href=\"{url}\">Baca selengkapnya</a>")
        out.append("")
    return out


def format_pesan(geo, tek, st=None, panas=None) -> str:
    baris = [
        "📰 <b>RINGKASAN BERITA</b>",
        f"📅 {tgl_id(datetime.now(WIB))}",
        ""
    ]
    if panas:
        baris += ["🔥 <b>TOPIK TERPANAS HARI INI</b>"]
        baris += _format_terpanas(panas)
    baris += ["", "🌍 <b>GEOPOLITIK</b>"]
    baris += _format_seksi(geo)
    baris += ["", "💻 <b>TEKNOLOGI</b>"]
    baris += _format_seksi(tek)
    if st is not None:
        baris += format_status_sistem(st)
    baris += [
        "",
        "—",
        "",
        "🔗 <a href=\"https://djanoer.github.io/media-monitor/\">Media Monitor</a>",
        "",
        "<i>Disusun otomatis dari Media Monitor</i>"
    ]
    return "\n".join(baris)


def _format_seksi(berita: list[dict]) -> list[str]:
    out = [""]
    for i, b in enumerate(berita, 1):
        judul = esc_html(b.get("title") or "")
        media = esc_html(b.get("media") or "")
        url = b.get("url") or ""
        out.append(f"<b>{i}. {media} - <a href=\"{url}\">{judul}</a></b>")
        ring = (b.get("ringkasan_ai") or "").strip()
        if ring:
            if len(ring) > 300:
                potongan = ring[:297]
                last100 = potongan[-100:]
                idx = last100.rfind(". ")
                if idx != -1:
                    ring = (potongan[:297 - (len(last100) - idx + 2)] + ".").strip()
                else:
                    idx_spasi = potongan.rfind(" ")
                    if idx_spasi != -1:
                        ring = potongan[:idx_spasi] + "…"
                    else:
                        ring = potongan + "…"
            out.append(f"   {ring}")
        out.append(f"   🔗 <a href=\"{url}\">Baca selengkapnya</a>")
        out.append("")
    return out


def status_sistem() -> dict:
    from datetime import datetime as _dt
    st = {"restart_24j": 0, "gagal_24j": 0, "restart_terakhir": None,
          "run_6j": 0, "fetch_error_6j": 0, "media_error_6j": [],
          "diringkas_6j": 0, "antri": 0}
    ev_path = os.path.expanduser("~/hooks/state/media_monitor_loop_events.jsonl")
    batas = _dt.now().timestamp() - 24 * 3600
    try:
        with open(ev_path, encoding="utf-8") as f:
            for baris in f:
                try:
                    ev = json.loads(baris)
                    if float(ev.get("ts", 0)) < batas:
                        continue
                    if ev.get("event") == "restart_ok":
                        st["restart_24j"] += 1
                        st["restart_terakhir"] = str(ev.get("waktu", ""))[-5:]
                    elif ev.get("event") == "restart_gagal":
                        st["gagal_24j"] += 1
                except Exception:
                    continue
    except Exception:
        pass
    try:
        con = sqlite3.connect(DB)
        cur = con.cursor()
        try:
            st["run_6j"] = cur.execute(
                "SELECT COUNT(*) FROM fetch_runs WHERE datetime(started_at) > datetime('now','-6 hours')"
            ).fetchone()[0]
        except Exception:
            pass
        try:
            st["fetch_error_6j"] = cur.execute(
                "SELECT COUNT(*) FROM fetch_media_log WHERE status='error' AND datetime(fetched_at) > datetime('now','-6 hours')"
            ).fetchone()[0]
        except Exception:
            pass
        try:
            rows = cur.execute(
                "SELECT DISTINCT media FROM fetch_media_log WHERE status='error' AND datetime(fetched_at) > datetime('now','-6 hours') ORDER BY media"
            ).fetchall()
            st["media_error_6j"] = [r[0] for r in rows]
        except Exception:
            pass
        try:
            st["diringkas_6j"] = cur.execute(
                "SELECT COUNT(*) FROM articles WHERE datetime(ringkasan_ai_at) > datetime('now','-6 hours')"
            ).fetchone()[0]
        except Exception:
            pass
        try:
            st["antri"] = cur.execute(
                "SELECT COUNT(*) FROM articles WHERE datetime(fetched_at) > datetime('now','-6 hours') AND (ringkasan_ai IS NULL OR ringkasan_ai = '')"
            ).fetchone()[0]
        except Exception:
            pass
        con.close()
    except Exception:
        pass
    return st


def format_status_sistem(st: dict) -> list[str]:
    out = ["", "🖥 <b>STATUS SISTEM — MEDIA MONITOR</b>"]
    r24 = st.get("restart_24j", 0)
    f24 = st.get("gagal_24j", 0)
    if r24 == 0 and f24 == 0:
        out.append("✅ Loop Media Monitor stabil — tidak ada restart dalam 24 jam terakhir.")
    if r24 >= 5:
        out.append(f"⚠️ <b>Loop Media Monitor TIDAK STABIL — direstart otomatis {r24}× dalam 24 jam terakhir (terakhir {st.get('restart_terakhir','?')} WITA).</b> Berhasil jalan lagi, tapi penyebabnya perlu dicek.")
    elif 0 < r24 < 5:
        out.append(f"🔁 Loop Media Monitor direstart otomatis {r24}× dalam 24 jam terakhir (terakhir {st.get('restart_terakhir','?')} WITA) — berhasil, tanpa intervensi.")
    if f24 > 0:
        out.append(f"🚨 <b>Restart loop Media Monitor GAGAL {f24}× dalam 24 jam terakhir — perlu dicek manual.</b>")
    out.append(f"📊 6 jam terakhir: {st.get('run_6j',0)} run · {st.get('diringkas_6j',0)} diringkas · {st.get('antri',0)} antri")
    if st.get("fetch_error_6j", 0) > 0:
        meds = [esc_html(m) for m in st.get("media_error_6j", [])]
        out.append(f"⚠️ Fetch error {st.get('fetch_error_6j',0)}× — media: {', '.join(meds)}")
    else:
        out.append("📥 Fetch bersih — tidak ada error dalam 6 jam terakhir.")
    return out


def kirim(token: str, chat_id: str, teks: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": teks,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"Gagal kirim Telegram: {e}", file=sys.stderr)
        return False


def main():
    # Muat .env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    envf = os.path.join(root, ".env")
    if os.path.exists(envf):
        for line in open(envf):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset", file=sys.stderr)
        sys.exit(1)

    test = "--test" in sys.argv
    if test:
        geo, tek = ambil_berita(limit_geo=2, limit_tek=2)
        panas = ambil_terpanas(3)
    else:
        geo, tek = ambil_berita(limit_geo=3, limit_tek=3)
        panas = ambil_terpanas(5)
    if not geo and not tek:
        print("Tidak ada berita 24 jam terakhir")
        sys.exit(0)

    pesan = format_pesan(geo, tek, status_sistem(), panas)
    if test:
        print("=== PREVIEW ===")
        print(pesan[:1500])
        print("===============")
    ok = kirim(token, chat_id, pesan)
    print("Terkirim" if ok else "GAGAL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
