"""Tests for electric_sheep_fold.migration — v0.1 bucket → v0.4 chunked
and v0.3 flat → v0.4 chunked."""
from __future__ import annotations

import json
from pathlib import Path

from electric_sheep_fold.layout import bucket_for, flam3_filename, flam3_path
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import (
    CHUNKED_VERIFIED_FILENAME,
    migrate_v0_1_if_needed,
    migrate_v3_to_v4_chunked,
    verify_chunked_consistency,
)


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


class TestMigratesIntoChunkedDir:
    def test_single_sheep(self, tmp_path: Path):
        _make_v0_1_bucket(tmp_path, 248, 100, b"<flame/>")
        result = migrate_v0_1_if_needed(tmp_path, 248)
        assert result is True
        # v0.4: lives under per-10k bucket dir, not v0.1's per-1k "00xxx" or
        # v0.3's flat layout.
        new_dest = flam3_path(248, 100, tmp_path)
        assert new_dest == tmp_path / "248" / "00000" / flam3_filename(248, 100)
        assert new_dest.exists()
        assert new_dest.read_bytes() == b"<flame/>"
        # Old v0.1 bucket removed
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


# ----- v0.3 flat → v0.4 chunked migration ------------------------------------


def _make_flat_flam3(corpus: Path, gen: int, sheep_id: int, content: bytes) -> Path:
    """Drop a v0.3-style flat .flam3 file at corpus/{gen}/{filename}."""
    gen_root = corpus / str(gen)
    gen_root.mkdir(parents=True, exist_ok=True)
    dest = gen_root / flam3_filename(gen, sheep_id)
    dest.write_bytes(content)
    return dest


def _make_chunked_flam3(corpus: Path, gen: int, sheep_id: int, content: bytes) -> Path:
    """Drop a v0.4-style chunked .flam3 file at corpus/{gen}/{bucket}/{filename}."""
    dest = flam3_path(gen, sheep_id, corpus)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return dest


class TestMigrateV3FlatToV4Chunked:
    def test_single_flat_file_moves_to_bucket(self, tmp_path: Path):
        _make_flat_flam3(tmp_path, 248, 100, b"<flame/>")
        results = migrate_v3_to_v4_chunked(tmp_path)
        assert len(results) == 1
        r = results[0]
        assert r.gen == 248
        assert r.moved == 1
        assert r.already_chunked == 0
        assert r.loose_count == 1
        # File now lives under the chunked path
        assert (tmp_path / "248" / "00000" / "electricsheep.248.00100.flam3").exists()
        # And NO flat residual at the gen root
        assert not (tmp_path / "248" / "electricsheep.248.00100.flam3").exists()

    def test_multiple_buckets_in_same_gen(self, tmp_path: Path):
        for sid in (50, 15_000, 25_000, 99_999):
            _make_flat_flam3(tmp_path, 247, sid, f"id-{sid}".encode())
        results = migrate_v3_to_v4_chunked(tmp_path)
        r = results[0]
        assert r.moved == 4
        assert r.bucket_count == 4  # one bucket per id since they're 10k apart
        for sid in (50, 15_000, 25_000, 99_999):
            assert flam3_path(247, sid, tmp_path).exists()
        # Sanity: bucket for id=99999 is "90000", not "99999"
        assert (tmp_path / "247" / "90000" / "electricsheep.247.99999.flam3").exists()

    def test_already_chunked_is_noop(self, tmp_path: Path):
        _make_chunked_flam3(tmp_path, 248, 100, b"a")
        results = migrate_v3_to_v4_chunked(tmp_path)
        r = results[0]
        assert r.moved == 0
        assert r.already_chunked == 1
        assert r.loose_count == 1

    def test_hybrid_corpus_moves_only_flat(self, tmp_path: Path):
        # 2 files already in bucket, 3 still flat
        _make_chunked_flam3(tmp_path, 248, 100, b"a")
        _make_chunked_flam3(tmp_path, 248, 10_001, b"b")
        _make_flat_flam3(tmp_path, 248, 200, b"c")
        _make_flat_flam3(tmp_path, 248, 5_000, b"d")
        _make_flat_flam3(tmp_path, 248, 50_000, b"e")
        results = migrate_v3_to_v4_chunked(tmp_path)
        r = results[0]
        assert r.moved == 3
        assert r.already_chunked == 2
        assert r.loose_count == 5
        # All 5 now accessible via flam3_path
        for sid in (100, 200, 5_000, 10_001, 50_000):
            assert flam3_path(248, sid, tmp_path).exists()

    def test_missing_txt_stays_at_gen_root(self, tmp_path: Path):
        gen_root = tmp_path / "247"
        gen_root.mkdir(parents=True)
        (gen_root / "missing.txt").write_text("1\n2\n3\n")
        _make_flat_flam3(tmp_path, 247, 100, b"<flame/>")
        results = migrate_v3_to_v4_chunked(tmp_path)
        # missing.txt should still be at gen root, not moved into a bucket
        assert (gen_root / "missing.txt").exists()
        assert (gen_root / "missing.txt").read_text() == "1\n2\n3\n"
        assert results[0].missing_count == 3

    def test_idempotent_on_rerun(self, tmp_path: Path):
        _make_flat_flam3(tmp_path, 248, 100, b"<flame/>")
        _make_flat_flam3(tmp_path, 248, 15_000, b"<flame/>")
        migrate_v3_to_v4_chunked(tmp_path)
        # Re-run: nothing to move
        results = migrate_v3_to_v4_chunked(tmp_path)
        r = results[0]
        assert r.moved == 0
        assert r.already_chunked == 2

    def test_writes_chunked_verified_json(self, tmp_path: Path):
        _make_flat_flam3(tmp_path, 248, 100, b"a")
        _make_flat_flam3(tmp_path, 247, 5_000, b"b")
        migrate_v3_to_v4_chunked(tmp_path)
        verified = tmp_path / CHUNKED_VERIFIED_FILENAME
        assert verified.exists()
        payload = json.loads(verified.read_text())
        assert payload["schema"] == "v0.4"
        gens = {g["gen"]: g for g in payload["gens"]}
        assert gens[248]["loose_count"] == 1
        assert gens[248]["bucket_count"] == 1
        assert gens[247]["loose_count"] == 1

    def test_atomic_move_preserves_content(self, tmp_path: Path):
        original = b"<flame name='preserved'/>"
        _make_flat_flam3(tmp_path, 248, 100, original)
        migrate_v3_to_v4_chunked(tmp_path)
        moved = flam3_path(248, 100, tmp_path)
        assert moved.read_bytes() == original

    def test_skips_non_flam3_files_at_gen_root(self, tmp_path: Path):
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        (gen_root / "missing.txt").write_text("1\n")
        (gen_root / "README.txt").write_text("note")
        _make_flat_flam3(tmp_path, 248, 100, b"<flame/>")
        results = migrate_v3_to_v4_chunked(tmp_path)
        assert results[0].moved == 1
        # Non-flam3 files survive at gen root
        assert (gen_root / "missing.txt").exists()
        assert (gen_root / "README.txt").exists()


class TestVerifyChunkedConsistency:
    def test_fresh_empty_corpus_is_consistent(self, tmp_path: Path):
        """No baseline file + no data is NOT a divergence — permissive for
        fresh corpora and test fixtures."""
        (tmp_path / "248").mkdir()
        assert verify_chunked_consistency(tmp_path) == []

    def test_flat_residual_without_baseline_is_a_divergence(self, tmp_path: Path):
        """Flat files at gen root signal incomplete migration even without
        a baseline file — the actual safety check."""
        gen_root = tmp_path / "248"
        gen_root.mkdir()
        (gen_root / "electricsheep.248.00100.flam3").write_bytes(b"x")
        divs = verify_chunked_consistency(tmp_path)
        assert divs
        assert any("migrate-chunked" in reason for _, reason in divs)

    def test_consistent_post_migrate(self, tmp_path: Path):
        _make_flat_flam3(tmp_path, 248, 100, b"a")
        _make_flat_flam3(tmp_path, 248, 15_000, b"b")
        migrate_v3_to_v4_chunked(tmp_path)
        assert verify_chunked_consistency(tmp_path) == []

    def test_residual_flat_file_is_a_divergence(self, tmp_path: Path):
        # Migrate one file cleanly
        _make_flat_flam3(tmp_path, 248, 100, b"a")
        migrate_v3_to_v4_chunked(tmp_path)
        # Then someone manually drops a flat file post-migration
        (tmp_path / "248" / "electricsheep.248.50000.flam3").write_bytes(b"x")
        divs = verify_chunked_consistency(tmp_path)
        assert divs
        assert any("flat .flam3" in reason for _, reason in divs)

    def test_shrinkage_below_baseline_is_a_divergence(self, tmp_path: Path):
        _make_flat_flam3(tmp_path, 248, 100, b"a")
        _make_flat_flam3(tmp_path, 248, 15_000, b"b")
        migrate_v3_to_v4_chunked(tmp_path)
        # Delete one file post-migration
        flam3_path(248, 100, tmp_path).unlink()
        divs = verify_chunked_consistency(tmp_path)
        assert divs
        assert any("unexpected deletion" in reason for _, reason in divs)

    def test_growth_above_baseline_is_ok(self, tmp_path: Path):
        # Live gens append over time — growth is fine
        _make_flat_flam3(tmp_path, 248, 100, b"a")
        migrate_v3_to_v4_chunked(tmp_path)
        # New fetched file appears in a bucket post-migration
        _make_chunked_flam3(tmp_path, 248, 200, b"newly-fetched")
        assert verify_chunked_consistency(tmp_path) == []
