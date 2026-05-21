#!/usr/bin/env bash
# Preserve every dead Electric Sheep generation from electricsheep.com.
#
# Three phases per gen: time-page enum → upper-bound discovery → gap sweep.
# Multiple gens run in parallel (different URL paths) to compress wall-clock;
# per-gen cadence stays at 2s±1s. Aggregate request rate at the default
# parallelism is ~few req/s — gentle for the archive's AWS-backed host.
#
# Does NOT touch v3d0 — that's the live-fetch flow (gens 247 + 248), use
# `electric-sheep-fold fetch-all` for those.
#
# Usage:
#   bash scripts/preserve_archived_sheep.sh                   # all dead gens, default parallelism
#   bash scripts/preserve_archived_sheep.sh -p 6              # cap at 6 workers
#   bash scripts/preserve_archived_sheep.sh 242 243           # specific gens (still parallel)
#   bash scripts/preserve_archived_sheep.sh -p 1 244          # single-gen sequential
#
# Output (repo-local; `corpus/` is gitignored):
#   corpus/_scrape-<gen>/electricsheep.<gen>.NNNNN.flam3   (canonical names)
#   corpus/_scrape-<gen>/_enumerated_ids.txt               (time-page cache)
#   corpus/_scrape-<gen>/_discovered_max_id.txt            (upper-bound cache)
#   corpus/_scrape-<gen>/_missing_404.txt                  (sticky 404 ledger)
#   corpus/_scrape-<gen>/_worker.log                       (per-gen log)
#   corpus/_scrape-preserve-archived.log                   (driver log)
#
# When each gen finishes, import + force-seal:
#   electric-sheep-fold import corpus/_scrape-<gen>
#   electric-sheep-fold seal --chunk NNNNN-NNNNN --gen <gen>   # for partial-final chunks

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

# Default dead-gen list per CLAUDE.md (numeric only — 'old' / 'very-old' need
# importer support before they can flow through; tracked separately).
DEFAULT_GENS=(23 165 169 191 198 242 243 244 245)
PARALLEL=4

usage() {
  cat <<EOF
Usage: $0 [-p N] [gen ...]
  -p N    max parallel workers (default 4)
  gen     specific gens to run (default: ${DEFAULT_GENS[*]})
EOF
  exit 1
}

while getopts ":p:h" opt; do
  case $opt in
    p) PARALLEL=$OPTARG ;;
    h) usage ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))

GENS=("$@")
if [ ${#GENS[@]} -eq 0 ]; then
  GENS=("${DEFAULT_GENS[@]}")
fi

DRIVER_LOG="corpus/_scrape-preserve-archived.log"
mkdir -p corpus
echo "[$(date '+%F %T')] preserve_archived_sheep: gens=${GENS[*]} parallel=$PARALLEL" \
  | tee -a "$DRIVER_LOG"

# Launch each gen as a background worker with its own log.
PIDS=()
RUNNING=0
LAUNCHED=0
for G in "${GENS[@]}"; do
  # Throttle to PARALLEL concurrent workers.
  while [ $RUNNING -ge $PARALLEL ]; do
    if wait -n 2>/dev/null; then
      RUNNING=$((RUNNING - 1))
    else
      # bash <4.3 may not support `wait -n`; fall back to waiting for first PID
      wait "${PIDS[0]}" 2>/dev/null
      PIDS=("${PIDS[@]:1}")
      RUNNING=$((RUNNING - 1))
    fi
  done

  OUT="corpus/_scrape-$G"
  mkdir -p "$OUT"
  WORKER_LOG="$OUT/_worker.log"
  echo "[$(date '+%F %T')] launching worker gen=$G -> $OUT" | tee -a "$DRIVER_LOG"
  (
    python3 scripts/scrape_archive_gen.py --gen "$G" --out "$OUT" \
      2>&1 | tee -a "$WORKER_LOG"
    echo "[$(date '+%F %T')] gen $G worker done" >> "$DRIVER_LOG"
  ) &
  PIDS+=("$!")
  LAUNCHED=$((LAUNCHED + 1))
  RUNNING=$((RUNNING + 1))
done

# Drain remaining workers
while [ $RUNNING -gt 0 ]; do
  if wait -n 2>/dev/null; then
    RUNNING=$((RUNNING - 1))
  else
    wait "${PIDS[0]}" 2>/dev/null
    PIDS=("${PIDS[@]:1}")
    RUNNING=$((RUNNING - 1))
  fi
done

echo "[$(date '+%F %T')] all $LAUNCHED workers done" | tee -a "$DRIVER_LOG"
