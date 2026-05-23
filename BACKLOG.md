# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

## v0.3 polish (deferred from Phase F code review)

- **🪶 Stream `.flam3` bytes in `release.py:_gather_gen_data`.** Currently
  loads every flam3 into memory at once → peak RAM ~1.3 GB for gen 244
  (86k files × ~15 KB). Fine on a 16 GB Mac but scales linearly with
  corpus growth. Fix: pass file paths through to `zipfile.write(path,
  arcname=...)` for loose-mode gens; keep the in-memory dict for the
  sealed-transit fallback (already in RAM via `zf.read`). One-day task.
- ~~**🪶 Promote `MissingSet._ids` to a public `sorted_ids()` accessor.**~~
  ✅ Resolved by Phase 0 cleanup of v0.4 (c35ed6e, 2026-05-23) —
  `sorted_ids()` added to `manifest.py`; `release.py` call site no longer
  needs the noqa-SLF001 carve-out.
- **🪶 `verify_unseal_consistency` should compare id-sets, not just
  counts.** Current check catches deletions (`actual_total <
  expected_total`) but a `missing.txt` overwrite that ADDS bogus entries
  while losing real ones could net out to the same total and slip
  through. The v0.2.2 incident class was net-smaller (matches current
  check) but a stronger diff would close the gap. Small.

## Tooling / ingest

- ~~**🗜️ Ship `.7z` Release artifact alongside `.zip`.**~~ ✅ Subsumed by
  v0.4's `corpus-all-{date}.tar.xz` mega-bundle (2026-05-23). tar.xz
  uses the same LZMA2 algorithm as 7z and ships in Python's stdlib (no
  new deps), with the cleanest cross-platform story (native on
  macOS / Linux; Windows via 7-Zip / WSL). Per-gen artifacts stay ZIP
  DEFLATE-9 since LZMA's cross-file dictionary advantage doesn't apply
  inside a single gen. Closed without separate .7z artifact.

## v0.5 candidates (post-v0.4)

- **Runtime NaN detection (`produces_nan: bool`).** Static checks
  (the v0.4 5-field set) catch the majority of NaN producers; a short
  chaos-game probe per genome would catch residuals. Index-build cost
  scales linearly; gate on whether v0.4's static-only verdict misses
  enough cases to matter for pyr3 integration.
- **Tone-mapping diversity fields.** Surface `gamma`, `vibrancy`,
  `estimator_minimum`, `estimator_curve` (the rest of the
  density-estimator + tone-map family). Currently only
  `has_density_estimator` is exposed.
- **Provenance field (`version`).** Flam3 root carries `version` (the
  renderer that produced this genome). Useful for archival forensics
  and pyr3 version-targeting.
- **gen 249+ live extension.** When ES rolls a new live gen: one-line
  edit to `LIVE_GENS` in `layout.py`, then `fetch-all --gen 249`.
- **Streaming `.flam3` bytes in `release.py:_gather_gen_data`.** Currently
  loads every flam3 into memory at once → peak RAM ~1.3 GB for gen 244
  (86k files × ~15 KB). Defer until corpus growth makes single-machine
  release-build painful. (Was a v0.3 polish entry — still valid post-v0.4.)
- **`verify_chunked_consistency` id-set comparison.** Current check
  catches deletions via count-shrinkage; a stronger diff that compares
  id-sets between baseline and current would close the
  "missing.txt-overwrite-that-nets-out-the-same-count" gap.
- ~~**📦 Embed MISSING.csv in sealed zips.**~~ ✅ Resolved by Phase 12b
  (v0.3 loose-corpus separation) — `missing.txt` now travels inside each
  release zip alongside `MANIFEST.csv`. The structural defense against
  bad-seal context loss is achieved by retiring seals entirely.
- **Sidecar files** — `--include-sidecars` flag if pyr3 ever needs `state.fsd` /
  `memory` / `spex`.
- **Browsable gallery** — GitHub Pages thumbnail grid (downstream of Phase 4 —
  needs pyr3 rendering to PNGs first).
- **Retry-known-missing** — `--retry-missing` flag if ES ever shifts numbering
  semantics. Not needed under current "gaps stay gaps" invariant.
- **Resume-on-SIGTERM banner** — print "Resuming from sheep N" on startup when a
  partial run is detected.
- **Server-index cache** — save the gen-NNN index HTML (~6MB for 248) as a
  one-time preservation artifact in case ES goes dark.
- ~~**`reseal --gen N`**~~ ✅ Resolved by Phase 12b — `sheep-fold release-build`
  rebuilds release zips from current loose corpus on demand; MANIFEST.csv
  schema extension only needs a re-run, not a multi-step reseal.
- ~~**`prune --gen N --id RANGE`**~~ ✅ Trivial under Phase 12b loose
  corpus — just `rm corpus/N/electricsheep.N.{id}.flam3` (and optionally
  add the id to `missing.txt` if it should sticky-skip future fetches).
  No CLI surface needed.
- **Range-discovery from server index HTML** — instead of `--upper 50000`, parse
  `/gen/N/` HTML once to determine the true upper bound.
- **Parallel chunk seal** — almost certainly never needed.
- ~~**Index-on-the-fly during fetch**~~ ✅ Moot under Phase 12b — no chunks
  to crash mid-write; loose `.flam3` files are individually atomic-written
  and the index regen reads them directly.
- ~~**`corpus/{gen}/index.csv` chunk overview**~~ ✅ Resolved by Phase 12b
  — no chunks. `sheep-fold status` covers per-gen file + missing counts.
- ~~**v0.3 design question: should the index aggregator also scan working
  dirs?**~~ — ✅ Resolved in Phase 11a (`sheep-fold index`): yes, it does.
  `iter_corpus_flames` walks sealed zips AND working-dir chunks; each record
  carries `sealed: bool` so agents can filter to frozen-only when needed.
