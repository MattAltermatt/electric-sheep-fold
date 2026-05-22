"""One-time v0.1 bucket → v0.3 loose-corpus migration.

Pre-v0.2 corpora used per-1k-id "bucket" subdirs (``corpus/{gen}/NNxxx/``).
This migration flattens any surviving v0.1 buckets into the v0.3 loose
shape (``corpus/{gen}/electricsheep.{gen}.{id}.flam3``). The v0.2 chunked
shape no longer appears anywhere in the working code path; the v0.2 →
v0.3 transition is handled by :mod:`electric_sheep_fold.unseal`.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path

from electric_sheep_fold.layout import flam3_path

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


def _atomic_move_into_place(src: Path, dest: Path) -> None:
    """``os.replace`` src → dest via a same-dir .tmp, parent-mkdir-safe."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)
    src.unlink()


def migrate_v0_1_if_needed(corpus_root: Path, gen: int) -> bool:
    """Detect v0.1 bucket layout under corpus/{gen}/ and flatten to v0.3.

    Returns True if migration ran (something was moved); False if nothing to do.
    Idempotent: second call is a no-op.
    """
    gen_root = corpus_root / str(gen)
    buckets = _list_v0_1_buckets(gen_root)
    if not buckets:
        return False

    log.info("migrating %d v0.1 buckets under %s", len(buckets), gen_root)

    for bucket in buckets:
        for flam3 in bucket.glob("electricsheep.*.flam3"):
            m = _FLAM3_RE.match(flam3.name)
            if not m:
                continue
            file_gen = int(m.group(1))
            if file_gen != gen:
                continue
            sheep_id = int(m.group(2))
            dest = flam3_path(gen, sheep_id, corpus_root)
            if dest.exists():
                # v0.3 file already in place — drop the bucket copy.
                flam3.unlink()
                continue
            _atomic_move_into_place(flam3, dest)

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

    return True
