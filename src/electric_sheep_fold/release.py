"""Release-artifact build for electric-sheep-fold v0.3.

Reads on-disk corpus state and produces ``build/release/`` zips on demand:

* ``gen-{N}.zip`` — per-generation; contains ``MANIFEST.csv`` + ``missing.txt``
  + flat ``electricsheep.{N}.{id}.flam3`` files
* ``corpus-all.zip`` — mega-bundle containing every ``gen-{N}.zip`` plus
  ``INDEX.md`` / ``index.json`` / ``ATTRIBUTION.md``
* ``INDEX.md`` + ``index.json`` — regenerated via the existing
  ``sheep-fold index`` machinery
* ``ATTRIBUTION.md`` — copied from ``corpus/ATTRIBUTION.md``

Corpus shape v0.3 is loose ``.flam3`` files in each gen dir; this module
also accepts the v0.2 sealed-zip-per-gen shape as a transit mode so we
have a release-build path before the one-time Phase D ``unseal``
migration runs.

All zip writes are atomic (``.tmp`` + ``os.replace``). Sheep ids are
iterated in sorted order for reproducible byte-stable output (modulo
zip member timestamps).
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from electric_sheep_fold.extract import MANIFEST_COLUMNS, extract_metadata
from electric_sheep_fold.index import build_index
from electric_sheep_fold.layout import (
    ARCHIVE_BASE_URL,
    BASE_URL_DEFAULT,
    LIVE_GENS,
    archive_url,
    flam3_filename,
    remote_url,
)
from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)

_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")
_SEALED_ZIP_RE = re.compile(r"^\d{5}-\d{5}\.zip$")
_GEN_DIR_RE = re.compile(r"^\d+$")


def _default_source_url_for(gen: int) -> Callable[[int], str]:
    """Default source-URL builder per gen (live → v3d0, dead → archive)."""
    if gen in LIVE_GENS:
        return lambda sid: remote_url(gen, sid, BASE_URL_DEFAULT)
    return lambda sid: archive_url(gen, sid, ARCHIVE_BASE_URL)


def _gather_gen_data(
    gen: int, corpus_root: Path
) -> tuple[dict[int, bytes], MissingSet]:
    """Return ``{sheep_id: content_bytes}`` + loaded MissingSet for one gen.

    Auto-detects mode:

    * **loose** (v0.3 native) — ``corpus/{gen}/electricsheep.{gen}.*.flam3``
      files on disk
    * **sealed** (v0.2 transit) — single ``corpus/{gen}/?????-?????.zip``
      contains the flam3s
    * **hybrid** — both shapes present; loose entries win on id collision
      (transient migration state, not expected post-Phase D)

    Sheep ids returned in insertion order; callers that need determinism
    should sort the dict keys themselves.
    """
    gen_dir = corpus_root / str(gen)
    if not gen_dir.is_dir():
        raise FileNotFoundError(f"gen dir not found: {gen_dir}")

    sealed_zips = sorted(gen_dir.glob("?????-?????.zip"))
    loose_paths = sorted(gen_dir.glob(f"electricsheep.{gen}.*.flam3"))
    # Hybrid is a transient unseal-in-progress state; safe to read both
    # (loose overrides sealed on id collision below) but worth flagging so
    # an operator notices a half-finished migration before shipping a
    # release built from mixed sources.
    if sealed_zips and loose_paths:
        log.warning(
            "gen %d: hybrid shape (%d sealed zip(s) + %d loose .flam3) — "
            "likely an interrupted unseal; run `sheep-fold unseal --gen %d` "
            "to finish before building releases",
            gen, len(sealed_zips), len(loose_paths), gen,
        )

    records: dict[int, bytes] = {}

    # Sealed zips first; loose overrides on collision (hybrid case).
    for zip_path in sealed_zips:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                m = _FLAM3_RE.match(name)
                if not m:
                    continue
                records[int(m.group(2))] = zf.read(name)

    for flam3_path in loose_paths:
        m = _FLAM3_RE.match(flam3_path.name)
        if not m:
            continue
        records[int(m.group(2))] = flam3_path.read_bytes()

    missing = MissingSet(gen_dir / "missing.txt")
    missing.load()
    return records, missing


def _build_manifest_bytes(
    gen: int,
    records: dict[int, bytes],
    *,
    source_url_for: Callable[[int], str],
    fetched_at: datetime,
) -> bytes:
    """Build MANIFEST.csv bytes via extract.extract_metadata, sorted by id."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=MANIFEST_COLUMNS)
    writer.writeheader()
    for sheep_id in sorted(records):
        row = extract_metadata(
            content=records[sheep_id],
            sheep_id=sheep_id,
            source_url=source_url_for(sheep_id),
            fetched_at=fetched_at,
        )
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _build_missing_bytes(missing: MissingSet) -> bytes:
    """Render MissingSet in its on-disk format (id-per-line, sorted)."""
    # Use the internal sorted set rather than re-reading the file —
    # _gather_gen_data already loaded it.
    ids = sorted(missing._ids)  # noqa: SLF001 — release.py owns this seam.
    return ("".join(f"{sid}\n" for sid in ids)).encode("utf-8")


def build_gen_zip(
    gen: int,
    corpus_root: Path,
    out_dir: Path,
    *,
    source_url_for: Callable[[int], str] | None = None,
    fetched_at: datetime | None = None,
) -> Path:
    """Build ``out_dir/gen-{gen}.zip`` from ``corpus/{gen}/`` state.

    Auto-detects loose-corpus (v0.3) vs sealed-zip-transit (v0.2) shape.
    Contents:

    * ``MANIFEST.csv`` (regenerated via ``extract.extract_metadata``)
    * ``missing.txt`` (id-per-line, sorted; mirrors on-disk format)
    * ``electricsheep.{gen}.{id}.flam3`` for every present sheep, flat

    Atomic write via ``.tmp`` + ``os.replace``. Returns the written path.
    """
    records, missing = _gather_gen_data(gen, corpus_root)
    if source_url_for is None:
        source_url_for = _default_source_url_for(gen)
    if fetched_at is None:
        fetched_at = datetime.now(tz=timezone.utc)

    manifest_bytes = _build_manifest_bytes(
        gen, records, source_url_for=source_url_for, fetched_at=fetched_at
    )
    missing_bytes = _build_missing_bytes(missing)

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"gen-{gen}.zip"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with zipfile.ZipFile(
        tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        zf.writestr("MANIFEST.csv", manifest_bytes)
        zf.writestr("missing.txt", missing_bytes)
        for sheep_id in sorted(records):
            zf.writestr(flam3_filename(gen, sheep_id), records[sheep_id])
    os.replace(tmp, dest)
    log.info(
        "built %s (%d sheep, %d missing)", dest.name, len(records), len(missing)
    )
    return dest


def _discover_gens(corpus_root: Path) -> list[int]:
    """Find numeric gen subdirs in corpus_root (skip ``_index`` etc.)."""
    return sorted(
        int(p.name)
        for p in corpus_root.iterdir()
        if p.is_dir() and _GEN_DIR_RE.match(p.name)
    )


def _build_mega_bundle(out_dir: Path) -> Path:
    """Pack every gen-*.zip + INDEX/index/ATTRIBUTION into corpus-all.zip.

    Mirrors the legacy ``scripts/build_release.sh`` `zip -X` behavior:
    DEFLATE level 9, no extra fields. Atomic via tmp + os.replace.
    """
    dest = out_dir / "corpus-all.zip"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    members = sorted(out_dir.glob("gen-*.zip")) + [
        out_dir / "INDEX.md",
        out_dir / "index.json",
        out_dir / "ATTRIBUTION.md",
    ]
    with zipfile.ZipFile(
        tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for p in members:
            if p.exists():
                zf.write(p, arcname=p.name)
    os.replace(tmp, dest)
    log.info("built %s", dest.name)
    return dest


def build_release(
    corpus_root: Path,
    out_dir: Path,
    *,
    only_gen: int | None = None,
    regen_index: bool = True,
) -> list[Path]:
    """Build the full release artifact set into ``out_dir``.

    Steps:
      1. Regenerate ``corpus/_index/{index.json,INDEX.md}`` (unless
         ``regen_index=False``).
      2. ``build_gen_zip`` for every numeric gen in ``corpus/`` (or just
         ``only_gen`` if specified).
      3. Copy ``INDEX.md`` / ``index.json`` / ``ATTRIBUTION.md`` from
         ``corpus/`` to ``out_dir/``.
      4. Build ``corpus-all.zip`` mega-bundle.

    ``only_gen`` mode skips steps 1, 3, and 4 — used by ``--gen N`` for
    fast per-gen rebuilds.

    Returns the list of paths written (in order).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if only_gen is not None:
        written.append(build_gen_zip(only_gen, corpus_root, out_dir))
        return written

    if regen_index:
        index_dir = corpus_root / "_index"
        log.info("regenerating corpus index → %s", index_dir)
        build_index(corpus_root, index_dir)

    for gen in _discover_gens(corpus_root):
        written.append(build_gen_zip(gen, corpus_root, out_dir))

    # Copy index + attribution from corpus into release dir.
    for fname in ("INDEX.md", "index.json"):
        src = corpus_root / "_index" / fname
        if src.exists():
            dest = out_dir / fname
            shutil.copy2(src, dest)
            written.append(dest)

    attr_src = corpus_root / "ATTRIBUTION.md"
    if attr_src.exists():
        attr_dest = out_dir / "ATTRIBUTION.md"
        shutil.copy2(attr_src, attr_dest)
        written.append(attr_dest)

    written.append(_build_mega_bundle(out_dir))
    return written
