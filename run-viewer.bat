@echo off
rem ============================================================
rem  Media Monitor - buka viewer sementara di browser.
rem  Letakkan file ini di folder utama project (sejajar
rem  run_scheduler.py), lalu double-click. Browser terbuka
rem  otomatis di http://localhost:8501
rem  Tutup window ini untuk menghentikan viewer.
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv tidak ditemukan di folder ini.
    echo Buat dulu dengan perintah:  python -m venv .venv
    pause
    exit /b 1
)

echo Membuka Media Monitor di browser...
".venv\Scripts\python.exe" -m streamlit run app/Home.py --browser.gatherUsageStats false
pause
