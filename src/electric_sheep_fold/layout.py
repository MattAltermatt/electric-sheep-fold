"""Pure path / URL math for electric-sheep-fold. No I/O. (v0.3 loose corpus.)"""
from __future__ import annotations

from pathlib import Path

BASE_URL_DEFAULT = "http://v3d0.sheepserver.net"
ARCHIVE_BASE_URL = "https://electricsheep.com/archives"

# Live gens — actively served by v3d0.sheepserver.net. `fetch` / `fetch-all`
# refuse other gens to prevent accidental live-server probes for dead gens
# (those use the archive scraper + `import` flow instead). Add the next gen
# here when ES rolls over.
LIVE_GENS: frozenset[int] = frozenset({247, 248})


def flam3_filename(gen: int, sheep_id: int) -> str:
    """Canonical filename — preserved verbatim per ES attribution scheme."""
    return f"electricsheep.{gen}.{sheep_id:05d}.flam3"


def flam3_path(gen: int, sheep_id: int, corpus_root: Path) -> Path:
    """Where a flam3 lives in the v0.3 loose corpus: corpus/{gen}/electricsheep.{gen}.{id}.flam3."""
    return corpus_root / str(gen) / flam3_filename(gen, sheep_id)


def release_zip_path(gen: int, out_dir: Path) -> Path:
    """Path of the consumer-facing release artifact for one gen."""
    return out_dir / f"gen-{gen}.zip"


def remote_url(gen: int, sheep_id: int, base: str = BASE_URL_DEFAULT) -> str:
    """Source URL on the ES v3d0 server.

    Note: dir segment is NON-padded (matches what ES publishes:
    /gen/248/100/, not /gen/248/00100/).
    """
    return f"{base}/gen/{gen}/{sheep_id}/{flam3_filename(gen, sheep_id)}"


def archive_url(gen: int, sheep_id: int, base: str = ARCHIVE_BASE_URL) -> str:
    """Source URL for a dead-gen sheep, served by electricsheep.com `spex` endpoint."""
    return f"{base}/generation-{gen}/{sheep_id}/spex"
