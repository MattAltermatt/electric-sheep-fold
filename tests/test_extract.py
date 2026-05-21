"""Tests for electric_sheep_fold.extract — pure XML → metadata-row."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from electric_sheep_fold.extract import MANIFEST_COLUMNS, extract_metadata, is_flam3_content


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

# Two sibling <flame> roots — legal flam3 (animation keyframes), illegal single-root XML.
MULTI_FLAME = b"""<flame name="frame1" nick="alice" time="0">
  <xform weight="0.5" linear="0.5" julia="0.3"/>
  <xform weight="0.5" spherical="1.0"/>
</flame>
<flame name="frame2" nick="alice" time="1">
  <xform weight="0.5" linear="0.5" disc="1.0"/>
  <xform weight="0.5" spherical="1.0" julia="0.4"/>
</flame>
"""

# Multi-flame with leading <?xml?> declaration (common in archive responses).
MULTI_FLAME_WITH_DECL = b"""<?xml version="1.0"?>
<flame name="kf1" time="0"><xform weight="1" linear="1"/></flame>
<flame name="kf2" time="1"><xform weight="1" julia="1"/></flame>
"""

# Server "none" placeholder — 5-byte response treated as 200 OK by the scraper bug.
NONE_PLACEHOLDER = b"none\n"

# Archive render-job envelope: `<get>` wrapper containing real flame data.
# Observed in gen 245 — 67% of fetched files use this shape. The inner flames
# are the actual sheep; the wrapper is request metadata we discard.
GET_ENVELOPE = b"""<get gen="245" id="12072" job="440">
<args time="120" bits="33" earlyclip="1"/>
<flame time="0" name="frameA" nick="anon">
  <xform weight="0.5" linear="0.5" julia="0.3"/>
  <xform weight="0.5" spherical="1.0"/>
</flame>
<flame time="1" name="frameB" nick="anon">
  <xform weight="0.5" disc="1.0"/>
</flame>
</get>
"""

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


class TestMultiFlame:
    """Flam3 files can carry multiple <flame> sibling roots for animation."""

    def test_multi_flame_no_xml_decl(self):
        row = extract_metadata(
            content=MULTI_FLAME, sheep_id=7, source_url=URL, fetched_at=NOW,
        )
        # First-flame representative stats:
        assert row["name"] == "frame1"
        assert row["nick"] == "alice"
        assert row["xform_count"] == 2  # first flame has 2 xforms
        # Variations: union across all flames in the animation
        assert row["variations"] == "disc;julia;linear;spherical"
        assert row["final_xform"] is False

    def test_multi_flame_with_xml_decl(self):
        row = extract_metadata(
            content=MULTI_FLAME_WITH_DECL, sheep_id=8, source_url=URL, fetched_at=NOW,
        )
        assert row["name"] == "kf1"
        assert row["xform_count"] == 1
        assert row["variations"] == "julia;linear"


class TestNonePlaceholder:
    """5-byte 'none\\n' bodies are not flame XML — degrade like MALFORMED."""

    def test_none_body_degrades_gracefully(self):
        row = extract_metadata(
            content=NONE_PLACEHOLDER, sheep_id=99, source_url=URL, fetched_at=NOW,
        )
        assert row["id"] == 99
        assert row["sha256"] == hashlib.sha256(NONE_PLACEHOLDER).hexdigest()
        assert row["file_size_bytes"] == 5
        assert row["xform_count"] == -1
        assert row["variations"] == ""
        assert row["name"] == ""


class TestGetEnvelope:
    """The archive sometimes serves <get>-wrapped flame data; we must accept it."""

    def test_get_envelope_validates(self):
        assert is_flam3_content(GET_ENVELOPE) is True

    def test_get_envelope_extracts_first_inner_flame(self):
        row = extract_metadata(
            content=GET_ENVELOPE, sheep_id=12072, source_url=URL, fetched_at=NOW,
        )
        assert row["name"] == "frameA"
        assert row["nick"] == "anon"
        assert row["xform_count"] == 2
        assert row["variations"] == "disc;julia;linear;spherical"


class TestIsFlam3Content:
    """Content validator used by the scraper to reject 'none' / non-flam3 200 responses."""

    def test_well_formed_single_flame(self):
        assert is_flam3_content(WELL_FORMED) is True

    def test_multi_flame_no_decl(self):
        assert is_flam3_content(MULTI_FLAME) is True

    def test_multi_flame_with_decl(self):
        assert is_flam3_content(MULTI_FLAME_WITH_DECL) is True

    def test_rejects_none_placeholder(self):
        assert is_flam3_content(NONE_PLACEHOLDER) is False

    def test_rejects_empty(self):
        assert is_flam3_content(b"") is False

    def test_rejects_html_error_page(self):
        assert is_flam3_content(b"<html><body>not found</body></html>") is False

    def test_rejects_arbitrary_text(self):
        assert is_flam3_content(b"this is not XML at all") is False

    def test_rejects_malformed_flame_xml(self):
        assert is_flam3_content(MALFORMED) is False


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
