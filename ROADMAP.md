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

## 🔮 Next phases

### Phase 10 — gen 248 live-track resume

Continue `sheep-fold fetch-all --gen 248` to fill the remaining slots on the live v3d0 server (sticky-404 + sealed chunks make this resumable). Then `--gen 247` for what v3d0 still serves live.

### Phase 11 — v0.3 pyr3-facing index / search

Aggregate per-chunk `MANIFEST.csv` rows into a corpus-wide searchable index. Query interface: filter by `xform_count`, variations, has-nick, etc. Subsumes the old "verify subcommand" idea (sha256 in MANIFEST enables verify-as-query) and the BACKLOG `attribution.csv extractor` entry. Open design question carried in BACKLOG: should the aggregator also scan working dirs, or only sealed zips?

### Phase 12 — pyr3 integration 🔥

pyr3 reads `corpus/{gen}/` (sealed zips + index) as parity-test source. The point of the whole exercise.

### Phase 13 — public corpus repo (optional) 🌐

Push sealed chunks to a separate `MattAltermatt/electric-sheep-fold-corpus` GitHub repo; chunked zips are the natural distribution unit.

### Phase 14 — additional generations 🐑

Run `sheep-fold fetch-all --gen 249` (etc.) as ES rolls over. Same tool, no code changes.

## 🚧 Todos (next session)

- Resume `sheep-fold fetch-all --gen 248` live track.
- Decide gen 247 plan: live-via-v3d0 vs treat as dead-gen archive (v3d0 still serves it but trickle-rate; `corpus/_scrape-247/` has 9007 symlinks pre-seeded from `~/dev/sheep/247/`). Same chunk shape either way under v0.2.1.
- Start Phase 11 (v0.3) design round; revisit the working-dir-vs-sealed-only aggregator question.
