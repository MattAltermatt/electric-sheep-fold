#!/usr/bin/env bash
# Pre-seed /tmp/scrape-<gen>/ from existing local archives so the scraper
# skips re-downloading what we already have. Uses symlinks (no copy, no
# disk waste). For gen 247 the source files lack the canonical
# electricsheep.247. prefix so we rename during the symlink.
#
# Usage:
#   bash scripts/seed_scrape_from_local.sh                  # default src
#   bash scripts/seed_scrape_from_local.sh /path/to/sheep   # alt src root
#
# Source layout expected:
#   <src>/244/electricsheep.244.NNNNN.flam3   (canonical names)
#   <src>/245/electricsheep.245.NNNNN.flam3   (canonical names)
#   <src>/247/NNNNN.flam3                     (stripped names; renamed here)
#
# Safe to re-run: ln -sf overwrites existing symlinks.

set -u
SRC="${1:-/Users/matt/dev/sheep}"
echo "seeding /tmp/scrape-{244,245,247}/ from $SRC"

mkdir -p /tmp/scrape-244 /tmp/scrape-245 /tmp/scrape-247

# 244 — canonical names, symlink straight through
n=0
for f in "$SRC"/244/electricsheep.244.*.flam3; do
  [ -f "$f" ] || continue
  ln -sf "$f" /tmp/scrape-244/
  n=$((n+1))
done
echo "  244: $n symlinks"

# 245 — canonical names
n=0
for f in "$SRC"/245/electricsheep.245.*.flam3; do
  [ -f "$f" ] || continue
  ln -sf "$f" /tmp/scrape-245/
  n=$((n+1))
done
echo "  245: $n symlinks"

# 247 — stripped names (NNNNN.flam3) → rename with electricsheep.247. prefix
n=0
for f in "$SRC"/247/[0-9]*.flam3; do
  [ -f "$f" ] || continue
  id=$(basename "$f" .flam3)
  ln -sf "$f" /tmp/scrape-247/electricsheep.247."${id}".flam3
  n=$((n+1))
done
echo "  247: $n symlinks"

echo "done."
