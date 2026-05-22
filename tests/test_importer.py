"""Tests for electric_sheep_fold.importer — bulk import existing local flames (v0.3 loose)."""
from __future__ import annotations

from pathlib import Path

import pytest

from electric_sheep_fold.importer import import_dir
from electric_sheep_fold.layout import flam3_filename, flam3_path
from electric_sheep_fold.manifest import MissingSet


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
        assert flam3_path(248, 100, corpus).exists()

    def test_multiple_files_same_gen(self, tmp_path: Path):
        src = tmp_path / "src"
        corpus = tmp_path / "corpus"
        src.mkdir()
        for sid in (100, 5_500, 15_000):
            _drop_flam3(src, 248, sid)
        stats = import_dir(src, corpus)
        assert stats.imported == 3
        for sid in (100, 5_500, 15_000):
            assert flam3_path(248, sid, corpus).exists()

    def test_no_chunk_subdirs(self, tmp_path: Path):
        """v0.3 invariant: no NNNNN-NNNNN subdirs under corpus/{gen}/."""
        src = tmp_path / "src"
        corpus = tmp_path / "corpus"
        src.mkdir()
        _drop_flam3(src, 248, 100)
        import_dir(src, corpus)
        gen_root = corpus / "248"
        # Only flat files; no subdirs.
        subdirs = [p for p in gen_root.iterdir() if p.is_dir()]
        assert subdirs == []


class TestImportNested:
    def test_finds_recursively(self, tmp_path: Path):
        src = tmp_path / "src"
        (src / "deep" / "nested").mkdir(parents=True)
        (src / "deep" / "nested" / flam3_filename(248, 100)).write_bytes(b"<flame/>")
        corpus = tmp_path / "corpus"
        stats = import_dir(src, corpus)
        assert stats.imported == 1
        assert flam3_path(248, 100, corpus).exists()


class TestImportSkipsExisting:
    def test_skips_when_already_in_corpus(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        corpus = tmp_path / "corpus"
        # Pre-populate corpus
        dest = flam3_path(248, 100, corpus)
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
        (src / "weird-name.flam3").write_bytes(b"<flame/>")
        _drop_flam3(src, 248, 100)
        corpus = tmp_path / "corpus"
        stats = import_dir(src, corpus)
        assert stats.imported == 1


class TestImportDeadGen:
    """The former 'whole-gen' path is now the default and only path."""

    def _build_scrape(
        self,
        src: Path,
        gen: int,
        present_ids: list[int],
        missing_ids: list[int],
    ) -> None:
        src.mkdir(parents=True, exist_ok=True)
        for sid in present_ids:
            _drop_flam3(src, gen, sid)
        if missing_ids:
            (src / "_missing_404.txt").write_text(
                "\n".join(str(m) for m in missing_ids) + "\n"
            )

    def test_imports_and_merges_missing(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(
            src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6]
        )

        stats = import_dir(src, corpus, gen=244)

        assert stats.imported == 2
        for sid in (3, 7):
            assert flam3_path(244, sid, corpus).exists()
        # No sealing; no zip
        assert not list((corpus / "244").glob("*.zip"))

    def test_missing_txt_populated(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(
            src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6]
        )

        import_dir(src, corpus, gen=244)

        missing_file = corpus / "244" / "missing.txt"
        assert missing_file.exists()
        ms = MissingSet(missing_file)
        ms.load()
        assert {0, 1, 2, 4, 5, 6} <= set(ms._ids)  # noqa: SLF001 — test of internals

    def test_gen_inferred_from_filenames(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(
            src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6]
        )

        # gen omitted; should auto-infer
        stats = import_dir(src, corpus)
        assert stats.imported == 2
        # Missing also merged when gen could be inferred from a single-gen src.
        ms = MissingSet(corpus / "244" / "missing.txt")
        ms.load()
        assert ms.contains(0)
        assert ms.contains(6)

    def test_multiple_gens_in_src_errors_without_explicit_gen(self, tmp_path: Path):
        src = tmp_path / "mixed"
        src.mkdir()
        _drop_flam3(src, 244, 0)
        _drop_flam3(src, 245, 0)
        corpus = tmp_path / "corpus"

        with pytest.raises(ValueError, match="multiple gens"):
            import_dir(src, corpus)

    def test_empty_src_is_noop(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        src.mkdir()
        corpus = tmp_path / "corpus"

        stats = import_dir(src, corpus, gen=244)

        assert stats.imported == 0
        assert stats.skipped == 0

    def test_idempotent(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(
            src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6]
        )

        first = import_dir(src, corpus, gen=244)
        second = import_dir(src, corpus, gen=244)

        assert first.imported == 2
        assert first.skipped == 0
        assert second.imported == 0
        assert second.skipped == 2
