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

- **Politeness:** default cadence is 20s, sequential only, identifiable User-Agent.
  Parallelism is forbidden — at this cadence it buys nothing and risks server load.
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

## Where things live

- `src/electric_sheep_fold/` — the four modules (`layout`, `manifest`, `fetch`, `cli`)
- `src/electric_sheep_fold/data/ATTRIBUTION.md` — the Sheep-Pack template
- `tests/` — pytest suites; pure / mock-driven, no real network
- `corpus/` — local data (gitignored). Auto-materialized on first `fetch`.
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
