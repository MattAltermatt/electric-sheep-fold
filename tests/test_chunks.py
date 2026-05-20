"""Tests for electric_sheep_fold.chunks — Chunk lifecycle (working → sealed)."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.layout import flam3_filename, sealed_zip_path
from electric_sheep_fold.manifest import MissingSet


NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


def _make_chunk(tmp_path: Path, start: int = 0, end: int = 10_000) -> Chunk:
    return Chunk(gen=248, start=start, end=end, corpus_root=tmp_path)


def _src_url(sheep_id: int) -> str:
    return f"http://v3d0.sheepserver.net/gen/248/{sheep_id}/electricsheep.248.{sheep_id:05d}.flam3"


def _fetched_at(sheep_id: int) -> datetime:
    return NOW


FLAM3 = b"""<?xml version="1.0"?><flame name="t" nick="bob">
<xform weight="1.0" linear="1.0"/>
</flame>
"""


class TestChunkStatus:
    def test_empty(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        assert c.status == "empty"

    def test_working_after_add(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        assert c.status == "working"

    def test_sealed_after_seal(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        # Mark every other id as missing so the range completes
        for sid in range(c.start, c.end):
            if sid != 100:
                ms.add(sid)
        c.seal(ms, source_url_for=_src_url, fetched_at_for=_fetched_at)
        assert c.status == "sealed"


class TestAddFlam3Atomic:
    def test_writes_into_working_dir(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        dest = c.working_dir / flam3_filename(248, 100)
        assert dest.exists()
        assert dest.read_bytes() == FLAM3

    def test_no_tmp_left_behind(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        tmp_glob = list(c.working_dir.glob("*.tmp"))
        assert tmp_glob == []


class TestContainsId:
    def test_working(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        assert c.contains_id(100)
        assert not c.contains_id(101)

    def test_sealed(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        for sid in range(c.start, c.end):
            if sid != 100:
                ms.add(sid)
        c.seal(ms, source_url_for=_src_url, fetched_at_for=_fetched_at)
        assert c.contains_id(100)
        assert not c.contains_id(101)


class TestReadFlam3:
    def test_read_working(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        assert c.read_flam3(100) == FLAM3

    def test_read_sealed(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        c.add_flam3(100, FLAM3)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        for sid in range(c.start, c.end):
            if sid != 100:
                ms.add(sid)
        c.seal(ms, source_url_for=_src_url, fetched_at_for=_fetched_at)
        assert c.read_flam3(100) == FLAM3

    def test_missing_raises_keyerror(self, tmp_path: Path):
        c = _make_chunk(tmp_path)
        with pytest.raises(KeyError):
            c.read_flam3(100)


class TestIsRangeComplete:
    def test_complete_when_every_id_known(self, tmp_path: Path):
        c = _make_chunk(tmp_path, start=0, end=10)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        c.add_flam3(5, FLAM3)
        for sid in range(0, 10):
            if sid != 5:
                ms.add(sid)
        assert c.is_range_complete(ms)

    def test_incomplete_when_id_unknown(self, tmp_path: Path):
        c = _make_chunk(tmp_path, start=0, end=10)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        c.add_flam3(5, FLAM3)
        # id 7 neither present nor missing
        for sid in (0, 1, 2, 3, 4, 6, 8, 9):
            ms.add(sid)
        assert not c.is_range_complete(ms)


class TestSeal:
    def _seal_one_sheep_chunk(self, tmp_path: Path) -> Chunk:
        c = _make_chunk(tmp_path, start=0, end=10)
        c.add_flam3(5, FLAM3)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        for sid in range(0, 10):
            if sid != 5:
                ms.add(sid)
        c.seal(ms, source_url_for=_src_url, fetched_at_for=_fetched_at)
        return c

    def test_zip_path_exists(self, tmp_path: Path):
        c = self._seal_one_sheep_chunk(tmp_path)
        assert c.zip_path.exists()
        assert c.zip_path == sealed_zip_path(248, 0, 10, tmp_path)

    def test_working_dir_removed(self, tmp_path: Path):
        c = self._seal_one_sheep_chunk(tmp_path)
        assert not c.working_dir.exists()

    def test_manifest_csv_is_first_entry(self, tmp_path: Path):
        c = self._seal_one_sheep_chunk(tmp_path)
        with zipfile.ZipFile(c.zip_path, "r") as zf:
            names = zf.namelist()
            assert names[0] == "MANIFEST.csv"

    def test_flam3_present_in_zip(self, tmp_path: Path):
        c = self._seal_one_sheep_chunk(tmp_path)
        with zipfile.ZipFile(c.zip_path, "r") as zf:
            assert "electricsheep.248.00005.flam3" in zf.namelist()
            assert zf.read("electricsheep.248.00005.flam3") == FLAM3

    def test_manifest_csv_content(self, tmp_path: Path):
        c = self._seal_one_sheep_chunk(tmp_path)
        with zipfile.ZipFile(c.zip_path, "r") as zf:
            text = zf.read("MANIFEST.csv").decode("utf-8")
        assert "id,sha256,file_size_bytes" in text  # header
        assert ",bob," in text  # nick of the sample flam3

    def test_no_tmp_zip_left(self, tmp_path: Path):
        c = self._seal_one_sheep_chunk(tmp_path)
        assert not c.zip_path.with_suffix(c.zip_path.suffix + ".tmp").exists()


class TestSealMultipleSheep:
    def test_seals_all_files(self, tmp_path: Path):
        c = _make_chunk(tmp_path, start=0, end=10)
        for sid in (1, 3, 5):
            c.add_flam3(sid, FLAM3)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        for sid in (0, 2, 4, 6, 7, 8, 9):
            ms.add(sid)
        c.seal(ms, source_url_for=_src_url, fetched_at_for=_fetched_at)
        with zipfile.ZipFile(c.zip_path, "r") as zf:
            names = set(zf.namelist())
            assert "MANIFEST.csv" in names
            for sid in (1, 3, 5):
                assert flam3_filename(248, sid) in names
