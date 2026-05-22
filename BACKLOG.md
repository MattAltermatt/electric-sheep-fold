# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

## Tooling / ingest

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
- **v0.3 design question: should the index aggregator also scan working dirs?**
  Per-chunk `MANIFEST.csv` is only built at seal time, so working-dir flames have
  no structured metadata until their chunk completes. A chunk that stays
  partially probed for years means those files are invisible to v0.3's pyr3
  index until either (a) the chunk seals naturally, (b) the user force-seals via
  `seal --chunk`, or (c) v0.3 grows on-the-fly extraction for working-dir files.
  Decision deferred to v0.3 design round; option (c) is more inclusive but
  costlier per query. Note: also informs the future `reseal` design (combining
  a force-sealed zip + new working dir back into one consistent zip).
