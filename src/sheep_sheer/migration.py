"""One-time v0.1 bucket → v0.2 chunk migration."""
from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.layout import (
    CHUNK_SIZE,
    chunk_for,
    flam3_filename,
    remote_url,
)
from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)

_BUCKET_RE = re.compile(r"^(\d{2})xxx$")
_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")


def _list_v0_1_buckets(gen_root: Path) -> list[Path]:
    if not gen_root.exists():
        return []
    return sorted(
        p for p in gen_root.iterdir()
        if p.is_dir() and _BUCKET_RE.match(p.name)
    )


def migrate_v0_1_if_needed(corpus_root: Path, gen: int) -> bool:
    """Detect v0.1 bucket layout under corpus/{gen}/ and convert to v0.2 chunks.

    Returns True if migration ran (something was moved); False if nothing to do.
    Idempotent: second call is no-op.
    """
    gen_root = corpus_root / str(gen)
    buckets = _list_v0_1_buckets(gen_root)
    if not buckets:
        return False

    log.info("migrating %d v0.1 buckets under %s", len(buckets), gen_root)

    missing = MissingSet(gen_root / "missing.txt")
    missing.load()

    touched_chunks: dict[tuple[int, int], Chunk] = {}
    # Capture mtime before each file is moved so sealed MANIFEST.csv carries original provenance
    mtimes: dict[tuple[int, int], datetime] = {}  # (gen, sheep_id) → utc datetime

    for bucket in buckets:
        for flam3 in bucket.glob("electricsheep.*.flam3"):
            m = _FLAM3_RE.match(flam3.name)
            if not m:
                continue
            file_gen = int(m.group(1))
            if file_gen != gen:
                continue
            sheep_id = int(m.group(2))
            content = flam3.read_bytes()

            # Capture mtime BEFORE the move while the original path still exists
            raw_mtime = flam3.stat().st_mtime
            mtimes[(gen, sheep_id)] = datetime.fromtimestamp(raw_mtime, tz=timezone.utc)

            start, end = chunk_for(sheep_id)
            key = (start, end)
            if key not in touched_chunks:
                touched_chunks[key] = Chunk(
                    gen=gen, start=start, end=end, corpus_root=corpus_root,
                )
            touched_chunks[key].add_flam3(sheep_id, content)

        # Guard: only rmtree if bucket contains no non-flam3 user files
        non_flam3 = [
            p.name for p in bucket.iterdir()
            if not _FLAM3_RE.match(p.name) and p.name != ".DS_Store"
        ]
        if non_flam3:
            log.warning(
                "bucket %s contains non-flam3 files %s — leaving intact",
                bucket, non_flam3,
            )
        else:
            shutil.rmtree(bucket, ignore_errors=False)

    # Try to seal every touched chunk whose range is now complete
    for chunk in touched_chunks.values():
        if chunk.is_range_complete(missing):
            chunk.seal(
                missing,
                source_url_for=lambda sid: remote_url(gen, sid),
                fetched_at_for=lambda sid: mtimes.get(
                    (chunk.gen, sid), datetime.now(tz=timezone.utc)
                ),
            )

    return True
