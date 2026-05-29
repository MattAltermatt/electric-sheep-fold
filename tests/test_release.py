"""Tests for electric_sheep_fold.release — v0.4 dated artifacts + chunked layout."""
from __future__ import annotations

import csv
import hashlib
import io
import tarfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from electric_sheep_fold.layout import bucket_for, flam3_filename, flam3_path
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
BUILD_DATE = date(2026, 5, 23)


def _populate_chunked_gen(
    corpus_root: Path,
    gen: int,
    sheep_ids: list[int],
    missing_ids: list[int],
) -> dict[int, bytes]:
    """Create corpus/{gen}/{bucket}/.flam3 + missing.txt at gen root."""
    gen_dir = corpus_root / str(gen)
    gen_dir.mkdir(parents=True, exist_ok=True)
    contents: dict[int, bytes] = {}
    for sid in sheep_ids:
        content = _flam3_for(sid)
        dest = flam3_path(gen, sid, corpus_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
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
        zf.writestr("MANIFEST.csv", "id,sha256\n")
        for sid in sheep_ids:
            content = _flam3_for(sid)
            zf.writestr(flam3_filename(gen, sid), content)
            contents[sid] = content

    (gen_dir / "missing.txt").write_text(
        "".join(f"{m}\n" for m in sorted(missing_ids))
    )
    return contents


class TestBuildGenZipChunked:
    """v0.4 native: chunked .flam3 files under per-10k bucket subdirs."""

    def test_zip_filename_includes_date(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10, 20, 30], [11, 12])
        path = build_gen_zip(
            248, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        assert path == out / "gen-248-2026-05-23.zip"
        assert path.exists()

    def test_default_date_is_today_utc(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10], [])
        path = build_gen_zip(248, corpus, out, fetched_at=FETCHED_AT)
        today = datetime.now(tz=timezone.utc).date().isoformat()
        assert path.name == f"gen-248-{today}.zip"

    def test_zip_members_use_chunked_layout(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        # ids spanning two buckets
        _populate_chunked_gen(corpus, 248, [10, 15_000], [])
        path = build_gen_zip(
            248, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        assert "MANIFEST.csv" in names
        assert "missing.txt" in names
        # Bucket-prefixed members; NO flat ones.
        assert f"{bucket_for(10)}/{flam3_filename(248, 10)}" in names
        assert f"{bucket_for(15_000)}/{flam3_filename(248, 15_000)}" in names
        assert flam3_filename(248, 10) not in names  # no flat duplicate

    def test_manifest_has_3_rows(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10, 20, 30], [11, 12])
        path = build_gen_zip(
            248, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        with zipfile.ZipFile(path) as zf:
            text = zf.read("MANIFEST.csv").decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
        assert len(rows) == 3
        assert {int(r["id"]) for r in rows} == {10, 20, 30}

    def test_missing_txt_byte_identical(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10, 20, 30], [11, 12, 13])
        original = (corpus / "248" / "missing.txt").read_bytes()
        path = build_gen_zip(
            248, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        with zipfile.ZipFile(path) as zf:
            in_zip = zf.read("missing.txt")
        assert in_zip == original

    def test_no_tmp_zip_left_behind(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10], [])
        build_gen_zip(
            248, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        assert not (out / "gen-248-2026-05-23.zip.tmp").exists()


class TestBuildGenZipSealedTransit:
    """v0.2 sealed zip in gen dir still recognized (defensive; no migration
    path should leave one behind in v0.4, but the read path is harmless)."""

    def test_sealed_input_produces_release_zip(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_sealed_gen(corpus, 165, [0, 1, 2], [3, 4])
        path = build_gen_zip(
            165, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        assert path.exists()
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
        assert "MANIFEST.csv" in names
        assert "missing.txt" in names
        # v0.4 chunked layout applies to output regardless of input shape
        assert f"{bucket_for(0)}/{flam3_filename(165, 0)}" in names


class TestSha256MatchesManifest:
    def test_each_flam3_sha256_matches_row(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        ids = [5, 10, 15, 20]
        _populate_chunked_gen(corpus, 248, ids, [6, 7])
        path = build_gen_zip(
            248, corpus, out, build_date=BUILD_DATE, fetched_at=FETCHED_AT
        )
        with zipfile.ZipFile(path) as zf:
            manifest_text = zf.read("MANIFEST.csv").decode("utf-8")
            by_id = {
                int(r["id"]): r
                for r in csv.DictReader(io.StringIO(manifest_text))
            }
            for sid in ids:
                blob = zf.read(f"{bucket_for(sid)}/{flam3_filename(248, sid)}")
                assert hashlib.sha256(blob).hexdigest() == by_id[sid]["sha256"]
                assert int(by_id[sid]["file_size_bytes"]) == len(blob)


class TestBuildReleaseFull:
    def test_full_build_writes_expected_artifacts(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1, 2], [3])
        _populate_chunked_gen(corpus, 248, [10, 20], [11])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        written = build_release(corpus, out, build_date=BUILD_DATE)
        names = {p.name for p in written}

        assert "gen-165-2026-05-23.zip" in names
        assert "gen-248-2026-05-23.zip" in names
        assert "corpus-all-2026-05-23.tar.xz" in names
        assert "INDEX.md" in names
        assert "index.json" in names
        assert "ATTRIBUTION.md" in names
        for p in written:
            assert p.exists(), p

    def test_mega_bundle_contains_chunked_tree(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1], [])
        _populate_chunked_gen(corpus, 248, [10, 15_000], [])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")
        build_release(corpus, out, build_date=BUILD_DATE)
        mega = out / "corpus-all-2026-05-23.tar.xz"
        with tarfile.open(mega, "r:xz") as tf:
            names = set(tf.getnames())
        # Per-gen MANIFEST + missing
        assert "165/MANIFEST.csv" in names
        assert "165/missing.txt" in names
        assert "248/MANIFEST.csv" in names
        # Chunked flam3 members under bucket subdirs
        assert f"165/{bucket_for(0)}/{flam3_filename(165, 0)}" in names
        assert f"248/{bucket_for(15_000)}/{flam3_filename(248, 15_000)}" in names
        # Top-level corpus assets
        assert "_index/index.json" in names
        assert "ATTRIBUTION.md" in names


class TestOverlayInvariant:
    """Load-bearing: per-gen zips + mega-bundle extract to the same tree."""

    def test_per_gen_unzip_matches_mega_subset(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1, 2], [3])
        _populate_chunked_gen(corpus, 248, [10, 15_000], [11])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")
        build_release(corpus, out, build_date=BUILD_DATE)

        # Path B — extract each per-gen zip under its gen dir
        stage_b = tmp_path / "stage_b"
        stage_b.mkdir()
        for gen in (165, 248):
            zpath = out / f"gen-{gen}-2026-05-23.zip"
            with zipfile.ZipFile(zpath) as zf:
                zf.extractall(stage_b / str(gen))

        # Path A — extract mega-bundle into another staging dir
        stage_a = tmp_path / "stage_a"
        stage_a.mkdir()
        mega = out / "corpus-all-2026-05-23.tar.xz"
        with tarfile.open(mega, "r:xz") as tf:
            tf.extractall(stage_a)

        # The per-gen subtree of A must match B exactly.
        for gen in (165, 248):
            a_tree = _walk_relative_files(stage_a / str(gen))
            b_tree = _walk_relative_files(stage_b / str(gen))
            assert a_tree == b_tree, f"gen {gen} overlay mismatch: A={a_tree} B={b_tree}"

            # And each file's contents match byte-for-byte.
            for rel in a_tree:
                a_bytes = (stage_a / str(gen) / rel).read_bytes()
                b_bytes = (stage_b / str(gen) / rel).read_bytes()
                assert a_bytes == b_bytes, f"content mismatch in {gen}/{rel}"


def _walk_relative_files(root: Path) -> set[str]:
    """Return every file's posix-style path relative to root."""
    if not root.exists():
        return set()
    out: set[str] = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root).as_posix())
    return out


class TestBuildReleaseSingleGen:
    def test_only_gen_skips_mega_and_index(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1, 2], [])
        _populate_chunked_gen(corpus, 248, [10, 20], [])

        written = build_release(corpus, out, build_date=BUILD_DATE, only_gen=165)
        names = {p.name for p in written}

        assert "gen-165-2026-05-23.zip" in names
        assert "gen-248-2026-05-23.zip" not in names
        assert "corpus-all-2026-05-23.tar.xz" not in names
        assert "INDEX.md" not in names

        out_files = {p.name for p in out.iterdir()}
        assert out_files == {"gen-165-2026-05-23.zip"}


class TestCLISmoke:
    def test_release_build_help(self):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["release-build", "--help"])
        assert result.exit_code == 0
        assert "release" in result.output.lower()

    def test_release_build_runs_with_date(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1], [2])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "release-build",
                "--corpus", str(corpus),
                "--out", str(out),
                "--date", "2026-05-23",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (out / "gen-165-2026-05-23.zip").exists()
        assert (out / "corpus-all-2026-05-23.tar.xz").exists()

    def test_release_build_single_gen_cli(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1], [])
        _populate_chunked_gen(corpus, 248, [10], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "release-build",
                "--corpus", str(corpus),
                "--out", str(out),
                "--gen", "165",
                "--date", "2026-05-23",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (out / "gen-165-2026-05-23.zip").exists()
        assert not (out / "gen-248-2026-05-23.zip").exists()
        assert not (out / "corpus-all-2026-05-23.tar.xz").exists()

    def test_release_build_rejects_malformed_date(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "release-build",
                "--corpus", str(corpus),
                "--out", str(out),
                "--date", "23-05-2026",  # wrong order
            ],
        )
        assert result.exit_code != 0


class TestBuildReleaseChunkArtifact:
    """release-build emits corpus-chunks-{date}.tar alongside other artifacts."""

    def test_full_build_emits_chunks_tar(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1, 2], [3])
        _populate_chunked_gen(corpus, 248, [10, 20], [11])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        written = build_release(corpus, out, build_date=BUILD_DATE)
        names = {p.name for p in written}

        assert "corpus-chunks-2026-05-23.tar" in names
        assert (out / "corpus-chunks-2026-05-23.tar").exists()

    def test_chunks_tar_is_valid_tar_with_gens_json(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10, 20], [])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        build_release(corpus, out, build_date=BUILD_DATE)
        chunks_tar = out / "corpus-chunks-2026-05-23.tar"
        with tarfile.open(chunks_tar, "r") as tf:
            names = set(tf.getnames())
        assert "gens.json" in names

    def test_chunks_tar_not_written_for_single_gen(self, tmp_path: Path):
        """only_gen mode skips the chunk artifact (mirrors skip_mega behaviour)."""
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 165, [0, 1], [])
        _populate_chunked_gen(corpus, 248, [10], [])

        written = build_release(corpus, out, build_date=BUILD_DATE, only_gen=165)
        names = {p.name for p in written}

        assert "corpus-chunks-2026-05-23.tar" not in names
        assert not (out / "corpus-chunks-2026-05-23.tar").exists()

    def test_chunks_tar_never_written_into_corpus(self, tmp_path: Path):
        """Chunk artifact must land in out_dir, NEVER inside corpus."""
        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10], [])
        (corpus / "ATTRIBUTION.md").write_text("# Attribution\n")

        build_release(corpus, out, build_date=BUILD_DATE)

        # No .tar files anywhere under corpus
        tar_files = list(corpus.rglob("*.tar"))
        assert tar_files == [], f"chunk artifact leaked into corpus: {tar_files}"


class TestCLIChunkCommand:
    """sheep-fold chunk subcommand — standalone chunk artifact build."""

    def test_chunk_help(self):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["chunk", "--help"])
        assert result.exit_code == 0
        assert "chunk" in result.output.lower()

    def test_chunk_produces_tar(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10, 20], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "chunk",
                "--date", "2026-05-23",
                "--corpus", str(corpus),
                "--out", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert (out / "corpus-chunks-2026-05-23.tar").exists()

    def test_chunk_tar_contains_gens_json(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "chunk",
                "--date", "2026-05-28",
                "--corpus", str(corpus),
                "--out", str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        chunks_tar = out / "corpus-chunks-2026-05-28.tar"
        with tarfile.open(chunks_tar, "r") as tf:
            names = set(tf.getnames())
        assert "gens.json" in names

    def test_chunk_rejects_malformed_date(self, tmp_path: Path):
        from typer.testing import CliRunner

        from electric_sheep_fold.cli import app

        corpus = tmp_path / "corpus"
        out = tmp_path / "out"
        _populate_chunked_gen(corpus, 248, [10], [])

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "chunk",
                "--date", "28-05-2026",
                "--corpus", str(corpus),
                "--out", str(out),
            ],
        )
        assert result.exit_code != 0
