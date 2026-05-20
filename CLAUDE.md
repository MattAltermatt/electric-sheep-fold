# CLAUDE.md — electric-sheep-fold

## Conventions

- **Default branch:** `main`.
- **Identity (this repo):** `muwamath <muwamath@proton.me>`. Set as `--local`,
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
    jitter, sequential, identifiable User-Agent. The live server generates
    fresh genomes; treat it as expensive and rare.
  - **Static archive (`electricsheep.com/archives/...`):** 2s ±1s jitter,
    sequential. Archive is static HTML/spex content; faster cadence is fine.
  - Parallelism across either endpoint is forbidden. Same operator (Scott
    Draves), so the two cadences also imply *never both at once* — finish one
    long-running fetch before starting the other.
- **Live-vs-dead gen scope:** the live tool (`electric-sheep-fold`) is geared to gens
  247 + 248 via v3d0. **Dead gens** (165, 169, 191, 198, 242, 243, 244, 245,
  23, "old", "very-old") are preserved by **throwaway scripts** under
  `scripts/` that scrape `electricsheep.com/archives` via `time/` enumeration
  + `spex` fetch. Output feeds `electric-sheep-fold import` → force-seal. The scripts
  exist only to backfill the immutable past; once each gen is preserved,
  they can be deleted.
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
- **Chunk size:** 10,000 ids per chunk; chunks named `NNNNN-NNNNN.zip`. Don't
  change without a deliberate spec update and a migration story.
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
- `scripts/` — throwaway preservation scripts for dead gens (see
  `scrape_archive_gen.py`). Not part of the live tool's contract.
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
