"""Tests for the CLI surface — range parsing + smoke."""
import pytest
import typer
from typer.testing import CliRunner

from electric_sheep_fold.cli import _parse_range, app

runner = CliRunner()


class TestParseRange:
    def test_valid(self):
        assert _parse_range("0..100") == (0, 100)
        assert _parse_range("1000..2000") == (1000, 2000)

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
    def test_top_level_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Polite mirror" in result.output

    def test_fetch_help(self):
        result = runner.invoke(app, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "START..END" in result.output


class TestStatus:
    def test_status_no_corpus(self, tmp_path):
        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "not yet materialized" in result.output

    def test_status_with_corpus(self, tmp_path):
        # Materialize a fake corpus
        gen_root = tmp_path / "248"
        bucket = gen_root / "00xxx"
        bucket.mkdir(parents=True)
        (bucket / "electricsheep.248.00100.flam3").write_bytes(b"x")
        (gen_root / "missing.txt").write_text("105\n200\n", encoding="utf-8")

        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 downloaded" in result.output
        assert "2 known-missing" in result.output


class TestFetchBadRange:
    def test_bad_range_exits_nonzero(self):
        """Bad range format should exit non-zero with an actionable error."""
        result = runner.invoke(app, ["fetch", "0,100"])
        assert result.exit_code != 0
        # Click renders BadParameter to stderr with the message we set
        assert "range must be" in (result.output + (result.stderr or ""))


class TestStatusWithRange:
    def test_status_range_computes_untried(self, tmp_path):
        # Materialize a corpus with sheep 100 downloaded, 105 missing, range = 100..110
        gen_root = tmp_path / "248"
        bucket = gen_root / "00xxx"
        bucket.mkdir(parents=True)
        (bucket / "electricsheep.248.00100.flam3").write_bytes(b"x")
        (gen_root / "missing.txt").write_text("105\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["status", "--corpus", str(tmp_path), "--range", "100..110"],
        )
        assert result.exit_code == 0
        # 10 total in range, 1 downloaded, 1 known-missing, 8 untried
        assert "1 downloaded" in result.output
        assert "1 known-missing" in result.output
        assert "8 untried" in result.output
        assert "100..110" in result.output

    def test_status_no_range_falls_back_to_two_stats(self, tmp_path):
        """Without --range, output should NOT include 'untried'."""
        gen_root = tmp_path / "248"
        bucket = gen_root / "00xxx"
        bucket.mkdir(parents=True)
        (bucket / "electricsheep.248.00100.flam3").write_bytes(b"x")
        (gen_root / "missing.txt").write_text("105\n", encoding="utf-8")

        result = runner.invoke(app, ["status", "--corpus", str(tmp_path)])
        assert result.exit_code == 0
        assert "1 downloaded" in result.output
        assert "1 known-missing" in result.output
        assert "untried" not in result.output
