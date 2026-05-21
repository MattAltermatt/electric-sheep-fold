"""Chunk lifecycle for electric-sheep-fold v0.2 (working → sealed)."""
from __future__ import annotations

import csv
import io
import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from electric_sheep_fold.extract import MANIFEST_COLUMNS, extract_metadata
from electric_sheep_fold.layout import (
    chunk_range_str,
    flam3_filename,
    sealed_zip_path,
)
from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)

Status = Literal["sealed", "working", "empty"]


class Chunk:
    """A single 10k id-range chunk for one generation."""

    def __init__(self, *, gen: int, start: int, end: int, corpus_root: Path) -> None:
        self.gen = gen
        self.start = start
        self.end = end
        self.corpus_root = corpus_root

    @property
    def range_str(self) -> str:
        return chunk_range_str(self.start, self.end)

    @property
    def zip_path(self) -> Path:
        return sealed_zip_path(self.gen, self.start, self.end, self.corpus_root)

    @property
    def working_dir(self) -> Path:
        return self.corpus_root / str(self.gen) / self.range_str

    @property
    def status(self) -> Status:
        if self.zip_path.exists():
            return "sealed"
        if self.working_dir.exists() and any(self.working_dir.iterdir()):
            return "working"
        return "empty"

    def add_flam3(self, sheep_id: int, content: bytes) -> None:
        """Atomic write into working dir (tmp + os.replace)."""
        self.working_dir.mkdir(parents=True, exist_ok=True)
        dest = self.working_dir / flam3_filename(self.gen, sheep_id)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(content)
        os.replace(tmp, dest)

    def contains_id(self, sheep_id: int) -> bool:
        """True if this sheep_id is present in the working dir OR the sealed zip."""
        if self.status == "sealed":
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                try:
                    zf.getinfo(flam3_filename(self.gen, sheep_id))
                    return True
                except KeyError:
                    return False
        dest = self.working_dir / flam3_filename(self.gen, sheep_id)
        return dest.exists()

    def read_flam3(self, sheep_id: int) -> bytes:
        """Read a flam3's bytes from sealed zip or working dir. Raises KeyError if absent."""
        name = flam3_filename(self.gen, sheep_id)
        if self.status == "sealed":
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                return zf.read(name)
        dest = self.working_dir / name
        if not dest.exists():
            raise KeyError(f"sheep {self.gen}.{sheep_id:05d} not in chunk {self.range_str}")
        return dest.read_bytes()

    def is_range_complete(self, missing: MissingSet) -> bool:
        """True if every id in [start, end) is in working dir OR missing.contains(id)."""
        present_ids = {
            int(p.name.rsplit(".", 2)[-2])
            for p in self.working_dir.glob(f"electricsheep.{self.gen}.*.flam3")
        } if self.working_dir.exists() else set()
        for sheep_id in range(self.start, self.end):
            if sheep_id in present_ids:
                continue
            if missing.contains(sheep_id):
                continue
            return False
        return True

    def seal(
        self,
        missing: MissingSet,
        *,
        source_url_for: Callable[[int], str],
        fetched_at_for: Callable[[int], datetime],
    ) -> None:
        """Build MANIFEST.csv + zip working dir → atomic-replace zip path → rm working dir."""
        if self.status == "sealed":
            log.info("chunk %s already sealed, skipping", self.range_str)
            return
        if not self.working_dir.exists():
            log.warning("chunk %s has no working dir, cannot seal", self.range_str)
            return

        flam3_paths = sorted(
            self.working_dir.glob(f"electricsheep.{self.gen}.*.flam3")
        )
        if not flam3_paths:
            log.warning("chunk %s working dir empty, cannot seal", self.range_str)
            return

        # Build MANIFEST.csv in memory
        rows: list[dict[str, object]] = []
        for path in flam3_paths:
            sheep_id = int(path.name.rsplit(".", 2)[-2])
            content = path.read_bytes()
            rows.append(
                extract_metadata(
                    content=content,
                    sheep_id=sheep_id,
                    source_url=source_url_for(sheep_id),
                    fetched_at=fetched_at_for(sheep_id),
                )
            )

        manifest_buf = io.StringIO()
        writer = csv.DictWriter(manifest_buf, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        manifest_bytes = manifest_buf.getvalue().encode("utf-8")

        # Write zip to tmp path, then atomic-rename
        self.zip_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_zip = self.zip_path.with_suffix(self.zip_path.suffix + ".tmp")
        with zipfile.ZipFile(
            tmp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            zf.writestr("MANIFEST.csv", manifest_bytes)
            for path in flam3_paths:
                zf.write(path, arcname=path.name)
        os.replace(tmp_zip, self.zip_path)

        # Clean up working dir
        shutil.rmtree(self.working_dir)
        log.info("sealed chunk %s (%d sheep)", self.range_str, len(flam3_paths))
