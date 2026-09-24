# Roadmap: Media Monitor — Dashboard Pemantauan Berita Indonesia

Dashboard Streamlit untuk memantau isu-isu yang ramai diberitakan 10 media nasional:
isu terpanas hari ini, perbandingan liputan antar media, dan tren volume pemberitaan.

## 1. Definisi Sukses

- Scheduler menarik berita terbaru dari 10 media **setiap 1 jam**, otomatis, tanpa intervensi manual.
- Dashboard menampilkan: daftar isu terpanas, detail artikel per isu per media, grafik tren volume.
- Tambah/kurangi media = edit file config, **tanpa ubah kode**.
- Retensi data bisa diubah lewat pengaturan (default 30 hari).
- Seluruh kode mengikuti struktur enterprise di bawah: tidak ada logika bisnis di file tampilan,
  tidak ada fungsi yang diduplikasi.

## 2. Keputusan yang Dikunci (25 Sep 2026)

| # | Keputusan | Status |
|---|-----------|--------|
| 1 | 10 media awal: Kompas, Detik, Tempo, CNN Indonesia, Liputan6, Antara, Jawa Pos, Republika, Bisnis Indonesia, Kumparan | Dikunci |
| 2 | Retensi 30 hari, dibuat **dinamis** lewat pengaturan | Dikunci |
| 3 | Klasterisasi isu **langsung versi embedding** (tanpa fase kata-kunci dulu) | Dikunci |
| 4 | Dashboard: Streamlit, jalan lokal (localhost) | Dikunci |
| 5 | Struktur: enterprise, DRY, config-driven | Dikunci |
| 6 | Kode ditulis **setelah roadmap disetujui**, per fase | Aturan kerja |

**Catatan keputusan #2:** data di dashboard selalu up-to-date dari sumber karena fetcher
menarik item terbaru dari RSS setiap siklus (1 jam). Retensi hanya mengatur berapa lama
artikel lama disimpan di database lokal, tidak memengaruhi kesegaran data baru.

## 3. Hasil Riset Feed RSS (diverifikasi 25 Sep 2026 via curl)

5 media punya RSS native yang valid, 5 lainnya memakai fallback **Google News RSS**
(`news.google.com/rss/search?q=site:<domain>`) karena RSS native-nya 404 / diblokir / tidak ada.

| Media | Feed | Status |
|-------|------|--------|
| Tempo | `https://rss.tempo.co/` | OK native (200, XML valid) |
| CNN Indonesia | `https://www.cnnindonesia.com/rss` | OK native (200, XML valid) |
| Antara | `https://www.antaranews.com/rss/terkini.xml` | OK native (daftar feed resmi di `/rss`) |
| Republika | `https://www.republika.co.id/rss` | OK native (200, XML valid) |
| Bisnis Indonesia | `https://rss.bisnis.com` | OK native (200; versi `www` diblokir Cloudflare) |
| Kompas | Google News RSS `site:kompas.com` | Fallback (RSS native 404) |
| Detik | Google News RSS `site:detik.com` | Fallback (`rss.detik.com` tidak terjangkau) |
| Liputan6 | Google News RSS `site:liputan6.com` | Fallback (RSS native 404) |
| Jawa Pos | Google News RSS `site:jawapos.com` | Fallback (RSS native 404) |
| Kumparan | Google News RSS `site:kumparan.com` | Fallback (tidak ada RSS publik) |

Catatan teknis untuk Fase 1:
- Link Google News RSS mengarah ke `news.google.com` (redirect). Ikuti redirect untuk
  mendapatkan URL artikel asli sebelum simpan (penting untuk dedup).
- Google News RSS bisa rate-limit bila dipanggil terlalu agresif. Jeda antar media 2-3 detik.
- Feed yang hari ini fallback bisa dipindah ke native kapan saja hanya lewat config.

## 4. Stack Teknologi

| Lapisan | Pilihan |
|---------|---------|
| Bahasa | Python 3.12 (versi di mesin: 3.12.3) |
| Virtual env | Terpisah per proyek: `~/workspace/media-monitor/.venv` |
| Ambil RSS | `feedparser` + `requests` |
| Scheduler | APScheduler (di dalam proses) atau cron sistem |
| Database | SQLite (pemakaian personal), pola repository |
| Cleaning teks | `Sastrawi` (stopword/stemming, bila perlu) |
| Embedding | `sentence-transformers` + model `intfloat/multilingual-e5-base` (768-dim, ~560 MB, CPU cukup). Alternatif ringan: `denaya/indoSBERT-large` (256-dim). Keputusan final di Fase 2 setelah uji cepat. |
| Clustering | HDBSCAN atau KMeans di atas embedding (dievaluasi di Fase 2) |
| Dashboard | Streamlit |
| Config | YAML (`config/media.yaml`, `config/settings.yaml`) |
| Testing | `pytest` |

## 5. Struktur Proyek (Enterprise)

```
media-monitor/
├── .venv/                  # virtual environment (tidak di-commit)
├── config/
│   ├── media.yaml          # daftar 10 media + URL feed + tipe (native/gnews)
│   └── settings.yaml       # interval fetch, retention_days, ambang clustering
├── src/
│   ├── __init__.py
│   ├── common/             # logging, http_client (retry, user-agent, jeda), utils
│   ├── ingestion/          # SATU fetcher generik untuk semua media (beda hanya di config)
│   ├── storage/            # repository SQLite: articles, issues, settings
│   ├── processing/         # cleaning, dedup, embedding, clustering, issue registry
│   └── scheduler/          # job fetch per jam + job cleanup retensi harian
├── app/
│   ├── Home.py             # isu terpanas hari ini
│   └── pages/
│       ├── 1_Detail_Isu.py
│       ├── 2_Perbandingan_Media.py
│       └── 3_Pengaturan.py  # ubah retention_days, aktif/nonaktif media
├── tests/
├── requirements.txt        # versi di-pin
├── ROADMAP.md              # file ini
└── README.md
```

**Aturan arsitektur (tidak bisa ditawar):**
1. File di `app/` hanya presentasi. Dilarang import `feedparser`/`requests` langsung;
   semua akses data lewat `src/storage` dan `src/processing`.
2. Tambah media baru = tambah blok YAML di `config/media.yaml`. Tidak boleh ada
   `if media == "kompas"` di kode.
3. Setiap fungsi ditulis sekali di `src/common` atau modulnya, dipakai ulang di mana-mana (DRY).
4. Semua nilai ajaib (interval, ambang similarity, retention) hidup di `config/`, bukan di kode.

## 6. Fase Kerja

### Fase 0 — Environment & Fondasi [WAJIB SELESAI DULU]

Tujuan: pondasi kokoh sebelum satu baris kode aplikasi ditulis.

**Prerequisite:**
- [ ] OS Linux/macOS/Windows dengan Python 3.12+ (`python3 --version`)
- [ ] `pip` dan `venv` tersedia (`python3 -m pip --version`)
- [ ] `git` terinstal (untuk versioning proyek)
- [ ] Koneksi internet (download ±700 MB: dependensi + model embedding)
- [ ] Ruang disk ±2 GB

**Langkah (berurutan):**
1. Buat direktori proyek: `~/workspace/media-monitor`
2. Buat virtual environment terpisah: `python3 -m venv .venv` (jangan pakai Python global,
   jangan campur dengan venv proyek lain)
3. Aktifkan venv, upgrade pip: `pip install --upgrade pip`
4. Buat `requirements.txt` dengan versi di-pin (feedparser, requests, streamlit,
   apscheduler, pyyaml, sentence-transformers, scikit-learn, Sastrawi, pytest)
5. Install: `pip install -r requirements.txt`
6. Buat kerangka folder sesuai struktur di bagian 5 (file `__init__.py` kosong)
7. Buat `config/media.yaml` (10 media dari tabel bagian 3) dan `config/settings.yaml`
8. Smoke test: `python -c "import feedparser, streamlit, sentence_transformers; print('ok')"`
   dan `streamlit hello` (pastikan dashboard contoh bisa dibuka di browser)

**Definition of Done Fase 0:**
- `pip freeze` di dalam venv hanya berisi dependensi proyek ini.
- Smoke test lolos, `streamlit hello` terbuka di browser.
- Struktur folder + config YAML sudah ada dan ter-commit ke git.

### Fase 1 — Ingestion Pipeline [SEDANG BERJALAN: uji 24 jam dimulai 25 Sep 2026 ~03:01 WITA]

- [x] `src/common/http_client.py`: request dengan retry, timeout, user-agent, jeda antar media
- [x] `src/ingestion/fetcher.py`: satu fetcher generik (feedparser), tangani native + Google News
      (ikuti redirect ke URL artikel asli)
- [x] `src/storage/`: skema SQLite (`articles`: url UNIQUE, media, judul, ringkasan, link,
      published_at, fetched_at) + repository; tabel `fetch_runs` + `fetch_media_log`
      untuk audit tiap siklus (dipakai halaman status Fase 4)
- [x] Dedup: URL sudah ada = skip (UNIQUE constraint + ON CONFLICT); terverifikasi 354 artikel,
      354 URL unik, 0 duplikat
- [x] `src/scheduler/`: job fetch tiap 1 jam untuk semua media aktif (APScheduler in-process,
      `run_scheduler.py`; `--once` untuk satu siklus / cron)
- [x] Logging: tiap siklus catat jumlah artikel baru per media ke `logs/fetch.log`

Keputusan tambahan Fase 1 (25 Sep 2026): `fetch.max_articles_per_media: 30` di
`config/settings.yaml` — feed Google News mengembalikan 100 item dan resolusi redirect
per link membuat satu siklus terlalu lama; feed terurut terbaru dulu jadi 30 teratas cukup.

**DoD:** scheduler jalan 24 jam percobaan, artikel dari 10 media masuk DB tanpa duplikat,
log rapi per media.

Temuan uji siklus manual (25 Sep 2026): 9/10 media OK (151 artikel baru satu siklus).

- `republika`: RSS native konsisten 403 Forbidden -> dipindah ke fallback Google News
  (commit `95926ff`, hanya ubah `config/media.yaml`, tanpa ubah kode).
- URL artikel Google News (`news.google.com/rss/articles/...`) TIDAK bisa di-resolve ke URL
  penerbit via HTTP redirect maupun decode token (format token baru bersifat opak).
  Namun uji empiris membuktikan token stabil per artikel antar fetch (100/100 sama dalam
  selang 90 detik), jadi tetap layak sebagai kunci dedup; link google juga berfungsi
  sebagai tautan sumber (browser me-redirect otomatis).
- Sebagai jaring pengaman bila token berubah antar siklus, dedup punya lapis kedua:
  pasangan (media, judul) yang sama dianggap artikel yang sama (commit `37e558b`).

### Fase 2 — Processing: Embedding & Klasterisasi Isu

- [ ] `src/processing/cleaning.py`: normalisasi judul/ringkasan (lowercase, hapus tag media)
- [ ] Uji cepat 2 model embedding pada 200 judul berita nyata → pilih yang cluster-nya
      paling masuk akal (kandidat: `intfloat/multilingual-e5-base` vs `denaya/indoSBERT-large`)
- [ ] `src/processing/embedder.py`: encode batch judul (+ringkasan), simpan vektor
- [ ] `src/processing/cluster.py`: clustering per jendela waktu (mis. 24 jam terakhir),
      hasilkan `issues` (label sementara = kata kunci topik)
- [ ] Issue registry: isu yang sama lintas hari dikenali (cocokkan centroid, ambang cosine)

**DoD:** 10 isu teratas hari itu relevan secara manual (cek 50 artikel sampel),
tidak ada satu isu raksasa berisi semua berita.

### Fase 3 — Dashboard Streamlit

- [ ] `app/Home.py`: daftar isu terpanas (judul isu, jumlah artikel, sparkline tren, top media)
- [ ] `app/pages/1_Detail_Isu.py`: timeline volume + daftar artikel per media + link ke sumber
- [ ] `app/pages/2_Perbandingan_Media.py`: pilih isu → bandingkan jumlah & sudut judul antar media
- [ ] Filter global di sidebar: rentang tanggal, pilih media
- [ ] Semua halaman hanya memanggil `src/storage` & `src/processing`. Tanpa logika bisnis.

**DoD:** dibuka di browser lokal, semua halaman berfungsi dengan data nyata 7 hari.

### Fase 4 — Pengaturan Dinamis & Retensi

- [ ] `app/pages/3_Pengaturan.py`: ubah `retention_days` (default 30), aktif/nonaktif media,
      ubah interval fetch — tersimpan ke DB/settings, tanpa edit file
- [ ] Job cleanup harian: hapus artikel lebih tua dari `retention_days`
- [ ] Halaman status: kesehatan tiap feed (terakhir sukses/gagal, jumlah artikel)

**DoD:** ubah retensi ke 7 hari → artikel lama terhapus otomatis besoknya;
nonaktifkan satu media → fetch berikutnya melewatinya.

### Fase 5 — (Masa Depan, bukan sekarang)

Analisis sentimen per artikel (IndoBERT) dan modul pencocokan klaim dengan database
fact-checker (TurnBackHoax/Mafindo, CekFakta). Dikerjakan **setelah** Fase 0-4 stabil
dan dashboard sudah dipakai harian.

## 7. Risiko & Mitigasi

| Risiko | Mitigasi |
|--------|----------|
| Google News RSS rate-limit | Jeda 2-3 detik antar media; interval 1 jam sudah konservatif |
| Media mengubah struktur RSS | Fetcher generik + health check per feed di halaman status |
| Model embedding 560 MB berat di awal | Download sekali, cache lokal; alternatif ringan sudah disiapkan |
| Isu lintas hari terpecah | Issue registry dengan pencocokan centroid (Fase 2) |

## 8. Aturan Kerja Proyek Ini

1. Roadmap dulu, kode menyusul — setiap fase didiskusikan sebelum dieksekusi.
2. Tidak ada full code sebelum instruksi eksplisit Nucifera.
3. Perubahan minimal, DRY, tanpa refactor yang tidak perlu.
4. Setiap update proyek → ingatkan Nucifera memperbarui halaman Notion terkait.
