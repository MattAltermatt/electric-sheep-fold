#!/usr/bin/env bash
# Live dashboard for the dead-gen preservation sweep.
#
# Refreshes every 5 seconds. Shows per-gen on-disk count and most recent
# log line tail. Ctrl-C to exit — does NOT touch the sweep itself.
#
# Usage:
#   scripts/watch_sweep.sh            # default 5s refresh, all gens
#   scripts/watch_sweep.sh 2          # 2s refresh
#   scripts/watch_sweep.sh 5 165 169  # only those gens

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

INTERVAL="${1:-5}"
shift 2>/dev/null || true

DEFAULT_GENS=(165 169 191 198 242 243 244 245)
GENS=("$@")
if [ ${#GENS[@]} -eq 0 ]; then
  GENS=("${DEFAULT_GENS[@]}")
fi

while true; do
  clear
  echo "=== electric-sheep-fold sweep — $(date '+%F %T') ==="
  ACTIVE=$(pgrep -f scrape_archive_gen.py 2>/dev/null | wc -l | tr -d ' ')
  echo "active workers: $ACTIVE"
  echo
  printf "  %-5s %10s  %s\n" "gen" "on-disk" "latest log line"
  printf "  %-5s %10s  %s\n" "---" "-------" "---------------"
  for G in "${GENS[@]}"; do
    DIR="corpus/_scrape-$G"
    N=$(find "$DIR" -maxdepth 1 -name "electricsheep.$G.*.flam3" 2>/dev/null | wc -l | tr -d ' ')
    # Pull a short tag from the latest log entry without baroque regex.
    LATEST=$(tail -1 "$DIR/_worker.log" 2>/dev/null | sed 's/.*\[gen=[^]]*\] //' | cut -c1-80)
    printf "  %-5s %10s  %s\n" "$G" "$N" "$LATEST"
  done
  echo
  echo "(refresh ${INTERVAL}s · Ctrl-C to exit)"
  sleep "$INTERVAL"
done
