"""Bulk import of existing local .flam3 files into the chunked layout."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.fetch import ensure_corpus_initialized
from electric_sheep_fold.layout import chunk_for, remote_url
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import migrate_v0_1_if_needed

log = logging.getLogger(__name__)

_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")


@dataclass
class ImportStats:
    imported: int = 0
    skipped: int = 0
    sealed: int = 0


def import_dir(src: Path, corpus_root: Path) -> ImportStats:
    """Recursively import all canonical electricsheep.*.flam3 files from src.

    Routes each file to its chunk's working dir via Chunk.add_flam3. After
    placing all files, sweeps each touched chunk and seals any whose range is
    now complete. Idempotent; existing files in the corpus are not overwritten.
    """
    ensure_corpus_initialized(corpus_root)
    if not src.exists():
        raise FileNotFoundError(f"import source not found: {src}")

    stats = ImportStats()
    gens_seen: set[int] = set()
    touched_chunks: dict[tuple[int, int, int], Chunk] = {}

    for path in src.rglob("electricsheep.*.flam3"):
        m = _FLAM3_RE.match(path.name)
        if not m:
            continue
        gen = int(m.group(1))
        sheep_id = int(m.group(2))
        gens_seen.add(gen)

        start, end = chunk_for(sheep_id)
        chunk_key = (gen, start, end)
        if chunk_key not in touched_chunks:
            touched_chunks[chunk_key] = Chunk(
                gen=gen, start=start, end=end, corpus_root=corpus_root,
            )
        chunk = touched_chunks[chunk_key]

        if chunk.contains_id(sheep_id):
            stats.skipped += 1
            continue

        chunk.add_flam3(sheep_id, path.read_bytes())
        stats.imported += 1

    # Run migration on every gen we touched (no-op if no v0.1 buckets present)
    for gen in gens_seen:
        migrate_v0_1_if_needed(corpus_root, gen)

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
