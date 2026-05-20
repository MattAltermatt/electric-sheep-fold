# electric-sheep-fold v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a polite, idempotent Python CLI that mirrors `.flam3` fractal-flame genomes from `v3d0.sheepserver.net/gen/248/` into a local `corpus/` directory, with sticky 404 memory and Sheep-Pack-compliant attribution.

**Architecture:** Four small modules under `src/electric_sheep_fold/` — `layout` (pure path/URL math), `manifest` (sticky-404 set), `fetch` (state-machine loop with httpx), `cli` (Typer entrypoint). Plus a packaged `data/ATTRIBUTION.md` template auto-copied into `corpus/` on first fetch. Tests are pure / mock-driven (`httpx.MockTransport`); no real network in CI.

**Tech Stack:** Python 3.11+, `httpx`, `typer`, `pytest`, `hatchling` build backend, `uv` for venv & install.

**Spec:** [`../specs/2026-05-19-electric-sheep-fold-v0.1-design.md`](../specs/2026-05-19-electric-sheep-fold-v0.1-design.md)

**Execution mode:** Tasks 1–6 are subagent-friendly (pure file edits + pytest). Task 7 (real-server smoke + user verify + FF-merge) is **lead-inline** because it issues live network calls at a 20s cadence and gates on user sign-off.

---

## Branching

Per user convention: all work happens on `feature/v0.1-bootstrap`. The first task creates this branch off `main` (which currently has the spec commit `43b6b8b`). FF-merge to `main` happens in Task 7 after user verify.

---

### Task 1: Repo bootstrap & doc set

**Files:**
- Create: `.gitignore`
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `LICENSE` (full GPL-3.0-or-later text)
- Create: `README.md`
- Create: `VISION.md`
- Create: `ROADMAP.md`
- Create: `CHANGELOG.md`
- Create: `BACKLOG.md`
- Create: `CLAUDE.md`
- Create: `src/electric_sheep_fold/__init__.py`
- Create: `src/electric_sheep_fold/data/__init__.py`
- Create: `src/electric_sheep_fold/data/ATTRIBUTION.md`
- Create: `tests/__init__.py`

No code modules yet — just the package skeleton, the doc set, and the Sheep-Pack attribution template that subsequent tasks will copy into place.

- [ ] **Step 1a: Create the feature branch.**

  ```bash
  cd /Users/matt/dev/muwamath/electric-sheep-fold
  git checkout -b feature/v0.1-bootstrap
  ```

- [ ] **Step 1b: Write `.gitignore`** with the contents below:

  ```gitignore
  # Python
  __pycache__/
  *.py[cod]
  *.egg-info/
  build/
  dist/
  .pytest_cache/
  .mypy_cache/
  .ruff_cache/
  .venv/
  venv/

  # Corpus data (large; lives in a separate repo if ever published — see ROADMAP Phase 4)
  /corpus/

  # IDE / OS
  .vscode/
  .idea/
  *.swp
  .DS_Store
  ```

- [ ] **Step 1c: Write `.python-version`** containing just `3.11`.

- [ ] **Step 1d: Write `pyproject.toml`** with the contents below:

  ```toml
  [project]
  name = "electric-sheep-fold"
  version = "0.1.0"
  description = "Polite, idempotent mirror of Electric Sheep .flam3 genomes — companion to pyr3"
  readme = "README.md"
  requires-python = ">=3.11"
  license = "GPL-3.0-or-later"
  authors = [{ name = "muwamath" }]
  dependencies = [
      "httpx>=0.27",
      "typer>=0.12",
  ]

  [project.optional-dependencies]
  dev = [
      "pytest>=8.0",
  ]

  [project.scripts]
  electric-sheep-fold = "electric_sheep_fold.cli:app"

  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["src/electric_sheep_fold"]

  [tool.pytest.ini_options]
  testpaths = ["tests"]
  addopts = "-v"
  ```

- [ ] **Step 1e: Write `LICENSE`** — full GPL-3.0-or-later text. Easiest method:

  ```bash
  curl -fsSL https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE
  ```

  Verify the file is ~35KB and starts with `GNU GENERAL PUBLIC LICENSE` + ends with the trailing usage notice.

- [ ] **Step 1f: Write `README.md`** with the contents below:

  ````markdown
  # 🐑 electric-sheep-fold

  > Polite, idempotent mirror of [Electric Sheep](https://electricsheep.org) `.flam3`
  > genomes — companion to [pyr3](../pyr3).

  ## Install

  ```sh
  uv pip install -e ".[dev]"
  ```

  ## Quickstart

  ```sh
  electric-sheep-fold fetch 0..100              # download sheep 0–99 in gen 248
  electric-sheep-fold status                    # show what's downloaded vs missing
  ```

  ## What it does

  Walks a half-open `[START, END)` range of sheep IDs in generation 248 (or `--gen N`)
  on the live ES v3d0 server, downloading any `.flam3` files that aren't already in
  the local `corpus/` directory, at a polite 20-second cadence (configurable). Empty
  sheep dirs (HTTP 404s) are recorded once in `corpus/248/missing.txt` and never
  re-probed.

  The local layout groups files by thousand under `corpus/248/00xxx/` through
  `corpus/248/40xxx/` — see [`VISION.md`](VISION.md) for why.

  ## Docs

  - [VISION.md](VISION.md) — the why
  - [ROADMAP.md](ROADMAP.md) — phases + live todos
  - [CHANGELOG.md](CHANGELOG.md) · [BACKLOG.md](BACKLOG.md) · [CLAUDE.md](CLAUDE.md)
  - Design spec: [`docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md`](docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md)

  ## License

  **Tool code (this repo):** [GPL-3.0-or-later](LICENSE).

  **Corpus data (downloaded `.flam3` files):** Creative Commons, per
  [electricsheep.org/license](https://electricsheep.org/license/). Algorithm-generated
  sheep are CC BY-NC; human-designed sheep are CC BY. The Sheep-Pack attribution file
  is auto-written to `corpus/ATTRIBUTION.md` on first `fetch`.
  ````

- [ ] **Step 1g: Write `VISION.md`** with the contents below:

  ```markdown
  # 🔮 Vision

  ## Why electric-sheep-fold exists

  [pyr3](../pyr3) is a deterministic fractal-flame renderer on the JVM. It claims
  byte-identical output across machines for any [flam3](https://github.com/scottdraves/flam3)
  genome. To prove that claim broadly, pyr3 needs a corpus of real Electric Sheep
  flames to render against — not just the single `244.00016` golden it ships with.

  electric-sheep-fold is the tool that builds that corpus.

  ## What "done" looks like

  - A local `corpus/248/` directory containing a meaningful fraction of gen 248's
    `.flam3` files, organized by thousand-bucket for git/filesystem friendliness.
  - A sticky `missing.txt` recording which sheep IDs were confirmed empty on the
    server, so we never re-probe them.
  - `corpus/ATTRIBUTION.md` in place per the ES license's Sheep-Pack clause.
  - pyr3 consumes the corpus for parity testing (Phase 3 — outside electric-sheep-fold's
    scope but the reason the tool exists).

  ## Politeness as a design constraint

  The live ES server (v3d0, lighttpd 1.4.33) is volunteer infrastructure preserving
  20+ years of crowdsourced generative art. electric-sheep-fold treats it accordingly:

  - **20-second default cadence** between requests; configurable but never
    parallelized.
  - **Sticky 404 memory** so we never re-probe known-empty dirs (the worst form of
    rudeness is also the most pointless — re-asking after we already learned the
    answer).
  - **Identifiable User-Agent** that names the project and links the repo, so server
    admins can reach us if our load is ever a problem.

  ## License lineage

  electric-sheep-fold (the tool) is GPL-3.0-or-later, matching pyr3 and the upstream flam3
  lineage from Scott Draves (2003). The corpus data is Creative Commons per ES
  policy — see [`README.md`](README.md) and (after first `fetch`)
  `corpus/ATTRIBUTION.md`.
  ```

- [ ] **Step 1h: Write `ROADMAP.md`** with the contents below:

  ```markdown
  # 🗺️ Roadmap

  > Phases are strategic milestones; the **🚧 Todos** block at the bottom is the
  > living set of next concrete actions.

  ## Phases

  ### Phase 1 — v0.1 ship 🛠️ *(in progress)*

  Bootstrap the tool: package + docs + four-module architecture (`layout`, `manifest`,
  `fetch`, `cli`) + tests + real-server smoke test. Spec:
  [`docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md`](docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md).

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

  - Execute the v0.1 plan ([`docs/superpowers/plans/2026-05-19-electric-sheep-fold-v0.1.md`](docs/superpowers/plans/2026-05-19-electric-sheep-fold-v0.1.md))
  ```

- [ ] **Step 1i: Write `CHANGELOG.md`** with the contents below:

  ```markdown
  # 📝 Changelog

  ## v0.1.0 — unreleased

  Initial ship.

  - Polite range-based mirror of `.flam3` files from `v3d0.sheepserver.net/gen/248/`
  - Sticky 404 memory via `corpus/{gen}/missing.txt`
  - Local-first dedup; skips cost zero server time
  - Atomic writes (tmp + `os.replace`); SIGKILL-safe
  - Bucket-by-thousand on-disk layout (`248/00xxx/`…`248/40xxx/`)
  - Auto-copied `corpus/ATTRIBUTION.md` (Sheep-Pack obligation per
    [electricsheep.org/license](https://electricsheep.org/license/))
  - Typer CLI: `electric-sheep-fold fetch`, `electric-sheep-fold status`
  - pytest suites for `layout`, `manifest`, `fetch` (mock-transport, no real network)
  ```

- [ ] **Step 1j: Write `BACKLOG.md`** with the contents below:

  ```markdown
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
  ```

- [ ] **Step 1k: Write `CLAUDE.md`** with the contents below:

  ```markdown
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
  ```

- [ ] **Step 1l: Write `src/electric_sheep_fold/__init__.py`**:

  ```python
  """electric-sheep-fold — polite mirror of Electric Sheep .flam3 genomes."""

  __version__ = "0.1.0"
  ```

- [ ] **Step 1m: Write `src/electric_sheep_fold/data/__init__.py`**:

  ```python
  """Package data (e.g., the ATTRIBUTION.md template)."""
  ```

- [ ] **Step 1n: Write `src/electric_sheep_fold/data/ATTRIBUTION.md`** with the contents below:

  ```markdown
  # Attribution

  This directory contains a collection of fractal-flame genomes (`.flam3` files)
  downloaded from the [Electric Sheep](https://electricsheep.org) v3d0 server using
  [electric-sheep-fold](https://github.com/muwamath/electric-sheep-fold), a companion tool to
  [pyr3](https://github.com/muwamath/pyr3).

  ## Required attribution

  **artwork by Scott Draves and the Electric Sheep**

  (Per [electricsheep.org/license](https://electricsheep.org/license/) — required for
  any redistribution, display, or use of these files.)

  ## License terms

  Per the Electric Sheep license, two Creative Commons licenses apply, depending on
  the origin of each sheep:

  | Source | License | Implication |
  |---|---|---|
  | **Algorithm-generated sheep** (the live `gen/N/` directories, including brood and edge archives) | [CC BY-NC 3.0 US](https://creativecommons.org/licenses/by-nc/3.0/us/) (Attribution-NonCommercial) | Non-commercial use only; lineage preserved in the genome |
  | **Human-designed sheep** (the "human" archive) | [CC BY 3.0 US](https://creativecommons.org/licenses/by/3.0/us/) (Attribution) | Designer credited by name on the `<flame nick="...">` attribute |

  The current electric-sheep-fold corpus targets `gen/248/`, which is the live
  algorithm-bred generation, so it is **predominantly CC BY-NC**.

  ## Commercial use

  Commercial use or use without attribution requires a separate license from
  Spotworks, LLC — contact `info@spotworks.com`.

  ## Filename convention

  Each file is named `electricsheep.<GEN>.<SERIAL>.flam3` (e.g.,
  `electricsheep.248.00100.flam3`) — this is itself an attribution mechanism per
  the ES license. electric-sheep-fold preserves this filename verbatim.

  ## Canonical source

  Full license terms: [electricsheep.org/license](https://electricsheep.org/license/).
  ```

- [ ] **Step 1o: Write `tests/__init__.py`** (empty file — just marks it a package):

  ```python
  ```

- [ ] **Step 1p: Smoke-test the build.**

  ```bash
  uv venv
  source .venv/bin/activate
  uv pip install -e ".[dev]"
  python -c "import electric_sheep_fold; print(electric_sheep_fold.__version__)"
  pytest --collect-only
  ```

  Expected: prints `0.1.0`, then `pytest` reports `no tests ran` (no test files yet — confirms collection works).

- [ ] **Step 1q: Commit.**

  ```bash
  git add .gitignore .python-version pyproject.toml LICENSE \
          README.md VISION.md ROADMAP.md CHANGELOG.md BACKLOG.md CLAUDE.md \
          src/ tests/
  git commit -m "bootstrap: package skeleton + six-doc set + attribution template"
  ```

---

### Task 2: `layout` module + tests

**Files:**
- Create: `src/electric_sheep_fold/layout.py`
- Test: `tests/test_layout.py`

Pure path / URL math with no I/O. The bucket-by-thousand convention, canonical filename format, and the dir-segment-non-padded / filename-segment-padded URL split all live here. Smallest, most-testable module — the right place to start TDD.

- [ ] **Step 2a: Write `tests/test_layout.py`** (failing tests first):

  ```python
  """Tests for electric_sheep_fold.layout — pure path/URL math."""
  from pathlib import Path

  import pytest

  from electric_sheep_fold.layout import (
      BASE_URL_DEFAULT,
      bucket_for,
      flam3_filename,
      local_path,
      remote_url,
  )


  class TestBucketFor:
      @pytest.mark.parametrize(
          "sheep_id, expected",
          [
              (0, "00xxx"),
              (1, "00xxx"),
              (999, "00xxx"),
              (1000, "01xxx"),
              (1999, "01xxx"),
              (40700, "40xxx"),
              (40999, "40xxx"),
              (41000, "41xxx"),
          ],
      )
      def test_bucket_boundaries(self, sheep_id, expected):
          assert bucket_for(sheep_id) == expected

      def test_negative_rejected(self):
          with pytest.raises(ValueError):
              bucket_for(-1)


  class TestFlam3Filename:
      def test_padding_default_gen(self):
          assert flam3_filename(248, 0) == "electricsheep.248.00000.flam3"
          assert flam3_filename(248, 100) == "electricsheep.248.00100.flam3"
          assert flam3_filename(248, 40700) == "electricsheep.248.40700.flam3"

      def test_padding_different_gen(self):
          assert flam3_filename(244, 16) == "electricsheep.244.00016.flam3"


  class TestLocalPath:
      def test_assembly_low_sheep(self, tmp_path: Path):
          assert local_path(248, 100, tmp_path) == (
              tmp_path / "248" / "00xxx" / "electricsheep.248.00100.flam3"
          )

      def test_assembly_high_sheep(self, tmp_path: Path):
          assert local_path(248, 40700, tmp_path) == (
              tmp_path / "248" / "40xxx" / "electricsheep.248.40700.flam3"
          )


  class TestRemoteUrl:
      def test_default_base(self):
          assert remote_url(248, 100) == (
              "http://v3d0.sheepserver.net/gen/248/100/electricsheep.248.00100.flam3"
          )

      def test_dir_segment_non_padded(self):
          # /gen/248/100/, NOT /gen/248/00100/
          url = remote_url(248, 100)
          assert "/248/100/" in url
          assert "/00100/" not in url

      def test_filename_segment_padded(self):
          url = remote_url(248, 100)
          assert url.endswith("electricsheep.248.00100.flam3")

      def test_custom_base(self):
          assert remote_url(248, 100, base="https://mirror.example.com") == (
              "https://mirror.example.com/gen/248/100/electricsheep.248.00100.flam3"
          )

      def test_base_default_constant(self):
          assert BASE_URL_DEFAULT == "http://v3d0.sheepserver.net"
  ```

- [ ] **Step 2b: Run tests, confirm they fail with ImportError.**

  ```bash
  pytest tests/test_layout.py -v
  ```

  Expected: ImportError or ModuleNotFoundError on `electric_sheep_fold.layout` (module doesn't exist yet).

- [ ] **Step 2c: Write `src/electric_sheep_fold/layout.py`** to make them pass:

  ```python
  """Pure path / URL math for electric-sheep-fold. No I/O."""
  from __future__ import annotations

  from pathlib import Path

  BASE_URL_DEFAULT = "http://v3d0.sheepserver.net"


  def bucket_for(sheep_id: int) -> str:
      """Return the bucket name for a sheep_id.

      0–999 → '00xxx', 1000–1999 → '01xxx', …, 40700–40999 → '40xxx'.
      """
      if sheep_id < 0:
          raise ValueError(f"sheep_id must be non-negative, got {sheep_id}")
      return f"{sheep_id // 1000:02d}xxx"


  def flam3_filename(gen: int, sheep_id: int) -> str:
      """Canonical filename — preserved verbatim per ES attribution scheme."""
      return f"electricsheep.{gen}.{sheep_id:05d}.flam3"


  def local_path(gen: int, sheep_id: int, corpus_root: Path) -> Path:
      """Local on-disk path for a given gen + sheep_id."""
      return (
          corpus_root
          / str(gen)
          / bucket_for(sheep_id)
          / flam3_filename(gen, sheep_id)
      )


  def remote_url(gen: int, sheep_id: int, base: str = BASE_URL_DEFAULT) -> str:
      """Source URL on the ES v3d0 server.

      Note: dir segment is NON-padded (matches what ES publishes:
      /gen/248/100/, not /gen/248/00100/).
      """
      return f"{base}/gen/{gen}/{sheep_id}/{flam3_filename(gen, sheep_id)}"
  ```

- [ ] **Step 2d: Run tests, confirm all pass.**

  ```bash
  pytest tests/test_layout.py -v
  ```

  Expected: all ~14 cases (parametrized) PASS.

- [ ] **Step 2e: Commit.**

  ```bash
  git add src/electric_sheep_fold/layout.py tests/test_layout.py
  git commit -m "feat: layout module (bucket math + path/URL derivation)"
  ```

---

### Task 3: `manifest` module + tests

**Files:**
- Create: `src/electric_sheep_fold/manifest.py`
- Test: `tests/test_manifest.py`

The sticky-404 skip-set. Persisted as `corpus/{gen}/missing.txt`, one sheep_id per line, sorted and deduped on write. Atomic save via tmp + `os.replace`. Load is idempotent (missing file = empty set).

- [ ] **Step 3a: Write `tests/test_manifest.py`** (failing tests first):

  ```python
  """Tests for electric_sheep_fold.manifest — MissingSet round-trips."""
  from pathlib import Path

  from electric_sheep_fold.manifest import MissingSet


  def test_load_empty_when_file_absent(tmp_path: Path):
      ms = MissingSet(tmp_path / "missing.txt")
      ms.load()
      assert len(ms) == 0
      assert not ms.contains(42)


  def test_add_then_contains(tmp_path: Path):
      ms = MissingSet(tmp_path / "missing.txt")
      ms.add(102)
      assert ms.contains(102)
      assert not ms.contains(103)


  def test_save_atomic_creates_file(tmp_path: Path):
      path = tmp_path / "missing.txt"
      ms = MissingSet(path)
      ms.add(102)
      ms.save_atomic()
      assert path.exists()
      assert path.read_text(encoding="utf-8") == "102\n"


  def test_save_sorted_and_deduped(tmp_path: Path):
      path = tmp_path / "missing.txt"
      ms = MissingSet(path)
      ms.add(207)
      ms.add(105)
      ms.add(102)
      ms.add(105)  # dup
      ms.save_atomic()
      assert path.read_text(encoding="utf-8") == "102\n105\n207\n"


  def test_round_trip(tmp_path: Path):
      path = tmp_path / "missing.txt"
      ms = MissingSet(path)
      ms.add(1)
      ms.add(42)
      ms.add(999)
      ms.save_atomic()

      ms2 = MissingSet(path)
      ms2.load()
      assert ms2.contains(1)
      assert ms2.contains(42)
      assert ms2.contains(999)
      assert not ms2.contains(2)
      assert len(ms2) == 3


  def test_save_creates_parent_dirs(tmp_path: Path):
      path = tmp_path / "248" / "missing.txt"
      ms = MissingSet(path)
      ms.add(1)
      ms.save_atomic()
      assert path.exists()


  def test_load_ignores_blank_lines(tmp_path: Path):
      path = tmp_path / "missing.txt"
      path.write_text("102\n\n105\n", encoding="utf-8")
      ms = MissingSet(path)
      ms.load()
      assert ms.contains(102)
      assert ms.contains(105)
      assert len(ms) == 2


  def test_no_tmp_left_behind(tmp_path: Path):
      path = tmp_path / "missing.txt"
      ms = MissingSet(path)
      ms.add(1)
      ms.save_atomic()
      tmp = path.with_suffix(path.suffix + ".tmp")
      assert not tmp.exists()
  ```

- [ ] **Step 3b: Run tests, confirm they fail with ImportError.**

  ```bash
  pytest tests/test_manifest.py -v
  ```

  Expected: ImportError on `electric_sheep_fold.manifest`.

- [ ] **Step 3c: Write `src/electric_sheep_fold/manifest.py`** to make them pass:

  ```python
  """Persistent sticky-404 skip-set for electric-sheep-fold."""
  from __future__ import annotations

  import os
  from pathlib import Path


  class MissingSet:
      """Sorted, deduped set of sheep_ids known to be missing on the server.

      File format: one decimal sheep_id per line, sorted ascending, trailing newline.
      Stored at `corpus/{gen}/missing.txt`. Append-only in spirit — we never
      re-probe an id once it's in here.
      """

      def __init__(self, path: Path) -> None:
          self.path = path
          self._ids: set[int] = set()

      def load(self) -> None:
          """Load IDs from disk. Missing file = empty set (idempotent)."""
          if not self.path.exists():
              self._ids = set()
              return
          with self.path.open("r", encoding="utf-8") as f:
              self._ids = {
                  int(line.strip())
                  for line in f
                  if line.strip()
              }

      def contains(self, sheep_id: int) -> bool:
          return sheep_id in self._ids

      def add(self, sheep_id: int) -> None:
          self._ids.add(sheep_id)

      def __len__(self) -> int:
          return len(self._ids)

      def save_atomic(self) -> None:
          """Write to disk: tmp file → os.replace. Sorted, deduped, newline-terminated."""
          self.path.parent.mkdir(parents=True, exist_ok=True)
          tmp = self.path.with_suffix(self.path.suffix + ".tmp")
          with tmp.open("w", encoding="utf-8") as f:
              for sid in sorted(self._ids):
                  f.write(f"{sid}\n")
          os.replace(tmp, self.path)
  ```

- [ ] **Step 3d: Run tests, confirm all pass.**

  ```bash
  pytest tests/test_manifest.py -v
  ```

  Expected: all 8 tests PASS.

- [ ] **Step 3e: Commit.**

  ```bash
  git add src/electric_sheep_fold/manifest.py tests/test_manifest.py
  git commit -m "feat: manifest module (sticky-404 MissingSet, atomic save)"
  ```

---

### Task 4: `fetch` module + tests

**Files:**
- Create: `src/electric_sheep_fold/fetch.py`
- Test: `tests/test_fetch.py`

The orchestration loop. `ensure_corpus_initialized(corpus_root)` runs once per invocation and auto-copies `data/ATTRIBUTION.md` into place. Then per sheep_id: local-skip / known-missing-skip / GET → 200=write-atomic / 404=record-missing / 5xx=transient. Skips cost zero sleep. `delay=0, jitter=0` in tests makes the loop instant.

- [ ] **Step 4a: Write `tests/test_fetch.py`** (failing tests first):

  ```python
  """Tests for electric_sheep_fold.fetch — state machine branches with MockTransport."""
  from pathlib import Path

  import httpx

  from electric_sheep_fold.fetch import ensure_corpus_initialized, fetch_range
  from electric_sheep_fold.layout import local_path
  from electric_sheep_fold.manifest import MissingSet


  def _build_client(handler):
      transport = httpx.MockTransport(handler)
      return httpx.Client(transport=transport)


  class TestEnsureCorpusInitialized:
      def test_creates_root_and_attribution(self, tmp_path: Path):
          root = tmp_path / "corpus"
          ensure_corpus_initialized(root)
          assert root.exists()
          attr = root / "ATTRIBUTION.md"
          assert attr.exists()
          assert "Scott Draves" in attr.read_text(encoding="utf-8")

      def test_idempotent_no_overwrite(self, tmp_path: Path):
          root = tmp_path / "corpus"
          root.mkdir()
          attr = root / "ATTRIBUTION.md"
          attr.write_text("custom content", encoding="utf-8")
          ensure_corpus_initialized(root)
          assert attr.read_text(encoding="utf-8") == "custom content"


  class TestFetchRange200:
      def test_writes_file_on_200(self, tmp_path: Path):
          body = b"<flame name='electricsheep.248.00100' />"

          def handler(request: httpx.Request) -> httpx.Response:
              return httpx.Response(200, content=body)

          client = _build_client(handler)
          stats = fetch_range(
              gen=248, start=100, end=101,
              corpus_root=tmp_path, client=client,
              delay=0, jitter=0,
          )
          assert stats.downloaded == 1
          assert stats.newly_missing == 0
          dest = local_path(248, 100, tmp_path)
          assert dest.exists()
          assert dest.read_bytes() == body


  class TestFetchRange404:
      def test_records_missing_and_persists(self, tmp_path: Path):
          def handler(request: httpx.Request) -> httpx.Response:
              return httpx.Response(404)

          client = _build_client(handler)
          stats = fetch_range(
              gen=248, start=102, end=103,
              corpus_root=tmp_path, client=client,
              delay=0, jitter=0,
          )
          assert stats.newly_missing == 1
          assert stats.downloaded == 0
          assert not local_path(248, 102, tmp_path).exists()

          ms = MissingSet(tmp_path / "248" / "missing.txt")
          ms.load()
          assert ms.contains(102)


  class TestFetchRange5xx:
      def test_does_not_record_missing(self, tmp_path: Path):
          def handler(request: httpx.Request) -> httpx.Response:
              return httpx.Response(503)

          client = _build_client(handler)
          stats = fetch_range(
              gen=248, start=200, end=201,
              corpus_root=tmp_path, client=client,
              delay=0, jitter=0,
          )
          assert stats.transient_errors == 1
          assert stats.newly_missing == 0
          ms = MissingSet(tmp_path / "248" / "missing.txt")
          ms.load()
          assert not ms.contains(200)


  class TestSkipLocal:
      def test_skips_when_file_present(self, tmp_path: Path):
          call_count = {"n": 0}

          def handler(request: httpx.Request) -> httpx.Response:
              call_count["n"] += 1
              return httpx.Response(200, content=b"never-served")

          # Pre-populate the local file.
          dest = local_path(248, 100, tmp_path)
          dest.parent.mkdir(parents=True, exist_ok=True)
          dest.write_bytes(b"already-here")

          client = _build_client(handler)
          stats = fetch_range(
              gen=248, start=100, end=101,
              corpus_root=tmp_path, client=client, delay=0, jitter=0,
          )
          assert stats.skip_local == 1
          assert call_count["n"] == 0
          assert dest.read_bytes() == b"already-here"


  class TestSkipKnownMissing:
      def test_skips_when_in_missing(self, tmp_path: Path):
          call_count = {"n": 0}

          def handler(request: httpx.Request) -> httpx.Response:
              call_count["n"] += 1
              return httpx.Response(200, content=b"never-served")

          # Pre-populate missing.txt.
          gen_root = tmp_path / "248"
          gen_root.mkdir(parents=True)
          ms = MissingSet(gen_root / "missing.txt")
          ms.add(102)
          ms.save_atomic()

          client = _build_client(handler)
          stats = fetch_range(
              gen=248, start=102, end=103,
              corpus_root=tmp_path, client=client, delay=0, jitter=0,
          )
          assert stats.skip_known_missing == 1
          assert call_count["n"] == 0


  class TestAtomicWrite:
      def test_no_tmp_left_after_success(self, tmp_path: Path):
          def handler(request: httpx.Request) -> httpx.Response:
              return httpx.Response(200, content=b"body")

          client = _build_client(handler)
          fetch_range(
              gen=248, start=100, end=101,
              corpus_root=tmp_path, client=client, delay=0, jitter=0,
          )
          dest = local_path(248, 100, tmp_path)
          tmp_file = dest.with_suffix(dest.suffix + ".tmp")
          assert dest.exists()
          assert not tmp_file.exists()


  class TestMultipleSheep:
      def test_mixed_200_and_404(self, tmp_path: Path):
          def handler(request: httpx.Request) -> httpx.Response:
              # 100 → 200, 101 → 404, 102 → 200
              if "/100/" in request.url.path:
                  return httpx.Response(200, content=b"a")
              if "/101/" in request.url.path:
                  return httpx.Response(404)
              if "/102/" in request.url.path:
                  return httpx.Response(200, content=b"c")
              return httpx.Response(500)

          client = _build_client(handler)
          stats = fetch_range(
              gen=248, start=100, end=103,
              corpus_root=tmp_path, client=client, delay=0, jitter=0,
          )
          assert stats.downloaded == 2
          assert stats.newly_missing == 1
          assert local_path(248, 100, tmp_path).exists()
          assert not local_path(248, 101, tmp_path).exists()
          assert local_path(248, 102, tmp_path).exists()
          ms = MissingSet(tmp_path / "248" / "missing.txt")
          ms.load()
          assert ms.contains(101)
  ```

- [ ] **Step 4b: Run tests, confirm they fail with ImportError.**

  ```bash
  pytest tests/test_fetch.py -v
  ```

  Expected: ImportError on `electric_sheep_fold.fetch`.

- [ ] **Step 4c: Write `src/electric_sheep_fold/fetch.py`** to make them pass:

  ```python
  """Polite orchestration loop for electric-sheep-fold."""
  from __future__ import annotations

  import logging
  import os
  import random
  import time
  from dataclasses import dataclass
  from importlib import resources
  from pathlib import Path

  import httpx

  from electric_sheep_fold.layout import local_path, remote_url
  from electric_sheep_fold.manifest import MissingSet

  log = logging.getLogger(__name__)


  USER_AGENT = (
      "electric-sheep-fold/0.1 (companion to pyr3; https://github.com/muwamath/electric-sheep-fold)"
  )


  @dataclass
  class FetchStats:
      downloaded: int = 0
      skip_local: int = 0
      skip_known_missing: int = 0
      newly_missing: int = 0
      transient_errors: int = 0


  def ensure_corpus_initialized(corpus_root: Path) -> None:
      """Create corpus root + copy ATTRIBUTION.md template into place if absent.

      Required by the ES Sheep-Pack license clause: any archive of sheep must
      carry an attribution file. We satisfy that here, the moment the corpus
      directory comes into existence.
      """
      corpus_root.mkdir(parents=True, exist_ok=True)
      attr_dest = corpus_root / "ATTRIBUTION.md"
      if not attr_dest.exists():
          template = resources.files("electric_sheep_fold.data").joinpath("ATTRIBUTION.md")
          attr_dest.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
          log.info("wrote ATTRIBUTION.md to %s", attr_dest)


  def _sleep_with_jitter(delay: float, jitter: float) -> None:
      if delay > 0:
          wait = delay + (random.uniform(0, jitter) if jitter > 0 else 0.0)
          time.sleep(wait)


  def fetch_range(
      gen: int,
      start: int,
      end: int,
      corpus_root: Path,
      client: httpx.Client,
      delay: float = 20.0,
      jitter: float = 5.0,
      timeout: float = 30.0,
  ) -> FetchStats:
      """Mirror sheep[start, end) for the given gen.

      Local-first dedup → known-missing dedup → GET → atomic write or
      record-missing. Skips cost zero server time and zero sleep.
      """
      ensure_corpus_initialized(corpus_root)

      gen_root = corpus_root / str(gen)
      gen_root.mkdir(parents=True, exist_ok=True)

      missing = MissingSet(gen_root / "missing.txt")
      missing.load()

      stats = FetchStats()

      for sheep_id in range(start, end):
          dest = local_path(gen, sheep_id, corpus_root)

          if dest.exists():
              log.info("skip-local %d.%05d", gen, sheep_id)
              stats.skip_local += 1
              continue

          if missing.contains(sheep_id):
              log.info("skip-known-missing %d.%05d", gen, sheep_id)
              stats.skip_known_missing += 1
              continue

          url = remote_url(gen, sheep_id)
          try:
              response = client.get(url, timeout=timeout)
          except httpx.HTTPError as e:
              log.warning("transient error for %d.%05d: %s", gen, sheep_id, e)
              stats.transient_errors += 1
              _sleep_with_jitter(delay, jitter)
              continue

          status = response.status_code
          if status == 200:
              dest.parent.mkdir(parents=True, exist_ok=True)
              tmp = dest.with_suffix(dest.suffix + ".tmp")
              tmp.write_bytes(response.content)
              os.replace(tmp, dest)
              log.info("downloaded %d.%05d", gen, sheep_id)
              stats.downloaded += 1
          elif status == 404:
              missing.add(sheep_id)
              missing.save_atomic()
              log.info("missing %d.%05d (recorded)", gen, sheep_id)
              stats.newly_missing += 1
          else:
              log.warning(
                  "unexpected status %d for %d.%05d — treating as transient",
                  status, gen, sheep_id,
              )
              stats.transient_errors += 1

          _sleep_with_jitter(delay, jitter)

      return stats


  def make_client() -> httpx.Client:
      """Build an httpx.Client carrying the polite User-Agent."""
      return httpx.Client(headers={"User-Agent": USER_AGENT})
  ```

- [ ] **Step 4d: Run all tests, confirm everything passes.**

  ```bash
  pytest -v
  ```

  Expected: every test from layout + manifest + fetch suites PASSes; no real network was hit (all via `MockTransport`).

- [ ] **Step 4e: Commit.**

  ```bash
  git add src/electric_sheep_fold/fetch.py tests/test_fetch.py
  git commit -m "feat: fetch module (state machine + atomic write + ATTRIBUTION init)"
  ```

---

### Task 5: `cli` module + tests

**Files:**
- Create: `src/electric_sheep_fold/cli.py`
- Test: `tests/test_cli.py`

Typer entrypoint wiring `fetch_range` and a simple `status` command. Range syntax `START..END` parsed with a small regex and validated (non-empty, end > start).

- [ ] **Step 5a: Write `tests/test_cli.py`** (failing tests first):

  ```python
  """Tests for the CLI surface — range parsing + smoke."""
  import pytest
  import typer
  from typer.testing import CliRunner

  from electric_sheep_fold.cli import _parse_range, app

  runner = CliRunner()


  class TestParseRange:
      def test_valid(self):
          assert _parse_range("0..100") == (0, 100)
          assert _parse_range("1000..2000") == (1000, 2000)

      @pytest.mark.parametrize("bad", ["0,100", "0..", "..100", "abc..def", ""])
      def test_invalid_format(self, bad):
          with pytest.raises(typer.BadParameter):
              _parse_range(bad)

      def test_empty_range_rejected(self):
          with pytest.raises(typer.BadParameter):
              _parse_range("100..100")

      def test_inverted_range_rejected(self):
          with pytest.raises(typer.BadParameter):
              _parse_range("100..50")


  class TestHelp:
      def test_top_level_help(self):
          result = runner.invoke(app, ["--help"])
          assert result.exit_code == 0
          assert "Polite mirror" in result.output

      def test_fetch_help(self):
          result = runner.invoke(app, ["fetch", "--help"])
          assert result.exit_code == 0
          assert "START..END" in result.output


  class TestStatus:
      def test_status_no_corpus(self, tmp_path):
          result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
          assert result.exit_code == 0
          assert "not yet materialized" in result.output

      def test_status_with_corpus(self, tmp_path):
          # Materialize a fake corpus
          gen_root = tmp_path / "248"
          bucket = gen_root / "00xxx"
          bucket.mkdir(parents=True)
          (bucket / "electricsheep.248.00100.flam3").write_bytes(b"x")
          (gen_root / "missing.txt").write_text("105\n200\n", encoding="utf-8")

          result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
          assert result.exit_code == 0
          assert "1 downloaded" in result.output
          assert "2 known-missing" in result.output
  ```

- [ ] **Step 5b: Run tests, confirm they fail with ImportError.**

  ```bash
  pytest tests/test_cli.py -v
  ```

  Expected: ImportError on `electric_sheep_fold.cli`.

- [ ] **Step 5c: Write `src/electric_sheep_fold/cli.py`** to make them pass:

  ```python
  """Typer entrypoint for electric-sheep-fold."""
  from __future__ import annotations

  import logging
  import re
  from pathlib import Path

  import typer

  from electric_sheep_fold.fetch import fetch_range, make_client
  from electric_sheep_fold.manifest import MissingSet

  app = typer.Typer(
      help="Polite mirror of Electric Sheep .flam3 genomes.",
      add_completion=False,
      no_args_is_help=True,
  )


  RANGE_RE = re.compile(r"^(\d+)\.\.(\d+)$")


  def _parse_range(range_str: str) -> tuple[int, int]:
      """Parse 'START..END' (half-open) → (start, end)."""
      m = RANGE_RE.match(range_str)
      if not m:
          raise typer.BadParameter(f"range must be START..END, got {range_str!r}")
      start, end = int(m.group(1)), int(m.group(2))
      if end <= start:
          raise typer.BadParameter(
              f"range must be non-empty: end ({end}) must exceed start ({start})"
          )
      return start, end


  @app.command()
  def fetch(
      range_str: str = typer.Argument(..., metavar="START..END", help="Half-open range, e.g., 0..2000"),
      gen: int = typer.Option(248, help="ES generation"),
      delay: float = typer.Option(20.0, help="Seconds between requests"),
      jitter: float = typer.Option(5.0, help="Random jitter added to delay (uniform 0..jitter)"),
      corpus: Path = typer.Option(Path("./corpus"), help="Corpus root directory"),
  ) -> None:
      """Download .flam3 files for sheep[start, end) into the corpus."""
      logging.basicConfig(level=logging.INFO, format="%(message)s")
      start, end = _parse_range(range_str)

      with make_client() as client:
          stats = fetch_range(
              gen=gen, start=start, end=end,
              corpus_root=corpus, client=client,
              delay=delay, jitter=jitter,
          )

      typer.echo(
          f"\n{gen}: {stats.downloaded} downloaded · "
          f"{stats.newly_missing} newly missing · "
          f"{stats.skip_local} skip-local · "
          f"{stats.skip_known_missing} skip-known-missing · "
          f"{stats.transient_errors} transient errors"
      )


  @app.command()
  def status(
      gen: int = typer.Option(248, help="ES generation"),
      corpus: Path = typer.Option(Path("./corpus"), help="Corpus root directory"),
  ) -> None:
      """Show corpus status: downloaded vs known-missing for the given gen."""
      gen_root = corpus / str(gen)
      if not gen_root.exists():
          typer.echo(f"{gen}: corpus not yet materialized (run `electric-sheep-fold fetch` first)")
          return

      downloaded = sum(1 for _ in gen_root.rglob("electricsheep.*.flam3"))
      ms = MissingSet(gen_root / "missing.txt")
      ms.load()
      typer.echo(f"{gen}: {downloaded} downloaded · {len(ms)} known-missing")


  if __name__ == "__main__":
      app()
  ```

- [ ] **Step 5d: Run all tests + a manual --help smoke.**

  ```bash
  pytest -v
  electric-sheep-fold --help
  electric-sheep-fold fetch --help
  ```

  Expected: pytest all-green; `--help` prints "Polite mirror of Electric Sheep .flam3 genomes" and lists `fetch` + `status` commands.

- [ ] **Step 5e: Commit.**

  ```bash
  git add src/electric_sheep_fold/cli.py tests/test_cli.py
  git commit -m "feat: Typer CLI (fetch + status commands, range parsing)"
  ```

---

### Task 6: Code review (fresh reviewer)

**Files:**
- No code changes from the review pass itself.
- Modify (only if review surfaces issues): any of the previously-created files.

Per user convention "code review is a required phase, as the second-to-last phase," dispatch a fresh `feature-dev:code-reviewer` (or `claude-caliper:task-reviewer` if that's the orchestrator's chosen reviewer agent) with NO implementation bias. Reviewer reads the spec + all source + all tests, comments on bugs / spec gaps / style.

- [ ] **Step 6a: Dispatch the code-reviewer agent** with this prompt:

  > Review the electric-sheep-fold v0.1 implementation against the spec at
  > `docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md`.
  >
  > Source: `src/electric_sheep_fold/{layout,manifest,fetch,cli}.py`,
  > `src/electric_sheep_fold/data/ATTRIBUTION.md`.
  > Tests: `tests/test_{layout,manifest,fetch,cli}.py`.
  > Docs: `README.md`, `VISION.md`, `ROADMAP.md`, `CHANGELOG.md`, `BACKLOG.md`,
  > `CLAUDE.md`.
  >
  > Check specifically:
  > 1. **Politeness invariants** — does the code preserve "skips cost zero sleep"?
  > 2. **Sticky 404 invariant** — once an id is in `missing.txt`, is there any
  >    path that re-probes it?
  > 3. **Atomic writes** — is there any state where a partial `.flam3` could exist
  >    at the final path after Ctrl-C?
  > 4. **License obligations** — is `ATTRIBUTION.md` actually copied into the
  >    corpus on first fetch? Does the file content match the ES license terms?
  > 5. **Test coverage** — does each state-machine branch have at least one test?
  > 6. **Type / signature consistency** — same names used the same way across
  >    modules?
  > 7. **No placeholders, no TODOs, no dead code.**
  >
  > Report any high-confidence issues. Do not nitpick formatting.

- [ ] **Step 6b: Address any critical issues** surfaced by the reviewer.

  For each critical issue:
  - Make the change inline (file Edit or Write).
  - Run `pytest -v` to confirm no regressions.
  - Commit with a clear `fix:` or `refactor:` message.

  Non-critical suggestions (style nits, doc polish) go to BACKLOG.md unless trivially fixed in passing.

- [ ] **Step 6c: Final test run.**

  ```bash
  pytest -v
  ```

  Expected: all tests pass; no real-network calls.

- [ ] **Step 6d: Commit any final adjustments** (if Step 6b made changes that
  weren't already committed individually):

  ```bash
  git status      # confirm clean
  ```

---

### Task 7: Real-server smoke test + user verify + FF-merge

**LEAD-INLINE.** This task issues live network calls at 20s cadence and gates on user sign-off; not appropriate for a subagent.

**Files:**
- Modify: `CHANGELOG.md` (mark v0.1.0 entry as shipped with today's date once verified)

- [ ] **Step 7a: Confirm clean working tree on `feature/v0.1-bootstrap`.**

  ```bash
  git status
  git log --oneline -10
  ```

  Expected: clean tree, commits visible from Tasks 1–5 (and any from Task 6).

- [ ] **Step 7b: Install in dev mode + run a real-server smoke fetch.**

  ```bash
  rm -rf corpus/                                 # ensure first-run path exercised
  electric-sheep-fold fetch 100..105
  ```

  Expected behavior:
  - Output begins with a log message about writing `ATTRIBUTION.md` to `corpus/`.
  - ~5 GET requests at 20s intervals (~100s wall-clock total).
  - Each `200` triggers a `downloaded 248.NNNNN` log line.
  - Final summary: `248: N downloaded · M newly missing · 0 skip-local · 0 skip-known-missing · 0 transient errors` where N + M == 5.

- [ ] **Step 7c: Verify the corpus contents.**

  ```bash
  ls corpus/
  ls corpus/248/
  ls corpus/248/00xxx/
  cat corpus/ATTRIBUTION.md | head -10
  cat corpus/248/missing.txt 2>/dev/null || echo "(no missing.txt — all 5 downloaded)"
  ```

  Expected: `ATTRIBUTION.md` present at corpus root, `248/00xxx/` contains 0–5 `electricsheep.248.001*.flam3` files, `missing.txt` lists 0–5 ids depending on what the real server returned.

- [ ] **Step 7d: Re-run the same command to confirm idempotency.**

  ```bash
  electric-sheep-fold fetch 100..105
  ```

  Expected: completes in well under 1 second (no network) with output like
  `248: 0 downloaded · 0 newly missing · N skip-local · M skip-known-missing · 0 transient errors` where N + M == 5.

- [ ] **Step 7e: Hand off to user for verify.**

  Print clearly to the user:
  - The smoke-fetch happened, summarize stats.
  - Which sheep were downloaded (5-digit ids) and which were 404.
  - `ATTRIBUTION.md` is in place.
  - Test suite is all-green.
  - Ask for explicit OK to FF-merge `feature/v0.1-bootstrap` → `main`.

  **Wait for user approval before continuing to Step 7f.**

- [ ] **Step 7f: Update CHANGELOG with ship date, commit, FF-merge to main.**

  Replace `## v0.1.0 — unreleased` with `## v0.1.0 — 2026-05-DD` (today's date).

  ```bash
  git add CHANGELOG.md
  git commit -m "docs: mark v0.1.0 shipped"
  git checkout main
  git merge --ff-only feature/v0.1-bootstrap
  git log --oneline -10                 # confirm history
  ```

  Optional (only if user explicitly wants it): push branches to origin.

---

## Self-Review

### Spec coverage check

Walked the spec section by section against the plan:

- §1 Context / motivation → covered in VISION.md (Task 1g)
- §2 Goals / non-goals → reflected in implementation scope (Tasks 2–5) and out-of-scope items deferred to BACKLOG (Task 1j)
- §3 Scope of v0.1 → all enumerated items appear: `fetch` (Task 5), `status` (Task 5), corpus layout (Task 2 → bucket math), missing.txt (Task 3 → MissingSet), ATTRIBUTION.md (Tasks 1n, 4 → ensure_corpus_initialized), LICENSE (Task 1e), six docs (Task 1f–k), pytest suites (Tasks 2–5)
- §4 License & attribution → Task 1e (LICENSE), Task 1n (ATTRIBUTION.md template), Task 4 (auto-copy in ensure_corpus_initialized)
- §5 Architecture → Task 2 (layout), Task 3 (manifest), Task 4 (fetch with §5.3 state machine + bootstrap), Task 5 (cli)
- §6 On-disk layout → reflected in file paths throughout Tasks 1–5
- §7 Polite-request defaults → encoded in `fetch_range` defaults (Task 4) + CLI option defaults (Task 5) + USER_AGENT constant
- §8 Testing strategy → matches Tasks 2a, 3a, 4a, 5a test files
- §9 Six-doc bootstrap → Task 1f–k
- §10 Phase-1 deliverable order → matches Task 1–7 ordering
- §11 Roadmap → Task 1h (ROADMAP.md)
- §12 Backlog → Task 1j (BACKLOG.md)
- §13 Open small choices → defaulted per spec; flip-points documented in CLAUDE.md (Task 1k)

✅ No gaps.

### Placeholder scan

Searched the plan for forbidden patterns. None present:
- No "TBD", "TODO", "fill in later", "etc."
- Every code step has a complete code block.
- Every test step has the full test code.
- Every commit step has the actual `git add` + commit message.
- The one "external content" instruction (Step 1e LICENSE) gives the exact `curl` URL.

### Type / signature consistency

Cross-checked names used in later tasks against definitions in earlier ones:

- `bucket_for`, `flam3_filename`, `local_path`, `remote_url`, `BASE_URL_DEFAULT` — defined in Task 2, imported in Tasks 4 + 5 tests. ✓
- `MissingSet` with `load`, `contains`, `add`, `save_atomic`, `__len__` — defined in Task 3, used in Tasks 4 + 5 + tests. ✓
- `FetchStats` (fields: `downloaded`, `skip_local`, `skip_known_missing`, `newly_missing`, `transient_errors`) — defined in Task 4, used in Task 5 CLI summary line. ✓
- `ensure_corpus_initialized`, `fetch_range`, `make_client`, `USER_AGENT` — defined in Task 4, used in Task 5 CLI + Task 4 tests. ✓
- `_parse_range`, `app` — defined in Task 5, used in Task 5 tests. ✓

✅ Consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-19-electric-sheep-fold-v0.1.md`.** Two execution options:

**1. Subagent-Driven (recommended for Tasks 1–6)** — fresh subagent per task, lead reviews between tasks, fast iteration on pure-Python work. Task 7 (real-server smoke + user verify + FF-merge) is **lead-inline** regardless — it issues live 20s-cadence network calls and gates on user sign-off, neither of which suit a dispatched subagent.

**2. Inline Execution** — execute all tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

The user-default for Python (code-only) projects is hybrid: subagent-driven for pure logic/test work, lead-inline for tasks needing live network or background processes (per the user's plan execution mode rule). Tasks 1–6 fit cleanly into the subagent track; Task 7 sits at the lead.

**Which approach?**
