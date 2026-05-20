"""Tests for electric_sheep_fold.importer — bulk import existing local flames."""
from __future__ import annotations

from pathlib import Path

from electric_sheep_fold.importer import import_dir
from electric_sheep_fold.layout import flam3_filename, working_path


def _drop_flam3(src: Path, gen: int, sheep_id: int, content: bytes = b"<flame/>") -> Path:
    dest = src / flam3_filename(gen, sheep_id)
    dest.write_bytes(content)
    return dest


class TestImportFlatDir:
    def test_single_file(self, tmp_path: Path):
        src = tmp_path / "src"
        corpus = tmp_path / "corpus"
        src.mkdir()
        _drop_flam3(src, 248, 100)
        stats = import_dir(src, corpus)
        assert stats.imported == 1
        assert stats.skipped == 0
        assert working_path(248, 100, corpus).exists()

    def test_multiple_files(self, tmp_path: Path):
        src = tmp_path / "src"
        corpus = tmp_path / "corpus"
        src.mkdir()
        for sid in (100, 5_500, 15_000):
            _drop_flam3(src, 248, sid)
        stats = import_dir(src, corpus)
        assert stats.imported == 3
        for sid in (100, 5_500, 15_000):
            assert working_path(248, sid, corpus).exists()


class TestImportNested:
    def test_finds_recursively(self, tmp_path: Path):
        src = tmp_path / "src"
        (src / "deep" / "nested").mkdir(parents=True)
        (src / "deep" / "nested" / flam3_filename(248, 100)).write_bytes(b"<flame/>")
        corpus = tmp_path / "corpus"
        stats = import_dir(src, corpus)
        assert stats.imported == 1
        assert working_path(248, 100, corpus).exists()


class TestImportSkipsExisting:
    def test_skips_when_in_working_dir(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        corpus = tmp_path / "corpus"
        # Pre-populate corpus
        dest = working_path(248, 100, corpus)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"existing")
        _drop_flam3(src, 248, 100, b"different")
        stats = import_dir(src, corpus)
        assert stats.skipped == 1
        assert stats.imported == 0
        # Existing content not overwritten
        assert dest.read_bytes() == b"existing"


class TestImportIgnoresNonFlam3:
    def test_ignores_unrelated_files(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "readme.txt").write_text("not a flam3")
        (src / "weird-name.flam3").write_bytes(b"<flame/>")  # doesn't match canonical pattern
        _drop_flam3(src, 248, 100)
        corpus = tmp_path / "corpus"
        stats = import_dir(src, corpus)
        assert stats.imported == 1
