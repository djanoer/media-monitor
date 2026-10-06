@echo off
rem ============================================================
rem  Media Monitor - Respons Publik (manual).
rem  Double-click file ini -> topik hangat otomatis dari berita
rem  24 jam terakhir diproses (YouTube + Google Trends).
rem  Selesai -> tutup window, refresh halaman Respons Publik.
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv tidak ditemukan di folder ini.
    echo Buat dulu dengan perintah:  python -m venv .venv
    pause
    exit /b 1
)

echo === Respons Publik: topik otomatis 24 jam terakhir ===
".venv\Scripts\python.exe" scripts/respon_publik.py --auto
echo.
echo === Selesai. Refresh halaman Respons Publik di browser. ===
pause
