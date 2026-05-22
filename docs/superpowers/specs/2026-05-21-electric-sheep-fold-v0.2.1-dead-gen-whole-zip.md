# 🐑 electric-sheep-fold v0.2.1 — dead-gen whole-zip policy

**Date:** 2026-05-21 · **Status:** draft → user-approved 2026-05-21 · **Extends:**
[v0.2 chunked-zip spec](2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md)

A small but load-bearing addendum: gens preserved while alive keep the 10k-id
chunk layout from v0.2; gens that were already dead when we first touched them
get one whole-gen zip instead. The gen's biography is encoded in the chunk
shape itself.

---

## 🎯 1. Motivation

After the 8 dead flam3-bearing gens (165, 169, 191, 198, 242, 243, 244, 245)
finished preservation via `scripts/scrape_archive_gen.py`, applying the v0.2
10k-chunk rule verbatim would produce 25 zips across these gens — gen 244 alone
would shard into 9 zips, several of them >50% sticky-404 inside synthetic
decade boundaries.

The "chunk = decade of ids" abstraction earns its keep for live gens (247, 248)
whose id space is still growing — decades fill up over time and seal as the
sweep reaches them. For frozen data with no growth path, the decade boundary is
synthetic bookkeeping. Range-completion for a dead gen *is* whole-gen.

## 📐 2. The rule

> **A gen's chunk shape is fixed by its preservation state at first touch:**
>
> - **Live at preservation** (sourced via `v3d0.sheepserver.net` → `sheep-fold
>   fetch`) → **10k-id chunks**, sealed as ranges complete. Keeps this shape
>   forever, even after the upstream gen dies.
> - **Dead at preservation** (sourced via `electricsheep.com/archives` →
>   `scripts/scrape_archive_gen.py` → `sheep-fold import --whole-gen`) →
>   **one whole-gen zip** spanning `[0, max_observed_id + 1)`.

The biography is visible in the listing: a gen with multiple `NNNNN-NNNNN.zip`
files had a live history; a gen with a single `NNNNN-NNNNN.zip` was archived
from already-dead state.

Current gens by policy:

```
Live-preserved (10k chunks):
  247 — sourced via v3d0 (archive-side scrape was a fallback, not canonical)
  248 — actively growing via v3d0

Dead-preserved (whole-gen zip):
  165, 169, 191, 198, 242, 243, 244, 245
```

If 247 or 248 ever die, they keep their 10k chunks forever. No re-chunking.

## 🧩 3. What changes in the v0.2 spec

§5.5 `importer.py` gains a whole-gen mode and §5.7 `cli.py` gains a
`--whole-gen` flag.

### 3.1 `importer.py` — new whole-gen path

```python
def import_dir(
    src: Path,
    corpus_root: Path,
    *,
    whole_gen: bool = False,
    gen: int | None = None,
) -> ImportStats:
    """
    Default mode (whole_gen=False): unchanged from v0.2. Routes each file to
    its 10k chunk's working dir; seals chunks whose range completes.

    whole_gen mode: All flam3s for `gen` in `src` go into one chunk spanning
    [0, max_observed_id + 1). The scrape's `_missing_404.txt` is copied into
    `corpus/{gen}/missing.txt` first. After import, the chunk is sealed.
    `gen` is required; inferred from filenames if a single gen is present in
    `src`.
    """
```

Internally calls `_import_whole_gen(src, corpus_root, gen)`:

1. Scan `src` recursively for `electricsheep.{gen}.NNNNN.flam3`.
2. Read `src/_missing_404.txt`, collect missing ids.
3. `max_id = max(all observed ids across flam3s + missing entries)`.
4. Append the missing ids to `corpus/{gen}/missing.txt` (MissingSet, atomic save).
5. Create `Chunk(gen=gen, start=0, end=max_id + 1, corpus_root=corpus_root)`.
6. For each flam3 in `src`: `chunk.add_flam3(sheep_id, content)`.
7. Reload missing set; `chunk.seal(...)` with `source_url_for = archive_url(gen, id)`.

### 3.2 `archive_url(gen, sheep_id)` — new helper in `layout.py`

```python
ARCHIVE_BASE_URL = "https://electricsheep.com/archives"

def archive_url(gen: int, sheep_id: int) -> str:
    """Source URL for a dead-gen sheep, served by the archive's `spex` endpoint."""
    return f"{ARCHIVE_BASE_URL}/generation-{gen}/{sheep_id}/spex"
```

Used by whole-gen seal to populate `source_url` in MANIFEST.csv.
`remote_url(gen, id)` (v3d0) is unchanged and used by live-gen seals.

### 3.3 `cli.py` — `import` command

```sh
# Live gen: unchanged (10k chunks)
sheep-fold import ~/Downloads/old-sheep-corpus

# Dead gen: one whole-gen zip
sheep-fold import corpus/_scrape-244/ --whole-gen
sheep-fold import corpus/_scrape-244/ --whole-gen --gen 244   # explicit
```

If `--whole-gen` is passed and `--gen` is omitted, the CLI infers the gen from
filenames; ambiguity (multiple gens in `src`) is a hard error.

## 🪨 4. Invariants preserved

- **Range-completion is still the seal trigger.** For whole-gen mode, the range
  IS `[0, max_id + 1)`; sealing only happens when every id in that range is
  either present or in `missing.txt`.
- **Sealed-immutable.** A whole-gen zip is just a chunk with a wide range; it's
  frozen on seal like any other.
- **`NNNNN-NNNNN.zip` naming.** A whole-gen zip is named for its actual span,
  e.g. `00000-86475.zip` for gen 244. Looks chunk-shaped because it IS a chunk
  — just one chunk covering the gen.
- **MANIFEST.csv schema.** Unchanged. Whole-gen MANIFEST.csv has one row per
  flam3, with `source_url` pointing to the archive.
- **Atomic seal.** Same `.tmp` + `os.replace` pattern.

## 🚫 5. Out of scope

- Auto-detection of dead-vs-live. The policy is a human judgment about gen
  state at preservation; the `--whole-gen` flag is the explicit declaration.
- Re-chunking a previously-sealed gen. Once sealed, the chunk shape is frozen.
  Reseal is still a backlog item from v0.2 if the schema needs to evolve.
- Mixed-mode gens. A gen is either chunked-as-live OR sealed-as-whole; no
  hybrid layouts.

## 🧪 6. Tests

- `test_importer.py` — new scenario: synthetic scrape dir (flam3s with gaps +
  `_missing_404.txt`) → `import_dir(..., whole_gen=True, gen=N)` → assert
  single `00000-NNNNN.zip`, MANIFEST row count, `source_url` points at archive,
  `corpus/{gen}/missing.txt` populated, range-complete.
- `test_layout.py` — `archive_url` happy-path.
- `test_cli.py` — `--whole-gen` flag plumbing + gen inference.

## 📚 7. Doc updates

- `CLAUDE.md` — chunk-size invariant amended to mention the live/dead split.
- `README.md` — quickstart adds a one-line note about `--whole-gen` for dead
  gens.
- `CHANGELOG.md` — v0.2.1 entry on FF-merge.
