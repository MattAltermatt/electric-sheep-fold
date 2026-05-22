"""Tests for electric_sheep_fold.migration — v0.1 bucket → v0.3 loose."""
from __future__ import annotations

from pathlib import Path

from electric_sheep_fold.layout import flam3_filename, flam3_path
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

    def test_v0_3_only_corpus(self, tmp_path: Path):
        """A loose-corpus dir without v0.1 buckets is a no-op."""
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        (gen_root / flam3_filename(248, 100)).write_bytes(b"<flame/>")
        assert migrate_v0_1_if_needed(tmp_path, 248) is False


class TestMigratesIntoLooseDir:
    def test_single_sheep(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        result = migrate_v0_1_if_needed(tmp_path, 248)
        assert result is True
        # v0.3: lives flat under corpus/{gen}/, not in a chunk subdir
        new_dest = flam3_path(248, 100, tmp_path)
        assert new_dest == tmp_path / "248" / flam3_filename(248, 100)
        assert new_dest.exists()
        assert new_dest.read_bytes() == b"<flame/>"
        # Old bucket removed
        assert not (tmp_path / "248" / "00xxx").exists()

    def test_multiple_sheep_same_bucket(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"a")
        _make_v0_1_bucket(tmp_path, 248, 500, b"b")
        _make_v0_1_bucket(tmp_path, 248, 999, b"c")
        migrate_v0_1_if_needed(tmp_path, 248)
        for sid in (100, 500, 999):
            assert flam3_path(248, sid, tmp_path).exists()
        assert not (tmp_path / "248" / "00xxx").exists()

    def test_multiple_buckets(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"a")
        _make_v0_1_bucket(tmp_path, 248, 5_500, b"b")
        _make_v0_1_bucket(tmp_path, 248, 15_000, b"c")
        migrate_v0_1_if_needed(tmp_path, 248)
        for sid in (100, 5_500, 15_000):
            assert flam3_path(248, sid, tmp_path).exists()


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


class TestMigrationGuardsRmtree:
    def test_non_flam3_file_prevents_bucket_removal(self, tmp_path: Path):
        """If a bucket contains non-flam3 user files, the bucket dir must survive."""
        flam3 = _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        bucket = flam3.parent
        (bucket / "unrelated.txt").write_text("notes", encoding="utf-8")

        migrate_v0_1_if_needed(tmp_path, 248)

        # Bucket dir still exists (not nuked)
        assert bucket.exists()
        assert (bucket / "unrelated.txt").exists()

        # But the flam3 WAS moved to the v0.3 loose path
        assert flam3_path(248, 100, tmp_path).exists()


class TestFetchPathSeesMigrationOutput:
    """Smoke-test that fetch.py's loose-path detection (``flam3_path(...).exists()``)
    correctly picks up files placed by the v0.1 → v0.3 migration. Replaces the
    v0.2-era 'chunk.contains_id' assertion."""

    def test_post_migration_path_matches_fetch_skip(self, tmp_path: Path):
        from electric_sheep_fold.layout import flam3_path

        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        migrate_v0_1_if_needed(tmp_path, 248)

        # fetch.py's local-skip predicate is exactly this:
        dest = flam3_path(248, 100, tmp_path)
        assert dest.exists()
