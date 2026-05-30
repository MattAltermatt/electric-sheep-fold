# 🗃️ electric-sheep-fold Backlog

Authoritative registry of open tasks. Every open task carries an `[ESF-NNN]` ID
(required) and best-effort flags (optional): `category · size · sigil · status`.

Forward-only — shipped work lives in [CHANGELOG.md](CHANGELOG.md); strategic
narrative + current phase lives in [ROADMAP.md](ROADMAP.md). Pull a ticket
forward when it becomes load-bearing. When a ticket ships, its entry is **deleted
here** (CHANGELOG owns the record); `git log -- BACKLOG.md` recovers the trail.

> **Next ID: ESF-038** — increment when creating a new entry. Never reuse, even
> for shipped/removed tasks.

**Sigils:** 🐛 bug · 🔧 fix/infra · 🔒 security · 🧪 test · 🐑 feature · 🪶 trivial.
**Sizes:** XS / S / M / L (cognitive + maintenance complexity, not wall-clock).

---

## ⏸ Deferred / declined (2026-05-29 code review)

Decisions on the record; revisit if circumstances change. The resolved review
tickets (ESF-017–028, 030–032, 035–036) shipped — see [CHANGELOG](CHANGELOG.md)
phases 12g–12j.

## [ESF-029] security · XS · 🔒 · ⏸ DEFERRED — SRI hash for the stats-page Chart.js CDN tag

`scripts/build_stats_page.py` is untracked and the page ships nowhere, so a
missing `integrity=`/`crossorigin` has no live attack surface. Pull forward the
moment the stats page is committed or published.

## [ESF-033] infra · L · 🔧 · ⏸ DEFERRED — provenance-attested release workflow (SLSA)

Provenance is meaningless for a locally-built artifact, so this requires moving
releases into CI — which collides with the ~3 GB gitignored corpus CI doesn't
have, for a threat model (tampered *executable* artifacts) that barely applies
to inert CC genome XML. GitHub already auto-publishes per-asset SHA256 digests.
Revisit if releases ever move to CI; the cheap first slice is a "verify your
download" README snippet over those digests.

## [ESF-037] infra · 🪶 · ⏸ DEFERRED — PyPI packaging metadata

Not publishing to PyPI (a legitimate choice for corpus tooling). If that changes:
fill `classifiers` / `keywords` / `[project.urls]` and publish via OIDC trusted
publishing (not a long-lived token).

## [ESF-034] infra · S · 🚫 WON'T DO — community-health files (CoC / CONTRIBUTING / templates)

Reviewed item-by-item and cut as ceremony for a solo niche repo: no contributor
community to govern; the PR checklist is redundant with the enforced CI gate;
README + CLAUDE.md already cover dev conventions. A ~2-minute add if a real
contributor community ever forms. (SECURITY.md from the same checklist shipped —
phase 12j.)

---

## 📚 Index richness (post-v0.4 — future schema bump)

## [ESF-001] feature · M · 🐑 · open — runtime NaN detection (`produces_nan: bool`)

Static checks (the v0.4 five-field set) catch most NaN producers; a short
chaos-game probe per genome would catch residuals. Index-build cost scales
linearly; gate on whether the static-only verdict misses enough cases to matter
for pyr3 integration.

## [ESF-002] feature · S · 🐑 · open — tone-mapping diversity fields

Surface `gamma`, `vibrancy`, `estimator_minimum`, `estimator_curve` — the rest of
the density-estimator + tone-map family. Currently only `has_density_estimator`
is exposed.

## [ESF-003] feature · XS · 🐑 · open — provenance field (`version`)

The flam3 root carries `version` (the renderer that produced the genome). Useful
for archival forensics and pyr3 version-targeting.

## 🔍 Index query ergonomics (Phase 12c candidate)

## [ESF-004] feature · M · 🐑 · open — SQLite-backed query interface

Faster than scanning the 60+ MB `index.json` for repeat lookups. Build on demand
from `index.json`; `index.json` stays canonical.

## [ESF-005] feature · S · 🐑 · open — curated examples file

Hand-picked pyr3-parity references + stress-test cases (a `curated.md` analog).

## [ESF-006] feature · S · 🐑 · open — palette-hash field

Group genomes by visually-equivalent palettes for de-duped browsing.

## [ESF-007] feature · S · 🐑 · open — incremental index rebuild

Rebuild only gens whose `_chunked-verified.json` `loose_count` changed since last
index — chunked layout makes this trivial (per-bucket mtime).

## 📦 Release artifact

## [ESF-008] feature · M · 🔧 · open — stream `.flam3` bytes in `release._gather_gen_data`

Currently loads every flam3 into memory at once → peak RAM ~1.3 GB for gen 244
(86k files × ~15 KB). Fix: pass file paths through to `zipfile.write(path,
arcname=…)` for loose-mode gens; keep the in-memory dict for the sealed-transit
fallback. Defer until corpus growth makes single-machine release-build painful.

## [ESF-009] feature · S · 🔧 · open — id-set diff for consistency checks

`verify_unseal_consistency` and `verify_chunked_consistency` catch deletions via
count shrinkage, but a `missing.txt` overwrite that ADDS bogus entries while
losing real ones could net to the same total and slip through. A stronger id-set
diff against the post-migrate baseline closes the gap. Related: the hybrid-dedup
fix (ESF-024, shipped phase 12g).

## 🛰️ Live preservation

## [ESF-010] feature · XS · 🐑 · open — gen 249+ live extension

When ES rolls a new live gen: one-line edit to `LIVE_GENS` in `layout.py`, then
`fetch-all --gen 249`.

## [ESF-011] feature · S · 🐑 · open — range-discovery from server index HTML

Instead of `--upper 50000`, parse `/gen/N/` HTML once to determine the true upper
bound and auto-extend.

## [ESF-012] feature · XS · 🐑 · open — resume-on-SIGTERM banner

Print "Resuming from sheep N" on startup when a partial run is detected.

## [ESF-013] feature · S · 🐑 · open — server-index cache

Save the `/gen/NNN/` index HTML (~6 MB for gen 248) as a one-time preservation
artifact in case the live server goes dark before a sweep finishes.

## [ESF-014] feature · XS · 🐑 · open — `--retry-missing` flag

Only if ES ever shifts numbering semantics. Not needed under the current "gaps
stay gaps" invariant.

## 🎨 Consumer-facing

## [ESF-015] feature · XS · 🐑 · open — sidecar files

`--include-sidecars` flag if pyr3 ever needs `state.fsd` / `memory` / `spex`
alongside the `.flam3`.

## [ESF-016] feature · M · 🐑 · open — browsable gallery

GitHub Pages thumbnail grid — downstream of pyr3 integration (needs pyr3 rendering
to PNGs first).
