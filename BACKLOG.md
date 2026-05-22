# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

## Tooling / ingest

- **🗜️ Ship `.7z` Release artifact alongside `.zip`.** Deferred 2026-05-22
  pending v0.3 ship. User-confirmed 7z extraction works fine on current
  macOS (Tahoe / Darwin 25) via native Archive Utility — the old
  "consumer needs Keka" objection was stale. User-reported ratio: 517 MB
  flam3 corpus → 5.4 MB (~96× compression). Subsumes the prior tar.xz
  entry (7z has cleaner cross-platform tooling story + same LZMA2
  underneath). **Why deferrable:** under v0.3 the on-disk corpus is loose
  `.flam3` files — random-access concerns no longer apply to the release
  artifact (which is download-and-extract only). Solid 7z's lack of
  random read inside the archive is irrelevant when the consumer's first
  step is `7zz x`. **Shape options when pulled forward:**
  - **A · Mega-bundle only.** Keep per-gen `gen-{N}.zip` (granular,
    universally supported); add `corpus-all.7z` alongside `corpus-all.zip`.
    Lowest-friction; serves bandwidth-conscious whole-corpus downloaders.
  - **B · Multi-format per gen.** Ship both `gen-{N}.zip` and `gen-{N}.7z`
    per gen. Double upload time + storage but consumers pick their poison.
  - **C · 7z as default.** All artifacts `.7z`; `.zip` becomes an optional
    legacy path. Smallest releases, highest tooling assumption.
  Pull forward when corpus growth makes the zip download size painful
  (e.g. live gen 247 cresting 50k+ sheep).
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
