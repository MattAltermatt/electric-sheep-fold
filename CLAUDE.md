# CLAUDE.md — electric-sheep-fold

## Commands

```sh
uv pip install -e ".[dev]"         # editable install + pytest
pytest -q                          # full test suite (~207 tests, no real network)
sheep-fold --help                  # CLI: fetch · fetch-all · import · status · index · release-build · migrate-chunked · verify-chunked · unseal · verify-unseal · chunk
sheep-fold index                   # rebuild corpus/_index/{index.json,INDEX.md} for pyr3 / agentic queries
sheep-fold release-build --date YYYY-MM-DD   # build/release/{gen-N-DATE.zip, corpus-all-DATE.tar.xz, corpus-chunks-DATE.tar, …}
sheep-fold chunk [--date YYYY-MM-DD]         # build/release/corpus-chunks-DATE.tar (standalone; also emitted by release-build)
./scripts/build_release.sh         # thin wrapper around `release-build` for the next GH Release upload
```

**What this repo is:** the preserved Electric Sheep `.flam3` corpus, with
the `sheep-fold` toolchain as its build/maintain pipeline. The corpus
itself is published as GitHub Releases tagged by ISO build date — per-gen
`gen-{N}-{date}.zip` + `corpus-all-{date}.tar.xz` mega-bundle + `INDEX.md`
+ `index.json` + `ATTRIBUTION.md`. The git tree holds the tooling + docs;
corpus data is gitignored and lives in Releases.

Agentic queries against the corpus are documented in
[`.claude/skills/pyr3-corpus-index/SKILL.md`](.claude/skills/pyr3-corpus-index/SKILL.md)
— `jq` recipes for variation lookup, pyr3-parity filtering, etc. Re-run
`sheep-fold index` after any `fetch` / `fetch-all` / `import` to keep the
index in sync with the corpus.

## Conventions

- **Default branch:** `main`.
- **Identity (this repo):** `MattAltermatt <1435066+MattAltermatt@users.noreply.github.com>`. Set as `--local`,
  not global.
- **Commits:** terse, no body, no `Co-Authored-By` trailer. `git log --oneline`
  should read like a story.
- **Branches:** `feature/<topic>` for work. FF-merge to `main` after user verify.
- **Docs are ship dependencies:** README, VISION, ROADMAP, CHANGELOG, BACKLOG all
  track code. Update in the same commit as the code they describe.
- **Releases tagged by ISO build date** (`YYYY-MM-DD`), not semver. This is
  a corpus archive woken occasionally to fetch more sheep + ship; each
  release is a snapshot in time. Tag = same date stamped into artifact
  filenames (`corpus-all-{date}.tar.xz`, `gen-{N}-{date}.zip`). Title
  format: `"Corpus snapshot YYYY-MM-DD"` optionally suffixed with notable
  changes. Pre-v0.4 tags (v0.1–v0.3) stay on semver as historical markers.

## Invariants (load-bearing)

These must NOT be violated without a deliberate spec update:

- **Politeness:** two cadences by endpoint type:
  - **Live sheep server (`v3d0.sheepserver.net/gen/{247,248}/...`):** 20s ±5s
    jitter, **strictly sequential**, identifiable User-Agent. The live server
    generates fresh genomes; treat it as expensive and rare. No parallelism.
  - **Static archive (`electricsheep.com/archives/...`):** 2s ±1s jitter per
    worker, **modest cross-gen parallelism allowed** (4 workers historically).
    AWS-backed; aggregate ~few req/s is gentle. Never run live + archive at
    the same time — finish the live op first.
- **Live-vs-dead gen scope:** the live tool (`sheep-fold fetch` /
  `fetch-all`) is hard-restricted to `LIVE_GENS = {247, 248}` in
  `layout.py`; any other `--gen` value errors out. Extending the set
  (when ES rolls gen 249) is a deliberate one-line edit. All eight dead
  flam3-bearing gens (165, 169, 191, 198, 242, 243, 244, 245) were fully
  preserved by 2026-05-21 via `scripts/scrape_archive_gen.py` (now
  retired); the workflow ran three phases per gen against
  `electricsheep.com/archives` — time-page enumeration → upper-bound
  discovery (doubling probe + binary search via `spex`) → gap sweep with
  flam3-envelope validation. Output fed `sheep-fold import` (writes
  chunked `.flam3` files into `corpus/{gen}/{bucket}/` + merges
  `_missing_404.txt` → `corpus/{gen}/missing.txt`). If ES rolls a NEW
  dead gen (e.g. 249 ends and becomes static), recover the scraper
  scripts via `git show v0.3.0:scripts/scrape_archive_gen.py` etc. — see
  [`docs/operations.md`](docs/operations.md) §"Preserve a new dead generation".
- **MPG-only generations are permanently out of scope.** `old`, `very-old`,
  and gen `23` are video-only on the archive — content-addressed by MD5 hash
  under `archives/{old,very-old}/...` (not `generation-N/`), no `spex`
  endpoint, no integer id space. They predate the network rendering protocol
  that produced flam3 genomes. **We will not preserve them here:** license
  status is unclear (the CC dual-license framework is keyed to flam3
  genomes), and there is no use case — these are pre-rendered videos, not
  inputs to the renderer this corpus feeds. Gen `202` is listed as a
  placeholder on the archive index (no date, no link) — known-missing
  upstream, not preservable.
- **Spex response shapes:** the archive `spex` endpoint returns multiple
  legal flam3 envelopes — both must be accepted:
  - Bare `<flame>...</flame>` (single frame) or multi-frame
    `<flame>...</flame><flame>...</flame>` for animation.
  - `<get gen=... id=... job=...><args.../><flame>...</flame></get>` — a
    render-job envelope wrapping the real flame. Strip-or-accept; `extract`
    finds inner flames at any depth.
  - Reject: empty bodies, `none\n` (5-byte sentinel), HTML error pages, any
    non-flame XML. These are recorded as missing, never saved as `.flam3`.
- **Sticky 404s:** once a sheep_id is in `corpus/{gen}/missing.txt`, we never
  re-probe it. ES numbering is append-only; gaps stay gaps. Re-probing wastes our
  time AND the server's.
- **Skip-without-network:** local-cache hits and known-missing hits MUST cost zero
  server time and zero sleep. Only requests that actually hit the network sleep.
- **Atomic writes:** every `.flam3` file at its final path is the complete file.
  Partial writes live in `<final>.tmp` until `os.replace`. SIGKILL-safe.
- **Filename preservation:** the `electricsheep.GGG.NNNNN.flam3` form is part of
  the ES attribution scheme — never rename, never strip, never re-encode.
- **Tool license:** GPL-3.0-or-later (matches pyr3, matches flam3 upstream).
  Corpus data is CC per ES policy — see [`README.md`](README.md).
- **Chunked-bucket layout, append-only** (v0.4 — supersedes v0.3 flat).
  `corpus/{gen}/{bucket}/electricsheep.{gen}.{id}.flam3` where
  `bucket = f"{(id // 10000) * 10000:05d}"`. `missing.txt` stays at
  `corpus/{gen}/missing.txt` (one per gen, not per bucket). Mutated only
  by `fetch-all` / `import` (append a flam3 OR append an id to
  `missing.txt`). Never deleted. Same shape for live + dead gens; the
  gen's biography is no longer encoded in the data layout. v0.4
  `bucket_for()` + `flam3_path()` in `layout.py` are the single source
  of truth for path construction.
- **Dated, overlay-compatible release artifacts.** Built on demand into
  `build/release/`, never `corpus/`. `sheep-fold release-build [--date YYYY-MM-DD]`
  emits:
  - `gen-{N}-{date}.zip` per gen — ZIP DEFLATE-9, members:
    `MANIFEST.csv` + `missing.txt` + `{bucket}/electricsheep.{N}.{id}.flam3`.
  - `corpus-all-{date}.tar.xz` mega-bundle — LZMA preset 6, full corpus
    tree including `_index/` + `ATTRIBUTION.md`.
  **Overlay invariant** (load-bearing — `test_release.py::TestOverlayInvariant`):
  extracting a per-gen zip under `{gen}/` produces the same on-disk
  subtree as extracting the mega-bundle then taking the matching subset.
  Consumers can grab piecemeal OR all-in-one and they fit together.
- **Daemon-verified chunked layout.** `sheep-fold migrate-chunked`
  reshapes v0.3 flat → v0.4 chunked (idempotent, SIGKILL-safe `os.replace`)
  and writes `corpus/_chunked-verified.json` (per-gen `loose_count` +
  `missing_count` + `bucket_count`). `fetch-all` startup calls both
  `verify_unseal_consistency` (v0.2 sentinel) and
  `verify_chunked_consistency` (v0.4); if any gen has flat `.flam3`
  files at the gen root the daemon refuses to start with "run
  migrate-chunked first."
- **Index v0.5 envelope:** `corpus/_index/index.json` is an object
  `{_schema_version: 5, _build_date: "YYYY-MM-DD", genomes: [...]}`.
  jq recipes use `.genomes[]`, not `.[]`. Five v0.4 pyr3 AutoRoute
  GPU-safety fields per genome (`has_hyper_trig`, `has_edisc`,
  `max_abs_affine_coef`, `xform_count_post_symmetry`,
  `has_density_estimator`) carry forward unchanged. v0.5 (2026-05-23)
  adds parser-detectable malformation flags (`has_nan_camera`,
  `has_nan_in_xforms`), makes `symmetry_kind` always-present
  (`int | null`), and renames `has_chaos` → `has_xaos` to match
  community naming. See
  [`.claude/skills/pyr3-corpus-index/SKILL.md`](.claude/skills/pyr3-corpus-index/SKILL.md).
- **MANIFEST.csv + missing.txt are the release seam:** every per-gen
  release zip contains `MANIFEST.csv` (11-col schema from v0.2 spec
  §4.1, still authoritative — unchanged through v0.4) + `missing.txt`
  (sticky-404 ids, id-per-line). The pyr3-facing index aggregates from
  both. Schemas in:
  [`docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md`](docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md) §4.1 (manifest),
  [`docs/superpowers/specs/2026-05-22-v0.3-loose-corpus.md`](docs/superpowers/specs/2026-05-22-v0.3-loose-corpus.md) §3 (v0.3 release artifact),
  [`docs/superpowers/specs/2026-05-23-v0.4-chunked-dated-release-and-index.md`](docs/superpowers/specs/2026-05-23-v0.4-chunked-dated-release-and-index.md) (v0.4 chunked + dated + index v4),
  [`docs/superpowers/specs/2026-05-23-v0.5-index-malformation-flags-and-xaos-rename.md`](docs/superpowers/specs/2026-05-23-v0.5-index-malformation-flags-and-xaos-rename.md) (v0.5 NaN flags + symmetry_kind always-present + has_chaos→has_xaos).
- **Delivery-chunk artifact** (`corpus-chunks-{date}.tar`). Built on demand
  into `build/release/` by `sheep-fold release-build` or standalone
  `sheep-fold chunk`. This is a distinct artifact from the per-gen `.zip`
  and `corpus-all.tar.xz`; it feeds the pyr3 renderer at
  `pyr3.app/v1/gen/{gen}/id/{id}` (baked same-origin into the GH Pages
  deploy). Members:
  - `gens.json` — plain JSON browse summary: `schema`, `build_date`,
    `chunk_size`, `gens[]` (gen / count / min_id / max_id).
  - `{gen}/avail.flam3idx` — per-gen present-id manifest: brotli of
    delta-varint(sorted ids). Lets the consumer enumerate sparse ids without
    unpacking every chunk.
  - `{gen}/{chunk_lo:05d}.flam3chunk` — one per non-empty 256-id window:
    brotli(JSON `{"_v": 1, "<id>": "<flam3 xml>", ...}`).
  **Load-bearing constants and contracts:**
  - `CHUNK_SIZE = 256` is part of the `/v1` URL contract
    (`chunk_lo = (id // 256) * 256`); changing it is a `/v1 → /v2` event.
  - Delivery-chunk granularity (256) is **independent** of the storage
    bucket size (10000). Two separate concerns; never conflate.
  - The `.flam3chunk` extension is **deliberate** and opaque — prevents any
    HTTP host from setting `Content-Encoding: br` (which would break the
    FE's manual brotli decode via `DecompressionStream`).
  - The `"_v"` field inside chunk JSON is the **chunk-format version**
    (currently `1`), independent of the URL `/v1` path prefix. Both may
    evolve separately.
  - `chunk.py` is the single source of truth for chunk math (`CHUNK_SIZE`,
    `chunk_lo()`, etc.).
  Spec: [`docs/superpowers/specs/2026-05-28-corpus-share-url-and-chunk-delivery-design.md`](docs/superpowers/specs/2026-05-28-corpus-share-url-and-chunk-delivery-design.md).

## Where things live

- `src/electric_sheep_fold/` — `layout`, `manifest`, `extract`, `fetch`,
  `importer`, `migration`, `index`, `release`, `chunk`, `unseal`, `cli`
- `src/electric_sheep_fold/data/ATTRIBUTION.md` — the Sheep-Pack template
- `tests/` — pytest suites; pure / mock-driven, no real network (~207 tests)
- `corpus/` — local data (gitignored, chunked layout). Auto-materialized
  on first `fetch`.
- `build/release/` — derived release artifacts (gitignored, rebuilt by
  `sheep-fold release-build`).
- `scripts/` — operational helpers: `build_release.sh` (release artifact
  assembly), `resume_live_fetch.sh` (background daemon resumption),
  `watch_sweep.sh` (sweep progress monitor). Dead-gen preservation scripts
  were removed in v0.4 after all 8 dead flam3-bearing gens were fully
  preserved (2026-05-21); see `docs/operations.md` §"Preserve a new dead
  generation" for recovery from git history if ES ever rolls a new dead gen.
- `docs/superpowers/specs/` — design specs (v0.1 / v0.2 / v0.2.1 / v0.3 / v0.4 / v0.5)
- `docs/superpowers/plans/` — implementation plans
