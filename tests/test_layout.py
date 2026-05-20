"""Tests for electric_sheep_fold.layout — pure path/URL math (v0.2 chunks)."""
from pathlib import Path

import pytest

from electric_sheep_fold.layout import (
    BASE_URL_DEFAULT,
    CHUNK_SIZE,
    chunk_for,
    chunk_range_str,
    flam3_filename,
    remote_url,
    sealed_zip_path,
    working_path,
)


class TestChunkSize:
    def test_constant(self):
        assert CHUNK_SIZE == 10_000


class TestChunkFor:
    @pytest.mark.parametrize(
        "sheep_id, expected",
        [
            (0, (0, 10_000)),
            (1, (0, 10_000)),
            (9_999, (0, 10_000)),
            (10_000, (10_000, 20_000)),
            (19_999, (10_000, 20_000)),
            (20_000, (20_000, 30_000)),
            (40_700, (40_000, 50_000)),
            (40_999, (40_000, 50_000)),
            (50_000, (50_000, 60_000)),
        ],
    )
    def test_boundaries(self, sheep_id, expected):
        assert chunk_for(sheep_id) == expected

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            chunk_for(-1)


class TestChunkRangeStr:
    @pytest.mark.parametrize(
        "start, end, expected",
        [
            (0, 10_000, "00000-09999"),
            (10_000, 20_000, "10000-19999"),
            (40_000, 50_000, "40000-49999"),
        ],
    )
    def test_format(self, start, end, expected):
        assert chunk_range_str(start, end) == expected


class TestFlam3Filename:
    def test_padding_default_gen(self):
        assert flam3_filename(248, 0) == "electricsheep.248.00000.flam3"
        assert flam3_filename(248, 100) == "electricsheep.248.00100.flam3"
        assert flam3_filename(248, 40_700) == "electricsheep.248.40700.flam3"

    def test_padding_different_gen(self):
        assert flam3_filename(244, 16) == "electricsheep.244.00016.flam3"


class TestWorkingPath:
    def test_low_sheep(self, tmp_path: Path):
        assert working_path(248, 100, tmp_path) == (
            tmp_path / "248" / "00000-09999" / "electricsheep.248.00100.flam3"
        )

    def test_chunk_boundary(self, tmp_path: Path):
        assert working_path(248, 10_000, tmp_path) == (
            tmp_path / "248" / "10000-19999" / "electricsheep.248.10000.flam3"
        )

    def test_high_sheep(self, tmp_path: Path):
        assert working_path(248, 40_700, tmp_path) == (
            tmp_path / "248" / "40000-49999" / "electricsheep.248.40700.flam3"
        )


class TestSealedZipPath:
    def test_basic(self, tmp_path: Path):
        assert sealed_zip_path(248, 0, 10_000, tmp_path) == (
            tmp_path / "248" / "00000-09999.zip"
        )

    def test_high_chunk(self, tmp_path: Path):
        assert sealed_zip_path(248, 40_000, 50_000, tmp_path) == (
            tmp_path / "248" / "40000-49999.zip"
        )


class TestRemoteUrl:
    def test_default_base(self):
        assert remote_url(248, 100) == (
            "http://v3d0.sheepserver.net/gen/248/100/electricsheep.248.00100.flam3"
        )

    def test_dir_segment_non_padded(self):
        url = remote_url(248, 100)
        assert "/248/100/" in url
        assert "/00100/" not in url

    def test_filename_segment_padded(self):
        url = remote_url(248, 100)
        assert url.endswith("electricsheep.248.00100.flam3")

    def test_custom_base(self):
        assert remote_url(248, 100, base="https://mirror.example.com") == (
            "https://mirror.example.com/gen/248/100/electricsheep.248.00100.flam3"
        )

    def test_base_default_constant(self):
        assert BASE_URL_DEFAULT == "http://v3d0.sheepserver.net"


class TestNoBucketSymbol:
    """v0.2 removes bucket_for entirely — guard against accidental re-introduction."""

    def test_bucket_for_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "bucket_for"), "bucket_for should be removed in v0.2"

    def test_local_path_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "local_path"), "local_path should be removed in v0.2"
