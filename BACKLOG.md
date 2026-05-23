# 🗃️ Backlog (unphased)

Forward-looking deferred TODO. Pull forward when one becomes load-bearing.
Shipped items live in [CHANGELOG.md](CHANGELOG.md); they do NOT linger here.

## Index richness (post-v0.4 — would land in a future schema bump)

- **Runtime NaN detection (`produces_nan: bool`).** Static checks (the
  v0.4 five-field set) catch the majority of NaN producers; a short
  chaos-game probe per genome would catch residuals. Index-build cost
  scales linearly; gate on whether v0.4's static-only verdict misses
  enough cases to matter for pyr3 integration.
- **Tone-mapping diversity fields.** Surface `gamma`, `vibrancy`,
  `estimator_minimum`, `estimator_curve` — the rest of the
  density-estimator + tone-map family. Currently only
  `has_density_estimator` is exposed.
- **Provenance field (`version`).** Flam3 root carries `version` (the
  renderer that produced this genome). Useful for archival forensics
  and pyr3 version-targeting.

## Index query ergonomics (Phase 12c candidate)

- **SQLite-backed query interface.** Faster than scanning the 60+ MB
  `index.json` for repeat lookups. Build on demand from `index.json`;
  index.json stays canonical.
- **Curated examples file (`curated.md` analog).** Hand-picked
  pyr3-parity references + stress-test cases.
- **Palette-hash field.** Group genomes by visually-equivalent
  palettes for de-duped browsing.
- **Incremental rebuild.** Rebuild only gens whose `_chunked-verified.json`
  `loose_count` changed since last index — chunked layout makes this
  trivial (per-bucket mtime).

## Release artifact

- **Streaming `.flam3` bytes in `release.py:_gather_gen_data`.** Currently
  loads every flam3 into memory at once → peak RAM ~1.3 GB for gen 244
  (86k files × ~15 KB). Defer until corpus growth makes single-machine
  release-build painful. Fix: pass file paths through to
  `zipfile.write(path, arcname=...)` for loose-mode gens; keep the
  in-memory dict for the sealed-transit fallback.
- **id-set diff for consistency checks.** Both `verify_unseal_consistency`
  and `verify_chunked_consistency` catch deletions via count
  shrinkage, but a `missing.txt` overwrite that ADDS bogus entries
  while losing real ones could net out to the same total and slip
  through. A stronger id-set diff against the post-migrate baseline
  would close the gap.

## Live preservation

- **gen 249+ live extension.** When ES rolls a new live gen: one-line
  edit to `LIVE_GENS` in `layout.py`, then `fetch-all --gen 249`.
- **Range-discovery from server index HTML.** Instead of `--upper 50000`,
  parse `/gen/N/` HTML once to determine the true upper bound and
  auto-extend.
- **Resume-on-SIGTERM banner.** Print "Resuming from sheep N" on startup
  when a partial run is detected.
- **Server-index cache.** Save the `/gen/NNN/` index HTML (~6 MB for
  gen 248) as a one-time preservation artifact in case the live server
  goes dark before we finish a sweep.
- **Retry-known-missing.** `--retry-missing` flag if ES ever shifts
  numbering semantics. Not needed under current "gaps stay gaps"
  invariant.

## Consumer-facing

- **Sidecar files.** `--include-sidecars` flag if pyr3 ever needs
  `state.fsd` / `memory` / `spex` alongside the `.flam3`.
- **Browsable gallery.** GitHub Pages thumbnail grid — downstream of
  pyr3 integration (needs pyr3 rendering to PNGs first).
