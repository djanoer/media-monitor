@echo off
rem ============================================================
rem  Media Monitor - peluncur scheduler (berjalan terus)
rem  Letakkan file ini di folder utama project (sejajar
rem  run_scheduler.py), lalu double-click untuk menjalankan.
rem  Tutup window ini untuk menghentikan scheduler.
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv tidak ditemukan di folder ini.
    echo Buat dulu dengan perintah:  python -m venv .venv
    pause
    exit /b 1
)

echo ============================================================
echo  Media Monitor berjalan - fetch tiap 1 jam.
echo  Tutup window ini untuk berhenti.
echo ============================================================
".venv\Scripts\python.exe" run_scheduler.py
pause
