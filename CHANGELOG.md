# 📝 Changelog

## v0.2.5 — 2026-05-22

### Phase 11e — per-xform variation-count index fields

Triggered by **pyr3 v0.16** surfacing the GPU `MAX_VARIATIONS_PER_XFORM = 4`
cap — the previous `variations[]` field was the genome-level UNION, which
lost per-xform density. pyr3 needed the per-xform distribution to make a
data-driven UBO-sizing decision for v0.17.

`index.py` `_index_genome` now emits per-genome:

- `xform_var_counts: [int]` — per-xform variation count (length matches
  `xform_count`; finalxform excluded).
- `max_var_per_xform`, `mean_var_per_xform`, `xforms_with_5plus_vars` —
  derived aggregates.
- `final_xform_var_count: int?` — finalxform's variation count if present,
  else `null`.
- `has_post_affine_per_xform: [bool]` — post-affine per-xform.
- `max_xform_weight: float` — largest pick-weight across regular xforms.

`INDEX.md` gains a *"Per-xform variation density"* section: full histogram +
the headline number (genomes with ≥1 xform exceeding the current cap of 4).
Two new `jq` recipes documented in the skill.

**Corpus snapshot (143,133 flames · 41,110 genomes):** 7,105 genomes
(~17.3%) have at least one xform exceeding the current pyr3:gpu cap of 4.
Cap=5 → 97.9% coverage; cap=8 → 99.5%; cap=15 → 100% (max observed = 15).

Hand-verified against `244/00000` (xform_var_counts = `[3, 5, 2]`). 179
tests green (+4 new in `TestPerXformVariationCounts`).

Tooling-only patch; no corpus change. The v0.2.2 Release assets stay
current — re-uploading isn't necessary unless downstream tooling needs the
new fields baked into a release zip.

## v0.2.4 — 2026-05-22

### Phase 11d — range-trust fetch skip-check

Bug surfaced after the v0.2.2 manual collapse-to-whole-gen ops left two
sealed live-gen zips violating the `is_range_complete` invariant:
`corpus/247/00000-29999.zip` claims `[0, 30000)` but only 9006 ids are in
its namelist; `corpus/248/00000-19999.zip` claims `[0, 20000)` with 2926.
`missing.txt` for both gens was sparse (15 + 6163 in-range entries vs.
~21k + ~11k gaps). v0.2.3's `_known_ids_in_gen_zips` skipped on namelist
hits, so the ~32k gap-ids fell through to network — `fetch-all` would
re-probe them at 20s cadence (~5d + ~2.5d wasted) before reaching new
frontier ids.

Fix: replace `_known_ids_in_gen_zips` with `_sealed_ids_in_gen`. The new
helper treats each sealed zip's filename-claimed `[start, end)` as
authoritative — no need to crack the zip open. This honors the CLAUDE.md
invariant *"range-completion is the seal trigger: a chunk seals when
every id in `[start, end)` has known status"*: the seal IS the
commitment over its range, namelist + `missing.txt` are bookkeeping
beneath it. Once sealed, decided.

Tooling-only patch; no corpus change. The v0.2.2 Release assets stay
current. Two new regression tests (`TestSkipSealedRange`); 175/175 green
(was 173). Cause forensics: the bad seals trace to a manual v0.2.2 ops
step (the commit only touched docs); the in-code seal paths
(`Chunk.seal` + `fetch_range`'s seal sweep + `_import_whole_gen`) all
gate on `is_range_complete` and remain correct. The "embed MISSING.csv
in sealed zips" idea moved from this patch's Phase 2 to a standalone
BACKLOG entry as the structural defense against future manual-ops
sparsity.

## v0.2.3 — 2026-05-21

### Phase 11c — fetch skip-check supports whole-gen layout

Bug surfaced after the v0.2.2 collapse to whole-gen: `fetch` / `fetch-all`
used `chunk_for(sheep_id)` to derive the expected zip path
(`corpus/{gen}/NNNNN-NNNNN.zip` at 10k boundaries) and only checked that
specific path for the skip-without-network test. Under the whole-gen
layout (a single wider zip like `00000-29999.zip`), the check missed ids
already preserved and would re-probe v3d0 for them — rude to the live
server and wasteful.

Fix: new `_known_ids_in_gen_zips()` in `fetch.py` scans every sealed zip
in `corpus/{gen}/` and builds a `set[int]` of preserved sheep_ids. The
fetch skip-check unions this with the existing chunk-specific check
(which still catches working-dir hits). Works under both per-chunk and
whole-gen layouts. One new regression test (`TestSkipWholeGenZipHit`);
173/173 tests green.

Tooling-only patch; no corpus change. The v0.2.2 Release assets stay
current. Version bump to make the wire surface (User-Agent string) reflect
the fix.

## v0.2.2 — 2026-05-21

### Phase 11b — corpus-first pivot + Release-based distribution

Repo identity refocused: **the corpus IS the deliverable, tooling is the
means.** Concrete changes:

- **GitHub Releases supersede LFS / separate-repo plans.** Each Release is
  a corpus snapshot tagged in time. Assets: per-gen `gen-{N}.zip` (10
  files, one per generation) + `corpus-all.zip` mega-bundle + `INDEX.md` +
  `index.json` + `ATTRIBUTION.md`. Stable filenames; Release tag carries
  the version. Unlimited free downloads via GitHub.
- **Chunk shape unified to whole-gen for all gens.** v0.2.1's live-vs-dead
  split (one day old) is dropped — the "10k chunks = distribution unit"
  rationale died under Release-based distribution. Gens 247 + 248
  collapsed from chunked layout (3 + 2 chunks respectively) into single
  whole-gen zips matching the 8 dead gens. `corpus/247/00000-29999.zip`
  (9006 sheep, 42MB), `corpus/248/00000-19999.zip` (2926 sheep, 14MB).
- **`scripts/build_release.sh` assembles the Release.** Renames per-gen
  zips to `gen-{N}.zip` (stable Release naming), builds the mega-bundle,
  copies index + attribution. Re-runnable; overwrites `build/release/`.
- **Doc refocus** (one commit per doc): README leads with the corpus + a
  `gh release download` quickstart; the tool gets a "Toolchain" section
  below. VISION reframed as preservation + pyr3-facing index. ROADMAP
  Phase 13 ("separate corpus repo, optional") is now obsolete — THIS repo
  is the corpus repo.

First snapshot Release: **v0.2.2** — 142,452 flames across 10 gens,
40,790 genomes, 99 distinct variations, 0 corrupt.

## v0.2.1 — 2026-05-21

### Phase 11a — corpus index + agentic skill

New `sheep-fold index` CLI command walks every sealed zip + working chunk in
`corpus/`, parses each `.flam3`, and emits two outputs to `corpus/_index/`:

- `index.json` — one record per flame: `id`, `gen`, `sheep_id`, `kind`
  (`genome` / `animation` / `corrupt`), `sealed` flag, plus structural
  metadata for genomes (variations list, xform_count, has_final_xform,
  has_post_affine, has_chaos, supersample, highlight_power,
  negative_weight_xforms, name/nick/url, dims, palette_mode, background, …).
- `INDEX.md` — aggregated tables: per-gen corpus shape, variation usage
  histogram, structural feature counts, xform distribution, query recipes.

Agent-facing surface: `.claude/skills/pyr3-corpus-index/SKILL.md` documents
when to invoke + `jq` recipes for variation lookup, pyr3-parity filtering,
rare-variation stress-test selection.

Schema is informed by pyr3's known limitations (`has_chaos`, `supersample`,
`highlight_power`) so an agent can find parity-friendly genomes in one
filter. The canonical 101-element flam3 `var_t` set lives in `index.py`
(99 standard + `hemisphere` + `post_curl` from ES corpora).

First full corpus index: **142,453 flames** across 10 gens — 40,790 genomes
(28.6%), 101,662 animations (71.4%), 1 corrupt; **99 distinct variations
seen**. ~45s to build; stdlib-only. 12 new tests (172 total).

### Phase 10b — partial unseal for in-progress live chunks

After the live-gen guard landed, the highest-id chunk in 247 (`20000-29999`)
and 248 (`10000-19999`) were unsealed back to working dirs so future
`fetch-all` runs against v3d0 can continue extending them. Sealed chunks
in the same gens (`247/00000-09999`, `247/10000-19999`, `248/00000-09999`)
stay sealed — those id ranges are treated as "done with this corpus"
relative to the archive snapshot.

### Phase 10 — live-gen guard + gen 247 chunked ingest

`sheep-fold fetch` / `fetch-all` now hard-reject any `--gen` value not in
`LIVE_GENS = {247, 248}` with a hint to use `scripts/scrape_archive_gen.py +
import --whole-gen` for dead gens. Extending the set when ES rolls gen 249 is
a one-line edit in `layout.py`. 12 new CLI guard tests (160 total green).

Gen 247 ingested into the chunked 10k-id layout from `corpus/_scrape-247/`
(9007 flam3s preseeded from `~/dev/sheep/247/`, ids `0`–`25845`) → three
working chunks `00000-09999`, `10000-19999`, `20000-29999` in `corpus/247/`.
No auto-seal yet (no `missing.txt` to prove range completion); chunks will
seal naturally as `fetch-all --gen 247` against v3d0 fills the gaps. Source
`_scrape-247/` symlink dir removed post-import.

### Phase 9 — dead-gen whole-zip policy

Dead-preserved gens (sourced from the `electricsheep.com/archives` static
mirror) now seal as a single whole-gen zip spanning `[0, max_observed_id + 1)`
instead of synthetic 10k-id decade chunks. Live-preserved gens (247 / 248,
sourced via `v3d0.sheepserver.net`) keep their 10k-chunk layout — the gen's
biography is encoded in the chunk shape itself, and a gen's shape is fixed
at first preservation (no re-chunking when an upstream gen eventually dies).

Spec:
[`docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md`](docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md).

Code changes:
- `layout.archive_url(gen, id)` — new helper for `electricsheep.com/archives`
  source URLs (used by whole-gen seals; `remote_url` continues to point at
  v3d0 for live-gen seals).
- `importer.import_dir(..., whole_gen=True, gen=N)` — new mode that scans the
  scrape dir for flam3s + `_missing_404.txt`, computes `max_id`, copies the
  missing set into `corpus/{gen}/missing.txt`, imports all flam3s into a
  single `Chunk(0, max_id+1)`, and seals.
- `sheep-fold import --whole-gen [--gen N]` — CLI flag plumbing; `gen` is
  inferred from filenames when omitted (errors if src has mixed gens).
- `CLAUDE.md` chunk-size invariant amended to describe the live/dead split.

13 importer tests + 3 layout tests added (148 total green).

### Phase 8b — all dead flam3 gens preserved + sealed

Eight dead flam3-bearing gens fully preserved + sealed under the v0.2.1
whole-gen policy. Every id in `[0, max_observed_id]` is accounted for as
either a `.flam3` on disk or a `missing.txt` entry:

| Gen | flam3s | sticky-404s | sealed zip            | size  |
|-----|-------:|------------:|-----------------------|------:|
| 165 |    998 |         100 | `00000-01097.zip`     | 0.6MB |
| 169 | 21,745 |         100 | `00000-21844.zip`     | 15.4MB |
| 191 | 21,743 |         107 | `00000-21849.zip`     | 20.9MB |
| 198 | 31,836 |         191 | `00000-32026.zip`     | 89.6MB |
| 242 |  3,388 |         306 | `00000-03693.zip`     | 14.2MB |
| 243 |  5,266 |      12,521 | `00000-17786.zip`     | 15.8MB |
| 244 | 33,594 |      52,982 | `00000-86575.zip`     | 204.5MB |
| 245 | 11,950 |         249 | `00000-12198.zip`     | 108.6MB |
| **Σ** | **130,520** | **66,556** | — | **~470MB** |

Gen 244 surfaced exactly one sweep-gap (id 67084 — no flam3, no missing
entry); a single HEAD probe against the archive returned 404, added to
`missing.txt`, re-seal completed cleanly. All MANIFEST.csv rows carry archive
`source_url`s; zero XML parse failures across all eight gens.

After seal, the raw `_scrape-{165,169,191,198,242,243,244,245}/` working
directories were removed — every flam3 is fully captured in the sealed zip
with provenance, so the raw dirs were ~1.8GB of redundant data. The
`_scrape-247/` symlink tree is preserved pending Phase 10's live-track
reconciliation.

### Project name finalized to `electric-sheep-fold`

The working name was set aside in favor of `electric-sheep-fold` —
`sheepfold` captures the sanctuary framing (the work here is preservation,
not extraction). CLI binary stays short: `sheep-fold`. Python package,
User-Agent string, README / docs / spec / plan filenames, GitHub repo
name all retargeted in one cutover commit. All 135 tests green after the
rename.

### Phase 8 — comprehensive dead-gen preservation pipeline

Three bugs discovered + fixed after the Phase 7 import surfaced corrupt
sealed zips (73% empty extractions on gens 191/198):

1. **`extract.py` couldn't parse multi-flame .flam3 files** — animation
   keyframes use multiple `<flame>` sibling roots (valid flam3, invalid
   single-root XML). Fix: wrap in synthetic `<sheep>` root and aggregate
   across all flames. Variations now union across the whole animation.
2. **Scraper saved 200-OK responses with body `"none\n"`** as 5-byte
   placeholder .flam3 files. New: `is_flam3_content()` validator (in
   `extract.py`) — rejects empty, `none`, HTML, non-XML 200s. The scraper
   now records them as missing.
3. **Extractor didn't recognize `<get>`-envelope responses** — the archive
   sometimes serves `<get gen=... id=... job=...><args/><flame/></get>`
   wrappers around real flame data. Fix: search `.//flame` at any depth.

Scraper rewrite (`scripts/scrape_archive_gen.py`):
- Three phases per gen: time-page enum → upper-bound discovery (doubling
  probe + windowed bisection) → gap sweep across `[0, max_id]`.
- Time-page indexes are partial — gen 244 reaches id 86,435+ but its
  `time/*.html` view caps at 31,999. Discovery + sweep close the gap.
- `scripts/preserve_archived_sheep.sh` rewritten as parallel-worker driver
  (default 4 workers, configurable). Per-gen cadence stays at 2s±1s; total
  aggregate ~few req/s — gentle for the archive's AWS host.

Cleanup utilities:
- `scripts/sanitize_scrape_dir.py` — quarantines `none` / empty / HTML
  files from existing scrape dirs into `missing.txt`. Ran across six
  scrape dirs: 959 files quarantined (191: 4, 198: 81, 242: 208, 243: 290,
  244: 227, 245: 149). Surfaced an interesting find: gen 245 has 7,963
  `<get>`-envelope files that are real flame data (now correctly
  preserved, not garbage).

Invariants updated:
- **Politeness** now permits modest cross-gen parallelism for the archive
  endpoint (still strictly sequential for live v3d0).
- **Spex response shapes** — three legal envelopes documented in CLAUDE.md
  (bare flame, multi-flame, `<get>`-wrapped); all accepted by extract.

Rolled back this session's botched imports of gens 191/198/242/243/245 —
sealed zips were dropped before any code shipped that depended on them.

19 new tests (multi-flame, `<get>` envelope, content validation,
discovery probe, sweep skip-without-network). Total: **135 passing**.

## v0.2.0 — 2026-05-20

Storage refactor + ergonomics.

- Chunked `.zip` storage at 10k id-range per chunk; sealed-immutable once a
  chunk's range is fully probed
- Per-chunk `MANIFEST.csv` inside each sealed zip (id, sha256, fetched_at,
  source_url, name, nick, url, xform_count, final_xform, variations) — seam for
  the v0.3 pyr3-facing index
- Automatic v0.1 → v0.2 migration on first fetch (one-shot, idempotent)
- New: `sheep-fold fetch-all` — fetch entire gen range
- New: `sheep-fold import <dir>` — bulk-import existing local flames
- New: `sheep-fold seal --chunk NNNNN-NNNNN` — force-seal an incomplete chunk
- `status` extended to show per-chunk state breakdown
- All v0.1 invariants preserved (politeness, sticky-404, atomic writes,
  filename preservation, license obligations)

### Deferred to v0.3

- `corpus/{gen}/index.csv` chunk-overview file (spec §5.8). `status` covers
  the user-visible need via filesystem glob; v0.3's aggregated MANIFEST.csv
  reader likely subsumes this.

## v0.1.0 — 2026-05-19

Initial ship.

- Polite range-based mirror of `.flam3` files from `v3d0.sheepserver.net/gen/248/`
- Sticky 404 memory via `corpus/{gen}/missing.txt`
- Local-first dedup; skips cost zero server time
- Atomic writes (tmp + `os.replace`); SIGKILL-safe
- Bucket-by-thousand on-disk layout (`248/00xxx/`…`248/40xxx/`)
- Auto-copied `corpus/ATTRIBUTION.md` (Sheep-Pack obligation per
  [electricsheep.org/license](https://electricsheep.org/license/))
- Typer CLI: `sheep-fold fetch`, `sheep-fold status`
- pytest suites for `layout`, `manifest`, `fetch` (mock-transport, no real network)
