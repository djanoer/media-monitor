@echo off
rem ============================================================
rem  Media Monitor - ALL IN ONE (satu double-click jalan semua).
rem  [1] Scheduler berita (15 media, tiap 1 jam) - window minimize
rem  [2] Sync Respons Publik (YouTube + Trends) - window sendiri
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

echo [2/3] Menjalankan sync Respons Publik di window terpisah...
start "Media Monitor - Sync" cmd /k ""%~dp0.venv\Scripts\python.exe" scripts/respon_publik.py --auto"

echo [3/3] Membuka viewer di browser...
".venv\Scripts\python.exe" -m streamlit run app/Home.py --browser.gatherUsageStats false --server.port 8502
pause
