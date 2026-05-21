"""Pure path / URL math for electric-sheep-fold. No I/O. (v0.2 chunks.)"""
from __future__ import annotations

from pathlib import Path

BASE_URL_DEFAULT = "http://v3d0.sheepserver.net"
CHUNK_SIZE = 10_000


def chunk_for(sheep_id: int) -> tuple[int, int]:
    """Return (start, end) of the 10k chunk containing sheep_id, half-open.

    0 → (0, 10000), 9999 → (0, 10000), 10000 → (10000, 20000), 40700 → (40000, 50000).
    """
    if sheep_id < 0:
        raise ValueError(f"sheep_id must be non-negative, got {sheep_id}")
    start = (sheep_id // CHUNK_SIZE) * CHUNK_SIZE
    return start, start + CHUNK_SIZE


def chunk_range_str(start: int, end: int) -> str:
    """'00000-09999' for chunk (0, 10000) — used for filenames and dir names."""
    return f"{start:05d}-{end - 1:05d}"


def flam3_filename(gen: int, sheep_id: int) -> str:
    """Canonical filename — preserved verbatim per ES attribution scheme."""
    return f"electricsheep.{gen}.{sheep_id:05d}.flam3"


def working_path(gen: int, sheep_id: int, corpus_root: Path) -> Path:
    """Where a flam3 lives during its chunk's WORKING phase."""
    start, end = chunk_for(sheep_id)
    return (
        corpus_root
        / str(gen)
        / chunk_range_str(start, end)
        / flam3_filename(gen, sheep_id)
    )


def sealed_zip_path(
    gen: int, chunk_start: int, chunk_end: int, corpus_root: Path
) -> Path:
    """Path of the sealed .zip for a given chunk."""
    return corpus_root / str(gen) / f"{chunk_range_str(chunk_start, chunk_end)}.zip"


def remote_url(gen: int, sheep_id: int, base: str = BASE_URL_DEFAULT) -> str:
    """Source URL on the ES v3d0 server.

    Note: dir segment is NON-padded (matches what ES publishes:
    /gen/248/100/, not /gen/248/00100/).
    """
    return f"{base}/gen/{gen}/{sheep_id}/{flam3_filename(gen, sheep_id)}"
