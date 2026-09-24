@echo off
rem ============================================================
rem  Media Monitor - scheduler + viewer dalam satu klik.
rem  Scheduler berjalan di window kecil (minimize),
rem  viewer dibuka di browser otomatis http://localhost:8502
rem  Tutup KEDUA window untuk berhenti total.
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv tidak ditemukan di folder ini.
    echo Buat dulu dengan perintah:  python -m venv .venv
    pause
    exit /b 1
)

echo Menjalankan scheduler di window terpisah (minimize)...
start "Media Monitor - Scheduler" /min ".venv\Scripts\python.exe" run_scheduler.py

echo Membuka viewer di browser...
".venv\Scripts\python.exe" -m streamlit run app/Home.py --browser.gatherUsageStats false --server.port 8502
pause
