"""Tests for electric_sheep_fold.extract — pure XML → metadata-row."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from electric_sheep_fold.extract import MANIFEST_COLUMNS, extract_metadata


WELL_FORMED = b"""<?xml version="1.0"?>
<flame name="example" nick="alice" url="http://example.com">
  <color index="0" rgb="255 0 0"/>
  <xform weight="0.5" linear="0.5" julia="0.3"/>
  <xform weight="0.5" spherical="1.0" julia="0.2" disc="0.1"/>
  <finalxform color="0" linear="1.0"/>
</flame>
"""

NO_FINAL = b"""<?xml version="1.0"?>
<flame name="x">
  <xform weight="1.0" linear="1.0"/>
</flame>
"""

NO_NICK = b"""<?xml version="1.0"?>
<flame name="algorithm-bred">
  <xform weight="1.0" linear="1.0"/>
  <xform weight="1.0" julia="0.5"/>
</flame>
"""

MALFORMED = b"<flame><xform>not closed properly"

NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
URL = "http://v3d0.sheepserver.net/gen/248/100/electricsheep.248.00100.flam3"


class TestExtractMetadataHappyPath:
    def test_full_row(self):
        row = extract_metadata(
            content=WELL_FORMED, sheep_id=100, source_url=URL, fetched_at=NOW,
        )
        assert row["id"] == 100
        assert row["sha256"] == hashlib.sha256(WELL_FORMED).hexdigest()
        assert row["file_size_bytes"] == len(WELL_FORMED)
        assert row["fetched_at"] == NOW.isoformat()
        assert row["source_url"] == URL
        assert row["name"] == "example"
        assert row["nick"] == "alice"
        assert row["url"] == "http://example.com"
        assert row["xform_count"] == 2  # finalxform excluded
        assert row["final_xform"] is True
        # variations: sorted unique across all non-final xforms
        assert row["variations"] == "disc;julia;linear;spherical"


class TestFinalXform:
    def test_no_final(self):
        row = extract_metadata(content=NO_FINAL, sheep_id=1, source_url="", fetched_at=NOW)
        assert row["final_xform"] is False
        assert row["xform_count"] == 1
        assert row["variations"] == "linear"


class TestHumanVsAlgorithm:
    def test_nick_present(self):
        row = extract_metadata(content=WELL_FORMED, sheep_id=1, source_url="", fetched_at=NOW)
        assert row["nick"] == "alice"

    def test_nick_absent(self):
        row = extract_metadata(content=NO_NICK, sheep_id=1, source_url="", fetched_at=NOW)
        assert row["nick"] == ""


class TestMalformedXml:
    def test_graceful_degradation(self):
        row = extract_metadata(content=MALFORMED, sheep_id=42, source_url=URL, fetched_at=NOW)
        # Identity fields always present
        assert row["id"] == 42
        assert row["sha256"] == hashlib.sha256(MALFORMED).hexdigest()
        assert row["file_size_bytes"] == len(MALFORMED)
        # XML-derived fields signal failure
        assert row["xform_count"] == -1
        assert row["variations"] == ""
        assert row["name"] == ""
        assert row["nick"] == ""
        assert row["final_xform"] is False


class TestVariationsDedup:
    def test_variations_sorted_and_deduped(self):
        row = extract_metadata(content=WELL_FORMED, sheep_id=1, source_url="", fetched_at=NOW)
        parts = row["variations"].split(";")
        assert parts == sorted(set(parts))


class TestMissingAttrsDefaultEmpty:
    def test_no_name_no_url(self):
        row = extract_metadata(content=NO_NICK, sheep_id=1, source_url="", fetched_at=NOW)
        assert row["name"] == "algorithm-bred"
        assert row["url"] == ""


class TestManifestColumns:
    def test_columns_constant(self):
        # The CSV writer needs a stable column order
        assert MANIFEST_COLUMNS == (
            "id", "sha256", "file_size_bytes", "fetched_at", "source_url",
            "name", "nick", "url", "xform_count", "final_xform", "variations",
        )

    def test_row_has_all_columns(self):
        row = extract_metadata(content=WELL_FORMED, sheep_id=1, source_url="", fetched_at=NOW)
        assert set(row.keys()) == set(MANIFEST_COLUMNS)
