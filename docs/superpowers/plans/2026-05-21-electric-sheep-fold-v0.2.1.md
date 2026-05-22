# electric-sheep-fold v0.2.1 Implementation Plan (retrospective)

**Goal:** Ship the live-vs-dead chunk-shape split, complete preservation of all known dead flam3-bearing gens, restrict the live fetch surface, and build the agentic corpus index that pyr3 (and any other agent) can query for examples by variation / structural attribute.

**Spec:** [`../specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md`](../specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md)

**Execution mode:** Lead-inline throughout — the work mixed file edits (pure logic + tests, subagent-friendly in principle) with live operational steps (CLI imports across 8 gens, force-seals, archive HEAD probes, cleanup of ~2.3GB of working data). Doing it inline kept the chain coherent and let the operational steps surface findings (like the gen 244 sweep-gap at id 67084, the upstream-lost gen 247 / sheep 249) before the next code change locked in assumptions.

**Branch:** `feature/v0.2-ingest-244-245-247` (already in flight from prior dead-gen preservation work).

---

## Phase 9 — dead-gen whole-zip policy

**Rule (load-bearing):** A gen's chunk shape is fixed at first preservation.
Live-preserved gens (sourced via `v3d0.sheepserver.net`) get 10k-id chunks
forever. Dead-preserved gens (sourced via `electricsheep.com/archives`) get
one whole-gen zip spanning `[0, max_observed_id + 1)`. No re-chunking.

### Tasks

1. **Spec draft.** New file `docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md` covering motivation, the rule, scope of v0.2 changes, invariants preserved.
2. **`layout.py` — archive URL helper.** Add `ARCHIVE_BASE_URL = "https://electricsheep.com/archives"` + `archive_url(gen, sheep_id)` returning `{base}/generation-{gen}/{sheep_id}/spex`. Pure function; 3 tests in `test_layout.py`.
3. **`importer.py` — whole-gen mode.** Add `import_dir(..., whole_gen=False, gen=None)`. When `whole_gen=True`: scan src for `electricsheep.{gen}.*.flam3`, read `_missing_404.txt`, compute `max_id`, seed `corpus/{gen}/missing.txt` via `MissingSet.add` + `save_atomic`, create `Chunk(0, max_id+1)`, add flam3s, seal. Gen inferred from filenames if omitted; multi-gen src → `ValueError`. 7 new tests in `test_importer.py`.
4. **`cli.py` — `--whole-gen` flag.** Wire `--whole-gen` + `--gen` on the `import` command; convert `ValueError` to `typer.BadParameter`.
5. **`CLAUDE.md` invariant update.** Replace the single-line chunk-size rule with the live/dead split, link the v0.2.1 spec.

**Tests after Phase 9:** 148/148 green (was 135; +13).

---

## Phase 8b — preserve all 8 dead flam3 gens via the new flow

Operational task: run `sheep-fold import corpus/_scrape-{gen}/ --whole-gen` for each of `165 / 169 / 191 / 198 / 242 / 243 / 244 / 245`.

### Tasks

1. **Sequential imports.** Smallest first (gen 165, 998 flam3s) as smoke-test; then the rest in one batch.
2. **Surface gen 244's sweep gap.** After bulk import, gen 244 was reported "not range-complete" — one id in `[0, 86575]` had neither a flam3 nor a `_missing_404.txt` entry. Diagnostic script identified id 67084. Single archive HEAD probe (`https://electricsheep.com/archives/generation-244/67084/spex`) returned 404 → appended `67084` to `_scrape-244/_missing_404.txt` → re-imported → sealed cleanly.
3. **Verify all 8 sealed zips.** For each: `unzip -l`, count flam3s, confirm MANIFEST.csv is present as first entry, source URLs point to archive, file count + missing.txt count = sweep range.

**Result:** 8 whole-gen zips totaling ~470MB; **130,520 flam3s** + **66,556 sticky-404s** captured.

| Gen | flam3s | sticky-404s | sealed zip | size |
|-----|-------:|------------:|------------|------:|
| 165 | 998 | 100 | `00000-01097.zip` | 0.6MB |
| 169 | 21,745 | 100 | `00000-21844.zip` | 15.4MB |
| 191 | 21,743 | 107 | `00000-21849.zip` | 20.9MB |
| 198 | 31,836 | 191 | `00000-32026.zip` | 89.6MB |
| 242 | 3,388 | 306 | `00000-03693.zip` | 14.2MB |
| 243 | 5,266 | 12,521 | `00000-17786.zip` | 15.8MB |
| 244 | 33,594 | 52,982 | `00000-86575.zip` | 204.5MB |
| 245 | 11,950 | 249 | `00000-12198.zip` | 108.6MB |

---

## Doc refresh

Full pass through README / VISION / ROADMAP / BACKLOG / CHANGELOG / CLAUDE.md after Phases 8b + 9. Most-violated shape rule was ROADMAP — shipped phases had grown multi-paragraph descriptions; collapsed to one-line bullets. CHANGELOG `Unreleased — 2026-05-21 (live)` promoted to `v0.2.1 — 2026-05-21` and new entries added at top. BACKLOG dropped the now-shipped Phase 7 preservation table. README quickstart updated for `--whole-gen`. VISION reframed as "two-track corpus" (live + preservation). CLAUDE.md gained a Commands section.

**One commit per doc** (skill convention).

---

## Phase 10 — live-gen guard + gen 247 chunked ingest

**Why:** The CLAUDE.md `Live-vs-dead gen scope` invariant said "the live tool is geared to gens 247 + 248" but didn't enforce it. Easy to accidentally `sheep-fold fetch --gen 165 0..100` and waste requests on a server that doesn't have it. Hard guard prevents this.

### Tasks

1. **`layout.LIVE_GENS = frozenset({247, 248})`** — single source of truth for which gens the live tool will hit. Comment notes the one-line edit to extend when ES rolls gen 249 (Phase 14 in ROADMAP).
2. **CLI guard in `cli.py`** — `_require_live_gen(gen)` raises `typer.BadParameter` with a helpful hint pointing at `scripts/scrape_archive_gen.py + import --whole-gen`. Invoked from both `fetch` and `fetch-all`.
3. **12 new CLI tests** — parametrize over all 8 dead gens + future gens (249, 300) to confirm rejection; positive paths covered indirectly via existing smoke tests.
4. **Gen 247 ingest** — `sheep-fold import corpus/_scrape-247/ --corpus corpus/` (default chunked mode; not `--whole-gen` since 247 is live-preserved). The 9007 symlinks (preseeded from `~/dev/sheep/247/`) landed as real files in three working chunks `00000-09999` / `10000-19999` / `20000-29999`. No auto-seal (no missing.txt → range incomplete).
5. **Cleanup** — `corpus/_scrape-247/` removed post-import (every byte now in the chunked working dirs).

**Tests after Phase 10:** 160/160 (was 148; +12).

---

## Phase 10b — partial unseal for in-progress live chunks

**Why:** User clarified that "completed chunks" meant "fully scanned" (every id either present or 404'd), not "currently has data." The earlier force-seal of all 5 chunks in 247/248 was a misinterpretation. Three of the five chunks are in id ranges where the archive snapshot represents the de-facto final state (`247/00000-09999`, `247/10000-19999`, `248/00000-09999`); the other two need to keep growing (`247/20000-29999`, `248/10000-19999`).

### Tasks

1. **Inline Python script.** For each named zip: extract entries (skip MANIFEST.csv) into a working dir alongside, delete the zip.
2. **Verify.** `sheep-fold status` shows correct sealed/working counts.

No code change — operational reversal of an over-broad force-seal. The `--whole-gen` and `seal` CLI surfaces already cover the lifecycle in both directions implicitly.

---

## Phase 11a — corpus index + pyr3-corpus-index skill

**Why:** pyr3 (the renderer this corpus feeds) needs to find genomes by variation, by structural attribute, and by pyr3-rendering compatibility. A `jq`-queryable JSON index over the whole sealed corpus solves this once for every future agent.

### Tasks

1. **`src/electric_sheep_fold/index.py` — new module.** ~340 LOC, stdlib only. Schema:
   - Per-flame record: `id` (`"{gen}/{sheep_id:05d}"`), `gen`, `sheep_id`, `byte_size`, `kind` (`genome` / `animation` / `corrupt`), `valid`, `sealed`.
   - Genome adds: `frame_count: 1`, `name`, `nick`, `url`, `dims`, `rotate`, `brightness`, `palette_mode`, `filter_shape`, `background`, `supersample`, `highlight_power`, `has_symmetry` (+ `symmetry_kind` if true), `xform_count`, `has_final_xform`, `has_post_affine`, `has_chaos`, `negative_weight_xforms`, `variations` (sorted list).
   - Animation adds: `frame_count` (count of `<flame ` opening tags).
   - Corrupt adds: `error`.
   - Walks both sealed zips AND working-dir chunks; `sealed: bool` distinguishes.
   - Canonical flam3 variation enum `VARIATIONS` is a 101-entry frozenset (99 standard + `hemisphere`, `post_curl` from ES corpora).
2. **`sheep-fold index` CLI** — emits to `corpus/_index/{index.json, INDEX.md}` by default; `--out` overrides.
3. **`tests/test_index.py` — 12 tests** covering parse classification (zero-byte / HTML / genome / rich genome with pyr3-limitation flags / animation / `<get>`-envelope), `iter_corpus_flames` (sealed + working), `build_index` happy + empty + parity-filter query.
4. **`.claude/skills/pyr3-corpus-index/SKILL.md`** — agent-facing doc. Frontmatter triggers on "find a flame with X variation", "give me a parity-friendly genome", "rebuild the index", etc. Full schema + `jq` recipes for variation lookup, pyr3-parity filtering, rare-variation stress-test selection.

**Result:** First build was ~44s wall-clock; **142,453 flames indexed** (40,790 genome, 101,662 animation, 1 corrupt) with **99 distinct variations seen**.

**Tests after Phase 11a:** 172/172 (was 160; +12).

### Sub-task — corrupt-flame triage

The single corrupt entry surfaced was `247/00249` (zero-byte). Probed all three sources:
- v3d0: `HTTP 200`, `Content-Length: 0`
- electricsheep.com archive: `HTTP 200`, `Content-Length: 0`
- Local `~/dev/sheep/247/00249.flam3`: 0 bytes since 2018-03-30

The sheep is **permanently lost upstream** — no recovery path. Treated as missing (consistent with how the scraper handles zero-byte 200 responses): unsealed `00000-09999.zip`, dropped the zero-byte placeholder, added `249` to `corpus/247/missing.txt`, resealed (3419 sheep instead of 3420). Rebuilt index → **0 corrupt**.

---

## Pre-merge cleanup sweep

Sanity pass before FF-merge surfaced a real version-skew bug and one stale backlog entry.

### Tasks

1. **Version bump.** `pyproject.toml` was at `0.1.0` (never bumped at v0.2 ship); `__init__.py` was at `0.2.0`. Synced both to `0.2.1`.
2. **`fetch.USER_AGENT` derivation.** Was hardcoded `"electric-sheep-fold/0.2 (…)"`; now `f"electric-sheep-fold/{__version__} (…)"` so future bumps don't drift.
3. **BACKLOG strike.** "v0.3 design question: should the index aggregator scan working dirs?" — resolved by Phase 11a (`iter_corpus_flames` does walk both; records carry `sealed: bool`). Struck with note.

---

## Execution Handoff

**Plan was retrofitted after execution** — the user asked for a plan doc to live alongside the spec; this captures what actually shipped, not what was predicted. Future v0.2.1-style retrospectives can use this shape: phases as logical sections, tasks as numbered bullets, operational findings (like the gen 244 sweep-gap or the 247/00249 lost-upstream case) called out inline so future readers know what to expect when running the same flow.

**Final state on branch `feature/v0.2-ingest-244-245-247`:**
- 13 commits (1 code + 6 doc-refresh + 1 live-gen guard + 1 follow-up changelog/roadmap + 1 indexer + skill + 1 cleanup + this plan doc)
- 172/172 tests green
- Corpus: 624MB / 142,452 flames / 0 corrupt / 99 variations
- Skill: `.claude/skills/pyr3-corpus-index/SKILL.md`

Ready for user verify + FF-merge to `main`.
