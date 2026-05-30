# 📝 Changelog

> **Release model:** corpus snapshots tagged by ISO build date
> (`YYYY-MM-DD`) — no semver. Each release is a self-contained snapshot
> of the corpus + tooling at a point in time. The 2026-05-23 entry below
> is the first under this convention; prior entries (v0.1–v0.3) kept
> their original semver tags as historical markers.

## Pending — next dated release

### Phase 12k — index schema v6: provenance + tone-map richness (ESF-002, ESF-003)

Bumped `index.json` to `_schema_version: 6` with five new per-genome fields:

- **ESF-003 — `version`.** The `<flame version=…>` renderer-provenance string
  (`""` when absent). Surfaces real forensic spread across the corpus — e.g.
  ~10.8k genomes from `FLAM3-LNX-v3.1.1`, down to individual `-dirty` builds.
- **ESF-002 — tone-map family.** `gamma`, `vibrancy`, `estimator_minimum`,
  `estimator_curve` — the rest of the density-estimator / tone-map family
  alongside the existing `has_density_estimator`. Stored as effective values
  (flam3 defaults when the attribute is absent: 4.0 / 1.0 / 0.0 / 0.4),
  matching the existing `brightness` / `highlight_power` convention.

`INDEX.md` gains a "Tone-map & provenance" section (non-default counts + top
renderer versions) and a tone-map query recipe. CLAUDE.md / README / SKILL.md
envelope docs updated to v6.

**ESF-006 (palette-hash) declined this round** — a 3-agent investigation
confirmed it would work (exact hashing buckets 65–95% of genomes; perceptual
adds <1pp before over-merging) but found no consumer: pyr3 parses palettes from
raw flam3, no jq recipe groups by palette, and the only future consumer (gallery
ESF-016) is deferred + blocked. Marked 🚫 WON'T DO in BACKLOG with the findings
preserved.

### Phase 12j — security & supply-chain hygiene (ESF-027, ESF-032, ESF-035)

- **ESF-032 — SECURITY.md + private reporting.** Added a security policy and
  enabled GitHub Private Vulnerability Reporting, so issues can be disclosed
  privately instead of in public issues.
- **ESF-027 — documented trust boundary.** SECURITY.md records the accepted
  plaintext-HTTP live-source risk (`v3d0` has no TLS) and its mitigations
  (defusedxml, inert content, non-flam3 rejection).
- **ESF-035 — Dependabot.** Weekly version + security-update PRs for the `uv`
  dependency graph and the SHA-pinned GitHub Actions.

Community-health extras (CoC / CONTRIBUTING / templates — ESF-034) were reviewed
item-by-item and deliberately declined as ceremony for a solo repo.

### Phase 12i — continuous integration (ESF-030, ESF-031)

First CI for the repo: `.github/workflows/ci.yml` runs on every push to `main`
and every PR. Hardened per current GitHub guidance — actions pinned to full
commit SHA, least-privilege `permissions: contents: read`, uv cache, and
`uv sync --locked` (which also fails the build if `uv.lock` drifts from
`pyproject.toml`).

- **ESF-030 — tests.** `pytest` across a Python 3.11 / 3.12 / 3.13 matrix.
- **ESF-031 — lint + types.** A `lint` job runs `ruff check` (E/F/I,
  line-length 100) + `mypy src`. Adopted `ruff`/`mypy` config in `pyproject`
  and cleared the existing debt (import order, unused imports, a handful of
  `int(object)` type-narrowings); 7 unsplittable INDEX.md jq-recipe lines
  carry an explicit `# noqa: E501`.

### Phase 12h — supply-chain hardening (ESF-026, ESF-028)

- **ESF-026 — defused XML.** Untrusted network `.flam3` is now parsed with
  `defusedxml.ElementTree` (both `extract.py` and `index.py`); entity/DTD/
  external bombs are rejected and classified `corrupt` instead of being
  expanded (a build-host DoS vector) or crashing. New `defusedxml>=0.7` dep.
- **ESF-028 — committed lockfile.** `uv.lock` (full pinned graph + sha256
  hashes, including the new `defusedxml`) is now tracked, so installs are
  reproducible and hash-verified instead of resolving fresh from PyPI.

### Phase 12g — code-review correctness pass (ESF-017–022)

Confirmed bugs + a metadata cleanup found in a three-critic whole-codebase
review, each fixed with regression tests:

- **ESF-017 — 6-digit sheep ids.** `_FLAM3_RE` matched exactly `\d{5}`, so any
  sheep id ≥ 100,000 was silently dropped by `import`, `index`,
  `migrate-chunked`, `release-build`, and `verify-unseal`. The pattern is now
  `\d{5,}` and lives once as `FLAM3_RE` in `layout.py` — the five former copies
  each kept their own, which is exactly how a width contract drifts.
- **ESF-018 — corpus poisoning via non-flam3 200s.** `fetch` wrote any HTTP 200
  body verbatim, so the archive's `none\n` placeholder or an HTML error page
  became a bogus `.flam3` that then marked the id skip-local forever. The write
  is now gated on `is_flam3_content()`; a non-flam3 200 is a transient error
  (no write, no missing-entry).

- **ESF-019 — version drift.** `pyproject` (`0.2.5`), `__init__` (`0.2.3`), and
  the actual v0.5 code all disagreed. Collapsed to one source: `__version__`
  in code, with `pyproject` reading it via hatch `dynamic` version. Now `0.5.0`.

- **ESF-021 — non-UTF-8 flam3.** `build_chunks_tar` aborted the whole delivery
  artifact on a single non-UTF-8 file; it now skips that file (excluded from
  avail + chunk, which must agree) and keeps building.
- **ESF-022 — corrupt vs animation.** A single `<flame>…</flame>` with trailing
  junk raised the same parse error as a real multi-flame animation and was
  mislabeled `animation`/`valid`; it is now `corrupt` unless ≥2 flames present.

- **ESF-020 — jitter cadence.** Confirmed the live-fetch inter-request wait is
  `[20s, 25s]` (20s base + 0–5s, one-sided) and that this is the intended,
  more-polite behavior. Docs reworded to match the code, the design noted in
  `_sleep_with_jitter`, and a lock test added so it stays one-sided.

Remaining review findings tracked as ESF-023..037 in [BACKLOG](BACKLOG.md).

### Phase 12f — delivery-chunk artifact + `sheep-fold chunk` CLI

New `corpus-chunks-{date}.tar` Release asset and standalone
`sheep-fold chunk [--date YYYY-MM-DD]` CLI command (also emitted
automatically by `sheep-fold release-build`). This artifact feeds
[pyr3](https://github.com/MattAltermatt/pyr3) at
`pyr3.app/v1/gen/{gen}/id/{id}` — baked same-origin into the GH Pages
deploy, no CORS, no third-party CDN.

**Tar members:**

- `gens.json` — plain JSON browse summary: `schema`, `build_date`,
  `chunk_size` (256), `gens[]` (gen / count / min_id / max_id).
- `{gen}/avail.flam3idx` — per-gen present-id manifest: brotli of
  delta-varint(sorted ids). Consumer can enumerate sparse ids without
  unpacking every chunk.
- `{gen}/{chunk_lo:05d}.flam3chunk` — one per non-empty 256-id window:
  brotli(JSON `{"_v": 1, "<id>": "<flam3 xml>", ...}`). ~172 KB each;
  whole corpus ≈ 110 MB brotli'd.

**Load-bearing invariants introduced:**

- `CHUNK_SIZE = 256` is part of the `/v1` URL contract; changing it is a
  `/v1 → /v2` event. Delivery-chunk granularity (256) is **independent**
  of the storage bucket size (10000).
- `.flam3chunk` extension is opaque by design — prevents `Content-Encoding: br`
  auto-set, which would break the FE's manual brotli decode.
- `"_v"` inside chunk JSON is the chunk-format version (`1`), independent
  of the URL `/v1` prefix.
- `chunk.py` is the single source of truth for all chunk math
  (`CHUNK_SIZE`, `chunk_lo()`, etc.).

**Code shape:** new `chunk.py` module (~200 LOC); `release.py` wires
`sheep-fold chunk` CLI + calls `build_chunks_tar()` from
`release-build`. 242/242 tests green.

Spec: `2026-05-28-corpus-share-url-and-chunk-delivery-design.md` (internal scaffolding).

### Phase 12e — index schema v5: malformation flags + xaos rename

Inbound design proposal from pyr3 (sibling repo) flagged ~153 of 149,904
corpus genomes (≈0.10%; gen-247 worst at ≈0.77%) carry
`<flame center="nan nan" scale="nan">` — textually invalid floats that no
flam3-lineage renderer can interpret. Every downstream consumer
reinvents a luminance-based discard pass to skip these. The structural
fact now lives in the corpus index. While the schema was being touched,
two adjacent cleanups landed in the same bump.

**Schema bump v4 → v5.** Consumers MUST check `_schema_version` before
applying v5 jq paths. No v4-compat shim — same policy as v3→v4.

**New field — `has_nan_camera: bool`.** `True` iff the `<flame>` root
element has a `center` or `scale` attribute whose value contains a `nan`
token (case-insensitive, whole-word — regex
`(?i)(?<![a-z0-9])nan(?![a-z0-9])`). Matches the canonical
malformation pyr3 named. ~0.1% of corpus (~153 of 149,904 genomes;
gen-247 worst).

**New field — `has_nan_in_xforms: bool`.** `True` iff any `<xform>` or
`<finalxform>` attribute value contains a NaN token. Covers affine
coefs (`coefs`, `post`) and any variation parameter that landed as
NaN. Same whole-word regex as `has_nan_camera`.

**Changed semantics — `symmetry_kind: int | null`.** Was `int` only
when `<symmetry>` was present in v4; consumers had to guard `?? 0`
or `// null` at every read. v5 always emits the field — `int` value
of the `kind` attribute when present, `null` when no `<symmetry>`
element. The companion `has_symmetry: bool` is unchanged and stays as
the cheap predicate.

**Renamed — `has_chaos` → `has_xaos`.** Same value semantics: `True`
iff any `<xform>` / `<finalxform>` has a `chaos` attribute. The XML
attribute name in source files is unchanged (still `chaos`); only the
index field name changes. Community/Apophysis/JWildfire/pyr3 standard
name is `xaos`, so this collapses the v0.4 dual-naming (v0.4's
INDEX.md already aliased the heading as `has_chaos (xaos)`).

**Inbound proposal context.** Flags came from pyr3 noticing the
all-black-render pattern. pyr3 will adopt the existing `has_chaos`
field name verbatim once renamed — no schema-breaking rename on their
side either; both repos converge on `has_xaos`.

**Out of scope:** `inf` / `-inf` / `infinity` detection (different
failure mode — dim output vs all-black — no named consumer); renderer-
specific quality flags ("renders as single dot," "GPU banding") stay in
each consumer's divergence log; v4-compat reader (consumers re-pull on
schema bump).

Spec: `2026-05-23-v0.5-index-malformation-flags-and-xaos-rename.md` (internal scaffolding).

## 2026-05-23 — chunked layout + dated artifacts + pyr3 AutoRoute index

(Was v0.4.0 in pre-release planning; renamed to date-tag at ship time
to match the corpus-snapshot release model.)

### Phase 12d — chunked corpus layout, dated release artifacts, pyr3 AutoRoute index fields

Three converging pressures resolved in one invariant evolution:

1. **Finder lag + human pattern-recognition** at big-gen scale — gen-244's
   33,594 files in one flat dir → APFS unbothered but `ls` walls and
   "what id ranges do we have?" hostile.
2. **Mega-bundle compression** — v0.3's `corpus-all.zip` ≈ 499 MB across
   ~166k flames; re-packed as `corpus-all.tar.xz` ≈ 110 MB (−78%). LZMA's
   cross-file dictionary compounds across redundant flame XML; per-file
   zip headers prevent that. v0.3 consumers download-and-extract whole,
   so the "no random-access into the archive" objection no longer bites.
3. **Pyr3 reparses flame XML to decide CPU vs GPU.** `AutoRoute.kt:73`
   queries five GPU-safety attributes the index didn't expose; pyr3's
   BACKLOG literally has an `has_nan_camera` field wishlist entry naming
   the gap.

**Disk layout** — `corpus/{gen}/{bucket}/electricsheep.{gen}.{id}.flam3`
where `bucket = (id // 10000) * 10000` zero-padded to 5 digits. Every gen
chunks the same way; no threshold rule. `missing.txt` stays at
`corpus/{gen}/missing.txt`.

**Release artifacts (hybrid)** — per-gen ZIP DEFLATE-9 stays optimal for
small gens (cross-file dictionary saturates within one flame's XML
anyway); mega-bundle becomes tar.xz where LZMA2 cross-file compounding
wins decisively:

- **`gen-{N}-{YYYY-MM-DD}.zip`** — ZIP DEFLATE-9, members
  `MANIFEST.csv` + `missing.txt` + `{bucket}/electricsheep.{N}.{id}.flam3`.
- **`corpus-all-{YYYY-MM-DD}.tar.xz`** — LZMA preset 6, full corpus tree
  (per-gen MANIFEST + missing + chunked .flam3 + `_index/` + `ATTRIBUTION.md`).
- **Overlay invariant** — per-gen zip extracted under `{gen}/` AND
  mega-bundle extracted into a staging dir produce byte-identical trees
  in the shared subset. Verified in `test_release.py::TestOverlayInvariant`.

**Index v0.4 envelope** — `index.json` is now an object:

```json
{
  "_schema_version": 4,
  "_build_date": "2026-05-23",
  "genomes": [<record>, ...]
}
```

jq recipes accordingly switch from `.[]` → `.genomes[]`.

**Index v0.4 fields** — five new pyr3 AutoRoute GPU-safety attributes per
genome record, driving `verdict()` without re-parsing flame XML:

| Field | Type | Failure mode it gates |
|---|---|---|
| `has_hyper_trig` | bool | tan/sec/csc/cot/tanh/sech/csch/coth — f32 denominator cancellation at ±π/2 |
| `has_edisc` | bool | edisc craters near unit circle → NaN (all-black render) |
| `max_abs_affine_coef` | float | `> 5` → f32 exponent loss → orbit NaN |
| `xform_count_post_symmetry` | int | `> 64` overflows GPU chaos pickTable |
| `has_density_estimator` | bool | soft tone-map gate; GPU lacks HSV-desaturation |

**CLI delta:**

- `sheep-fold migrate-chunked` — **new.** One-shot v0.3 flat → v0.4
  chunked migration. Idempotent. Writes `corpus/_chunked-verified.json`
  as the daemon-resume baseline.
- `sheep-fold verify-chunked` — **new.** Consistency check against the
  baseline (exits nonzero on residual flat files or shrinkage).
- `sheep-fold release-build --date YYYY-MM-DD` — **new flag.** Stamps
  the date into artifact filenames + `index.json._build_date`.
  Defaults to today UTC.

**Daemon-resume guard** — `fetch-all` startup now refuses to start if
any gen has flat `.flam3` files at the gen root (signals incomplete
migration). Bypasses cleanly on fresh / fully-chunked corpora.

**Code shape:** ~600 LOC added (~250 in `release.py` for tar.xz + chunked
zips, ~200 in `index.py` for the 5 new fields + schema envelope, ~150 in
`migration.py` for the v3→v4 migration), 207/207 tests green.

**Retired invariants** (superseded; see [`CLAUDE.md`](CLAUDE.md)):

- Loose-corpus flat layout
- Single-shape release artifact filenames (no date)
- `index.json` as a flat JSON array

**New invariants:**

- Chunked-bucket layout (`{gen}/{bucket}/`)
- Dated release artifacts + overlay invariant
- `index.json` v0.4 envelope with `_schema_version: 4` + `_build_date`
- Per-gen ZIP + mega-bundle tar.xz hybrid; consumers grab piecemeal OR
  bulk and trees fit together

## v0.3.0 — 2026-05-22

### Phase 12b — loose-corpus separation; release artifact built on demand

The "sealed-immutable whole-gen zip" model of v0.2 conflated the on-disk
corpus state with the distribution artifact. v0.2.2's chunk-shape
collapse destroyed sticky-404 provenance for gens 247 + 248 because
`missing.txt` lived outside the sealed zip. v0.3 separates the two:

- **`corpus/{gen}/`** is now flat `electricsheep.{gen}.{id}.flam3` files
  + `missing.txt` for ALL gens (live + dead). Same shape everywhere; the
  gen's biography is no longer encoded in the data layout.
- **`build/release/`** holds the consumer-facing zips, built on demand
  from corpus state via `sheep-fold release-build`. Pure derivative;
  reproducible.
- **`missing.txt` now travels inside the release zip** alongside
  `MANIFEST.csv`. Sticky-404 provenance is artifact-permanent — the
  v0.2.2-class data-loss incident can't recur because reseal can't lose
  what isn't separate.

**CLI delta:**

- `sheep-fold seal` — **removed.** Sealing the working dir was the
  v0.2.x ceremony around chunk completion; the v0.3 working dir IS the
  canonical state.
- `sheep-fold release-build` — **new.** Builds `build/release/gen-{N}.zip`
  + `corpus-all.zip` + index + attribution from corpus state.
- `sheep-fold unseal` + `sheep-fold verify-unseal` — **new.** One-time
  v0.2 → v0.3 migration tool (SIGKILL-safe 6-step state machine) +
  consistency check for the daemon-resume guard.
- `sheep-fold import` — `--whole-gen` flag dropped (now default and only mode).

**Retired invariants** (see CLAUDE.md):

- Sealed-immutable
- Range-completion is the seal trigger
- Chunk shape: whole-gen for every gen

**New invariants** (see CLAUDE.md):

- Loose-corpus, append-only
- Release-built on demand
- Daemon-verified id counts post-migration

**Code shape:** ~250 LOC out, ~150 LOC in. `chunks.py` retired entirely;
zip-assembly logic moved to `release.py`. `fetch.py` simplified
substantially (no chunk-aware loops, no seal sweep). `importer.py`
collapsed from dual chunked/whole-gen modes to one flat-write path.

**Migration ran clean** against the live corpus: 143,307 loose files
across 10 gens, 74,029 sticky-404 entries preserved. Live-fetch resume
point captured at gen 247 / id 32085 (last recorded 404). Daemon
restarted on the v0.3 code path.

### Gap-id catchup (one-time, post-migration)

v0.2.4's range-trust skip-check treated each sealed zip's filename-claimed
range as authoritative ("the seal is the commitment over its range") even
when the namelist + `missing.txt` didn't cover every id in that range. v0.3
removes range-trust — `missing.txt` is the sole source of truth for
known-empty ids. As a result, **31,822 gap-ids** in gens 247 + 248
(~21k + ~11k respectively) that v0.2.4 treated as decided-without-record
are now "unknown" to v0.3 and will be politely re-probed as the daemon
sweeps. At the 20s live cadence this is ~7.4 days of background work,
running concurrently with normal corpus extension. Each newly-confirmed
404 atomically appends to `missing.txt`; each (hypothetical) 200 gets
fetched. We accept the polite traffic cost to gain ground-truth state vs.
inheriting v0.2's incomplete bookkeeping.

The 8 dead gens (165, 169, 191, 198, 242–245) are tight — loose count +
missing.txt count exactly equals the claimed range — so no catchup
happens there.

Spec: `2026-05-22-v0.3-loose-corpus.md` (internal scaffolding).
v0.2.5 is the off-machine fallback artifact (final sealed-shape snapshot).

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
(9007 flam3s preseeded from a local mirror, ids `0`–`25845`) → three
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

Spec: `2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md` (internal scaffolding).

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
