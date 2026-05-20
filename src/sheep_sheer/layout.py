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
