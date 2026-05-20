# 🐑 electric-sheep-fold v0.2 — design

**Date:** 2026-05-20 · **Status:** draft → user review · **Predecessor:** [v0.1 design](2026-05-19-electric-sheep-fold-v0.1-design.md)

Storage refactor + ergonomics. Per-thousand bucket dirs become sealed-immutable `.zip`
chunks of 10k id-range each, with a per-chunk `MANIFEST.csv` carrying enough
structured metadata to feed a future pyr3-facing index. Two new CLI commands
(`fetch-all`, `import`) put the chunked layout to work.

---

## 🎯 1. Context & motivation

v0.1 shipped a polite per-file mirror. Two pressures motivate v0.2:

1. **Filesystem hygiene.** ~8k `.flam3` files per gen (gen 248) × N gens × bucket
   subdirs = inode pressure + awkward distribution. Bundles win on every axis that
   matters: storage compactness, mirrorability, fewer-things-to-track.
2. **Pyr3-facing index foundation.** pyr3 (sibling renderer) needs to query the
   corpus to find structurally interesting flames for parity testing — different
   xform counts, variation sets, color modes. v0.3 will ship the corpus-wide
   aggregated index; v0.2 lays the seam by extracting per-chunk metadata at seal
   time.

The user-stated bar for the storage format: **humans must be able to open bundles
without installing anything** on stock macOS Finder / Windows 10/11 Explorer.
Dueling-agent research (`tar.zst` vs `.zip` vs `.tar.gz`) found only `.zip` passes
that bar on every modern consumer OS GUI.

## 🧭 2. Goals & non-goals

### Goals (v0.2)

1. **Chunked `.zip` storage** at 10k id-range per chunk
   (`corpus/{gen}/{NNNNN-NNNNN}.zip`), sealed-immutable once a chunk's range is
   fully probed.
2. **Working-directory lifecycle** during fetch: per-file atomic writes into a
   scratch dir; one-shot seal to `.zip` when the range completes.
3. **Per-chunk `MANIFEST.csv`** inside each sealed zip, carrying enough metadata
   for v0.3's pyr3 index to aggregate without re-reading every flam3.
4. **Auto-fetch** the entire range of a gen: `electric-sheep-fold fetch-all 248`.
5. **Import** existing local `.flam3` files (anywhere) into the chunked layout:
   `electric-sheep-fold import <src-dir>`.
6. **Automatic v0.1→v0.2 migration** of existing local corpora on first v0.2 fetch.
7. **All v0.1 invariants preserved**: politeness, sticky-404s, skip-without-network,
   atomic writes, filename preservation, license/attribution obligations.

### Non-goals (v0.2)

- ❌ **Corpus-wide aggregated index** (`corpus/{gen}/index.{csv,db}` summarizing all
  chunks) — that's v0.3, designed with pyr3's actual query patterns in scope.
- ❌ **Search interface** — also v0.3.
- ❌ **zstd / 7z / tar.gz** — `.zip` is locked per the human-access bar.
- ❌ **Re-extracting metadata from sealed zips** — extraction happens only at seal
  time. Re-seal a chunk if its `MANIFEST.csv` schema needs to grow.
- ❌ **Removing the `.flam3` files from sealed zips after read** — the zip IS the
  canonical store; no cache extraction directory.

## 🗺️ 3. Scope of v0.2

What ships:

- `electric-sheep-fold fetch START..END [--gen 248] [--delay 20] [--jitter 5]` — same UX,
  internally writes to chunked working dirs and seals on range completion.
- `electric-sheep-fold fetch-all [--gen 248] [--upper 50000]` — fetch the entire id range
  in one polite session (resumable; idempotent).
- `electric-sheep-fold import <src-dir> [--gen-from-filename]` — recursively find
  `electricsheep.*.flam3` files in `<src-dir>` and place them into the chunked
  layout. Sealed where range complete.
- `electric-sheep-fold status [--gen 248]` — extended to show chunk states (N sealed, M
  working, K empty).
- `electric-sheep-fold seal [--gen 248] [--chunk NNNNN-NNNNN]` — manual force-seal of a
  working chunk whose range isn't fully probed yet (escape hatch for partial-
  range fetches).
- On-disk layout: `corpus/{gen}/{NNNNN-NNNNN}.zip` (sealed) +
  `corpus/{gen}/{NNNNN-NNNNN}/` (working dirs) + `corpus/{gen}/missing.txt`
  (gen-wide, unchanged) + `corpus/{gen}/index.csv` (chunk overview).
- Per-chunk `MANIFEST.csv` as the first entry inside every sealed zip.
- pytest suites updated for new layout; new suite for chunks module; new tests for
  fetch-all, import, migration.

## 🧩 4. The MANIFEST.csv seam (load-bearing)

This is the "ship the seam now, evolve the trigger later" piece. v0.2 extracts
per-chunk metadata at seal time; v0.3 aggregates chunk manifests into the
corpus-wide pyr3 index, no re-read of sealed zips needed.

### 4.1 Schema (one row per `.flam3` in the chunk)

| Column | Type | Source | Notes |
|---|---|---|---|
| `id` | int | filename | e.g. `100` for `electricsheep.248.00100.flam3` |
| `sha256` | hex str (64) | content | integrity / dedup / v0.3 verify |
| `file_size_bytes` | int | content len | cheap proxy for "complex flame" |
| `fetched_at` | ISO-8601 UTC | clock | provenance |
| `source_url` | str | computed | the `remote_url(gen, id)` it was fetched from |
| `name` | str | `<flame name=...>` | flame display name (often empty) |
| `nick` | str | `<flame nick=...>` | designer handle; presence = human-designed |
| `url` | str | `<flame url=...>` | designer's URL |
| `xform_count` | int | count of `<xform>` | structural complexity signal |
| `final_xform` | bool | `<finalxform>` present | rendering pathway flag |
| `variations` | semicolon-joined str | unique variation names across all xforms | e.g. `linear;julia;spherical` |

**XML parsing**: Python stdlib `xml.etree.ElementTree`. The flam3 root is `<flame>`;
variations live as attributes on each `<xform>` (e.g. `<xform linear="0.5"
julia="0.3" .../>`) — extract attribute names from each xform, dedup across the
flame, sort, join with `;`.

**Robustness**: a `.flam3` that fails XML parse → log a warning, write the row with
`xform_count=-1, variations=""`, but still include the file in the zip (the genome
matters even if our metadata pass tripped).

### 4.2 Why these fields specifically

- 🪨 `id`, `sha256`, `file_size_bytes`, `fetched_at`, `source_url` — identity +
  integrity + provenance. Mandatory.
- 🪨 `xform_count`, `final_xform`, `variations` — the **pyr3-relevant structural
  signals**. Coverage of different xform counts and variation combinations is
  exactly what parity testing wants.
- 🎨 `name`, `nick`, `url` — designer attribution + the CC BY / CC BY-NC split
  (algorithm-bred sheep have no `nick`; human-designed do). Subsumes the
  `attribution.csv extractor` BACKLOG entry — same data, persisted earlier.

**Deferred to v0.3 (intentionally not in the seam):**

- Palette hash, palette size — palette structure varies less and pyr3 can compute
  on demand.
- Render hints (`size_w`, `size_h`, `quality`, `zoom`, `oversample`,
  `interpolation`) — pyr3 reads these directly from the `.flam3` at render time;
  no need to mirror in the manifest.

### 4.3 Schema evolution

If v0.3 needs additional fields, the path forward is a **re-seal pass**: extract
each sealed zip into a working dir, drop in the new `MANIFEST.csv` with extended
columns, re-zip. CLI verb: `electric-sheep-fold reseal --gen 248 [--chunk N]`. Not built in
v0.2; mentioned here so the seam evolution story is clear.

## 🧱 5. Architecture

Modules under `src/electric_sheep_fold/`. New module marked 🆕; revised marked ✏️.

| Module | Purpose | Key surface |
|---|---|---|
| `layout.py` ✏️ | Pure path / URL math, **chunk-aware** | `chunk_for(id)`, `chunk_range_str(start,end)`, `working_path(...)`, `sealed_zip_path(...)`, `remote_url(...)`, `flam3_filename(...)` |
| `manifest.py` | MissingSet — **unchanged from v0.1** | as v0.1 |
| `chunks.py` 🆕 | Chunk lifecycle: working-dir, seal, MANIFEST.csv, read | `Chunk(gen, start, end, root)`, `.status`, `.add_flam3(id, content)`, `.read_flam3(id)`, `.is_range_complete(missing)`, `.seal(missing)` |
| `extract.py` 🆕 | Pure XML → metadata-row | `extract_metadata(content: bytes, id: int, source_url: str, fetched_at: datetime) -> dict` |
| `fetch.py` ✏️ | Polite loop, **writes via Chunk**, seals on boundary cross | `fetch_range(...)`, `fetch_all(...)`, `make_client()` |
| `importer.py` 🆕 | Bulk import of existing local `.flam3`s | `import_dir(src: Path, corpus_root: Path) -> ImportStats` |
| `migration.py` 🆕 | One-time v0.1 bucket → v0.2 chunk migration | `migrate_v0_1_if_needed(corpus_root, gen)` |
| `cli.py` ✏️ | Typer entrypoint, new commands | `fetch`, `fetch-all`, `import`, `status`, `seal` |

**Module boundaries:**

- `layout` + `extract` + `manifest` are **pure** (no I/O outside MissingSet's
  file ops). Trivially unit-testable.
- `chunks` is **I/O-heavy but state-machine pure** (Chunk.seal is deterministic
  given working dir contents + missing set).
- `fetch`, `importer`, `migration` orchestrate I/O + chunks; testable via
  filesystem fixtures (`tmp_path`) and `httpx.MockTransport`.
- `cli` stays thin.

### 5.1 `layout.py` — chunk math (v0.2 changes)

```python
CHUNK_SIZE = 10_000

def chunk_for(sheep_id: int) -> tuple[int, int]:
    """Return (start, end) of the 10k chunk containing sheep_id.

    0 → (0, 10000), 9999 → (0, 10000), 10000 → (10000, 20000), 40700 → (40000, 50000).
    """

def chunk_range_str(start: int, end: int) -> str:
    """'00000-09999' for chunk (0, 10000) — used for filenames and dir names."""
    return f"{start:05d}-{end-1:05d}"

def working_path(gen: int, sheep_id: int, corpus_root: Path) -> Path:
    """Where a flam3 lives during its chunk's WORKING phase."""
    start, end = chunk_for(sheep_id)
    return corpus_root / str(gen) / chunk_range_str(start, end) / flam3_filename(gen, sheep_id)

def sealed_zip_path(gen: int, chunk_start: int, chunk_end: int, corpus_root: Path) -> Path:
    return corpus_root / str(gen) / f"{chunk_range_str(chunk_start, chunk_end)}.zip"
```

Removed: `bucket_for`, the old `local_path` (replaced by `working_path` +
`sealed_zip_path`). `flam3_filename` and `remote_url` unchanged.

### 5.2 `chunks.py` — the Chunk class

```python
class Chunk:
    """A single 10k id-range chunk for one generation."""

    gen: int
    start: int     # inclusive
    end: int       # exclusive
    corpus_root: Path

    @property
    def range_str(self) -> str: ...                # "00000-09999"
    @property
    def zip_path(self) -> Path: ...                # sealed artifact path
    @property
    def working_dir(self) -> Path: ...             # scratch path
    @property
    def status(self) -> Literal["sealed", "working", "empty"]: ...

    def contains_id(self, sheep_id: int) -> bool:
        """Sheep present in working dir OR sealed zip."""

    def read_flam3(self, sheep_id: int) -> bytes:
        """Read from sealed zip if sealed; else from working dir. Raises KeyError if absent."""

    def add_flam3(self, sheep_id: int, content: bytes) -> None:
        """Atomic write into working dir (tmp + os.replace). Creates working_dir."""

    def is_range_complete(self, missing: MissingSet) -> bool:
        """True if every id in [start, end) is in working dir OR missing.contains(id)."""

    def seal(self, missing: MissingSet, *, source_url_for, fetched_at_for) -> None:
        """
        1. Build MANIFEST.csv from working dir contents (via extract.extract_metadata).
        2. Write zip to {zip_path}.tmp: MANIFEST.csv first entry, then all flam3s, DEFLATE level 9.
        3. os.replace(.tmp, zip_path) — atomic.
        4. shutil.rmtree(working_dir) — clean up.
        """
```

Reseal (for v0.3 schema evolution) is deferred to BACKLOG — no stub in v0.2.

**Atomicity**: `seal()` builds the zip at `{zip_path}.tmp` and atomically renames.
SIGKILL mid-seal leaves the working dir intact + an orphan `.tmp` that's overwritten
on the next seal attempt. The chunk's data is never lost.

**fetched_at provenance**: passed in as a callable `fetched_at_for(sheep_id) -> datetime`
so the caller controls how it's sourced (filesystem mtime for migrated v0.1 files,
clock-now for freshly-fetched, etc.).

### 5.3 `extract.py` — XML → metadata row

```python
def extract_metadata(
    content: bytes,
    *,
    sheep_id: int,
    source_url: str,
    fetched_at: datetime,
) -> dict[str, str]:
    """Parse flam3 XML; return a row dict matching MANIFEST.csv columns.

    Robust to parse failures: returns the row with xform_count=-1, variations=""
    when XML is malformed (logs a warning). Always includes sha256 + file_size.
    """
```

Pure function, no I/O. Unit tests cover: happy path, malformed XML, missing
attributes, multiple xforms with overlapping variations, final-xform presence.

### 5.4 `fetch.py` — chunk-aware orchestration

```python
def fetch_range(gen, start, end, corpus_root, client, delay=20, jitter=5, timeout=30) -> FetchStats:
    """v0.2 behavior:
    1. Migrate v0.1 layout if present (one-shot, idempotent).
    2. Load missing.txt.
    3. For each id in [start, end):
       - Determine its chunk.
       - If sealed-zip contains id → skip-local, no network.
       - Else if working_dir contains id → skip-local, no network.
       - Else if missing.contains(id) → skip-known-missing, no network.
       - Else GET; 200 → chunk.add_flam3 + maybe seal; 404 → missing.add + save; 5xx → transient.
       - Sleep only after a real request.
       - On chunk boundary cross (id == chunk.end - 1 and range now complete) → chunk.seal().
    4. After loop: attempt to seal every touched chunk whose range is now complete.
    """

def fetch_all(gen, corpus_root, client, *, upper=50_000, delay=20, jitter=5) -> FetchStats:
    """Wrapper: fetch_range(gen, 0, upper, ...). Sticky-404 fills any tail of empty ids."""
```

The "sealed zip contains id" check is the **only** v0.2-specific bit of read
overhead during fetch. It's cheap: `zipfile.ZipFile.namelist()` is O(1) after the
central-directory load; or test membership via `try ZipFile.getinfo(name)`. We cache
the open `ZipFile` per chunk during the loop to amortize.

### 5.5 `importer.py` — bulk import

```python
def import_dir(src: Path, corpus_root: Path) -> ImportStats:
    """
    Recursively find files matching electricsheep.{gen}.{id:05d}.flam3 in src.
    For each:
      - Determine gen, id, chunk.
      - Skip if already in corpus (sealed-zip or working-dir hit).
      - Read bytes, write via Chunk.add_flam3.
    After all files processed:
      - For every chunk touched, if is_range_complete(missing) → seal.
    Idempotent.
    """
```

Use case: a user has a directory of `.flam3`s from elsewhere (an old v0.1 corpus, a
backup drive, a Sheep-Pack download). Drop them in; electric-sheep-fold integrates them
into the chunked layout.

### 5.6 `migration.py` — v0.1 auto-migration

```python
def migrate_v0_1_if_needed(corpus_root: Path, gen: int) -> bool:
    """If corpus/{gen}/NNxxx/ dirs exist (v0.1 bucket layout):
      1. For each bucket, for each electricsheep.*.flam3 inside:
         - chunks[chunk_for(id)].add_flam3(id, content)
      2. For each chunk touched, if is_range_complete(missing) → seal.
      3. shutil.rmtree() the empty NNxxx/ buckets.
    Returns True if migration ran, False if nothing to migrate. Idempotent."""
```

Called from `fetch_range` and `import_dir` before any new writes. Idempotent: runs
once, leaves no v0.1 buckets, subsequent calls no-op.

### 5.7 `cli.py` — new commands

```sh
# Same as v0.1
electric-sheep-fold fetch 0..2000

# NEW: auto-fetch the whole gen
electric-sheep-fold fetch-all                          # gen 248, ids 0..50000
electric-sheep-fold fetch-all --gen 249 --upper 80000

# NEW: import existing local flames
electric-sheep-fold import ~/Downloads/old-sheep-corpus
electric-sheep-fold import /Volumes/Backup/corpus

# NEW: status shows chunk-level state
electric-sheep-fold status
# 248: 4 sealed chunks · 1 working · 1 empty · 8341 sheep total · 31659 known-missing

# NEW: force-seal an incomplete chunk
electric-sheep-fold seal --chunk 20000-29999
```

### 5.8 The `corpus/{gen}/index.csv` (chunk overview)

One row per chunk. Tracks status without having to scan `*.zip` + working dirs.
**Per-gen, not corpus-wide.** (Corpus-wide aggregation is v0.3.)

| Column | Type | Notes |
|---|---|---|
| `chunk_range` | str | "00000-09999" |
| `status` | str | `sealed` \| `working` \| `empty` |
| `count_present` | int | files in chunk (sealed entries or working files) |
| `count_missing` | int | ids in this range present in missing.txt |
| `sealed_at` | ISO-8601 or empty | timestamp of seal, empty if not yet sealed |

Updated atomically (tmp + os.replace) on every chunk state change. Cheap (one row
per chunk, ~5 rows per current gen).

## 🗂️ 6. On-disk layout (v0.2)

```
electric-sheep-fold/
├── (all the v0.1 docs + tooling — unchanged)
├── src/electric_sheep_fold/
│   ├── __init__.py            (__version__ = "0.2.0")
│   ├── cli.py                 ✏️ new commands
│   ├── chunks.py              🆕
│   ├── extract.py             🆕
│   ├── fetch.py               ✏️ chunk-aware
│   ├── importer.py            🆕
│   ├── layout.py              ✏️ chunk_for replaces bucket_for
│   ├── manifest.py            (unchanged)
│   ├── migration.py           🆕
│   └── data/
│       └── ATTRIBUTION.md     (unchanged)
├── tests/
│   ├── test_chunks.py         🆕
│   ├── test_extract.py        🆕
│   ├── test_fetch.py          ✏️ updated for new layout
│   ├── test_importer.py       🆕
│   ├── test_layout.py         ✏️ chunk math
│   ├── test_manifest.py       (unchanged)
│   └── test_migration.py      🆕
└── corpus/                    (gitignored)
    ├── ATTRIBUTION.md
    └── 248/
        ├── index.csv          🆕 chunk overview
        ├── missing.txt
        ├── 00000-09999.zip    🆕 sealed chunk
        │   ├── MANIFEST.csv
        │   ├── electricsheep.248.00100.flam3
        │   ├── electricsheep.248.00103.flam3
        │   └── ...
        ├── 10000-19999.zip    🆕 sealed chunk
        ├── 20000-29999/       🆕 working dir for in-progress chunk
        │   ├── electricsheep.248.20042.flam3
        │   └── electricsheep.248.20103.flam3
        └── 30000-39999/       🆕 working dir
            └── ...
```

**v0.1 bucket dirs (`00xxx/`…`40xxx/`) no longer exist.** Auto-migration deletes
them on first v0.2 fetch.

## 🤝 7. Polite-request defaults (unchanged from v0.1)

All v0.1 politeness invariants carry forward verbatim. Chunking is purely a
storage concern; the cadence, sequentiality, User-Agent, sticky-404, and
skip-without-network rules are untouched.

| Setting | Default | Why |
|---|---|---|
| Delay | 20s | unchanged |
| Jitter | ±5s | unchanged |
| Concurrency | 1 | unchanged — sequential only |
| User-Agent | `electric-sheep-fold/0.2 (companion to pyr3; ...)` | version bump only |
| Sticky 404 | gen-wide `missing.txt` | unchanged |

## 🧪 8. Testing strategy

- **`test_layout.py`** — new `chunk_for` boundary cases, `chunk_range_str`,
  `working_path`, `sealed_zip_path`. Existing `flam3_filename` / `remote_url`
  tests carry forward.
- **`test_extract.py`** — XML parsing happy path, malformed XML graceful
  degradation, attribute extraction (name/nick/url), xform_count, variations
  dedup+sort, final_xform detection. All pure.
- **`test_chunks.py`** — Chunk lifecycle: empty → working → sealed. seal() writes
  MANIFEST.csv as first entry; preserves all flam3s; deletes working dir.
  is_range_complete logic. read_flam3 from both states.
- **`test_fetch.py`** — updated v0.1 tests for new layout; new tests for chunk
  boundary seal trigger, end-of-fetch seal sweep, sealed-zip cache hit.
- **`test_importer.py`** — flat-dir import, nested-dir import, partial-overlap
  with existing corpus, seal-after-complete-range.
- **`test_migration.py`** — v0.1 bucket layout → v0.2 chunks; partial v0.1 corpus;
  idempotency (run twice, second is no-op).
- **`test_cli.py`** — updated `status` output; `fetch-all` smoke; `import` smoke;
  `seal --chunk` smoke.
- **`test_manifest.py`** — unchanged.

All pure / mock-driven, no real network in CI. Real-server smoke test is one
manual `electric-sheep-fold fetch 105..110` after install to confirm wire compatibility.

## 🔄 9. Migration & upgrade story

### v0.1 → v0.2

**Automatic, one-shot, idempotent.** First time `fetch` (or `import`) runs against a
v0.1 corpus, the migration module:

1. Detects v0.1 bucket dirs (`corpus/{gen}/NNxxx/`).
2. Walks each bucket, groups files by v0.2 chunk range, calls
   `Chunk.add_flam3(id, content)` for each.
3. For every touched chunk, if `is_range_complete(missing) → seal()`.
4. Deletes the now-empty v0.1 bucket dirs.

The v0.1 `corpus/{gen}/missing.txt` is preserved verbatim — sticky-404 invariant
carries over without translation. Chunks where the range is partially probed (most
of them, since the v0.1 corpus rarely covers a complete 10k range) end up as
**working chunks** until the user fetches the remaining ids.

### Wire-format compatibility

No change to the ES server interaction — `remote_url(gen, id)` and the
20s-polite-sequential cadence are unchanged. Server-side, v0.2 is
indistinguishable from v0.1.

### Tool-version coexistence

v0.1 and v0.2 don't coexist gracefully against the same corpus directory: v0.1
won't see files inside `.zip` chunks. If a user pins v0.1 after running v0.2,
they'll see "0 downloaded" for ids actually present in sealed chunks. **Mitigation:**
v0.2's `pyproject.toml` bumps version to `0.2.0`; the version is surfaced in the
User-Agent; install via `pip install -e .` always picks up the local checkout.
Cross-version mixing isn't supported and isn't on the roadmap.

## 📚 10. Doc updates required (ship dependencies)

- **`CHANGELOG.md`** — v0.2.0 entry (initially "unreleased", marked with date on
  FF-merge).
- **`README.md`** — Quickstart updated: `fetch-all`, `import`, mention chunked
  `.zip` storage briefly.
- **`VISION.md`** — Add a "What v0.2 changes" paragraph: per-file → chunked
  bundles; storage hygiene; seam for pyr3-facing index.
- **`ROADMAP.md`** — Phase shape evolves (see §12).
- **`BACKLOG.md`** — Remove the now-subsumed `attribution.csv extractor` entry
  (its data is captured in MANIFEST.csv).
- **`CLAUDE.md`** — Add chunked-storage invariants (chunk size = 10k, seal is
  range-completion-triggered, sealed zips are immutable, MANIFEST.csv is the
  seam for v0.3 aggregation).

## 🛠️ 11. Build sequence (Phase 2, deliverable order)

Concrete order; a full task-by-task plan lives in
`docs/superpowers/plans/2026-05-20-electric-sheep-fold-v0.2.md` (drafted alongside this
spec). Sketch:

1. Branch + version bump + doc shells.
2. `layout.py` chunk math + tests.
3. `extract.py` + tests (pure XML parsing).
4. `chunks.py` + tests (lifecycle: working → sealed via seal()).
5. `migration.py` + tests (v0.1 bucket → v0.2 chunk).
6. `fetch.py` rewrite for chunk-aware + tests updated.
7. `importer.py` + tests.
8. `cli.py` new commands + tests.
9. Doc updates (README/VISION/ROADMAP/CHANGELOG/BACKLOG/CLAUDE).
10. Code review (fresh reviewer).
11. Real-server smoke (`electric-sheep-fold fetch 105..110`) + idempotency + user verify.
12. FF-merge to main.

## 🔮 12. Roadmap reshape

Pre-v0.2 ROADMAP had Phase 2 = `verify` subcommand, Phase 3 = pyr3 integration.
v0.2 + v0.3 reshapes this:

- **Phase 1** ✅ v0.1 shipped (2026-05-19)
- **Phase 2** 🛠️ **v0.2 — chunked-zip storage + ergonomics** *(this spec)*
- **Phase 3** 🔮 **v0.3 — pyr3-facing index/search**
  - Aggregate per-chunk MANIFEST.csv into corpus-wide index
  - Query interface (filter by xform_count, variations, has-nick, etc.)
  - Subsumes the old "verify" phase (sha256 in MANIFEST.csv enables verify
    trivially as a query)
  - Subsumes the BACKLOG `attribution.csv extractor`
- **Phase 4** 🔥 **pyr3 actually integrates** — pyr3 reads `corpus/{gen}/` (sealed
  zips + index) as parity-test source.
- **Phase 5** 🌐 **public corpus repo (optional)** — chunked zips are the natural
  distribution unit; one repo with one `.zip` per chunk, README pointing at
  `ATTRIBUTION.md`.
- **Phase 6** 🐑 **additional generations** — `--gen 249` etc.

## 🗃️ 13. Backlog (post-v0.2 unphased)

- **`reseal --gen N`** — re-extract + re-seal all chunks with the current schema.
  Needed when v0.3+ extends MANIFEST.csv columns.
- **`prune --gen N --id RANGE`** — remove sheep from a sealed chunk (re-seal
  pathway). Rare use case; could come up if a corrupt flam3 is discovered.
- **Range-discovery from server index HTML** — instead of `--upper 50000`, parse
  `/gen/N/` HTML once to determine the true upper bound. Optimization; current
  default works fine.
- **Parallel chunk seal** — sealing is CPU-bound (deflate + sha256); could run
  concurrently across chunks. Almost certainly never needed (seals are seconds
  apart at 20s cadence).
- **Index-on-the-fly during fetch** — write `MANIFEST.csv` rows incrementally
  during fetch, not just at seal time. Would survive partial-chunk crashes
  cleanly. Not in v0.2 because seal-time extraction is simpler and adequate.

## 🧷 14. Open small choices (defaulted, easy to flip)

| Choice | Default | Flip via |
|---|---|---|
| Chunk size | 10,000 ids | `CHUNK_SIZE` constant in `layout.py` |
| Zip compression | DEFLATE level 9 | `chunks.py` seal() argument |
| `MANIFEST.csv` placement | first entry inside the zip | could be sidecar `.csv` next to zip — flip if v0.3 wants cheaper aggregation without opening zips |
| `fetch-all` upper bound | 50,000 | `--upper` CLI flag |
| Importer behavior on duplicates | skip silently | could log; could fail-loud; could overwrite |
| Migration trigger | automatic on first v0.2 fetch | could require explicit `electric-sheep-fold migrate` if user wants control |
| v0.1 missing.txt → v0.2 missing.txt | preserved verbatim | n/a — invariant |
| MANIFEST.csv schema | columns defined in §4.1 | extend via `reseal`; never break columns once shipped |
