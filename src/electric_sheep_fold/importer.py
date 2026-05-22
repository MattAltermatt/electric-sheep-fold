"""Bulk import of existing local .flam3 files into the chunked layout."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.fetch import ensure_corpus_initialized
from electric_sheep_fold.layout import archive_url, chunk_for, remote_url
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import migrate_v0_1_if_needed

log = logging.getLogger(__name__)

_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")


@dataclass
class ImportStats:
    imported: int = 0
    skipped: int = 0
    sealed: int = 0


def import_dir(
    src: Path,
    corpus_root: Path,
    *,
    whole_gen: bool = False,
    gen: int | None = None,
) -> ImportStats:
    """Recursively import all canonical electricsheep.*.flam3 files from src.

    Default mode (whole_gen=False): routes each file to its 10k chunk's working
    dir via Chunk.add_flam3. After placing all files, sweeps each touched chunk
    and seals any whose range is now complete. Idempotent; existing files in
    the corpus are not overwritten.

    Whole-gen mode (whole_gen=True): all flam3s for `gen` go into a single
    chunk spanning [0, max_observed_id + 1). Also copies `src/_missing_404.txt`
    into `corpus/{gen}/missing.txt` so the chunk's range can complete. After
    import, seals the single chunk. `gen` is required; if omitted, inferred
    from filenames when src contains exactly one gen. Source URLs in MANIFEST
    point to the electricsheep.com archive (not v3d0).
    """
    ensure_corpus_initialized(corpus_root)
    if not src.exists():
        raise FileNotFoundError(f"import source not found: {src}")

    if whole_gen:
        if gen is None:
            gen = _infer_single_gen(src)
        return _import_whole_gen(src, corpus_root, gen)

    stats = ImportStats()
    gens_seen: set[int] = set()
    touched_chunks: dict[tuple[int, int, int], Chunk] = {}

    for path in src.rglob("electricsheep.*.flam3"):
        m = _FLAM3_RE.match(path.name)
        if not m:
            continue
        file_gen = int(m.group(1))
        sheep_id = int(m.group(2))
        gens_seen.add(file_gen)

        start, end = chunk_for(sheep_id)
        chunk_key = (file_gen, start, end)
        if chunk_key not in touched_chunks:
            touched_chunks[chunk_key] = Chunk(
                gen=file_gen, start=start, end=end, corpus_root=corpus_root,
            )
        chunk = touched_chunks[chunk_key]

        if chunk.contains_id(sheep_id):
            stats.skipped += 1
            continue

        chunk.add_flam3(sheep_id, path.read_bytes())
        stats.imported += 1

    # Run migration on every gen we touched (no-op if no v0.1 buckets present)
    for g in gens_seen:
        migrate_v0_1_if_needed(corpus_root, g)

    # Seal sweep
    for chunk in touched_chunks.values():
        missing = MissingSet(corpus_root / str(chunk.gen) / "missing.txt")
        missing.load()
        if chunk.status != "sealed" and chunk.is_range_complete(missing):
            chunk.seal(
                missing,
                source_url_for=lambda sid, g=chunk.gen: remote_url(g, sid),
                fetched_at_for=lambda sid: datetime.now(tz=timezone.utc),
            )
            stats.sealed += 1

    return stats


def _infer_single_gen(src: Path) -> int:
    """Return the unique gen number across all flam3 filenames in src.

    Raises ValueError if src has zero or multiple gens — caller must pass
    `gen=` explicitly in that case.
    """
    gens: set[int] = set()
    for path in src.rglob("electricsheep.*.flam3"):
        m = _FLAM3_RE.match(path.name)
        if m:
            gens.add(int(m.group(1)))
    if not gens:
        raise ValueError(
            f"cannot infer gen: no electricsheep.*.flam3 files found in {src}"
        )
    if len(gens) > 1:
        raise ValueError(
            f"cannot infer gen: src {src} contains multiple gens {sorted(gens)}; "
            "pass gen=N explicitly"
        )
    return gens.pop()


def _import_whole_gen(src: Path, corpus_root: Path, gen: int) -> ImportStats:
    """Single-chunk seal: all source flam3s + missing → one zip [0, max+1)."""
    stats = ImportStats()

    flam3_paths: list[tuple[int, Path]] = []
    for path in src.rglob("electricsheep.*.flam3"):
        m = _FLAM3_RE.match(path.name)
        if not m:
            continue
        if int(m.group(1)) != gen:
            continue
        flam3_paths.append((int(m.group(2)), path))

    src_missing_file = src / "_missing_404.txt"
    missing_ids: list[int] = []
    if src_missing_file.exists():
        for line in src_missing_file.read_text().splitlines():
            line = line.strip()
            if line and line.lstrip("-").isdigit():
                missing_ids.append(int(line))

    if not flam3_paths and not missing_ids:
        log.warning("nothing to import for gen %d from %s", gen, src)
        return stats

    max_id = max(
        max((sid for sid, _ in flam3_paths), default=-1),
        max(missing_ids, default=-1),
    )
    chunk = Chunk(gen=gen, start=0, end=max_id + 1, corpus_root=corpus_root)

    if chunk.status == "sealed":
        log.info(
            "gen %d already sealed as %s, skipping whole-gen import",
            gen, chunk.range_str,
        )
        return stats

    missing = MissingSet(corpus_root / str(gen) / "missing.txt")
    missing.load()
    for sid in missing_ids:
        missing.add(sid)
    missing.save_atomic()

    for sheep_id, path in flam3_paths:
        if chunk.contains_id(sheep_id):
            stats.skipped += 1
            continue
        chunk.add_flam3(sheep_id, path.read_bytes())
        stats.imported += 1

    missing.load()
    if chunk.is_range_complete(missing):
        chunk.seal(
            missing,
            source_url_for=lambda sid, g=gen: archive_url(g, sid),
            fetched_at_for=lambda sid: datetime.now(tz=timezone.utc),
        )
        stats.sealed += 1
        log.info(
            "sealed whole-gen %d as %s (%d sheep, %d missing)",
            gen, chunk.range_str, stats.imported, len(missing),
        )
    else:
        log.warning(
            "gen %d not range-complete after whole-gen import "
            "(max_id=%d, flam3s=%d, missing=%d); chunk left as working",
            gen, max_id, len(flam3_paths), len(missing),
        )

    return stats
