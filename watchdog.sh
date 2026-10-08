#!/bin/bash
# Watchdog media-monitor: cek loop tiap 5 menit, nyalakan ulang + notif Telegram jika mati.
# 0 token Muse. Dijalankan sebagai background process terpisah.
set -u
REPO="$HOME/workspace/media-monitor"
LOGDIR="$HOME/workspace/logs/media-monitor"
mkdir -p "$LOGDIR"
WLOG="$LOGDIR/watchdog.log"

# Muat kredensial Telegram
if [ -f "$REPO/.env" ]; then
    set -a; . "$REPO/.env"; set +a
fi

notif() {
    local pesan="$1"
    echo "[$(date '+%F %T')] $pesan" >> "$WLOG"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -m 15 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=${pesan}" \
            -d "parse_mode=HTML" > /dev/null 2>&1
    fi
}

echo "[$(date '+%F %T')] watchdog dimulai" >> "$WLOG"

while true; do
    sleep 300  # cek tiap 5 menit
    if ! pgrep -f "run_loop.sh" > /dev/null; then
        notif "⚠️ <b>Media Monitor</b>: loop terdeteksi mati, menyalakan ulang..."
        bash "$REPO/run_loop.sh" > /dev/null 2>&1 &
        sleep 5
        if pgrep -f "run_loop.sh" > /dev/null; then
            notif "✅ <b>Media Monitor</b>: loop berhasil dinyalakan ulang."
        else
            notif "❌ <b>Media Monitor</b>: GAGAL menyalakan ulang! Perlu intervensi manual."
        fi
    fi
done
