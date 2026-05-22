# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

## Tooling / ingest

- **🗜️ Ship `.tar.xz` Release artifact alongside `.zip`.** Deferred 2026-05-22
  pending real demand. Benchmark on gen 244 (943 MB uncompressed): current
  DEFLATE-9 zip = 214 MB; `tar.xz` preset-9e = 58 MB (**−73%**). Whole-corpus
  projection: ~525 MB → ~140 MB. Solid LZMA2 dedupes across the 33k+ entries'
  shared XML scaffolding / palette structure, which per-entry DEFLATE can't
  see. **Why not in-tree:** in-tree zips are hot-path random-access for
  `sheep-fold fetch / import / index` AND agentic `jq` queries; solid
  archives require decompressing up to the target entry. Keep `.zip` in
  tree, add `.tar.xz` only as a Release-distribution-only artifact for
  fresh-install downloaders. Pull forward when someone complains about
  download size. *Rejected sibling:* LZMA-in-zip is portable to bsdtar /
  Finder but **silently skips on Info-ZIP `unzip` 6.00** (default on macOS
  + most Linux), so a non-starter for zip-format compatibility claims.
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
