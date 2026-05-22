# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

## Tooling / ingest

- **📦 Embed MISSING.csv in sealed zips.** Extend `Chunk.seal()` to write
  `MISSING.csv` alongside `MANIFEST.csv` listing every id in `[start, end)`
  that isn't a `.flam3` member (one row per id, plus `reason` /
  `recorded_at` columns mirroring the working missing.txt entries). Pure
  additive seal-format change; backwards-compatible (older consumers
  ignore the extra entry). Provenance value for the v0.3+ pyr3-facing
  index — lets agents answer "why is this id missing?" against the
  sealed artifact alone, without needing a live `missing.txt`. Also
  structural defense against future manual-ops bad seals like the v0.2.2
  collapse that produced sparse `corpus/247/00000-29999.zip` +
  `corpus/248/00000-19999.zip` (now handled by v0.2.4's range-trust
  skip-check, but embedded MISSING would have prevented the lost-context
  entirely).
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
- **`reseal --gen N`** — re-extract + re-seal all chunks with the current schema.
  Needed when v0.3+ extends MANIFEST.csv columns.
- **`prune --gen N --id RANGE`** — remove sheep from a sealed chunk (re-seal
  pathway). Rare; useful if a corrupt flam3 is discovered.
- **Range-discovery from server index HTML** — instead of `--upper 50000`, parse
  `/gen/N/` HTML once to determine the true upper bound.
- **Parallel chunk seal** — almost certainly never needed.
- **Index-on-the-fly during fetch** — write `MANIFEST.csv` rows incrementally
  during fetch (not just at seal time) for crash-resilience of partial chunks.
- **`corpus/{gen}/index.csv` chunk overview** — per-gen file tracking chunk
  status + `sealed_at` timestamps. Spec §5.8. v0.3's aggregated index likely
  subsumes this; revisit when v0.3 lands.
- ~~**v0.3 design question: should the index aggregator also scan working
  dirs?**~~ — ✅ Resolved in Phase 11a (`sheep-fold index`): yes, it does.
  `iter_corpus_flames` walks sealed zips AND working-dir chunks; each record
  carries `sealed: bool` so agents can filter to frozen-only when needed.
