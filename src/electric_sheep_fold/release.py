"""Release-artifact build for electric-sheep-fold v0.4.

Reads on-disk chunked corpus state and produces dated ``build/release/``
artifacts on demand:

* ``gen-{N}-{YYYY-MM-DD}.zip`` — per-generation; ZIP DEFLATE-9. Members:
  ``MANIFEST.csv``, ``missing.txt``, ``{bucket}/electricsheep.{N}.{id}.flam3``.
* ``corpus-all-{YYYY-MM-DD}.tar.xz`` — mega-bundle; full corpus tree
  including ``{gen}/MANIFEST.csv``, ``{gen}/missing.txt``,
  ``{gen}/{bucket}/electricsheep.{N}.{id}.flam3``, ``_index/*``,
  ``ATTRIBUTION.md``. LZMA preset 6.
* ``INDEX.md`` + ``index.json`` — regenerated via ``sheep-fold index``.
* ``ATTRIBUTION.md`` — copied from ``corpus/ATTRIBUTION.md``.

Overlay invariant: per-gen zip extracted under ``{gen}/`` produces the
same on-disk tree as the matching subset of the mega-bundle. Consumers
can grab piecemeal or all-in-one and they fit together.

All zip / tar.xz writes are atomic (``.tmp`` + ``os.replace``). Sheep
ids iterate in sorted order for reproducible byte-stable output (modulo
member timestamps).
"""
from __future__ import annotations

import csv
import io
import logging
import lzma
import os
import re
import shutil
import tarfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from electric_sheep_fold.chunk import build_chunks_tar
from electric_sheep_fold.extract import MANIFEST_COLUMNS, extract_metadata
from electric_sheep_fold.index import build_index
from electric_sheep_fold.layout import FLAM3_RE as _FLAM3_RE
from electric_sheep_fold.layout import (
    ARCHIVE_BASE_URL,
    BASE_URL_DEFAULT,
    LIVE_GENS,
    archive_url,
    bucket_for,
    flam3_filename,
    remote_url,
)
from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)

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
    loose_paths = sorted(gen_dir.rglob(f"electricsheep.{gen}.*.flam3"))
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
    ids = missing.sorted_ids()
    return ("".join(f"{sid}\n" for sid in ids)).encode("utf-8")


def _gen_zip_filename(gen: int, build_date: date) -> str:
    return f"gen-{gen}-{build_date.isoformat()}.zip"


def _mega_tarxz_filename(build_date: date) -> str:
    return f"corpus-all-{build_date.isoformat()}.tar.xz"


def _chunks_tar_filename(build_date: date) -> str:
    return f"corpus-chunks-{build_date.isoformat()}.tar"


def build_gen_zip(
    gen: int,
    corpus_root: Path,
    out_dir: Path,
    *,
    build_date: date | None = None,
    source_url_for: Callable[[int], str] | None = None,
    fetched_at: datetime | None = None,
) -> Path:
    """Build ``out_dir/gen-{gen}-{date}.zip`` from ``corpus/{gen}/`` state.

    Contents (v0.4 chunked):

    * ``MANIFEST.csv`` (regenerated via ``extract.extract_metadata``)
    * ``missing.txt`` (id-per-line, sorted; mirrors on-disk format)
    * ``{bucket}/electricsheep.{gen}.{id}.flam3`` — chunked tree mirroring
      disk layout, so ``unzip -d {gen}/`` reproduces the corpus tree.

    Atomic write via ``.tmp`` + ``os.replace``. Returns the written path.
    """
    records, missing = _gather_gen_data(gen, corpus_root)
    if source_url_for is None:
        source_url_for = _default_source_url_for(gen)
    if fetched_at is None:
        fetched_at = datetime.now(tz=timezone.utc)
    if build_date is None:
        build_date = datetime.now(tz=timezone.utc).date()

    manifest_bytes = _build_manifest_bytes(
        gen, records, source_url_for=source_url_for, fetched_at=fetched_at
    )
    missing_bytes = _build_missing_bytes(missing)

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / _gen_zip_filename(gen, build_date)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with zipfile.ZipFile(
        tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        zf.writestr("MANIFEST.csv", manifest_bytes)
        zf.writestr("missing.txt", missing_bytes)
        for sheep_id in sorted(records):
            arcname = f"{bucket_for(sheep_id)}/{flam3_filename(gen, sheep_id)}"
            zf.writestr(arcname, records[sheep_id])
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


def _build_mega_tarxz(
    corpus_root: Path,
    out_dir: Path,
    build_date: date,
    *,
    source_url_for_gen: Callable[[int], Callable[[int], str]] | None = None,
    fetched_at: datetime | None = None,
    preset: int = 6,
) -> Path:
    """Pack the full v0.4 corpus tree into ``out_dir/corpus-all-{date}.tar.xz``.

    Members (corpus-relative):

      * ``{gen}/MANIFEST.csv``
      * ``{gen}/missing.txt``
      * ``{gen}/{bucket}/electricsheep.{gen}.{id}.flam3``
      * ``_index/index.json``, ``_index/INDEX.md``
      * ``ATTRIBUTION.md``

    Overlay invariant: extracting this archive into an empty staging
    dir produces the same tree as ``unzip``-ing every per-gen zip into
    its respective ``{gen}/`` subdir (modulo the ``_index/`` and
    ``ATTRIBUTION.md`` top-level files which only the tar.xz carries).

    Atomic via tmp + os.replace. LZMA preset defaults to 6 (good ratio,
    reasonable build time).
    """
    if fetched_at is None:
        fetched_at = datetime.now(tz=timezone.utc)

    dest = out_dir / _mega_tarxz_filename(build_date)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    out_dir.mkdir(parents=True, exist_ok=True)

    with lzma.open(tmp, "wb", preset=preset) as xz, \
         tarfile.open(fileobj=xz, mode="w|") as tf:
        for gen in _discover_gens(corpus_root):
            records, missing = _gather_gen_data(gen, corpus_root)
            url_for = (
                source_url_for_gen(gen)
                if source_url_for_gen is not None
                else _default_source_url_for(gen)
            )
            manifest_bytes = _build_manifest_bytes(
                gen, records, source_url_for=url_for, fetched_at=fetched_at
            )
            missing_bytes = _build_missing_bytes(missing)
            _tar_addbytes(tf, f"{gen}/MANIFEST.csv", manifest_bytes)
            _tar_addbytes(tf, f"{gen}/missing.txt", missing_bytes)
            for sheep_id in sorted(records):
                arcname = (
                    f"{gen}/{bucket_for(sheep_id)}/"
                    f"{flam3_filename(gen, sheep_id)}"
                )
                _tar_addbytes(tf, arcname, records[sheep_id])

        for rel in ("_index/index.json", "_index/INDEX.md", "ATTRIBUTION.md"):
            src = corpus_root / rel
            if src.exists():
                tf.add(src, arcname=rel, recursive=False)

    os.replace(tmp, dest)
    log.info("built %s", dest.name)
    return dest


def _tar_addbytes(tf: tarfile.TarFile, arcname: str, data: bytes) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mtime = 0  # reproducible-ish; epoch-seconds-zero
    info.mode = 0o644
    tf.addfile(info, io.BytesIO(data))


def build_release(
    corpus_root: Path,
    out_dir: Path,
    *,
    build_date: date | None = None,
    only_gen: int | None = None,
    regen_index: bool = True,
    skip_mega: bool = False,
    skip_chunks: bool = False,
) -> list[Path]:
    """Build the full v0.4 release artifact set into ``out_dir``.

    Steps:
      1. Regenerate ``corpus/_index/{index.json,INDEX.md}`` (unless
         ``regen_index=False``).
      2. ``build_gen_zip`` for every numeric gen in ``corpus/`` (or just
         ``only_gen`` if specified). Filename ``gen-{N}-{date}.zip``.
      3. Copy ``INDEX.md`` / ``index.json`` / ``ATTRIBUTION.md`` from
         ``corpus/`` to ``out_dir/``.
      4. Build ``corpus-all-{date}.tar.xz`` mega-bundle (unless
         ``skip_mega=True``).
      5. Build ``corpus-chunks-{date}.tar`` delivery-chunk artifact (unless
         ``skip_chunks=True``).

    ``only_gen`` mode skips steps 1, 3, 4, and 5 — used by ``--gen N`` for
    fast per-gen rebuilds. ``skip_mega`` / ``skip_chunks`` are test-only
    escape hatches to avoid compression cost on small fixtures.

    Returns the list of paths written (in order).
    """
    # Single `fetched_at` shared across per-gen zips AND mega-bundle so
    # their MANIFEST.csv outputs are byte-identical — load-bearing for the
    # overlay invariant.
    fetched_at = datetime.now(tz=timezone.utc)
    if build_date is None:
        build_date = fetched_at.date()

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if only_gen is not None:
        written.append(
            build_gen_zip(
                only_gen, corpus_root, out_dir,
                build_date=build_date, fetched_at=fetched_at,
            )
        )
        return written

    if regen_index:
        index_dir = corpus_root / "_index"
        log.info("regenerating corpus index → %s", index_dir)
        build_index(corpus_root, index_dir, build_date=build_date)

    for gen in _discover_gens(corpus_root):
        written.append(
            build_gen_zip(
                gen, corpus_root, out_dir,
                build_date=build_date, fetched_at=fetched_at,
            )
        )

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

    if not skip_mega:
        written.append(_build_mega_tarxz(
            corpus_root, out_dir, build_date, fetched_at=fetched_at,
        ))

    if not skip_chunks:
        chunks_dest = out_dir / _chunks_tar_filename(build_date)
        build_chunks_tar(corpus_root, chunks_dest, build_date.isoformat())
        log.info("built %s", chunks_dest.name)
        written.append(chunks_dest)

    return written
