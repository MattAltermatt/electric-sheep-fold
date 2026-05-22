"""Tests for electric_sheep_fold.release — release-build (loose + sealed transit)."""
from __future__ import annotations

import csv
import hashlib
import io
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from electric_sheep_fold.layout import flam3_filename
from electric_sheep_fold.release import build_gen_zip, build_release


FLAM3_TEMPLATE = (
    b'<?xml version="1.0"?>'
    b'<flame name="t-{id}" nick="bob" url="http://x">'
    b'<xform weight="1.0" linear="1.0"/>'
    b'</flame>'
)


def _flam3_for(sheep_id: int) -> bytes:
    return FLAM3_TEMPLATE.replace(b"{id}", str(sheep_id).encode())


def _src_url(sheep_id: int) -> str:
    return f"http://test/{sheep_id}"


FETCHED_AT = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)


def _populate_loose_gen(
    corpus_root: Path,
    gen: int,
    sheep_ids: list[int],
    missing_ids: list[int],
) -> dict[int, bytes]:
    """Create corpus/{gen}/ as a loose dir with flam3s + missing.txt."""
    gen_dir = corpus_root / str(gen)
    gen_dir.mkdir(parents=True, exist_ok=True)
    contents: dict[int, bytes] = {}
    for sid in sheep_ids:
        content = _flam3_for(sid)
        (gen_dir / flam3_filename(gen, sid)).write_bytes(content)
        contents[sid] = content
    (gen_dir / "missing.txt").write_text(
        "".join(f"{m}\n" for m in sorted(missing_ids))
    )
    return contents


def _populate_sealed_gen(
    corpus_root: Path,
    gen: int,
    sheep_ids: list[int],
    missing_ids: list[int],
    *,
    start: int = 0,
    end: int | None = None,
) -> dict[int, bytes]:
    """Create corpus/{gen}/ as a v0.2 sealed zip + missing.txt (no loose)."""
    gen_dir = corpus_root / str(gen)
    gen_dir.mkdir(parents=True, exist_ok=True)
    if end is None:
        end = (max(sheep_ids) if sheep_ids else 0) + 1

    contents: dict[int, bytes] = {}
    zip_path = gen_dir / f"{start:05d}-{end - 1:05d}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Mimic v0.2 layout: MANIFEST.csv first, then flam3s.
        zf.writestr("MANIFEST.csv", "id,sha256\n")
        for sid in sheep_ids:
            content = _flam3_for(sid)
            zf.writestr(flam3_filename(gen, sid), content)
            contents[sid] = content

    (gen_dir / "missing.txt").write_text(
        "".join(f"{m}\n" for m in sorted(missing_ids))
    )
    return contents


class TestBuildGenZipLoose:
    """v0.3 native: loose .flam3 files in gen dir."""

    def test_zip_written(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 248, [10, 20, 30], [11, 12])
        path = build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        assert path == out / "gen-248.zip"
        assert path.exists()

    def test_zip_contents_present(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 248, [10, 20, 30], [11, 12])
        path = build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        assert "MANIFEST.csv" in names
        assert "missing.txt" in names
        assert flam3_filename(248, 10) in names
        assert flam3_filename(248, 20) in names
        assert flam3_filename(248, 30) in names

    def test_manifest_has_3_rows(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 248, [10, 20, 30], [11, 12])
        path = build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        with zipfile.ZipFile(path) as zf:
            text = zf.read("MANIFEST.csv").decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        assert len(rows) == 3
        assert {int(r["id"]) for r in rows} == {10, 20, 30}

    def test_missing_txt_byte_identical(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 248, [10, 20, 30], [11, 12, 13])
        original = (corpus / "248" / "missing.txt").read_bytes()
        path = build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        with zipfile.ZipFile(path) as zf:
            in_zip = zf.read("missing.txt")
        assert in_zip == original

    def test_no_tmp_zip_left_behind(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 248, [10], [])
        build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        assert not (out / "gen-248.zip.tmp").exists()


class TestBuildGenZipSealedTransit:
    """v0.2 transit mode: gen dir holds a sealed zip; release-build unpacks it."""

    def test_sealed_input_produces_release_zip(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_sealed_gen(corpus, 165, [0, 1, 2], [3, 4])
        path = build_gen_zip(165, corpus, out, fetched_at=FETCHED_AT)
        assert path.exists()
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        assert "MANIFEST.csv" in names
        assert "missing.txt" in names
        assert flam3_filename(165, 0) in names
        assert flam3_filename(165, 1) in names
        assert flam3_filename(165, 2) in names

    def test_sealed_manifest_csv_not_carried_through(self, tmp_path: Path):
        # The v0.2 MANIFEST.csv inside the sealed zip is replaced by a fresh
        # one built from extract.extract_metadata; v0.2's "id,sha256\n"
        # stub must NOT survive.
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_sealed_gen(corpus, 165, [0, 1, 2], [])
        path = build_gen_zip(165, corpus, out, fetched_at=FETCHED_AT)
        with zipfile.ZipFile(path) as zf:
            text = zf.read("MANIFEST.csv").decode("utf-8")
        # Fresh manifest has the full 11-column header.
        assert "id,sha256,file_size_bytes,fetched_at,source_url" in text

    def test_sealed_missing_txt_preserved(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_sealed_gen(corpus, 165, [0, 1], [99, 100, 101])
        original = (corpus / "165" / "missing.txt").read_bytes()
        path = build_gen_zip(165, corpus, out, fetched_at=FETCHED_AT)
        with zipfile.ZipFile(path) as zf:
            assert zf.read("missing.txt") == original


class TestSha256MatchesManifest:
    def test_each_flam3_sha256_matches_row(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        ids = [5, 10, 15, 20]
        _populate_loose_gen(corpus, 248, ids, [6, 7])
        path = build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        with zipfile.ZipFile(path) as zf:
            manifest_text = zf.read("MANIFEST.csv").decode("utf-8")
            by_id = {
                int(r["id"]): r
                for r in csv.DictReader(io.StringIO(manifest_text))
            }
            for sid in ids:
                blob = zf.read(flam3_filename(248, sid))
                assert hashlib.sha256(blob).hexdigest() == by_id[sid]["sha256"]
                assert int(by_id[sid]["file_size_bytes"]) == len(blob)


class TestBuildReleaseFull:
    def test_full_build_writes_expected_artifacts(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 165, [0, 1, 2], [3])
        _populate_loose_gen(corpus, 248, [10, 20], [11])
        # ATTRIBUTION.md at corpus root (build_release copies it through).
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        written = build_release(corpus, out)
        names = {p.name for p in written}

        assert "gen-165.zip" in names
        assert "gen-248.zip" in names
        assert "corpus-all.zip" in names
        assert "INDEX.md" in names
        assert "index.json" in names
        assert "ATTRIBUTION.md" in names
        # Each listed path exists on disk.
        for p in written:
            assert p.exists(), p

    def test_mega_bundle_contains_gen_zips(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 165, [0, 1], [])
        _populate_loose_gen(corpus, 248, [10], [])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")
        build_release(corpus, out)
        with zipfile.ZipFile(out / "corpus-all.zip") as zf:
            names = set(zf.namelist())
        assert "gen-165.zip" in names
        assert "gen-248.zip" in names
        assert "INDEX.md" in names
        assert "index.json" in names
        assert "ATTRIBUTION.md" in names


class TestBuildReleaseSingleGen:
    def test_only_gen_skips_mega_and_index(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 165, [0, 1, 2], [])
        _populate_loose_gen(corpus, 248, [10, 20], [])

        written = build_release(corpus, out, only_gen=165)
        names = {p.name for p in written}

        assert "gen-165.zip" in names
        # Single-gen mode: no other gen zips, no mega-bundle, no index copies.
        assert "gen-248.zip" not in names
        assert "corpus-all.zip" not in names
        assert "INDEX.md" not in names
        assert "index.json" not in names

        # Side-effect check: nothing else in the out dir either.
        out_files = {p.name for p in out.iterdir()}
        assert out_files == {"gen-165.zip"}


class TestCLISmoke:
    def test_release_build_help(self):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["release-build", "--help"])
        assert result.exit_code == 0
        assert "release" in result.output.lower()

    def test_release_build_runs(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 165, [0, 1], [2])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "release-build",
                "--corpus", str(corpus),
                "--out", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert (out / "gen-165.zip").exists()
        assert (out / "corpus-all.zip").exists()

    def test_release_build_single_gen_cli(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_loose_gen(corpus, 165, [0, 1], [])
        _populate_loose_gen(corpus, 248, [10], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "release-build",
                "--corpus", str(corpus),
                "--out", str(out),
                "--gen", "165",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (out / "gen-165.zip").exists()
        assert not (out / "gen-248.zip").exists()
        assert not (out / "corpus-all.zip").exists()
