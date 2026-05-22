#!/usr/bin/env bash
# Assemble the GitHub Release artifact set from current corpus/ state.
#
# Thin wrapper around `sheep-fold release-build`. Output: build/release/
# (gitignored) containing:
#   gen-{N}.zip          (one per generation — MANIFEST.csv + missing.txt + flat .flam3s)
#   corpus-all.zip       (mega-bundle: every gen-zip + index + attribution)
#   INDEX.md             (human + agent-readable corpus index)
#   index.json           (machine-queryable corpus index)
#   ATTRIBUTION.md       (Sheep-Pack attribution per ES license)
#
# Re-runnable; the release-build command writes atomically and overwrites
# existing artifacts in --out.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORPUS="${CORPUS:-$REPO_ROOT/corpus}"
OUT="${OUT:-$REPO_ROOT/build/release}"

sheep-fold release-build --corpus "$CORPUS" --out "$OUT"

echo
echo "==> Release assets in $OUT:"
ls -1sh "$OUT" | sed 's/^/    /'
echo
echo "==> total size:"
du -sh "$OUT" | sed 's/^/    /'
echo
echo "Next: create the Release with:"
echo
echo "  gh release create vX.Y.Z \\"
echo "    --title 'vX.Y.Z — corpus snapshot' \\"
echo "    --notes-file <(cat $REPO_ROOT/docs/release-notes-vX.Y.Z.md) \\"
echo "    $OUT/*"
