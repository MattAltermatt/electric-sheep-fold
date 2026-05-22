# CLAUDE.md — electric-sheep-fold

## Conventions

- **Default branch:** `main`.
- **Identity (this repo):** `MattAltermatt <1435066+MattAltermatt@users.noreply.github.com>`. Set as `--local`,
  not global.
- **Commits:** terse, no body, no `Co-Authored-By` trailer. `git log --oneline`
  should read like a story.
- **Branches:** `feature/<topic>` for work. FF-merge to `main` after user verify.
- **Docs are ship dependencies:** README, VISION, ROADMAP, CHANGELOG, BACKLOG all
  track code. Update in the same commit as the code they describe.

## Invariants (load-bearing)

These must NOT be violated without a deliberate spec update:

- **Politeness:** two cadences by endpoint type:
  - **Live sheep server (`v3d0.sheepserver.net/gen/{247,248}/...`):** 20s ±5s
    jitter, **strictly sequential**, identifiable User-Agent. The live server
    generates fresh genomes; treat it as expensive and rare. No parallelism.
  - **Static archive (`electricsheep.com/archives/...`):** 2s ±1s jitter per
    worker, **modest cross-gen parallelism allowed** (default 4 workers via
    `scripts/preserve_archived_sheep.sh`). AWS-backed; aggregate ~few req/s
    is gentle. Never run live + archive at the same time — finish the live
    op first.
- **Live-vs-dead gen scope:** the live tool (`sheep-fold`) is geared to gens
  247 + 248 via v3d0. **Dead, flam3-bearing gens** (165, 169, 191, 198, 242,
  243, 244, 245) are preserved by `scripts/scrape_archive_gen.py` which runs
  three phases per gen against `electricsheep.com/archives`:
  1. **Time-page enumeration (optional)** — harvest ids linked from
     `time/*.html`. Partial: gen 244's time view stops at id 31,999 even
     though sheep exist up to id 86,435+. Gens 165 + 169 have NO time view
     at all (404); phase 1 falls through to phase 2 — discovery is what
     actually finds the upper bound, time pages are just a free preseed.
  2. **Upper-bound discovery** — doubling probe + windowed binary search via
     `spex` to find the highest valid sheep id. Cached.
  3. **Gap sweep** — for every id in `[0, max_id]` not on disk and not in
     `_missing_404.txt`, GET `spex`. Accept only valid flam3 (see
     `is_flam3_content`); 404 / `none\n` / non-flam3 → record missing.
  Output → `sheep-fold import` → force-seal partial chunks. Scripts can be
  deleted once each gen is fully preserved.
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
- **Chunk size — live vs dead split** ([v0.2.1 addendum](docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md)):
  - **Live-preserved gens** (sourced via `v3d0.sheepserver.net`, gens 247 +
    248) → **10k ids per chunk**, chunks named `NNNNN-NNNNN.zip`. Keep this
    shape forever, even after the upstream gen dies.
  - **Dead-preserved gens** (sourced via `electricsheep.com/archives`, gens
    165 / 169 / 191 / 198 / 242 / 243 / 244 / 245) → **one whole-gen zip**
    spanning `[0, max_observed_id + 1)`, e.g. `00000-86475.zip` for gen 244.
  - A gen's chunk shape is fixed at first preservation; never re-chunked.
- **Sealed-immutable:** once a chunk is sealed (`.zip` exists), its contents are
  frozen. No append-to-zip. Re-key flow is `reseal` (backlog).
- **Range-completion is the seal trigger:** a chunk seals when every id in
  `[start, end)` has known status (present in working dir OR in `missing.txt`).
- **MANIFEST.csv is the seam:** the first entry of every sealed zip carries the
  extraction the v0.3 pyr3-facing index aggregates from. Schema in
  [`docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md`](docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md) §4.1.

## Where things live

- `src/electric_sheep_fold/` — `layout`, `manifest`, `chunks`, `extract`, `fetch`,
  `importer`, `migration`, `cli`
- `src/electric_sheep_fold/data/ATTRIBUTION.md` — the Sheep-Pack template
- `tests/` — pytest suites; pure / mock-driven, no real network
- `corpus/` — local data (gitignored). Auto-materialized on first `fetch`.
- `scripts/` — preservation scripts for dead gens:
  - `scrape_archive_gen.py` — enum + discover + sweep against electricsheep.com
  - `preserve_archived_sheep.sh` — parallel driver across multiple gens
  - `sanitize_scrape_dir.py` — scrub `none` / empty / HTML files into missing.txt
  - `seed_scrape_from_local.sh` — preseed scrape dirs from a local sheep archive
  These are *operational* tools, kept until each gen is fully preserved.
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
