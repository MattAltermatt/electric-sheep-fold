"""Tests for electric_sheep_fold.layout — pure path/URL math (v0.3 loose)."""
from pathlib import Path

from electric_sheep_fold.layout import (
    ARCHIVE_BASE_URL,
    BASE_URL_DEFAULT,
    LIVE_GENS,
    archive_url,
    flam3_filename,
    flam3_path,
    release_zip_path,
    remote_url,
)


class TestLiveGens:
    def test_default_set(self):
        assert LIVE_GENS == frozenset({247, 248})


class TestFlam3Filename:
    def test_padding_default_gen(self):
        assert flam3_filename(248, 0) == "electricsheep.248.00000.flam3"
        assert flam3_filename(248, 100) == "electricsheep.248.00100.flam3"
        assert flam3_filename(248, 40_700) == "electricsheep.248.40700.flam3"

    def test_padding_different_gen(self):
        assert flam3_filename(244, 16) == "electricsheep.244.00016.flam3"


class TestFlam3Path:
    def test_low_sheep(self, tmp_path: Path):
        assert flam3_path(248, 100, tmp_path) == (
            tmp_path / "248" / "electricsheep.248.00100.flam3"
        )

    def test_dead_gen(self, tmp_path: Path):
        assert flam3_path(244, 40_700, tmp_path) == (
            tmp_path / "244" / "electricsheep.244.40700.flam3"
        )

    def test_zero_id(self, tmp_path: Path):
        assert flam3_path(247, 0, tmp_path) == (
            tmp_path / "247" / "electricsheep.247.00000.flam3"
        )


class TestReleaseZipPath:
    def test_basic(self, tmp_path: Path):
        assert release_zip_path(248, tmp_path) == tmp_path / "gen-248.zip"

    def test_dead_gen(self, tmp_path: Path):
        assert release_zip_path(244, tmp_path) == tmp_path / "gen-244.zip"


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


class TestArchiveUrl:
    def test_archive_url_shape(self):
        assert archive_url(244, 100) == (
            "https://electricsheep.com/archives/generation-244/100/spex"
        )

    def test_archive_url_zero_id(self):
        assert archive_url(244, 0).endswith("/generation-244/0/spex")

    def test_archive_base_constant(self):
        assert ARCHIVE_BASE_URL == "https://electricsheep.com/archives"


class TestRetiredHelpers:
    """v0.3 removes chunk-* helpers — guard against accidental re-introduction."""

    def test_bucket_for_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "bucket_for")

    def test_local_path_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "local_path")

    def test_chunk_for_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "chunk_for"), "chunk_for retired in v0.3"

    def test_chunk_range_str_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "chunk_range_str"), "chunk_range_str retired in v0.3"

    def test_sealed_zip_path_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "sealed_zip_path"), "sealed_zip_path retired in v0.3"

    def test_working_path_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "working_path"), "working_path retired in v0.3"

    def test_chunk_size_removed(self):
        import electric_sheep_fold.layout as layout_mod
        assert not hasattr(layout_mod, "CHUNK_SIZE"), "CHUNK_SIZE retired in v0.3"
