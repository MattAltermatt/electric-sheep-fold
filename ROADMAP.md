# 🗺️ Roadmap

> Phases are strategic milestones; the **🚧 Todos** block at the bottom is the
> living set of next concrete actions.

## Phases

### Phase 1 — v0.1 ship ✅ *(shipped 2026-05-19)*

Bootstrapped the tool: package + docs + four-module architecture (`layout`,
`manifest`, `fetch`, `cli`) + 52 tests + real-server smoke test. Spec:
[`docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md`](docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md).
Live verification: `electric-sheep-fold fetch 100..105` → 1 downloaded + 4 recorded as
sticky 404s, ~119s wall at the default 20s polite cadence. Idempotency confirmed
(re-run = 0 network, 0.14s).

### Phase 2 — `verify` subcommand 🔮

Re-hash all corpus files; surface any local truncation or damage. Cheap (no
network).

### Phase 3 — pyr3 integration 🔥

Pyr3 reads from `corpus/248/` directly as a parity-test source. The point of the
whole exercise.

### Phase 4 — public corpus repo (optional) 🌐

Push `corpus/` to a separate `muwamath/electric-sheep-fold-corpus` GitHub repo if there's
demand. ~440MB worst case for full gen 248, well within plain-git limits.

### Phase 5 — additional generations 🐑

Run `--gen 249` (etc.) as ES rolls over. Same script, no changes needed.

## 🚧 Todos (current phase)

- Phase 2 (`verify` subcommand) — start when next session resumes, or pull from
  Phase 3 (pyr3 integration) first if that's the bigger payoff.
