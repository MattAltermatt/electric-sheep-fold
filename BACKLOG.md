# 🗃️ Backlog (unphased)

Ideas that aren't yet scheduled to a phase. Pull forward when one becomes
load-bearing.

- **`attribution.csv` extractor** — parse each `.flam3` XML root tag (`nick`,
  `url`) and emit a per-sheep credit ledger. Distinguishes algorithm-bred (no
  `nick`) from human-designed sheep.
- **Sidecar files** — `--include-sidecars` flag if pyr3 ever needs `state.fsd` /
  `memory` / `spex`.
- **Browsable gallery** — GitHub Pages thumbnail grid (downstream of Phase 3 — needs
  pyr3 rendering to PNGs first).
- **Retry-known-missing** — `--retry-missing` flag if ES ever shifts numbering
  semantics. Not needed under current "gaps stay gaps" invariant.
- **Resume-on-SIGTERM banner** — print "Resuming from sheep N" on startup when a
  partial run is detected.
- **Server-index cache** — save the gen-NNN index HTML (~6MB for 248) as a one-time
  preservation artifact in case ES goes dark.
- **User-Agent assertion test** — add a `MockTransport` test that inspects
  `request.headers["user-agent"]` and asserts it starts with `electric-sheep-fold/`. The
  invariant is currently enforced only by code inspection. (Surfaced by Phase 1
  holistic review.)
- **Shared logging setup across CLI commands** — `fetch` configures the root logger
  via `basicConfig`; `status` doesn't. Lift to module level (or a shared `_setup`
  helper) once `status` ever needs to surface a log line. (Surfaced by Phase 1
  holistic review.)
- **`status` (no-range) "untried" wording** — spec §5.4 example shows `untried in
  0..2000` as part of the default output, but "untried" is only meaningful when a
  range is given. Either add a one-line README note explaining the divergence, or
  amend the spec example for v0.2. (Surfaced by Phase 1 holistic review.)
