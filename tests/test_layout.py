"""Tests for electric_sheep_fold.layout — pure path/URL math (v0.4 chunked)."""
from pathlib import Path

from electric_sheep_fold.layout import (
    ARCHIVE_BASE_URL,
    BASE_URL_DEFAULT,
    FLAM3_RE,
    LIVE_GENS,
    archive_url,
    bucket_for,
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


class TestFlam3Re:
    """ESF-017: the canonical filename regex must accept ids ≥ 100,000.

    `flam3_filename` pads to a MINIMUM of 5 digits, so ids ≥ 100,000 produce
    6-digit forms. A `\\d{5}` pattern silently drops them from index / import /
    migrate / release / verify. The shared regex uses `\\d{5,}`.
    """

    def test_matches_five_digit_id(self):
        m = FLAM3_RE.match(flam3_filename(248, 12_345))
        assert m is not None
        assert m.group(1) == "248"
        assert m.group(2) == "12345"

    def test_matches_six_digit_id(self):
        # The ESF-017 regression: id ≥ 100000 → 6-digit filename.
        m = FLAM3_RE.match(flam3_filename(248, 100_000))
        assert m is not None
        assert m.group(2) == "100000"

    def test_rejects_short_unpadded_id(self):
        # A literal 3-digit id is malformed (the tool always pads to ≥5).
        assert FLAM3_RE.match("electricsheep.248.123.flam3") is None

    def test_rejects_non_flam3(self):
        assert FLAM3_RE.match("MANIFEST.csv") is None
        assert FLAM3_RE.match("electricsheep.248.00100.flam3.tmp") is None


class TestBucketFor:
    def test_id_zero(self):
        assert bucket_for(0) == "00000"

    def test_id_below_first_boundary(self):
        assert bucket_for(9_999) == "00000"

    def test_id_at_first_boundary(self):
        assert bucket_for(10_000) == "10000"

    def test_id_high_five_digit(self):
        assert bucket_for(99_999) == "90000"

    def test_id_six_digit_grows_naturally(self):
        # zero-pad is a MIN; ids ≥100000 produce 6-digit bucket strings
        assert bucket_for(100_000) == "100000"

    def test_id_typical_gen244(self):
        assert bucket_for(40_700) == "40000"

    def test_id_just_below_decade(self):
        assert bucket_for(19_999) == "10000"


class TestFlam3Path:
    def test_low_sheep_bucketed(self, tmp_path: Path):
        assert flam3_path(248, 100, tmp_path) == (
            tmp_path / "248" / "00000" / "electricsheep.248.00100.flam3"
        )

    def test_dead_gen_bucketed(self, tmp_path: Path):
        assert flam3_path(244, 40_700, tmp_path) == (
            tmp_path / "244" / "40000" / "electricsheep.244.40700.flam3"
        )

    def test_zero_id_bucketed(self, tmp_path: Path):
        assert flam3_path(247, 0, tmp_path) == (
            tmp_path / "247" / "00000" / "electricsheep.247.00000.flam3"
        )

    def test_boundary_id_starts_new_bucket(self, tmp_path: Path):
        # id=10000 lives under bucket "10000", not "00000"
        assert flam3_path(247, 10_000, tmp_path) == (
            tmp_path / "247" / "10000" / "electricsheep.247.10000.flam3"
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
    """v0.2 chunk-* helpers stay retired; v0.4 reintroduces bucket_for with
    a different shape (id // 10000 floor-bucket, not chunk-of-10k range)."""

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
