# 🗺️ Roadmap

> Phases are strategic milestones; the **🚧 Todos** block at the bottom is the
> living set of next concrete actions. Verbose per-phase ship detail lives in
> [`CHANGELOG.md`](CHANGELOG.md).

## ✅ Shipped

- **Phase 1 — v0.1 polite mirror** *(2026-05-19)* — initial polite range-based fetch + sticky-404 + bucket-by-thousand layout.
- **Phase 2 — v0.2 chunked-zip storage** *(2026-05-20)* — sealed-immutable 10k id-range `.zip` chunks + per-chunk `MANIFEST.csv` seam + `fetch-all` + `import` + v0.1→v0.2 auto-migration.
- **Phase 7 — dead-gen archive preservation pipeline** *(2026-05-21)* — `scripts/scrape_archive_gen.py` (enum + discover + sweep) against `electricsheep.com/archives`; sanitizer, parallel driver, multi-flame + `<get>`-envelope parsing.
- **Phase 8 — all dead flam3 gens preserved** *(2026-05-21)* — 165 / 169 / 191 / 198 / 242 / 243 / 244 / 245 fully swept; 130,520 flam3s on disk + 66,556 sticky-404s recorded.
- **Phase 9 — v0.2.1 whole-gen zip policy** *(2026-05-21)* — dead-preserved gens seal as one `00000-NNNNN.zip` instead of synthetic decade chunks; live-preserved gens (247 / 248) keep 10k chunks.
- **Phase 10 — live-gen guard + gen 247 ingest** *(2026-05-21)* — `fetch` / `fetch-all` hard-restricted to `LIVE_GENS = {247, 248}`; gen 247 ingested from `corpus/_scrape-247/` into three working chunks `00000-09999` / `10000-19999` / `20000-29999` (9007 flam3s, awaiting v3d0 fetch-all to complete + seal).

## 🔮 Next phases

### Phase 11a — gen 247 + 248 live-track completion

Run `sheep-fold fetch-all --gen 247` + `--gen 248` against v3d0 to fill the remaining slots. For 247 this completes the existing three working chunks; for 248 this continues the existing fill. Sticky-404 + sealed chunks make both resumable.

### Phase 11b — v0.3 pyr3-facing index / search

Aggregate per-chunk `MANIFEST.csv` rows into a corpus-wide searchable index. Query interface: filter by `xform_count`, variations, has-nick, etc. Subsumes the old "verify subcommand" idea (sha256 in MANIFEST enables verify-as-query) and the BACKLOG `attribution.csv extractor` entry. Open design question carried in BACKLOG: should the aggregator also scan working dirs, or only sealed zips?

### Phase 12 — pyr3 integration

pyr3 reads `corpus/{gen}/` (sealed zips + index) as parity-test source. The point of the whole exercise.

### Phase 13 — public corpus repo (optional) 🌐

Push sealed chunks to a separate `MattAltermatt/electric-sheep-fold-corpus` GitHub repo; chunked zips are the natural distribution unit.

### Phase 14 — additional generations 🐑

Run `sheep-fold fetch-all --gen 249` (etc.) as ES rolls over. Same tool, no code changes.

## 🚧 Todos (next session)

- Run `sheep-fold fetch-all --gen 247` against v3d0 to backfill the three working chunks (currently 9007 flam3s; need missing.txt populated to seal).
- Continue `sheep-fold fetch-all --gen 248` live track.
- Start Phase 11b (v0.3) design round; revisit the working-dir-vs-sealed-only aggregator question.
