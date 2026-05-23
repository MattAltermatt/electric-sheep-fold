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
- **Phase 10b — partial unseal for in-progress live chunks** *(2026-05-21)* — `247/00000-09999` + `247/10000-19999` + `248/00000-09999` stay sealed (archive-snapshot final); `247/20000-29999` + `248/10000-19999` unsealed back to working dirs so v3d0 fetch-all can continue extending them.
- **Phase 11a — corpus index + agentic skill** *(2026-05-21)* — `sheep-fold index` builds `corpus/_index/{index.json,INDEX.md}` with per-flame structural metadata + pyr3-limitation flags; `.claude/skills/pyr3-corpus-index/SKILL.md` documents `jq` query recipes. First build: 142,453 flames, 40,790 genomes, 99 distinct variations.
- **Phase 11b — v0.2.2 corpus-first pivot + Release distribution** *(2026-05-21)* — repo refocused: the corpus IS the deliverable, tooling is the means. GitHub Releases supersede LFS / separate-repo plans. Chunk shape unified to whole-gen for all gens (live + dead); v0.2.1 live-vs-dead split dropped. `scripts/build_release.sh` assembles per-gen `gen-{N}.zip` + `corpus-all.zip` mega-bundle + index + attribution. First snapshot Release: `v0.2.2` with 142,452 flames across 10 gens.
- **Phase 12b — v0.3 loose-corpus separation** *(2026-05-22, tag `v0.3.0`)* — see [CHANGELOG](CHANGELOG.md#v030--2026-05-22).
- **Phase 12d — v0.4 chunked layout + dated release + pyr3 AutoRoute index** *(2026-05-23, tag [`2026-05-23`](https://github.com/MattAltermatt/electric-sheep-fold/releases/tag/2026-05-23))* — also the **release-model pivot to ISO-date tags**. See [CHANGELOG](CHANGELOG.md#2026-05-23--chunked-layout--dated-artifacts--pyr3-autoroute-index).

## 🔮 Next phases

### Phase 12a — gen 247 + 248 live-track extensions (continuous)

Continue `sheep-fold fetch-all --gen 247` + `--gen 248` against v3d0 to extend each gen's `max_id` over time. Sticky-404 + already-on-disk skip-without-network make the cadence efficient. v0.3 made this safe (no reseal / no sticky-404 loss on extension); release uploads are deferred until v0.4 ships the chunked-dated artifact shape. Driven in the background by `scripts/resume_live_fetch.sh`.

### Phase 12c — pyr3-facing index ergonomics (post-v0.4)

The Phase 11a indexer is a complete first cut. Future extensions to consider: SQLite-backed query interface (faster than scanning 34MB JSON), curated examples file (`curated.md` analog), palette-hash field, incremental rebuild (rebuild only gens that changed since last index). v0.3's loose corpus + v0.4's chunked layout make incremental rebuild trivial (mtime per bucket dir). Subsumes the old "verify subcommand" idea (sha256 in MANIFEST enables verify-as-query) and the BACKLOG `attribution.csv extractor` entry.

### Phase 13 — pyr3 integration

pyr3 reads `corpus/{gen}/` (loose files + index) as parity-test source. The point of the whole exercise.

### Phase 14 — additional generations 🐑

Run `sheep-fold fetch-all --gen 249` (etc.) as ES rolls over. One-line edit to extend `LIVE_GENS` in `layout.py`; no other code changes.

## 🚧 Todos (next wake-up)

This is a corpus archive woken occasionally to fetch more sheep + ship a dated snapshot. No continuous-daemon expectation.

- 🐑 **Routine refresh:** `./scripts/resume_live_fetch.sh <upper>` to extend gens 247 + 248 → `sheep-fold index` → `sheep-fold release-build --date YYYY-MM-DD` → `gh release create YYYY-MM-DD`. `migrate-chunked` is a no-op on already-chunked corpus.
- Phase 13 (pyr3 integration) — pyr3 reads `corpus/{gen}/{bucket}/` + AutoRoute index fields as parity-test source. Lives outside this repo.
- 🔮 **If ES rolls a new dead gen** (e.g. 249 ends and becomes static): recover archive-scraper scripts via `git show v0.3.0:scripts/scrape_archive_gen.py` etc. — see [`docs/operations.md`](docs/operations.md) §Preserve a new dead generation.
- Phase 12c (index ergonomics — SQLite, palette-hash, incremental rebuild) — pull forward when corpus-growth slows or pyr3 integration demands faster queries.
