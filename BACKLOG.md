# 🗃️ electric-sheep-fold Backlog

Authoritative registry of open tasks. Every open task carries an `[ESF-NNN]` ID
(required) and best-effort flags (optional): `category · size · sigil · status`.

Forward-only — shipped work lives in [CHANGELOG.md](CHANGELOG.md); strategic
narrative + current phase lives in [ROADMAP.md](ROADMAP.md). Pull a ticket
forward when it becomes load-bearing. When a ticket ships, its entry is **deleted
here** (CHANGELOG owns the record); `git log -- BACKLOG.md` recovers the trail.

> **Next ID: ESF-039** — increment when creating a new entry. Never reuse, even
> for shipped/removed tasks.

**Sigils:** 🐛 bug · 🔧 fix/infra · 🔒 security · 🧪 test · 🐑 feature · 🪶 trivial.
**Sizes:** XS / S / M / L (cognitive + maintenance complexity, not wall-clock).

> **Ordering:** open sections run in rough priority order (most-likely-next at
> top), and tickets within a section run cheap-win / foundational first. Parked
> work (deferred / declined) lives at the bottom.

---

## 🛰️ Live preservation (most-likely-next — routine refresh + new gens)

## [ESF-010] feature · XS · 🐑 · open — gen 249+ live extension

When ES rolls a new live gen: one-line edit to `LIVE_GENS` in `layout.py`, then
`fetch-all --gen 249`.

## [ESF-011] feature · S · 🐑 · open — range-discovery from server index HTML

Instead of `--upper 50000`, parse `/gen/N/` HTML once to determine the true upper
bound and auto-extend.

## [ESF-013] feature · S · 🐑 · open — server-index cache

Save the `/gen/NNN/` index HTML (~6 MB for gen 248) as a one-time preservation
artifact in case the live server goes dark before a sweep finishes. Shares the
HTML-fetch with [ESF-011].

## [ESF-012] feature · XS · 🐑 · open — resume-on-SIGTERM banner

Print "Resuming from sheep N" on startup when a partial run is detected.

## [ESF-014] feature · XS · 🐑 · open — `--retry-missing` flag

Only if ES ever shifts numbering semantics. Not needed under the current "gaps
stay gaps" invariant.

---

## 🔍 Index query ergonomics (pull forward when `index.json` scans slow / pyr3 demands)

## [ESF-007] feature · S · 🐑 · open — incremental index rebuild

Rebuild only gens whose `_chunked-verified.json` `loose_count` changed since last
index — chunked layout makes this trivial (per-bucket mtime). Foundational: makes
every later index field cheap to backfill.

## [ESF-004] feature · M · 🐑 · open — SQLite-backed query interface

Faster than scanning the 60+ MB `index.json` for repeat lookups. Build on demand
from `index.json`; `index.json` stays canonical.

## [ESF-005] feature · S · 🐑 · open — curated examples file

Hand-picked pyr3-parity references + stress-test cases (a `curated.md` analog).

---

## 📚 Index richness (future schema bump — cheap fields first)

## [ESF-003] feature · XS · 🐑 · open — provenance field (`version`)

The flam3 root carries `version` (the renderer that produced the genome). Useful
for archival forensics and pyr3 version-targeting.

## [ESF-002] feature · S · 🐑 · open — tone-mapping diversity fields

Surface `gamma`, `vibrancy`, `estimator_minimum`, `estimator_curve` — the rest of
the density-estimator + tone-map family. Currently only `has_density_estimator`
is exposed.

## [ESF-001] feature · M · 🐑 · open — runtime NaN detection (`produces_nan: bool`)

Static checks (the v0.4 five-field set) catch most NaN producers; a short
chaos-game probe per genome would catch residuals. Index-build cost scales
linearly; gate on whether the static-only verdict misses enough cases to matter
for pyr3 integration.

---

## 📦 Release artifact (defer until corpus growth makes single-machine build painful)

## [ESF-038] feature · M · 🔧 · open — `release-build --skip-unchanged` (fingerprint-gated data artifacts)

Automate the release flow so unchanged corpus data isn't re-compressed. The data
artifacts (per-gen `.zip`, `corpus-all.tar.xz`, `corpus-chunks.tar`) are pure
functions of the corpus bytes; only the index also depends on parser/schema code.
Rule: **always rebuild + ship `index.json` / `INDEX.md` (cheap, ~90s); rebuild a
data artifact only when its inputs changed.** Cheap fingerprints already exist —
per-gen `MANIFEST.csv` is `(id, sha256)`, and `corpus/_chunked-verified.json`
tracks per-gen `loose_count` / `missing_count` / `bucket_count`. Store last-release
fingerprints in a small state file; `--skip-unchanged` diffs them, reuses the
prior-dated asset for unchanged gens, and skips `corpus-all` / `chunks` when no
gen changed. Motivating case: the 2026-05-29 schema-v6 release re-ran a ~20-min
q11-brotli `corpus-chunks` pass that produced byte-identical data to 2026-05-28.
**Constraint:** local-only automation (a flag + script/Makefile), NOT GitHub
Actions — the corpus is gitignored + ~554 MB, the same wall that deferred
[ESF-033]. **Filename subtlety:** reuse the prior-dated asset for unchanged gens
(a 2026-05-29 release honestly containing `gen-244-2026-05-23.zip`) rather than
re-stamping. Related: [ESF-007] (incremental index rebuild), [ESF-008] (release
memory).

## [ESF-009] feature · S · 🔧 · open — id-set diff for consistency checks

`verify_unseal_consistency` and `verify_chunked_consistency` catch deletions via
count shrinkage, but a `missing.txt` overwrite that ADDS bogus entries while
losing real ones could net to the same total and slip through. A stronger id-set
diff against the post-migrate baseline closes the gap. Related: the hybrid-dedup
fix (ESF-024, shipped phase 12g).

## [ESF-008] feature · M · 🔧 · open — stream `.flam3` bytes in `release._gather_gen_data`

Currently loads every flam3 into memory at once → peak RAM ~1.3 GB for gen 244
(86k files × ~15 KB). Fix: pass file paths through to `zipfile.write(path,
arcname=…)` for loose-mode gens; keep the in-memory dict for the sealed-transit
fallback. Defer until corpus growth makes single-machine release-build painful.

---

## 🎨 Consumer-facing (downstream of pyr3 integration)

## [ESF-015] feature · XS · 🐑 · open — sidecar files

`--include-sidecars` flag if pyr3 ever needs `state.fsd` / `memory` / `spex`
alongside the `.flam3`.

## [ESF-016] feature · M · 🐑 · open — browsable gallery

GitHub Pages thumbnail grid — downstream of pyr3 integration (needs pyr3 rendering
to PNGs first).

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

## [ESF-006] feature · S · 🐑 · 🚫 WON'T DO — palette-hash field for de-duped browsing

Field in search of a consumer. A 3-agent investigation (2026-05-29) confirmed it
would *work* — exact-normalized hashing collapses 65–95% of genomes into shared
color-scheme buckets (ES copies parent palettes verbatim far more than it mutates
them; the genetic-drift hypothesis was wrong, and perceptual/quantized hashing
adds <1pp before it fuses visibly-distinct palettes). But nothing consumes it:
pyr3 parses palettes straight from raw `.flam3`, no `jq` recipe groups by palette,
and the only plausible consumer (browsable gallery [ESF-016]) is itself deferred +
blocked on pyr3 PNG rendering. Revisit only if a gallery materializes — and if so,
note the two findings worth preserving: (1) the corpus has **two** palette
encodings (inline `<color>` RGB in gens 198/242–248 vs `palette="N"` integer refs
in the four oldest gens — the latter needs a separate `palette_ref` field, ~637
distinct, 95% dedup), and (2) ship **exact** (`sha256[:16]`), not perceptual.

## [ESF-034] infra · S · 🚫 WON'T DO — community-health files (CoC / CONTRIBUTING / templates)

Reviewed item-by-item and cut as ceremony for a solo niche repo: no contributor
community to govern; the PR checklist is redundant with the enforced CI gate;
README + CLAUDE.md already cover dev conventions. A ~2-minute add if a real
contributor community ever forms. (SECURITY.md from the same checklist shipped —
phase 12j.)
