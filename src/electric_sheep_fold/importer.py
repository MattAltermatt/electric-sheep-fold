"""Bulk import of existing local .flam3 files into the v0.3 loose corpus."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from electric_sheep_fold.fetch import _atomic_write_flam3, ensure_corpus_initialized
from electric_sheep_fold.layout import flam3_path
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import migrate_v0_1_if_needed

log = logging.getLogger(__name__)

_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")


@dataclass
class ImportStats:
    imported: int = 0
    skipped: int = 0


def import_dir(
    src: Path,
    corpus_root: Path,
    *,
    gen: int | None = None,
) -> ImportStats:
    """Recursively import all canonical electricsheep.*.flam3 files from src.

    Loose-corpus v0.3 semantics: every flam3 lands as a flat file under
    ``corpus/{gen}/electricsheep.{gen}.{id}.flam3``. Idempotent — existing
    corpus files are not overwritten. Sticky-404 data in
    ``src/_missing_404.txt`` is merged into ``corpus/{gen}/missing.txt``.

    ``gen`` may be omitted when ``src`` contains exactly one gen; otherwise
    pass it explicitly. The argument used to gate a separate "whole-gen"
    seal path in v0.2; v0.3 has only the one path.
    """
    ensure_corpus_initialized(corpus_root)
    if not src.exists():
        raise FileNotFoundError(f"import source not found: {src}")

    stats = ImportStats()
    gens_seen: set[int] = set()

    flam3_targets: list[tuple[int, int, Path]] = []
    for path in src.rglob("electricsheep.*.flam3"):
        m = _FLAM3_RE.match(path.name)
        if not m:
            continue
        file_gen = int(m.group(1))
        if gen is not None and file_gen != gen:
            continue
        sheep_id = int(m.group(2))
        flam3_targets.append((file_gen, sheep_id, path))
        gens_seen.add(file_gen)

    # Validate gen-inference contract when filtering wasn't applied above.
    if gen is None and len(gens_seen) > 1:
        raise ValueError(
            f"cannot infer gen: src {src} contains multiple gens "
            f"{sorted(gens_seen)}; pass gen=N explicitly"
        )

    for file_gen, sheep_id, path in flam3_targets:
        dest = flam3_path(file_gen, sheep_id, corpus_root)
        if dest.exists():
            stats.skipped += 1
            continue
        _atomic_write_flam3(dest, path.read_bytes())
        stats.imported += 1

    # Merge any _missing_404.txt sticky-404 sidecar into the gen's missing.txt.
    # Resolve the target gen: explicit > inferred from single-gen src.
    sticky_gen = gen
    if sticky_gen is None and len(gens_seen) == 1:
        sticky_gen = next(iter(gens_seen))
    src_missing_file = src / "_missing_404.txt"
    if sticky_gen is not None and src_missing_file.exists():
        missing = MissingSet(corpus_root / str(sticky_gen) / "missing.txt")
        missing.load()
        for line in src_missing_file.read_text().splitlines():
            line = line.strip()
            if line and line.lstrip("-").isdigit():
                missing.add(int(line))
        missing.save_atomic()

    # Run legacy v0.1 → v0.2 migration on every gen we touched (no-op if no
    # v0.1 buckets present). The migration now produces loose files too.
    for g in gens_seen:
        migrate_v0_1_if_needed(corpus_root, g)

    return stats
