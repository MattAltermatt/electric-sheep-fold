"""Tests for electric_sheep_fold.unseal — v0.2 → v0.3 migration tool."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from electric_sheep_fold.extract import MANIFEST_COLUMNS, extract_metadata
from electric_sheep_fold.layout import flam3_filename
from electric_sheep_fold.unseal import (
    UnsealResult,
    unseal_gen,
    verify_unseal_consistency,
)


FLAM3_TEMPLATE = (
    b'<?xml version="1.0"?>'
    b'<flame name="t-{id}" nick="bob" url="http://x">'
    b'<xform weight="1.0" linear="1.0"/>'
    b'</flame>'
)


def _flam3_for(sheep_id: int) -> bytes:
    return FLAM3_TEMPLATE.replace(b"{id}", str(sheep_id).encode())


FETCHED_AT = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


def _make_sealed_zip(
    gen_dir: Path,
    gen: int,
    sheep_ids: list[int],
    *,
    start: int = 0,
    end: int | None = None,
) -> tuple[Path, dict[int, bytes]]:
    """Construct a v0.2-shape sealed zip in ``gen_dir`` with a real MANIFEST.csv.

    The MANIFEST.csv carries true sha256 / file_size_bytes for each flam3
    so verification can succeed (unlike test_release.py's "id,sha256\\n"
    stub which is meant to be discarded by release-build).
    """
    gen_dir.mkdir(parents=True, exist_ok=True)
    if end is None:
        end = (max(sheep_ids) if sheep_ids else 0) + 1

    contents: dict[int, bytes] = {sid: _flam3_for(sid) for sid in sheep_ids}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=MANIFEST_COLUMNS)
    writer.writeheader()
    for sid in sorted(sheep_ids):
        writer.writerow(
            extract_metadata(
                content=contents[sid],
                sheep_id=sid,
                source_url=f"http://test/{sid}",
                fetched_at=FETCHED_AT,
            )
        )
    manifest_bytes = buf.getvalue().encode("utf-8")

    zip_path = gen_dir / f"{start:05d}-{end - 1:05d}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("MANIFEST.csv", manifest_bytes)
        for sid in sorted(sheep_ids):
            zf.writestr(flam3_filename(gen, sid), contents[sid])
    return zip_path, contents


def _populate_v0_2_gen(
    corpus_root: Path,
    gen: int,
    sheep_ids: list[int],
    missing_ids: list[int],
) -> tuple[Path, dict[int, bytes]]:
    """Build a v0.2-shape gen dir: sealed zip + missing.txt."""
    gen_dir = corpus_root / str(gen)
    zip_path, contents = _make_sealed_zip(gen_dir, gen, sheep_ids)
    (gen_dir / "missing.txt").write_text(
        "".join(f"{m}\n" for m in sorted(missing_ids))
    )
    return zip_path, contents


# ----- Round-trip ------------------------------------------------------------


class TestUnsealRoundTrip:
    def test_unseal_synthetic_gen_round_trip(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        zip_path, contents = _populate_v0_2_gen(
            corpus, 165, [0, 1, 2, 3, 4], [99, 100]
        )

        result = unseal_gen(165, corpus)

        assert isinstance(result, UnsealResult)
        assert result.gen == 165
        assert result.loose_count == 5
        assert result.missing_count == 2
        assert result.skipped is False

        gen_dir = corpus / "165"
        # Loose .flam3 files all present.
        for sid in contents:
            p = gen_dir / flam3_filename(165, sid)
            assert p.exists(), p
            assert p.read_bytes() == contents[sid]
        # MANIFEST.csv preserved.
        assert (gen_dir / "MANIFEST.csv").exists()
        # missing.txt preserved.
        assert (gen_dir / "missing.txt").exists()
        # Source zip gone.
        assert not zip_path.exists()
        # Marker gone.
        assert not (gen_dir / ".unseal-state").exists()
        # Tmp dir gone.
        assert not (gen_dir / ".unseal-tmp").exists()
        # Verified-log row written.
        log_path = corpus / "_unseal-verified.json"
        records = json.loads(log_path.read_text())
        assert len(records) == 1
        assert records[0]["gen"] == 165
        assert records[0]["loose_count"] == 5
        assert records[0]["missing_count"] == 2
        assert "unsealed_at" in records[0]

    def test_unseal_byte_identity(self, tmp_path: Path):
        """Each loose .flam3 has the same sha256 as the source-zip member."""
        corpus = tmp_path / "corpus"
        zip_path, contents = _populate_v0_2_gen(corpus, 248, [10, 20, 30], [])

        # Compute expected sha256s from the original-content fixture.
        expected = {
            sid: hashlib.sha256(b).hexdigest() for sid, b in contents.items()
        }

        unseal_gen(248, corpus)

        gen_dir = corpus / "248"
        for sid, expected_sha in expected.items():
            blob = (gen_dir / flam3_filename(248, sid)).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == expected_sha

    def test_unseal_preserves_missing_txt(self, tmp_path: Path):
        """missing.txt is byte-identical pre- and post-unseal."""
        corpus = tmp_path / "corpus"
        _populate_v0_2_gen(corpus, 165, [0, 1], [50, 60, 70])
        original_bytes = (corpus / "165" / "missing.txt").read_bytes()

        unseal_gen(165, corpus)

        assert (corpus / "165" / "missing.txt").read_bytes() == original_bytes


# ----- SIGKILL recovery ------------------------------------------------------


class TestSigKillRecovery:
    def test_sigkill_mid_extract_partial_tmp_recovers(self, tmp_path: Path):
        """Pre-populate `.unseal-state=extracted` + PARTIAL .unseal-tmp/.

        Behavior: if the tmp dir's file count doesn't match the source-zip
        member count, the implementation nukes and re-extracts. Step (c)
        sha256-verifies the result either way, so this is the safer
        choice (compared to "continue from partial").
        """
        corpus = tmp_path / "corpus"
        _, contents = _populate_v0_2_gen(corpus, 165, [0, 1, 2, 3, 4], [])

        gen_dir = corpus / "165"
        tmp_dir = gen_dir / ".unseal-tmp"
        tmp_dir.mkdir()
        # Drop 3 of 5 flam3s + MANIFEST stub (deliberately incomplete + wrong).
        (tmp_dir / flam3_filename(165, 0)).write_bytes(_flam3_for(0))
        (tmp_dir / flam3_filename(165, 1)).write_bytes(_flam3_for(1))
        (tmp_dir / flam3_filename(165, 2)).write_bytes(_flam3_for(2))
        (tmp_dir / "MANIFEST.csv").write_text("id\n")  # stub
        (gen_dir / ".unseal-state").write_text("extracted")

        result = unseal_gen(165, corpus)
        assert result.loose_count == 5
        assert result.skipped is False
        # All five expected files now present at their final paths.
        for sid in contents:
            assert (gen_dir / flam3_filename(165, sid)).exists()

    def test_idempotent_completed(self, tmp_path: Path):
        """Running unseal twice: second call returns skipped=True."""
        corpus = tmp_path / "corpus"
        _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])
        first = unseal_gen(165, corpus)
        second = unseal_gen(165, corpus)
        assert first.skipped is False
        assert second.skipped is True
        assert second.gen == 165
        # Counts come through from the log even on the skipped path.
        assert second.loose_count == 3
        assert second.missing_count == 0

    def test_idempotent_verified_resumes_from_d(self, tmp_path: Path):
        """Pre-populate `.unseal-state=verified` with complete .unseal-tmp/.

        unseal_gen should resume from step (d) without re-doing (b)/(c).
        Verify by writing a sentinel sha256-correct flam3 set + a custom
        MANIFEST.csv with a recognizable timestamp, then asserting the
        resulting gen dir has that MANIFEST.csv intact (vs a regenerated
        one).
        """
        corpus = tmp_path / "corpus"
        zip_path, contents = _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])

        gen_dir = corpus / "165"
        tmp_dir = gen_dir / ".unseal-tmp"
        tmp_dir.mkdir()

        # Hand-construct a real MANIFEST.csv matching the contents.
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        for sid in sorted(contents):
            w.writerow(
                extract_metadata(
                    content=contents[sid],
                    sheep_id=sid,
                    source_url="sentinel://verified-resume",
                    fetched_at=FETCHED_AT,
                )
            )
        manifest_bytes = buf.getvalue().encode("utf-8")
        (tmp_dir / "MANIFEST.csv").write_bytes(manifest_bytes)
        for sid in contents:
            (tmp_dir / flam3_filename(165, sid)).write_bytes(contents[sid])
        (gen_dir / ".unseal-state").write_text("verified")

        result = unseal_gen(165, corpus)
        assert result.skipped is False
        # The sentinel-marked MANIFEST.csv we hand-wrote was preserved
        # (proof we didn't re-extract from the source zip, which would
        # have replaced it with the original-source MANIFEST).
        assert (gen_dir / "MANIFEST.csv").read_bytes() == manifest_bytes
        # All flam3s in place.
        for sid in contents:
            assert (gen_dir / flam3_filename(165, sid)).exists()


# ----- Snapshot semantics ----------------------------------------------------


class TestSnapshot:
    def test_snapshot_idempotent_same_sha(self, tmp_path: Path):
        """Pre-existing snapshot with matching sha256 is reused, not recopied."""
        corpus = tmp_path / "corpus"
        snapshot_root = tmp_path / "snap"
        zip_path, _ = _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])

        snap_path = snapshot_root / "gen-165.zip"
        snap_path.parent.mkdir(parents=True)
        snap_path.write_bytes(zip_path.read_bytes())
        snap_mtime_before = snap_path.stat().st_mtime

        result = unseal_gen(165, corpus, snapshot_root=snapshot_root)
        assert result.skipped is False
        assert result.snapshot_path == snap_path
        # Snapshot file untouched (same mtime — would have changed on copy).
        assert snap_path.stat().st_mtime == snap_mtime_before

    def test_snapshot_sha_mismatch_errors(self, tmp_path: Path):
        """Pre-existing snapshot with different sha256 is a hard error."""
        corpus = tmp_path / "corpus"
        snapshot_root = tmp_path / "snap"
        _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])

        snap_path = snapshot_root / "gen-165.zip"
        snap_path.parent.mkdir(parents=True)
        snap_path.write_bytes(b"DIFFERENT-FILE-CONTENT")

        with pytest.raises(RuntimeError, match="snapshot sha256 mismatch"):
            unseal_gen(165, corpus, snapshot_root=snapshot_root)


# ----- Verify-unseal consistency ---------------------------------------------


class TestVerifyConsistency:
    def test_consistency_happy_path(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        _populate_v0_2_gen(corpus, 165, [0, 1, 2], [99])
        _populate_v0_2_gen(corpus, 248, [10, 20], [11])
        unseal_gen(165, corpus)
        unseal_gen(248, corpus)

        divergences = verify_unseal_consistency(corpus)
        assert divergences == []

    def test_consistency_detects_deleted_flam3(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])
        unseal_gen(165, corpus)

        # Simulate corpus drift: delete one .flam3 by hand.
        (corpus / "165" / flam3_filename(165, 1)).unlink()

        divergences = verify_unseal_consistency(corpus)
        assert len(divergences) == 1
        gen, reason = divergences[0]
        assert gen == 165
        assert "drift" in reason.lower()

    def test_consistency_detects_truncated_missing_txt(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        _populate_v0_2_gen(corpus, 165, [0, 1], [50, 60, 70])
        unseal_gen(165, corpus)

        # Truncate missing.txt — lose 2 of 3 entries.
        (corpus / "165" / "missing.txt").write_text("50\n")

        divergences = verify_unseal_consistency(corpus)
        assert len(divergences) == 1
        assert divergences[0][0] == 165


# ----- CLI smoke -------------------------------------------------------------


class TestCLISmoke:
    def test_unseal_help(self):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["unseal", "--help"])
        assert result.exit_code == 0
        assert "unseal" in result.output.lower()

    def test_unseal_dry_run_does_not_touch_disk(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        zip_path, _ = _populate_v0_2_gen(corpus, 165, [0, 1, 2], [99])
        before_zip_bytes = zip_path.read_bytes()
        before_missing_bytes = (corpus / "165" / "missing.txt").read_bytes()

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "unseal",
                "--gen", "165",
                "--corpus", str(corpus),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        # No mutation.
        assert zip_path.read_bytes() == before_zip_bytes
        assert (corpus / "165" / "missing.txt").read_bytes() == before_missing_bytes
        assert not (corpus / "165" / ".unseal-state").exists()
        assert not (corpus / "165" / ".unseal-tmp").exists()
        assert not (corpus / "_unseal-verified.json").exists()

    def test_unseal_gen_via_cli(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        zip_path, _ = _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "unseal",
                "--gen", "165",
                "--corpus", str(corpus),
                "--snapshot-root", str(tmp_path / "snap"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert not zip_path.exists()
        assert (corpus / "165" / flam3_filename(165, 1)).exists()
        assert (tmp_path / "snap" / "gen-165.zip").exists()

    def test_verify_unseal_via_cli(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        _populate_v0_2_gen(corpus, 165, [0, 1, 2], [])
        unseal_gen(165, corpus)

        runner = CliRunner()
        result = runner.invoke(
            app, ["verify-unseal", "--corpus", str(corpus)]
        )
        assert result.exit_code == 0, result.output
        assert "ok" in result.output.lower()
