"""Tests for electric_sheep_fold.importer — bulk import existing local flames."""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

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


class TestImportWholeGen:
    """Whole-gen mode (v0.2.1): dead-preserved gens seal as one zip."""

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

    def test_seals_single_zip_with_correct_range(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6])

        stats = import_dir(src, corpus, whole_gen=True, gen=244)

        assert stats.imported == 2
        assert stats.sealed == 1
        zip_path = corpus / "244" / "00000-00007.zip"
        assert zip_path.exists()
        # Working dir is removed on seal
        assert not (corpus / "244" / "00000-00007").exists()

    def test_manifest_carries_archive_urls(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6])

        import_dir(src, corpus, whole_gen=True, gen=244)

        zip_path = corpus / "244" / "00000-00007.zip"
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = zf.read("MANIFEST.csv").decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(manifest)))
        assert len(rows) == 2
        assert {int(r["id"]) for r in rows} == {3, 7}
        for r in rows:
            assert r["source_url"].startswith("https://electricsheep.com/archives/generation-244/")
            assert r["source_url"].endswith("/spex")

    def test_missing_txt_populated(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6])

        import_dir(src, corpus, whole_gen=True, gen=244)

        missing_file = corpus / "244" / "missing.txt"
        assert missing_file.exists()
        ids_on_disk = {int(line) for line in missing_file.read_text().splitlines() if line.strip()}
        assert ids_on_disk == {0, 1, 2, 4, 5, 6}

    def test_gen_inferred_from_filenames(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6])

        stats = import_dir(src, corpus, whole_gen=True)  # gen omitted

        assert stats.sealed == 1
        assert (corpus / "244" / "00000-00007.zip").exists()

    def test_multiple_gens_in_src_errors_without_explicit_gen(self, tmp_path: Path):
        src = tmp_path / "mixed"
        src.mkdir()
        _drop_flam3(src, 244, 0)
        _drop_flam3(src, 245, 0)
        corpus = tmp_path / "corpus"

        with pytest.raises(ValueError, match="multiple gens"):
            import_dir(src, corpus, whole_gen=True)

    def test_empty_src_is_noop(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        src.mkdir()
        corpus = tmp_path / "corpus"

        stats = import_dir(src, corpus, whole_gen=True, gen=244)

        assert stats.imported == 0
        assert stats.sealed == 0
        assert not (corpus / "244" / "00000-00000.zip").exists()

    def test_idempotent_after_seal(self, tmp_path: Path):
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        self._build_scrape(src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 5, 6])

        first = import_dir(src, corpus, whole_gen=True, gen=244)
        second = import_dir(src, corpus, whole_gen=True, gen=244)

        assert first.sealed == 1
        assert second.sealed == 0
        assert second.imported == 0

    def test_range_incomplete_leaves_chunk_working(self, tmp_path: Path):
        """If some id in [0, max_id] has no flam3 AND no missing entry, no seal."""
        src = tmp_path / "_scrape-244"
        corpus = tmp_path / "corpus"
        # max_id will be 7 (from flam3 id=7). id=5 has neither file nor missing entry.
        self._build_scrape(src, gen=244, present_ids=[3, 7], missing_ids=[0, 1, 2, 4, 6])

        stats = import_dir(src, corpus, whole_gen=True, gen=244)

        assert stats.imported == 2
        assert stats.sealed == 0
        # Chunk left as working dir
        assert (corpus / "244" / "00000-00007").exists()
        assert not (corpus / "244" / "00000-00007.zip").exists()
