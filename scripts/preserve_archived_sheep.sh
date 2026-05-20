#!/usr/bin/env bash
# Download archived sheep (electricsheep.com/archives) for every dead
# generation, sequentially, smallest-first. Polite 2s ±1s cadence (static
# archive content). Resumable: rerun picks up where it left off.
#
# Does NOT touch v3d0 — that's the live-fetch flow for gens 247 + 248
# (use `electric-sheep-fold fetch-all` for those).
#
# Usage:
#   bash scripts/preserve_archived_sheep.sh           # all default gens
#   bash scripts/preserve_archived_sheep.sh 242 243   # specific gens
#
# Output:
#   /tmp/scrape-<gen>/electricsheep.<gen>.NNNNN.flam3   (canonical names)
#   /tmp/scrape-<gen>/_enumerated_ids.txt               (resume cache)
#   /tmp/scrape-<gen>/_missing_404.txt                  (404 ledger)
#   /tmp/preserve-archived.log                          (combined log)
#
# When done (or anytime — each gen is independent), import + force-seal:
#   electric-sheep-fold import /tmp/scrape-242
#   electric-sheep-fold seal --chunk 00000-09999 --gen 242
#
# Estimated total time @ 2s cadence:
#   gen 242 (~3,584 sheep)   →  ~2 hr
#   gen 243 (~6,080)         →  ~3.4 hr
#   gen 245 (~12,096)        →  ~6.7 hr
#   gen 191 (~21,760)        →  ~12 hr
#   gen 244 (~32,000)        →  ~17.8 hr
#   gen 198 (~31,936)        →  ~17.8 hr
#   total                    →  ~60 hr (~2.5 days continuous)

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

LOG="/tmp/preserve-archived.log"
GENS=("$@")
if [ ${#GENS[@]} -eq 0 ]; then
  GENS=(242 243 245 191 244 198)
fi

echo "[$(date '+%F %T')] preserve_archived_sheep: gens ${GENS[*]}" | tee -a "$LOG"
for G in "${GENS[@]}"; do
  OUT="/tmp/scrape-$G"
  echo "[$(date '+%F %T')] === gen $G -> $OUT ===" | tee -a "$LOG"
  python scripts/scrape_archive_gen.py --gen "$G" --out "$OUT" 2>&1 | tee -a "$LOG"
  echo "[$(date '+%F %T')] gen $G done" | tee -a "$LOG"
done
echo "[$(date '+%F %T')] all gens done" | tee -a "$LOG"
