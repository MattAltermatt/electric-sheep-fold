# 🗃️ electric-sheep-fold Backlog

Authoritative registry of open tasks. Every open task carries an `[ESF-NNN]` ID
(required) and best-effort flags (optional): `category · size · sigil · status`.

Forward-only — shipped work lives in [CHANGELOG.md](CHANGELOG.md); strategic
narrative + current phase lives in [ROADMAP.md](ROADMAP.md). Pull a ticket
forward when it becomes load-bearing.

> **Next ID: ESF-038** — increment when creating a new entry. Never reuse, even
> for shipped/removed tasks.

**Sigils:** 🐛 bug · 🔧 fix/infra · 🔒 security · 🧪 test · 🐑 feature · 🪶 trivial.
**Sizes:** XS / S / M / L (cognitive + maintenance complexity, not wall-clock).

---

## 🔎 Code-review findings (filed 2026-05-29)

Three-critic whole-codebase review (correctness · security · modern-GitHub
standards). Top two are confirmed data-integrity bugs and are queued for the
next work block.

## [ESF-017] bug · S · 🐛 · ✅ **RESOLVED (2026-05-29, `1b6552a`)** — `_FLAM3_RE` `\d{5}` silently drops ids ≥ 100,000

> **✅ Resolved 2026-05-29.** Centralized the pattern as `FLAM3_RE` in
> `layout.py` with `\d{5,}`; repointed all five consumers (importer / index /
> migration / release / unseal) at it, deleting the five copies. Regression
> test in `test_layout.py::TestFlam3Re` (5- and 6-digit ids). 250 tests green.

**Symptom (verified 2026-05-29):** all five copies of `_FLAM3_RE` use `(\d{5})`
— exactly five digits — but `layout.flam3_filename` formats ids with `:05d`
(a *minimum* of 5; 6+ digits at id ≥ 100,000). Any sheep ≥ 100,000 would be
written to disk correctly by `fetch` but then invisible to `import`, `index`,
`migrate-chunked`, `release-build`, and `verify-unseal`. **Latent today** (gen
247 max ~25.8k, 248 ~40k) but a real time-bomb on corpus growth / gen-249.
**Files:** `importer.py:16`, `index.py:70`, `migration.py:32`, `release.py:54`,
`unseal.py:42`. **Fix:** `\d{5,}` (or `\d+` with an int cap) in all five; add a
regression test with a 6-digit id. Consider centralizing the regex in `layout.py`
so there's one source of truth.

## [ESF-018] bug · S · 🐛 · ✅ **RESOLVED (2026-05-29, `e51396d`)** — `fetch.py` writes unvalidated 200-OK bodies to corpus

> **✅ Resolved 2026-05-29.** Gated the 200 write on
> `is_flam3_content(response.content)`; a non-flam3 200 (the `none\n` sentinel,
> an HTML error page) is now a transient error — no write, no missing-entry, no
> skip-local poisoning. Regression tests in
> `test_fetch.py::TestFetchRange200NonFlame`.

**Symptom (verified 2026-05-29):** `is_flam3_content()` exists (`extract.py:38`,
fully tested against `none\n` / HTML / empty) but has **zero callers**. `fetch.py`
writes `response.content` verbatim on any HTTP 200 (`fetch.py:134-135`). A
non-flame 200 (the documented `none\n` sentinel, an HTML error page) becomes a
poisoned `.flam3`, then marks that id `skip_local` so the bad data is permanent.
**Fix:** gate the write on `is_flam3_content(response.content)`; a 200 that fails
the check is a transient error (no write, no missing-entry, retry/sleep). Add a
fetch test for the `none\n`-body case.

## [ESF-019] chore · XS · 🔧 · ✅ **RESOLVED (2026-05-29)** — version metadata drift (3-way)

> **✅ Resolved 2026-05-29.** Collapsed to a single source: `__init__.__version__`
> = `0.5.0`; `pyproject` now declares `dynamic = ["version"]` with
> `[tool.hatch.version] path = "src/electric_sheep_fold/__init__.py"`, so the
> packaged metadata is read from the code and can't drift. `pip install -e .`
> rebuilt metadata to `0.5.0`. Regression test `test_version.py` asserts the
> single-source wiring + that the User-Agent carries the version.

`pyproject.toml:3` = `0.2.5`, `__init__.py:3` = `0.2.3`, actual code state =
v0.4/v0.5. The semver field is orphaned under the ISO-date release model. **Fix:**
pick one truth — bump to `0.5.0` to match the toolchain, or adopt `hatch-vcs`, or
document that the package version intentionally tracks the toolchain spec, not the
release tag. Sync `__init__.__version__` to match.

## [ESF-020] bug · XS · 🐛 · ✅ **RESOLVED (2026-05-29)** — politeness jitter is one-sided

> **✅ Resolved 2026-05-29 (docs-to-code, no behavior change).** User decision:
> the code is the source of truth — `[20s, 25s]` (20s base + 0–5s) is *more*
> polite than the literal "±5s" and stays that way. Corrected the wording in
> CLAUDE.md / README / operations.md to match, documented the one-sided design
> in `_sleep_with_jitter`, and locked it with `test_fetch.py::TestSleepJitterOneSided`
> so it can't be "symmetrized" later.


`fetch.py:49-52` computes `delay + uniform(0, jitter)` → range `[delay,
delay+jitter]`, i.e. `[20, 25]`. The spec says "20s ±5s" = `[15, 25]`. Always ≥
the base delay (more conservative, so no politeness violation) but a spec
mismatch. **Fix:** `delay + uniform(-jitter, jitter)` with a `max(0, …)` floor —
**preserve the 20/5 constants** (politeness values are sacrosanct; this changes
only the formula's symmetry), or document the asymmetry as intentional.

## [ESF-021] bug · XS · 🐛 · ✅ **RESOLVED (2026-05-29, `55c18b8`)** — `build_chunks_tar` aborts on one non-UTF-8 flam3

> **✅ Resolved 2026-05-29.** `read_text` is now wrapped; a `UnicodeDecodeError`
> skips the file (excluded from BOTH avail and chunk so they stay consistent)
> with a warning, instead of aborting the artifact. Test
> `test_chunk.py::test_build_chunks_tar_skips_non_utf8_file`.


`chunk.py:211` uses `read_text(encoding="utf-8")`; a single non-UTF-8 `.flam3`
(reachable via ESF-018, or rare attr-value bytes) raises `UnicodeDecodeError` and
kills the whole artifact build. **Fix:** `read_bytes().decode("utf-8",
errors="replace")` or per-file try/except + warning skip.

## [ESF-022] bug · S · 🐛 · ✅ **RESOLVED (2026-05-29, `04808ba`)** — corrupt files misclassified as valid animations

> **✅ Resolved 2026-05-29.** The "junk after document element" branch now
> requires ≥2 `<flame` markers to be classified as an animation; otherwise the
> file is `corrupt` (`error="junk-after-document"`). Test
> `test_index.py::…::test_single_flame_with_trailing_junk_is_corrupt`.


`index.py:100-102` routes any `"junk after document element"` parse error to
`_index_animation` (→ `kind="animation"`, `valid=True`). A genuinely corrupt
single-flame file (`<flame>…</flame>GARBAGE`) is counted as a 1-frame animation
rather than `corrupt`. **Fix:** only treat as animation when byte-counting finds
≥ 2 `<flame` occurrences; otherwise `corrupt`.

## [ESF-023] bug · S · 🐛 · open — unseal move can clobber a newer corpus file on resume

`unseal.py:292-296` does `os.replace(src, dest)` unconditionally; if a parallel
`fetch` wrote a newer corpus file for the same id between steps, the unsealed
(older) content silently overwrites it. **Fix:** check `dest.exists()` before
replacing (skip-or-verify-identical), matching the docstring's stated
idempotency contract.

## [ESF-024] bug · S · 🐛 · open — index can emit duplicate ids in hybrid sealed+loose state

`index.iter_corpus_flames` (`index.py:330-359`) `rglob`s loose files AND reads
sealed-zip members; an id present in both (a real transit state) is emitted
twice. `release._gather_gen_data` dedups; this path does not. **Fix:** dedup by
id in `build_index`. Related to ESF-009 (id-set diff).

## [ESF-025] test · M · 🧪 · open — coverage gaps for load-bearing failure paths

No tests for: a 200 non-flame body poisoning the corpus (ESF-018), non-UTF-8
flam3 in `build_chunks_tar` (ESF-021), corrupt-vs-animation classification
(ESF-022), or the unseal SIGKILL-resume clobber (ESF-023). Add regressions
alongside each fix.

## [ESF-026] security · S · 🔒 · ✅ **RESOLVED (2026-05-29, `4d8f353`)** — parse untrusted XML with `defusedxml`

> **✅ Resolved 2026-05-29.** Both `ET.fromstring` callsites (`extract.py`,
> `index.py`) now use `defusedxml.ElementTree`; `except` clauses broadened to
> `(ET.ParseError, DefusedXmlException)` so an entity/DTD/external bomb is
> classified `corrupt` (or non-flame), never expanded or crashing the build.
> Added `defusedxml>=0.7` dep. Test
> `test_index.py::…::test_entity_bomb_is_corrupt_not_expanded`.


Network-sourced `.flam3` is parsed with stdlib `ElementTree` (`extract.py`,
`index.py`). XXE is blocked by Python's expat defaults, but **billion-laughs
internal-entity expansion is reachable** → build-host DoS during `index` /
`release-build`. **Fix:** drop-in `defusedxml.ElementTree`; add it to deps.

## [ESF-027] security · XS · 🔒 · open — document the plaintext-HTTP trust boundary

The live server is fetched over `http://v3d0.sheepserver.net` (`layout.py:6`);
the 200 body is written with no TLS / hash / signature, so an on-path attacker
can poison the corpus (and amplifies ESF-026). Upstream is a 2010-era lighttpd
likely without TLS, so this may be unavoidable — but it should be an explicit,
documented trust boundary (and a standing reason to keep ESF-026 done).

## [ESF-028] infra · XS · 🔧 · ✅ **RESOLVED (2026-05-29)** — commit `uv.lock`

> **✅ Resolved 2026-05-29.** `uv.lock` (now pinning the full graph incl.
> `defusedxml` from ESF-026, with sha256 hashes) is tracked. Reverses the
> earlier leave-it-untracked stance — a CLI that ingests untrusted data and
> publishes public artifacts should pin its supply chain.


`uv.lock` pins exact versions with sha256 hashes but is **untracked**; runtime
deps float on `>=` lower bounds, so a fresh install resolves to whatever is
newest on PyPI with no hash verification. For a CLI that ingests untrusted data
and publishes public artifacts, commit the lockfile.

## [ESF-029] security · XS · 🔒 · open — SRI hash for Chart.js in the stats page

`scripts/build_stats_page.py:146` loads `chart.js@4.4.1` from jsDelivr with no
`integrity=`/`crossorigin`. Low priority — the page is currently an untracked
local artifact — but add SRI before it's ever published.

## [ESF-030] infra · S · 🔧 · ✅ **RESOLVED (2026-05-29)** — stand up CI (no `.github/workflows/` exists)

> **✅ Resolved 2026-05-29.** Added `.github/workflows/ci.yml`: pytest on
> `push: main` + `pull_request`, matrix py3.11/3.12/3.13, actions SHA-pinned
> (`checkout` v6.0.2, `setup-uv` v8.1.0), top-level `permissions: contents:
> read`, uv cache, `uv sync --locked` (also guards the lockfile). First live
> run happens when the branch is pushed / a PR opens. **Follow-ups:** ESF-031
> (add ruff+mypy steps), ESF-036 (require this check via a branch ruleset).


The ~207-test suite runs on faith — nothing executes it on push/PR. **Fix:** add
`ci.yml` running `pytest` across a `python-version: [3.11, 3.12, 3.13]` matrix on
`pull_request` + `push: main`; pin actions to full commit SHA; top-level
`permissions: contents: read`; enable dep caching. Highest-leverage hygiene item.

## [ESF-031] infra · S · 🔧 · ✅ **RESOLVED (2026-05-29)** — ruff + mypy config, enforced in CI

> **✅ Resolved 2026-05-29.** Added `[tool.ruff]` (select E/F/I, line-length
> 100 — 88 was never followed) + `[tool.mypy]` (ignore-missing-imports) to
> pyproject, plus `ruff`/`mypy` to the dev extra. Fixed all findings: auto-fixed
> unused imports + import order, wrapped policy at 100 with `# noqa: E501` on 7
> unsplittable INDEX.md jq-recipe literals, typed `_load_verified_log` →
> `dict[str, Any]` (cleared 6 `int(object)` mypy errors), moved test_chunk
> mid-file imports to top. CI `lint` job now runs `ruff check` + `mypy src`.
> Debt turned out trivial (≈13 real items), not the M–L I'd feared.


`.gitignore` lists `.ruff_cache/` + `.mypy_cache/` (so both run locally) but
`pyproject.toml` has no `[tool.ruff]`/`[tool.mypy]` and the `dev` extra omits
them. The quality bar is invisible/unreproducible. **Fix:** add both to the `dev`
extra, add config blocks, run in CI (depends on ESF-030).

## [ESF-032] infra · XS · 🔒 · open — `SECURITY.md` + private vulnerability reporting

No security policy and no documented reporting channel for a tool that makes
outbound HTTP requests. **Fix:** add `SECURITY.md` (supported versions +
reporting channel) and enable GitHub Private Vulnerability Reporting.

## [ESF-033] infra · M · 🔧 · open — provenance-attested release workflow

Releases are hand-assembled + uploaded (`scripts/build_release.sh` ends in a
copy-paste `gh release create`). No SLSA provenance; consumers `tar -xJf` blindly
with no verification story. **Fix:** tag-triggered workflow running `release-build`
+ `actions/attest-build-provenance` + upload; add a "verify your download" snippet
(`gh attestation verify` / asset digests) to the README.

## [ESF-034] infra · S · 🐑 · open — community-health files

Missing `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates. `has_issues`
is on but there's no triage scaffolding or stated contribution workflow. A
lightweight `CONTRIBUTING.md` is the highest-value one.

## [ESF-035] infra · XS · 🔧 · open — Dependabot (+ optional CodeQL)

`dependabot_security_updates` is disabled; no `.github/dependabot.yml`. Deps
float unmonitored. **Fix:** add a Dependabot config; CodeQL is lower priority for
a small pure-Python CLI but cheap to add.

## [ESF-036] infra · XS · 🔧 · open — branch-protection ruleset on `main`

`main` is unprotected (`protected: false`, 0 rulesets); the documented
FF-merge-after-verify workflow is not enforced. **Fix (after ESF-030):** ruleset
requiring the CI status check + linear history.

## [ESF-037] infra · 🪶 · open — packaging metadata polish (only if PyPI is ever wanted)

Not on PyPI (a legitimate choice for corpus tooling). If publishing is ever
desired: fill `classifiers`, `keywords`, `[project.urls]`, and use OIDC trusted
publishing (not a long-lived token). README should state "install from source;
not published to PyPI." Defer unless publishing becomes a goal.

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
diff against the post-migrate baseline closes the gap. Related: ESF-024.

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
