# Media Monitor

Dashboard Streamlit untuk memantau isu-isu yang ramai diberitakan 15 media nasional Indonesia, lengkap dengan sentimen, skor risiko, dan respons publik (YouTube + Google Trends).

Lihat `ROADMAP.md` untuk rencana fase kerja, keputusan desain, dan hasil riset feed RSS.

## Cara pakai (Windows, double-click)

| File | Fungsi | Kapan dipakai |
|------|--------|---------------|
| `all-in-one.bat` | **Rutin harian.** Menjalankan semuanya: [1] scheduler 15 media tiap 1 jam (window minimize), [2] sync Respons Publik → ekspor statis → push github.io (berantai di satu window), [3] viewer Streamlit di browser (`localhost:8502`) | Tiap buka laptop, cukup ini saja |
| `respon-publik.bat` | Sync Respons Publik saja (topik hangat 24 jam → YouTube + Trends), **tanpa** push ke github.io | Mau topik segar di dashboard lokal saja |
| `ekspor-statis.bat` | Generate `docs/index.html` dari DB lokal lalu push → situs `djanoer.github.io/media-monitor` terbit | Mau update situs manual kapan pun |
| `run-all.bat` | *(lama)* Scheduler + viewer saja, tanpa sync/ekspor | Digantikan `all-in-one.bat` |

Alur data: scheduler fetch RSS tiap jam → unduh isi artikel → analisa sentimen + risiko otomatis → (manual/otomatis) sync Respons Publik → ekspor statis → GitHub Pages.

Catatan:
- Jangan jalankan dua `.bat` bersamaan — ada kunci proses otomatis yang menolak duplikat.
- Tutup semua window untuk berhenti total. Aman dimatikan kapan pun (transaksi atomik + WAL).
- Aktifkan GitHub Pages sekali: Settings repo → Pages → source `main`, folder `/docs`.

## Menjalankan scheduler (manual / testing)

Dari root proyek dengan venv aktif:

```bash
# satu siklus fetch lalu keluar (untuk testing / cron)
.venv/bin/python run_scheduler.py --once

# jalan terus, fetch tiap 1 jam (APScheduler in-process)
.venv/bin/python run_scheduler.py
```

Log: `logs/fetch.log`. Database: `data/media_monitor.db`.
Menjalankan test: `.venv/bin/python -m pytest tests/ -q`

## Setup mandiri dari repo (Windows)

Untuk orang lain yang mau menjalankan sendiri dari repo ini:

**1. Prasyarat:** Windows 10/11, Python 3.10+ ([python.org](https://www.python.org/downloads/), centang "Add python.exe to PATH" saat instal), git.

**2. Clone & install:**
```bat
git clone https://github.com/djanoer/media-monitor.git
cd media-monitor
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**3. (Opsional) YouTube API key** — hanya untuk data video di Respons Publik. Tanpa ini, bagian YouTube dilewati dan Google Trends tetap jalan. Dua cara (pilih salah satu):

```bat
:: Cara A: environment variable (laptop utama)
setx YOUTUBE_API_KEY "isi-dengan-key-kamu"
```
Tutup-buka terminal setelah `setx`.

```bat
:: Cara B: file .env (praktis untuk laptop kedua)
copy .env.example .env
:: lalu edit .env, isi YOUTUBE_API_KEY dengan key aslimu
```
File `.env` tidak ikut ke git (sudah di `.gitignore`).

Buat key di [Google Cloud Console](https://console.cloud.google.com/) → aktifkan *YouTube Data API v3* → Credentials → API key.

**4. Jalankan:** double-click `all-in-one.bat`. Saat pertama kali DB masih kosong — scheduler mengisi berita tiap 1 jam; halaman Respons Publik terisi setelah sync pertama selesai (±4 menit).

**5. (Opsional) Terbitkan ke GitHub Pages:** fork repo → Settings → Pages → source `main`, folder `/docs` → situs terbit di `https://<username>.github.io/media-monitor/`. Update situs: double-click `ekspor-statis.bat`.
