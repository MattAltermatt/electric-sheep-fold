"""Tests for the CLI — range parsing + smoke for fetch / fetch-all / import / seal / status."""
from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from electric_sheep_fold.cli import _parse_chunk_range, _parse_range, app
from electric_sheep_fold.layout import flam3_filename, working_path

runner = CliRunner()


class TestParseRange:
    def test_valid(self):
        assert _parse_range("0..100") == (0, 100)

    @pytest.mark.parametrize("bad", ["0,100", "0..", "..100", "abc..def", ""])
    def test_invalid_format(self, bad):
        with pytest.raises(typer.BadParameter):
            _parse_range(bad)

    def test_empty_range_rejected(self):
        with pytest.raises(typer.BadParameter):
            _parse_range("100..100")

    def test_inverted_range_rejected(self):
        with pytest.raises(typer.BadParameter):
            _parse_range("100..50")


class TestParseChunkRange:
    def test_valid_standard_chunk(self):
        assert _parse_chunk_range("00000-09999") == (0, 10_000)

    def test_valid_second_chunk(self):
        assert _parse_chunk_range("10000-19999") == (10_000, 20_000)

    def test_inverted_range_rejected(self):
        with pytest.raises(typer.BadParameter):
            _parse_chunk_range("00100-00099")

    @pytest.mark.parametrize("bad", ["not-a-range", "0-9999", "00000..09999", ""])
    def test_malformed_rejected(self, bad):
        with pytest.raises(typer.BadParameter):
            _parse_chunk_range(bad)


class TestHelp:
    def test_top_level(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Polite mirror" in result.output

    def test_fetch_help(self):
        assert runner.invoke(app, ["fetch", "--help"]).exit_code == 0

    def test_fetch_all_help(self):
        assert runner.invoke(app, ["fetch-all", "--help"]).exit_code == 0

    def test_import_help(self):
        assert runner.invoke(app, ["import", "--help"]).exit_code == 0

    def test_seal_help(self):
        assert runner.invoke(app, ["seal", "--help"]).exit_code == 0

    def test_status_help(self):
        assert runner.invoke(app, ["status", "--help"]).exit_code == 0


class TestStatusNoCorpus:
    def test_friendly_message(self, tmp_path: Path):
        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "not yet materialized" in result.output


class TestStatusWithChunks:
    def test_reports_chunk_breakdown(self, tmp_path: Path):
        # Create a working chunk + a sealed zip (fake — just an empty zip file)
        import zipfile
        gen_root = tmp_path / "248"
        (gen_root / "00000-09999").mkdir(parents=True)
        (gen_root / "00000-09999" / flam3_filename(248, 100)).write_bytes(b"<flame/>")
        sealed = gen_root / "10000-19999.zip"
        with zipfile.ZipFile(sealed, "w") as zf:
            zf.writestr("MANIFEST.csv", "id\n")
        (gen_root / "missing.txt").write_text("500\n600\n")

        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 sealed" in result.output
        assert "1 working" in result.output
        assert "2 known-missing" in result.output


class TestImportSmoke:
    def test_imports_a_file(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / flam3_filename(248, 100)).write_bytes(b"<flame/>")
        corpus = tmp_path / "corpus"
        result = runner.invoke(app, ["import", str(src), "--corpus", str(corpus)])
        assert result.exit_code == 0
        assert "imported 1" in result.output
        assert working_path(248, 100, corpus).exists()


class TestLiveGenGuard:
    """fetch / fetch-all refuse gens not in LIVE_GENS (247, 248)."""

    @pytest.mark.parametrize("dead_gen", [165, 169, 191, 198, 242, 243, 244, 245])
    def test_fetch_rejects_dead_gen(self, tmp_path: Path, dead_gen: int):
        result = runner.invoke(
            app,
            ["fetch", "0..1", "--gen", str(dead_gen), "--corpus", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "not a live gen" in result.output
        assert "--whole-gen" in result.output

    @pytest.mark.parametrize("dead_gen", [165, 244])
    def test_fetch_all_rejects_dead_gen(self, tmp_path: Path, dead_gen: int):
        result = runner.invoke(
            app,
            ["fetch-all", "--gen", str(dead_gen), "--upper", "10", "--corpus", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "not a live gen" in result.output

    @pytest.mark.parametrize("future_gen", [249, 300])
    def test_fetch_rejects_future_gen_until_added(self, tmp_path: Path, future_gen: int):
        """Forward-compat reminder: extending LIVE_GENS is a deliberate edit."""
        result = runner.invoke(
            app,
            ["fetch", "0..1", "--gen", str(future_gen), "--corpus", str(tmp_path)],
        )
        assert result.exit_code != 0
        assert "not a live gen" in result.output
