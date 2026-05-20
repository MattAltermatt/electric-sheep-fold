# 📝 Changelog

## v0.2.0 — 2026-05-20

Storage refactor + ergonomics.

- Chunked `.zip` storage at 10k id-range per chunk; sealed-immutable once a
  chunk's range is fully probed
- Per-chunk `MANIFEST.csv` inside each sealed zip (id, sha256, fetched_at,
  source_url, name, nick, url, xform_count, final_xform, variations) — seam for
  the v0.3 pyr3-facing index
- Automatic v0.1 → v0.2 migration on first fetch (one-shot, idempotent)
- New: `electric-sheep-fold fetch-all` — fetch entire gen range
- New: `electric-sheep-fold import <dir>` — bulk-import existing local flames
- New: `electric-sheep-fold seal --chunk NNNNN-NNNNN` — force-seal an incomplete chunk
- `status` extended to show per-chunk state breakdown
- All v0.1 invariants preserved (politeness, sticky-404, atomic writes,
  filename preservation, license obligations)

### Deferred to v0.3

- `corpus/{gen}/index.csv` chunk-overview file (spec §5.8). `status` covers
  the user-visible need via filesystem glob; v0.3's aggregated MANIFEST.csv
  reader likely subsumes this.

## v0.1.0 — 2026-05-19

Initial ship.

- Polite range-based mirror of `.flam3` files from `v3d0.sheepserver.net/gen/248/`
- Sticky 404 memory via `corpus/{gen}/missing.txt`
- Local-first dedup; skips cost zero server time
- Atomic writes (tmp + `os.replace`); SIGKILL-safe
- Bucket-by-thousand on-disk layout (`248/00xxx/`…`248/40xxx/`)
- Auto-copied `corpus/ATTRIBUTION.md` (Sheep-Pack obligation per
  [electricsheep.org/license](https://electricsheep.org/license/))
- Typer CLI: `electric-sheep-fold fetch`, `electric-sheep-fold status`
- pytest suites for `layout`, `manifest`, `fetch` (mock-transport, no real network)
