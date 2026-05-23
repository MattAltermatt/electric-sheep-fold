"""Tests for the CLI — range parsing + smoke for fetch / fetch-all / import / status (v0.3)."""
from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from electric_sheep_fold.cli import _parse_range, app
from electric_sheep_fold.layout import flam3_filename, flam3_path

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

    def test_status_help(self):
        assert runner.invoke(app, ["status", "--help"]).exit_code == 0

    def test_release_build_help(self):
        assert runner.invoke(app, ["release-build", "--help"]).exit_code == 0

    def test_unseal_help(self):
        assert runner.invoke(app, ["unseal", "--help"]).exit_code == 0

    def test_verify_unseal_help(self):
        assert runner.invoke(app, ["verify-unseal", "--help"]).exit_code == 0


class TestSealRetired:
    """v0.3 retires the `seal` command. Guard against accidental re-introduction."""

    def test_seal_command_removed(self):
        result = runner.invoke(app, ["seal", "--help"])
        assert result.exit_code != 0  # typer errors out on unknown subcommand


class TestStatusNoCorpus:
    def test_friendly_message(self, tmp_path: Path):
        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "not yet materialized" in result.output


class TestStatusLooseCorpus:
    def test_reports_loose_count_and_missing(self, tmp_path: Path):
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        # Drop two loose flam3 files
        (gen_root / flam3_filename(248, 100)).write_bytes(b"<flame/>")
        (gen_root / flam3_filename(248, 101)).write_bytes(b"<flame/>")
        (gen_root / "missing.txt").write_text("500\n600\n")

        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "2 loose flam3" in result.output
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
        assert flam3_path(248, 100, corpus).exists()


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
        # v0.4 hint points to operations.md (archive-scrape scripts removed,
        # recoverable from git history if ES ever rolls a new dead gen).
        assert "operations.md" in result.output

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
