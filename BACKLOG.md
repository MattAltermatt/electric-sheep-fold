# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

## Tooling / ingest

- **🩹 Sticky-404 set lost for live-gen pre-seeded ranges (2026-05-22).** Sealed
  whole-gen zips `corpus/247/00000-29999.zip` (9006 flames) and
  `corpus/248/00000-19999.zip` (2926 flames) violate the `is_range_complete`
  invariant: their `missing.txt` only accounts for 15 and 6163 ids in-range
  respectively, leaving ~20979 (247) + ~10911 (248) gap-ids that fetch-all now
  re-probes at 20s cadence (~5d + ~2.5d wasted). **Symptom (observed 2026-05-22):**
  `scripts/resume_live_fetch.sh` hits network on 247.00036 (404) instead of
  skip-known-missing. **Hypothesis (unverified):** seal was done from
  pre-seeded local archive (`/Users/matt/dev/sheep/247`) via a path that didn't
  populate or enforce missing.txt for [0, zip_end). **Next phase:** verify
  hypothesis against current code first. Two fixes (sequenced):
  1. *Back-fill migration* — for each sealed zip, compute
     `set(range(start, end)) - set(zip_contents)` and add to `missing.txt`.
     One-time sub-second per gen. Conservative (assumes gaps = 404s).
  2. *Embed MISSING in zip* — extend seal to write `MISSING.csv` alongside
     `MANIFEST.csv` inside the zip; load it at fetch-start. Removes the
     seal-and-purge failure mode entirely. Pairs with the back-fill above.
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
