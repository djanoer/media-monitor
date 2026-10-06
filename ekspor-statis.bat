@echo off
rem ============================================================
rem  Media Monitor - Ekspor statis untuk GitHub Pages.
rem  Generate docs/index.html dari DB lokal, lalu commit + push.
rem  Situs terbit di https://djanoer.github.io/media-monitor/
rem  (aktifkan sekali: Settings repo -> Pages -> main /docs)
rem ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv tidak ditemukan di folder ini.
    pause
    exit /b 1
)

echo Mengekspor dashboard statis...
".venv\Scripts\python.exe" scripts/ekspor_statis.py
if errorlevel 1 (
    echo [ERROR] ekspor gagal.
    pause
    exit /b 1
)

echo Commit + push docs/ ...
git add docs/index.html
git commit -m "Ekspor statis dashboard" --quiet
git push origin main
echo.
echo Selesai. Cek https://djanoer.github.io/media-monitor/ beberapa menit lagi.
pause
