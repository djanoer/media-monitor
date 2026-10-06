@echo off
rem ============================================================
rem  Media Monitor - ALL IN ONE (satu double-click jalan semua).
rem  [1] Scheduler berita (15 media, tiap 1 jam) - window minimize
rem  [2] Sync Respons Publik -^> ekspor statis -^> push github.io (window sendiri)
rem  [3] Viewer Streamlit dibuka di browser (localhost:8502)
rem  Tutup SEMUA window untuk berhenti total.
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv tidak ditemukan di folder ini.
    echo Buat dulu dengan perintah:  python -m venv .venv
    pause
    exit /b 1
)

echo [1/3] Menjalankan scheduler di window terpisah (minimize)...
start "Media Monitor - Scheduler" /min ".venv\Scripts\python.exe" run_scheduler.py

echo [2/3] Sync + ekspor + push github.io di window terpisah...
start "Media Monitor - Sync" cmd /k ".venv\Scripts\python.exe scripts/respon_publik.py --auto && .venv\Scripts\python.exe scripts/ekspor_statis.py && git add docs/index.html && git commit -m Ekspor-statis --quiet && git push origin main && echo. && echo [SELESAI] github.io diperbarui."

echo [3/3] Membuka viewer di browser...
".venv\Scripts\python.exe" -m streamlit run app/Home.py --browser.gatherUsageStats false --server.port 8502
pause
