"""Tests for electric_sheep_fold.layout — pure path/URL math."""
from pathlib import Path

import pytest

from electric_sheep_fold.layout import (
    BASE_URL_DEFAULT,
    bucket_for,
    flam3_filename,
    local_path,
    remote_url,
)


class TestBucketFor:
    @pytest.mark.parametrize(
        "sheep_id, expected",
        [
            (0, "00xxx"),
            (1, "00xxx"),
            (999, "00xxx"),
            (1000, "01xxx"),
            (1999, "01xxx"),
            (40700, "40xxx"),
            (40999, "40xxx"),
            (41000, "41xxx"),
        ],
    )
    def test_bucket_boundaries(self, sheep_id, expected):
        assert bucket_for(sheep_id) == expected

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            bucket_for(-1)


class TestFlam3Filename:
    def test_padding_default_gen(self):
        assert flam3_filename(248, 0) == "electricsheep.248.00000.flam3"
        assert flam3_filename(248, 100) == "electricsheep.248.00100.flam3"
        assert flam3_filename(248, 40700) == "electricsheep.248.40700.flam3"

    def test_padding_different_gen(self):
        assert flam3_filename(244, 16) == "electricsheep.244.00016.flam3"


class TestLocalPath:
    def test_assembly_low_sheep(self, tmp_path: Path):
        assert local_path(248, 100, tmp_path) == (
            tmp_path / "248" / "00xxx" / "electricsheep.248.00100.flam3"
        )

    def test_assembly_high_sheep(self, tmp_path: Path):
        assert local_path(248, 40700, tmp_path) == (
            tmp_path / "248" / "40xxx" / "electricsheep.248.40700.flam3"
        )


class TestRemoteUrl:
    def test_default_base(self):
        assert remote_url(248, 100) == (
            "http://v3d0.sheepserver.net/gen/248/100/electricsheep.248.00100.flam3"
        )

    def test_dir_segment_non_padded(self):
        # /gen/248/100/, NOT /gen/248/00100/
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
