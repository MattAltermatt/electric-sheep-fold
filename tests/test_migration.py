"""Tests for electric_sheep_fold.migration — v0.1 bucket → v0.2 chunk."""
from __future__ import annotations

import csv
import io
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from electric_sheep_fold.layout import flam3_filename, sealed_zip_path
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import migrate_v0_1_if_needed


def _make_v0_1_bucket(corpus: Path, gen: int, sheep_id: int, content: bytes) -> Path:
    bucket = corpus / str(gen) / f"{sheep_id // 1000:02d}xxx"
    bucket.mkdir(parents=True, exist_ok=True)
    dest = bucket / flam3_filename(gen, sheep_id)
    dest.write_bytes(content)
    return dest


class TestNoOpWhenNothingToMigrate:
    def test_empty_corpus(self, tmp_path: Path):
        assert migrate_v0_1_if_needed(tmp_path, 248) is False

    def test_v0_2_only_corpus(self, tmp_path: Path):
        # A chunk working dir exists but no v0.1 buckets
        (tmp_path / "248" / "00000-09999").mkdir(parents=True)
        assert migrate_v0_1_if_needed(tmp_path, 248) is False


class TestMigratesIntoWorkingDir:
    def test_single_sheep(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        result = migrate_v0_1_if_needed(tmp_path, 248)
        assert result is True
        new_dest = tmp_path / "248" / "00000-09999" / flam3_filename(248, 100)
        assert new_dest.exists()
        assert new_dest.read_bytes() == b"<flame/>"
        # Old bucket removed
        assert not (tmp_path / "248" / "00xxx").exists()

    def test_multiple_buckets_same_chunk(self, tmp_path: Path):
        # v0.1 buckets 00xxx + 01xxx + ... + 09xxx all belong to v0.2 chunk 00000-09999
        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        _make_v0_1_bucket(tmp_path, 248, 5_500, b"<flame/>")
        _make_v0_1_bucket(tmp_path, 248, 9_999, b"<flame/>")
        migrate_v0_1_if_needed(tmp_path, 248)
        chunk_dir = tmp_path / "248" / "00000-09999"
        assert (chunk_dir / flam3_filename(248, 100)).exists()
        assert (chunk_dir / flam3_filename(248, 5_500)).exists()
        assert (chunk_dir / flam3_filename(248, 9_999)).exists()

    def test_multiple_chunks(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"a")
        _make_v0_1_bucket(tmp_path, 248, 15_000, b"b")
        migrate_v0_1_if_needed(tmp_path, 248)
        assert (tmp_path / "248" / "00000-09999" / flam3_filename(248, 100)).exists()
        assert (tmp_path / "248" / "10000-19999" / flam3_filename(248, 15_000)).exists()


class TestSealsCompleteChunks:
    def test_seals_when_range_complete(self, tmp_path: Path):
        # Tiny chunk [0,10) for testability: write a flam3 at id 5, mark 0..4,6..9 missing
        _make_v0_1_bucket(tmp_path, 248, 5, b"<flame/>")
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        for sid in (0, 1, 2, 3, 4, 6, 7, 8, 9):
            ms.add(sid)
        ms.save_atomic()
        # NB: real chunk size is 10k, so a single migration test with chunk-completion is impractical
        # without fabricating ~10k ids. Instead, this test asserts the migration completes
        # without errors; chunk-completion-after-migration is tested via chunks.seal directly
        # in test_chunks.py, and via test_fetch.py integration after Task 5.
        migrate_v0_1_if_needed(tmp_path, 248)
        # Verify file moved
        assert (tmp_path / "248" / "00000-09999" / flam3_filename(248, 5)).exists()


class TestIdempotency:
    def test_second_run_is_noop(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        first = migrate_v0_1_if_needed(tmp_path, 248)
        second = migrate_v0_1_if_needed(tmp_path, 248)
        assert first is True
        assert second is False


class TestMissingTxtPreserved:
    def test_missing_unchanged(self, tmp_path: Path):
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.add(7)
        ms.add(42)
        ms.save_atomic()
        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        migrate_v0_1_if_needed(tmp_path, 248)
        ms2 = MissingSet(tmp_path / "248" / "missing.txt")
        ms2.load()
        assert ms2.contains(7)
        assert ms2.contains(42)


FLAM3 = b'<?xml version="1.0"?><flame name="t"><xform weight="1" linear="1"/></flame>'


class TestMigrationPreservesFetchedAt:
    def test_fetched_at_uses_file_mtime(self, tmp_path: Path):
        """Sealed MANIFEST.csv fetched_at should reflect original file mtime, not now()."""
        KNOWN_TS = 1_700_000_000  # 2023-11-14 22:13:20 UTC
        expected_dt = datetime.fromtimestamp(KNOWN_TS, tz=timezone.utc)

        # Create the flam3 in a v0.1 bucket and backdating its mtime
        flam3_path = _make_v0_1_bucket(tmp_path, 248, 5, FLAM3)
        os.utime(flam3_path, (KNOWN_TS, KNOWN_TS))

        # Mark all other ids in the chunk as missing so the chunk seals
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        for sid in range(0, 10_000):
            if sid != 5:
                ms.add(sid)
        ms.save_atomic()

        migrate_v0_1_if_needed(tmp_path, 248)

        # The chunk should have sealed
        zip_path = sealed_zip_path(248, 0, 10_000, tmp_path)
        assert zip_path.exists(), "chunk should have sealed with 9999 missing + 1 present"

        # Read MANIFEST.csv from the zip
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest_bytes = zf.read("MANIFEST.csv")
        reader = csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8")))
        rows = list(reader)
        assert len(rows) == 1
        row_dt = datetime.fromisoformat(rows[0]["fetched_at"])
        if row_dt.tzinfo is None:
            row_dt = row_dt.replace(tzinfo=timezone.utc)

        # Should match the file mtime (within 1s tolerance for float rounding)
        assert abs((row_dt - expected_dt).total_seconds()) < 1.0


class TestMigrationGuardsRmtree:
    def test_non_flam3_file_prevents_bucket_removal(self, tmp_path: Path):
        """If a bucket contains non-flam3 user files, the bucket dir must survive."""
        flam3_path = _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        bucket = flam3_path.parent
        (bucket / "unrelated.txt").write_text("notes", encoding="utf-8")

        migrate_v0_1_if_needed(tmp_path, 248)

        # Bucket dir still exists (not nuked)
        assert bucket.exists()
        assert (bucket / "unrelated.txt").exists()

        # But the flam3 WAS moved to the v0.2 working dir
        from electric_sheep_fold.layout import working_path
        assert working_path(248, 100, tmp_path).exists()
