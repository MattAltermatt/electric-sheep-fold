#!/usr/bin/env bash
# Assemble the GitHub Release artifact set from current corpus/ state.
#
# Output: build/release/ (gitignored) containing:
#   gen-{N}.zip          (one per generation — renamed from corpus/{N}/NNNNN-NNNNN.zip)
#   corpus-all.zip       (mega-bundle: every gen + index + attribution)
#   INDEX.md             (human + agent-readable corpus index)
#   index.json           (machine-queryable corpus index)
#   ATTRIBUTION.md       (Sheep-Pack attribution per ES license)
#
# Re-runnable; overwrites build/release/ on each invocation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORPUS="${CORPUS:-$REPO_ROOT/corpus}"
OUT="${OUT:-$REPO_ROOT/build/release}"

if [[ ! -d "$CORPUS" ]]; then
  echo "error: corpus dir not found at $CORPUS" >&2
  exit 1
fi

echo "==> regenerating index (sheep-fold index --corpus $CORPUS)"
sheep-fold index --corpus "$CORPUS"

echo "==> preparing $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"

echo "==> assembling per-gen Release assets"
for gen_dir in "$CORPUS"/*/; do
  gen_name="$(basename "$gen_dir")"
  # Skip _index/ and any non-numeric subdirs (e.g. _scrape-*)
  if ! [[ "$gen_name" =~ ^[0-9]+$ ]]; then
    continue
  fi

  # Find the single sealed zip for this gen.
  zip_files=("$gen_dir"/?????-?????.zip)
  if [[ ${#zip_files[@]} -ne 1 ]] || [[ ! -f "${zip_files[0]}" ]]; then
    echo "error: expected exactly one sealed zip in $gen_dir, found ${#zip_files[@]}" >&2
    echo "       (Phase A must collapse live gens before building a Release)" >&2
    exit 1
  fi

  cp "${zip_files[0]}" "$OUT/gen-${gen_name}.zip"
  echo "    gen-${gen_name}.zip ← $(basename "${zip_files[0]}")"
done

echo "==> copying index + attribution"
cp "$CORPUS/_index/index.json" "$OUT/index.json"
cp "$CORPUS/_index/INDEX.md" "$OUT/INDEX.md"
cp "$CORPUS/ATTRIBUTION.md" "$OUT/ATTRIBUTION.md"

echo "==> building corpus-all.zip mega-bundle"
(
  cd "$OUT"
  # -q quiet, -X strip extra (mtime + perms) for reproducibility
  zip -q -X corpus-all.zip gen-*.zip INDEX.md index.json ATTRIBUTION.md
)

echo
echo "==> Release assets in $OUT:"
ls -1sh "$OUT" | sed 's/^/    /'
echo
echo "==> total size:"
du -sh "$OUT" | sed 's/^/    /'
echo
echo "Next: create the Release with:"
echo
echo "  gh release create v0.2.2 \\"
echo "    --title 'v0.2.2 — corpus snapshot' \\"
echo "    --notes-file <(cat $REPO_ROOT/docs/release-notes-v0.2.2.md) \\"
echo "    $OUT/*"
