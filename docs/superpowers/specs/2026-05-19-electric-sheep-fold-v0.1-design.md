# 🐑 electric-sheep-fold v0.1 — design

**Date:** 2026-05-19 · **Status:** draft → user review

A polite, idempotent Python CLI that mirrors `.flam3` fractal-flame genomes from the live
[Electric Sheep](https://electricsheep.org) v3d0 server into a local corpus directory,
intended primarily as a parity-test source for the [pyr3](../../../../pyr3) renderer.

---

## 🎯 1. Context & motivation

**pyr3** (Kotlin/JVM, sibling project) is a deterministic fractal-flame renderer that
currently has a single parity golden: sheep `244.00016`. To prove pyr3's claim of
byte-identical, flam3-faithful output, it needs a much **broader corpus** of real ES
flames to render against.

The current live ES server publishes generation 248 at:

```
http://v3d0.sheepserver.net/gen/248/<sheep_id>/electricsheep.248.<sheep_id:05d>.flam3
```

Each sheep dir also contains `state.fsd`, `memory`, `spex`, `dequeue`, and `size`
sidecar files, but only the `.flam3` (the XML genome) is needed for pyr3's purposes.

**electric-sheep-fold** is the tool that mirrors those `.flam3` files locally, politely (so we
don't burden the lighttpd 1.4.33 backend), idempotently (resumable across sessions
without re-fetching what we already have, and without re-probing dirs we already
confirmed are empty), and with first-class respect for the Electric Sheep CC licenses.

## 🧭 2. Goals & non-goals

### Goals (v0.1)

1. **Local, idempotent mirror** of `.flam3` files from `gen/248/`, range-driven via CLI.
2. **Polite cadence**: configurable delay (default 20s) + jitter; never parallel.
3. **Sticky 404 memory**: once a sheep_id is confirmed missing on the server, never
   re-probe it. (ES sheep numbering is append-only; gaps stay gaps forever.)
4. **Skip-without-network** for sheep already in the local corpus or already in the
   known-missing set. Sleep only after requests that actually hit the network.
5. **Crash-safe writes**: tmp-file + `os.replace`, no partial flam3s masquerading as
   complete. `missing.txt` written after every add.
6. **License-honored redistribution**: the corpus ships as a proper "Sheep Pack" per
   the [ES license terms](https://electricsheep.org/license/), with `ATTRIBUTION.md`
   inside.
7. **Project doc set**: VISION, ROADMAP, CHANGELOG, BACKLOG, CLAUDE, README — same
   shape as the pyr3 sibling, for navigability.

### Non-goals (v0.1)

- ❌ Pulling sidecar files (`state.fsd`, `memory`, `spex`, `dequeue`, `size`). Future
  phase if pyr3 needs them.
- ❌ Rendering thumbnails / PNGs. Pyr3's job.
- ❌ Parallel downloads. At a 20s polite cadence, parallelism = zero benefit, real
  server risk.
- ❌ Public GitHub corpus repo on day one. Local-only ships first; remote publishing is
  a deliberate Phase 4 decision.
- ❌ Other generations (249+). Parameterizable via `--gen`, but day-1 focus is 248.
- ❌ Commercial redistribution. Per ES license, algorithm sheep are CC BY-NC; we
  surface this in `ATTRIBUTION.md` but do not gate against it in code.

## 🗺️ 3. Scope of v0.1

What ships:

- `sheep-fold fetch START..END [--gen 248] [--delay 20] [--jitter 5]` — main loop.
- `sheep-fold status [--gen 248]` — counts downloaded / known-missing / untried.
- Local corpus at `./corpus/248/<bucket>/electricsheep.248.<id:05d>.flam3`.
- `./corpus/248/missing.txt` — sorted, deduped, per-gen sticky 404 set.
- `./corpus/ATTRIBUTION.md` — the Sheep-Pack attribution file (license obligation).
- `./LICENSE` — GPL-3.0-or-later for the tool code.
- Six-doc bootstrap (README, VISION, ROADMAP, CHANGELOG, BACKLOG, CLAUDE).
- `pytest` suites for the pure modules (`layout`, `manifest`) and a mock-transport test
  for the fetch loop branches.

## 📜 4. License & attribution (load-bearing)

Two distinct licenses apply, and they cover **different things**:

### 4.1 The TOOL code → GPL-3.0-or-later

The Python code in `src/`, `tests/`, and the docs in this repo: **GPL-3.0-or-later**,
matching pyr3 and the upstream flam3 lineage (Scott Draves, C `double`). The `LICENSE`
file at repo root carries the full text. `pyproject.toml` declares
`license = "GPL-3.0-or-later"` (SPDX identifier).

### 4.2 The CORPUS data → Creative Commons (per electricsheep.org/license/)

Every `.flam3` file we download is licensed by the Electric Sheep project under one of
two CC licenses, depending on origin:

| Source | License | Implication |
|---|---|---|
| **Algorithm-generated sheep** (live `gen/N/`, brood, edge) | [CC BY-NC 3.0 US](https://creativecommons.org/licenses/by-nc/3.0/us/) (Attribution-NonCommercial) | Non-commercial use only; lineage preserved |
| **Human-designed sheep** (the "human" archive) | [CC BY 3.0 US](https://creativecommons.org/licenses/by/3.0/us/) (Attribution) | Designer credited by name |

Gen 248 (our day-1 target) is the live algorithm-bred generation, so the corpus is
**predominantly CC BY-NC**. Individual sheep tagged with a `nick="..."` attribute on
the `<flame>` root may be human-designed contributions — Phase-future
`attribution.csv` extractor will distinguish them.

### 4.3 The "Sheep Pack" obligation

The ES license includes a clause for redistributing collections:

> *"If you are distributing your own Sheep Packs (archives containing many sheep),
> then include the attribution in the metainfo (description) of the pack, and in a
> text or html file inside the pack."*

The corpus directory **is** such a pack. To satisfy this, electric-sheep-fold writes
`corpus/ATTRIBUTION.md` as part of Phase 1 bootstrap, containing:

1. The required attribution string: **"artwork by Scott Draves and the Electric Sheep"**.
2. The two CC license names + links.
3. A note that algorithm-generated sheep are non-commercial.
4. A pointer to the canonical license page (`https://electricsheep.org/license/`).
5. The filename convention `electricsheep.XXX.YYYYY.flam3` (which is itself an
   attribution mechanism per the policy — preserved verbatim by electric-sheep-fold).

Any future Phase 4 public corpus repo (see §11) will surface `ATTRIBUTION.md` from its
README and include the attribution string in the repo description (the "metainfo" of
the pack).

### 4.4 What electric-sheep-fold specifically does

- ✅ Preserves the full `electricsheep.GGG.NNNNN.flam3` filename verbatim.
- ✅ Preserves the `.flam3` XML byte-for-byte (no re-serialization, no stripping).
- ✅ Ships `ATTRIBUTION.md` as a **package data file**
  (`src/electric_sheep_fold/data/ATTRIBUTION.md`), then copies it to `corpus/ATTRIBUTION.md`
  the first time `fetch` materializes the corpus directory. This way the
  obligation-satisfying file is always alongside the data, even though `corpus/`
  itself is gitignored from the tool repo.
- ✅ Sends a `User-Agent` identifying the tool + linking the repo (so server admins
  can reach us).
- ✅ Surfaces the license terms in `README.md` and `VISION.md`.
- 🔮 (Phase-future) `attribution.csv` extractor reads each flam3's root attrs and
  emits a per-sheep credit ledger (`nick`, `url`, lineage).

## 🧱 5. Architecture

Four modules under `src/electric_sheep_fold/`, each with one job:

| Module | Purpose | Key surface |
|---|---|---|
| **`layout.py`** | Pure path / URL math, no I/O | `bucket_for(id)`, `local_path(gen, id, root)`, `remote_url(gen, id, base)` |
| **`manifest.py`** | Persistent sticky-404 skip-set | `MissingSet(path)` with `contains(id)`, `add(id)`, `save_atomic()` |
| **`fetch.py`** | Polite orchestration loop | `fetch_range(gen, start, end, root, client, delay, jitter)` |
| **`cli.py`** | Typer entrypoint | `sheep-fold fetch ...`, `sheep-fold status ...` |

**Why this split:** `layout` and `manifest` are pure → unit-testable without network.
`fetch` takes an injected `httpx.Client` → testable with a `MockTransport` for the
200/404/transient branches. `cli` is thin glue.

### 5.1 `layout.py` — bucket math

```python
def bucket_for(sheep_id: int) -> str:
    """0 → '00xxx', 999 → '00xxx', 1000 → '01xxx', 40700 → '40xxx'."""
    return f"{sheep_id // 1000:02d}xxx"

def local_path(gen: int, sheep_id: int, corpus_root: Path) -> Path:
    return (
        corpus_root
        / str(gen)
        / bucket_for(sheep_id)
        / f"electricsheep.{gen}.{sheep_id:05d}.flam3"
    )

def remote_url(gen: int, sheep_id: int, base: str = "http://v3d0.sheepserver.net") -> str:
    # ES publishes dirs as non-padded ints: /gen/248/100/, not /gen/248/00100/
    return f"{base}/gen/{gen}/{sheep_id}/electricsheep.{gen}.{sheep_id:05d}.flam3"
```

Note: the **remote URL** uses non-padded `{sheep_id}` for the directory segment
(matches ES server: `/gen/248/100/...`), while the **filename and local path** use
the 5-digit padded form (matches what's IN the file and what the ES license tells us
to preserve).

### 5.2 `manifest.py` — MissingSet

```python
class MissingSet:
    def __init__(self, path: Path): ...
    def load(self) -> None: ...           # idempotent; missing file = empty set
    def contains(self, sheep_id: int) -> bool: ...
    def add(self, sheep_id: int) -> None: ...   # in-memory add
    def save_atomic(self) -> None: ...    # tmp + os.replace, sorted, deduped
```

**File format** (`corpus/248/missing.txt`):

```
102
105
207
...
```

One decimal sheep_id per line, sorted ascending, deduped on write. Trailing newline.
Git-friendly: small line-oriented diffs as new gaps are discovered.

### 5.3 `fetch.py` — the per-sheep state machine

**Bootstrap (runs once per `fetch` invocation, before the loop):**

- Ensure `corpus_root/` exists (create if not).
- Ensure `corpus_root/ATTRIBUTION.md` exists. If absent, copy the file from
  `importlib.resources.files("electric_sheep_fold.data") / "ATTRIBUTION.md"` into place. This
  guarantees the Sheep-Pack attribution obligation is satisfied the moment any
  `.flam3` lands.
- Ensure `corpus_root/{gen}/` exists.
- Load `corpus_root/{gen}/missing.txt` into `MissingSet` (or initialize empty).

**Then for each `sheep_id` in `[start, end)`:**

```
┌── local file exists?      ──► skip-local         (log, NO network, NO sleep)
│
├── id in missing.txt?      ──► skip-known-missing (log, NO network, NO sleep)
│
└── GET <remote_url>, 30s timeout
       ├── 200 ──► write tmp → os.replace → final path
       │           → log downloaded
       │           → sleep(delay + uniform(0, jitter))
       │
       ├── 404 ──► missing.add(id); missing.save_atomic()
       │           → log missing
       │           → sleep(delay + uniform(0, jitter))
       │
       └── 5xx / timeout / connection-error ──► log transient (do NOT record)
                   → sleep(delay + uniform(0, jitter))
                   → continue
```

**Atomicity invariants:**

- A `.flam3` file at its final path is **always** the full file. Partial writes live in
  `<final>.tmp` until `os.replace`.
- `missing.txt` is saved **after every `add`**. SIGKILL-safe; we never lose a recorded
  404.
- Skips cost zero server time — sleep is gated on actual network activity.

### 5.4 `cli.py` — Typer

```sh
# Default: gen 248, sheep 0..1999, 20s+jitter pace, ./corpus root
sheep-fold fetch 0..2000

# Different gen, snappier
sheep-fold fetch 0..500 --gen 249 --delay 10 --jitter 2

# Corpus elsewhere
sheep-fold fetch 1000..1100 --corpus /Volumes/Big/sheep-corpus

# Quick status
sheep-fold status
# 248: 327 downloaded · 41 known-missing · 1632 untried in 0..2000
```

**Range syntax:** `START..END`, half-open `[START, END)`, matches Python / Rust idiom.

## 🗂️ 6. On-disk layout

```
electric-sheep-fold/
├── pyproject.toml                  # uv-installable; runtime: httpx, typer
├── LICENSE                         # GPL-3.0-or-later (tool code)
├── README.md                       # user-facing entry point
├── VISION.md                       # the why
├── ROADMAP.md                      # phases + live todos
├── CHANGELOG.md                    # version history
├── BACKLOG.md                      # unphased ideas
├── CLAUDE.md                       # per-repo conventions for future-me
├── .gitignore                      # excludes corpus/ (code vs. data separation)
├── .python-version                 # 3.11+
├── src/electric_sheep_fold/
│   ├── __init__.py
│   ├── cli.py
│   ├── fetch.py
│   ├── layout.py
│   ├── manifest.py
│   └── data/
│       └── ATTRIBUTION.md          # template copied to corpus/ on first fetch
├── tests/
│   ├── __init__.py
│   ├── test_layout.py
│   ├── test_manifest.py
│   └── test_fetch.py
├── docs/superpowers/
│   ├── specs/2026-05-19-electric-sheep-fold-v0.1-design.md     # this file
│   └── plans/                      # populated by writing-plans step
└── corpus/                         # GITIGNORED in tool repo
    ├── ATTRIBUTION.md              # the Sheep-Pack attribution file
    └── 248/
        ├── missing.txt
        ├── 00xxx/
        │   ├── electricsheep.248.00100.flam3
        │   └── electricsheep.248.00101.flam3
        ├── 01xxx/
        │   └── electricsheep.248.01500.flam3
        └── 40xxx/
            └── electricsheep.248.40700.flam3
```

**Bucket sizing rationale:** by-thousand → **41 buckets at root** (00xxx through
40xxx), ≤1000 files each. Stays comfortably under git/filesystem/Finder slowdown
thresholds (~5–10k files per dir is where things bog), and the `XXxxx` mask telegraphs
the bucket boundary at a glance.

**`corpus/` is gitignored:** the tool repo stays small (code only). If we ever publish
the data, it goes to a separate `MattAltermatt/electric-sheep-fold-corpus` repo (see Phase 4),
which would carry `ATTRIBUTION.md` un-ignored at its root.

## 🤝 7. Polite-request defaults

| Setting | Default | Why |
|---|---|---|
| Delay | 20s | User-specified; ultra-polite, plenty of headroom for lighttpd 1.4.33 |
| Jitter | ±5s | Uniform [0, jitter] added to delay; avoids perfectly-fixed cadence in logs |
| Concurrency | 1 | Sequential; parallelism = zero benefit at 20s gap |
| Timeout | 30s | Connection + read; 5xx + timeout = transient (not recorded) |
| User-Agent | `electric-sheep-fold/0.1 (companion to pyr3; https://github.com/MattAltermatt/electric-sheep-fold)` | Identifiable + contactable per RFC 9110 §10.1.5 |
| Retry on transient | None in v0.1 | We just continue; next run retries naturally |

## 🧪 8. Testing strategy

- **`test_layout.py`** — bucket math (`0`, `999`, `1000`, `40700`, `40999`), URL
  derivation, path derivation. Pure functions; ~10 cases; runs in <100ms.
- **`test_manifest.py`** — `MissingSet` round-trips: load empty, add a few, save,
  reload, assert sorted + deduped. Uses `pytest`'s `tmp_path`.
- **`test_fetch.py`** — `fetch_range` with `httpx.MockTransport`:
  - 200 path → file written, no add to missing
  - 404 path → file not written, id added to missing.txt
  - 5xx path → file not written, id NOT added to missing.txt
  - already-local → no network call (assert via mock call count)
  - already-in-missing → no network call

All tests pure / mock-driven, no real network. Real-network smoke test is a one-off
manual `sheep-fold fetch 100..105` after install, not part of the suite.

## 📚 9. The six-doc bootstrap

Same shape as the pyr3 sibling — written as part of Phase 1, not as code-after-the-fact:

| Doc | What it carries |
|---|---|
| **README.md** | Hook + install + 3-line quickstart + license summary + links to other docs |
| **VISION.md** | Why this exists; relationship to pyr3 and ES; what "done" looks like; ES license context |
| **ROADMAP.md** | Numbered phases + live todos (see §11 below) |
| **CHANGELOG.md** | Version history; v0.1 entry for initial ship |
| **BACKLOG.md** | Unphased ideas (attribution.csv, gallery, multi-gen, verify subcommand) |
| **CLAUDE.md** | Per-repo conventions: terse commits, no trailers, polite-request defaults, sticky 404 invariant, where corpus lives, CC-license respect, etc. |

All docs get emoji-flavored section headers per user voice preferences.

## 🛠️ 10. Project bootstrap (Phase 1, deliverable order)

1. `git init -b main`; set local identity to `MattAltermatt / 1435066+MattAltermatt@users.noreply.github.com` ✅ *(done)*
2. Write `docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md` (this file).
   Commit. ⏳ *(in progress)*
3. Write the six-doc set (README, VISION, ROADMAP, CHANGELOG, BACKLOG, CLAUDE).
4. Write `LICENSE` (GPL-3.0-or-later full text) at repo root.
5. Write `pyproject.toml`, `.gitignore`, `.python-version`, `src/electric_sheep_fold/__init__.py`,
   `src/electric_sheep_fold/data/ATTRIBUTION.md` (the package-data Sheep-Pack attribution
   template, ready to be copied into `corpus/` by `fetch` on first run).
6. Write `layout.py` + `test_layout.py`. TDD: red → green → commit.
7. Write `manifest.py` + `test_manifest.py`. TDD: red → green → commit.
8. Write `fetch.py` + `test_fetch.py` (with `MockTransport`). TDD: red → green → commit.
9. Write `cli.py` (Typer entrypoint). Smoke-test `sheep-fold --help`.
10. Real-server smoke test: `sheep-fold fetch 100..105` (~80s wall, ≤5 files).
    Confirms the auto-copy of `ATTRIBUTION.md` into `corpus/` happens on first run.
11. Update CHANGELOG; user-verify; FF-merge to main.

## 🔮 11. Roadmap (Phase 2+)

- **Phase 2 — `verify` subcommand.** Re-hash all corpus files; surface any local
  truncation or damage. Cheap (no network).
- **Phase 3 — pyr3 integration.** Pyr3 reads from `corpus/248/` directly as a
  parity-test source. The point of the whole exercise.
- **Phase 4 — public corpus repo (optional).** Push `corpus/` to a separate
  `MattAltermatt/electric-sheep-fold-corpus` GitHub repo. ~440MB worst case for full gen 248
  (40k × 11KB), well within plain-git limits — no LFS needed. README of that repo
  must surface `ATTRIBUTION.md`; repo description carries the attribution string per
  the Sheep-Pack clause.
- **Phase 5 — additional generations.** Run `--gen 249` (etc.) as ES rolls over.
  Same script, no changes needed beyond the flag.

## 🗃️ 12. Backlog (unphased)

- **`attribution.csv` extractor.** Parse each `.flam3` XML root tag for
  `<flame name="..." nick="..." url="...">`; emit a CSV of who-rendered-what for a
  richer credit ledger than the file alone. Distinguishes algorithm-bred (no `nick`)
  from human-designed (named `nick`) — surfaces who-designed-what for the CC BY
  half of the corpus.
- **Sidecar files.** If pyr3 ever needs `state.fsd` / `memory` / `spex`, add a
  `--include-sidecars` flag.
- **Browsable gallery.** GitHub Pages-style thumbnail grid (requires pyr3 rendering
  the corpus to PNGs first — explicitly downstream of Phase 3). Must carry
  attribution per the ES policy for "use on the web."
- **Retry-known-missing.** If the user ever wants to recheck the 404 set (e.g.,
  after a server topology change), a `--retry-missing` flag. Not needed under the
  current "append-only ES numbering → gaps stay gaps" assumption.
- **Resume-on-SIGTERM banner.** Nice-to-have: print "Resuming from sheep N" on
  startup when the local corpus + missing.txt indicate a previous partial run.
- **Server-index cache.** Optionally save the gen-NNN index HTML (~6MB for 248) as
  a one-time preservation artifact — useful if ES ever goes dark.

## 🧷 13. Open small choices (defaulted, easy to flip)

| Choice | Default | Flip via |
|---|---|---|
| Range syntax | `0..2000` | Could switch to `--start 0 --end 2000` |
| Jitter | enabled, ±5s | `--jitter 0` to disable |
| `missing.txt` granularity | per-gen | per-bucket if it grows past ~10k lines |
| `corpus/` in git? | gitignored in tool repo | inverted in Phase 4 (separate corpus repo) |
| User-Agent contact URL | `github.com/MattAltermatt/electric-sheep-fold` | swap once the repo URL is real |
| Tool license | GPL-3.0-or-later (matches pyr3 + flam3 lineage) | MIT / Apache if you'd rather |
| Python tooling | uv + pyproject.toml | conventional, no setup-py |
