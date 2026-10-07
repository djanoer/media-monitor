#!/bin/bash
# ============================================================
# Media Monitor - Pipeline otomatis server (0 token).
# Cron tiap jam: fetch -> respon publik -> ekspor statis -> git push.
#
#   5 * * * * /home/hatch/workspace/media-monitor/pipeline.sh
#
# Exit code: 0 = sukses, 1 = gagal di salah satu tahap.
# Log: ~/workspace/logs/media-monitor/pipeline-YYYYMMDD-HHMM.log
# ============================================================
set -u

ROOT="/home/hatch/workspace/media-monitor"
VENV="$ROOT/.venv-server/bin/python"
LOGDIR="/home/hatch/workspace/logs/media-monitor"
STAMP="$(date +%Y%m%d-%H%M)"
LOG="$LOGDIR/pipeline-$STAMP.log"
LOCKFILE="$ROOT/data/pipeline.lock"

mkdir -p "$LOGDIR"

# Anti-overlap: jika run sebelumnya masih jalan >90 mnt, anggap basi.
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "$(date -Iseconds) | SKIP | pipeline sebelumnya masih berjalan" >> "$LOG"
    exit 0
fi

log() { echo "$(date -Iseconds) | $1 | $2" | tee -a "$LOG"; }
fail() { log "GAGAL" "$1"; exit 1; }

cd "$ROOT" || fail "tidak bisa cd ke $ROOT"

# Muat .env bila ada (API keys)
if [ -f "$ROOT/.env" ]; then
    set -a; . "$ROOT/.env"; set +a
fi

log "MULAI" "pipeline run $STAMP"

# Tahap 1: fetch + unduh isi + analisa sentimen/risiko
log "TAHAP1" "fetch_cycle --once"
"$VENV" run_scheduler.py --once >> "$LOG" 2>&1 \
    || fail "fetch_cycle gagal (lihat log)"

# Tahap 2: respon publik (topik otomatis; best-effort, gagal tidak fatal)
log "TAHAP2" "respon_publik --auto"
"$VENV" scripts/respon_publik.py --auto >> "$LOG" 2>&1 \
    || log "WARN" "respon_publik gagal, lanjut (best-effort)"

# Tahap 3: ekspor statis -> docs/index.html
log "TAHAP3" "ekspor_statis"
"$VENV" scripts/ekspor_statis.py >> "$LOG" 2>&1 \
    || fail "ekspor_statis gagal (lihat log)"

# Tahap 4: commit + push hanya jika ada perubahan (idempoten)
if git diff --quiet docs/ 2>/dev/null; then
    log "TAHAP4" "tidak ada perubahan docs/, skip push"
else
    log "TAHAP4" "push perubahan"
    git add docs/index.html >> "$LOG" 2>&1 \
        || fail "git add gagal"
    git -c user.name="media-monitor-bot" -c user.email="bot@localhost" \
        commit -m "Ekspor otomatis $STAMP" --quiet >> "$LOG" 2>&1 \
        || fail "git commit gagal"
    git push origin main >> "$LOG" 2>&1 \
        || fail "git push gagal"
    log "TAHAP4" "push sukses"
fi

log "SELESAI" "pipeline run $STAMP sukses"
exit 0
