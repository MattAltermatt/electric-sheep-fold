#!/usr/bin/env bash
# Resume the live-server fetch for both live gens (247 + 248), sequentially.
#
# Honors the live-server invariant: 20s ±5s jitter, strictly sequential —
# never two fetchers against v3d0.sheepserver.net at once. Gens 247 and 248
# run back-to-back, not in parallel. Skip-known-missing + on-disk skips are
# built into the fetcher, so re-runs cost zero server time on prior ids.
#
# If a chain is already running, this script attaches to its log instead of
# launching a second one.
#
# Usage:
#   scripts/resume_live_fetch.sh          # gens 247 then 248, upper 50000
#   scripts/resume_live_fetch.sh 60000    # custom upper for both gens

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

UPPER="${1:-50000}"
GENS=(247 248)

LOGDIR="corpus/_live-fetch-logs"
mkdir -p "$LOGDIR"
PIDFILE="$LOGDIR/.chain.pid"

attach_existing() {
  local pid="$1"
  local log
  log="$(lsof -p "$pid" 2>/dev/null \
    | awk -v d="$LOGDIR" '$NF ~ d"/fetch-live-" {print $NF; exit}')"
  if [ -z "$log" ]; then
    log="$(ls -t "$LOGDIR"/fetch-live-*.log 2>/dev/null | head -1)"
  fi
  echo "already running: pid $pid  log: $log"
  echo "tailing existing log (Ctrl-C exits tail; does NOT stop fetch)..."
  echo
  exec tail -f "$log"
}

# Existing chain wrapper?
if [ -f "$PIDFILE" ]; then
  EXISTING_PID="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$EXISTING_PID" ] && kill -0 "$EXISTING_PID" 2>/dev/null; then
    attach_existing "$EXISTING_PID"
  fi
  rm -f "$PIDFILE"
fi

# Bare fetch-all running outside the chain wrapper?
BARE_PID="$(pgrep -f "sheep-fold fetch-all" | head -1)"
if [ -n "$BARE_PID" ]; then
  attach_existing "$BARE_PID"
fi

LOG="$LOGDIR/fetch-live-$(date +%Y%m%d-%H%M).log"

nohup bash -c '
  set -u
  for gen in '"${GENS[*]}"'; do
    echo "=== gen $gen — starting at $(date -u +%FT%TZ) ==="
    sheep-fold fetch-all --gen "$gen" --upper "'"$UPPER"'" || echo "=== gen $gen — exited nonzero ==="
    echo "=== gen $gen — finished at $(date -u +%FT%TZ) ==="
  done
  echo "=== chain complete at $(date -u +%FT%TZ) ==="
' > "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"
disown

echo "launched chain: gens ${GENS[*]}  upper $UPPER  (wrapper pid $PID)"
echo "log: $LOG"
echo "stop with: kill $PID  (kills the wrapper AND any child fetch-all)"
echo
echo "tailing (Ctrl-C exits tail; does NOT stop chain)..."
echo
sleep 1
exec tail -f "$LOG"
