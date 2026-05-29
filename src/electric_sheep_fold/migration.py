"""Corpus migrations.

* :func:`migrate_v0_1_if_needed` — v0.1 per-1k bucket layout
  (``corpus/{gen}/NNxxx/``) → current chunked shape via
  :func:`electric_sheep_fold.layout.flam3_path`. Idempotent.
* :func:`migrate_v3_to_v4_chunked` — v0.3 flat layout
  (``corpus/{gen}/electricsheep.{gen}.{id}.flam3``) → v0.4 chunked
  (``corpus/{gen}/{bucket}/electricsheep.{gen}.{id}.flam3``). Writes
  ``corpus/_chunked-verified.json`` for fetch-all's daemon-resume guard.
* :func:`verify_chunked_consistency` — daemon-resume guard checking
  current state matches the post-migrate baseline.

v0.2 → v0.3 (sealed-zip → loose) lives in
:mod:`electric_sheep_fold.unseal` and remains its own module.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from electric_sheep_fold.layout import FLAM3_RE as _FLAM3_RE
from electric_sheep_fold.layout import flam3_path
from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)

_BUCKET_RE = re.compile(r"^(\d{2})xxx$")

CHUNKED_VERIFIED_FILENAME = "_chunked-verified.json"


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


# ----- v0.3 flat → v0.4 chunked migration ------------------------------------


@dataclass
class GenMigrateResult:
    """Per-gen outcome of :func:`migrate_v3_to_v4_chunked`."""
    gen: int
    moved: int          # flat files relocated into bucket subdirs
    already_chunked: int  # files that were already in a bucket subdir (no-op)
    loose_count: int    # post-migration total .flam3 count
    missing_count: int  # post-migration missing.txt entry count
    bucket_count: int   # number of distinct bucket subdirs


_GEN_DIR_RE = re.compile(r"^\d+$")


def _atomic_move_intra_dir(src: Path, dest: Path) -> None:
    # Same-filesystem rename — atomic on POSIX. dest parent is mkdir'd by
    # caller (one mkdir per bucket per gen, not per file).
    os.replace(src, dest)


def migrate_v3_to_v4_chunked(corpus_root: Path) -> list[GenMigrateResult]:
    """Reshape flat v0.3 corpus → v0.4 chunked under per-10k bucket subdirs.

    For each gen dir, every flat ``electricsheep.{gen}.{id}.flam3`` file
    is moved into ``corpus/{gen}/{bucket}/`` where
    ``bucket = bucket_for(id)``. Atomic per-file via ``os.replace``;
    SIGKILL-safe (no half-moved file). ``missing.txt`` stays at
    ``corpus/{gen}/missing.txt``.

    Idempotent — re-running on an already-chunked corpus is a no-op
    (no flat files to move; counts match).

    Writes ``corpus/_chunked-verified.json`` recording per-gen
    ``{loose_count, missing_count, bucket_count}`` as the daemon-resume
    baseline. Returns the per-gen result list.
    """
    if not corpus_root.is_dir():
        raise FileNotFoundError(f"corpus root not found: {corpus_root}")

    results: list[GenMigrateResult] = []
    gen_dirs = sorted(
        p for p in corpus_root.iterdir()
        if p.is_dir() and _GEN_DIR_RE.match(p.name)
    )

    for gen_dir in gen_dirs:
        gen = int(gen_dir.name)
        moved = 0
        # Flat files only at the gen-dir top level (glob, not rglob).
        flat_paths = sorted(gen_dir.glob(f"electricsheep.{gen}.*.flam3"))
        for src in flat_paths:
            m = _FLAM3_RE.match(src.name)
            if not m:
                continue
            sheep_id = int(m.group(2))
            dest = flam3_path(gen, sheep_id, corpus_root)
            if src.resolve() == dest.resolve():
                continue  # already at chunked path (defensive)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                # Collision shouldn't happen in practice (flat + chunked
                # of same id) but if it does the chunked file wins; drop
                # the flat duplicate.
                src.unlink()
                continue
            _atomic_move_intra_dir(src, dest)
            moved += 1

        # Post-migration counts (rglob catches everything bucketed).
        all_flam3 = list(gen_dir.rglob(f"electricsheep.{gen}.*.flam3"))
        already_chunked = len(all_flam3) - moved
        bucket_dirs = sorted(
            p for p in gen_dir.iterdir() if p.is_dir() and p.name != "_index"
        )
        ms = MissingSet(gen_dir / "missing.txt")
        ms.load()

        results.append(GenMigrateResult(
            gen=gen,
            moved=moved,
            already_chunked=already_chunked,
            loose_count=len(all_flam3),
            missing_count=len(ms),
            bucket_count=len(bucket_dirs),
        ))
        log.info(
            "gen %d: moved %d, already_chunked %d, loose_total %d, "
            "missing %d, buckets %d",
            gen, moved, already_chunked, len(all_flam3), len(ms),
            len(bucket_dirs),
        )

    _write_chunked_verified(corpus_root, results)
    return results


def _write_chunked_verified(
    corpus_root: Path, results: list[GenMigrateResult]
) -> None:
    payload = {
        "schema": "v0.4",
        "gens": [
            {
                "gen": r.gen,
                "loose_count": r.loose_count,
                "missing_count": r.missing_count,
                "bucket_count": r.bucket_count,
            }
            for r in results
        ],
    }
    dest = corpus_root / CHUNKED_VERIFIED_FILENAME
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, dest)


def _load_chunked_verified(corpus_root: Path) -> list[dict] | None:
    p = corpus_root / CHUNKED_VERIFIED_FILENAME
    if not p.exists():
        return None
    return json.loads(p.read_text())["gens"]


def verify_chunked_consistency(
    corpus_root: Path,
) -> list[tuple[int, str]]:
    """Daemon-resume guard for v0.4 chunked layout.

    Returns a list of ``(gen, reason)`` for divergences:

      * **Any** gen dir containing flat ``corpus/{gen}/*.flam3`` files
        at the top level → migration incomplete (the main safety check;
        always active, regardless of baseline file presence).
      * If ``_chunked-verified.json`` exists: total ``.flam3`` count
        dropped below the baseline → unexpected deletion. Growth above
        baseline is fine — live gens append.

    Absence of ``_chunked-verified.json`` is NOT a divergence — fresh
    corpora and test fixtures legitimately start without one. Migration
    writes the baseline; subsequent runs benefit from the shrink check.
    """
    divergences: list[tuple[int, str]] = []
    if not corpus_root.is_dir():
        return divergences

    gen_dirs = [
        p for p in corpus_root.iterdir()
        if p.is_dir() and _GEN_DIR_RE.match(p.name)
    ]
    for gen_dir in gen_dirs:
        gen = int(gen_dir.name)
        flat_residual = list(gen_dir.glob(f"electricsheep.{gen}.*.flam3"))
        if flat_residual:
            divergences.append((
                gen,
                f"{len(flat_residual)} flat .flam3 file(s) at gen root — "
                f"run `sheep-fold migrate-chunked`",
            ))

    records = _load_chunked_verified(corpus_root)
    if records is not None:
        for r in records:
            gen = int(r["gen"])
            gen_dir = corpus_root / str(gen)
            if not gen_dir.is_dir():
                divergences.append((gen, f"gen dir missing: {gen_dir}"))
                continue
            actual_loose = sum(
                1 for _ in gen_dir.rglob(f"electricsheep.{gen}.*.flam3")
            )
            expected_loose = int(r["loose_count"])
            if actual_loose < expected_loose:
                divergences.append((
                    gen,
                    f"loose count {actual_loose} < baseline {expected_loose} "
                    f"(unexpected deletion)",
                ))
    return divergences
