"""Tests for electric_sheep_fold.index — corpus aggregation for agentic / pyr3 use."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from electric_sheep_fold.index import (
    VARIATIONS,
    build_index,
    iter_corpus_flames,
    parse_flame,
)


GENOME_LINEAR = (
    b'<?xml version="1.0"?>'
    b'<flame name="test" size="640 480" brightness="4">'
    b'  <xform weight="1" linear="1" coefs="1 0 0 1 0 0"/>'
    b'  <xform weight="0.5" julia="1" coefs="1 0 0 1 0 0"/>'
    b'</flame>'
)

GENOME_RICH = (
    b'<flame name="rich" nick="alice" url="http://example.com" '
    b'size="800 600" rotate="45" palette_mode="linear" '
    b'background="0.1 0.0 0.0" supersample="4" highlight_power="1">'
    b'  <symmetry kind="2"/>'
    b'  <xform weight="-0.3" disc="1" coefs="1 0 0 1 0 0" chaos="1 1"/>'
    b'  <xform weight="0.7" bubble="1" coefs="1 0 0 1 0 0" '
    b'    post="0.5 0 0 0.5 0 0"/>'
    b'  <finalxform color="0" linear="1" coefs="1 0 0 1 0 0"/>'
    b'</flame>'
)

ANIMATION = (
    b'<flame name="frame1"><xform weight="1" linear="1" coefs="1 0 0 1 0 0"/></flame>'
    b'<flame name="frame2"><xform weight="1" spherical="1" coefs="1 0 0 1 0 0"/></flame>'
    b'<flame name="frame3"><xform weight="1" julia="1" coefs="1 0 0 1 0 0"/></flame>'
)


class TestVariationsSet:
    def test_canonical_size(self):
        # 99-entry flam3 var_t plus the two ES-corpus extras (hemisphere, post_curl).
        assert len(VARIATIONS) == 101

    def test_includes_common(self):
        for v in ("linear", "spherical", "julian", "bubble", "disc", "polar"):
            assert v in VARIATIONS


class TestParseFlame:
    def test_zero_byte_is_corrupt(self):
        rec = parse_flame(b"", 248, 100)
        assert rec["kind"] == "corrupt"
        assert rec["error"] == "zero-byte"

    def test_html_is_corrupt(self):
        rec = parse_flame(b"<html>not a flame</html>", 248, 100)
        assert rec["kind"] == "corrupt"

    def test_simple_genome(self):
        rec = parse_flame(GENOME_LINEAR, 248, 100)
        assert rec["kind"] == "genome"
        assert rec["valid"] is True
        assert rec["xform_count"] == 2
        assert rec["variations"] == ["julia", "linear"]
        assert rec["has_final_xform"] is False
        assert rec["has_post_affine"] is False
        assert rec["has_chaos"] is False
        assert rec["supersample"] == 1
        assert rec["highlight_power"] == -1
        assert rec["negative_weight_xforms"] == 0

    def test_rich_genome_pyr3_flags(self):
        rec = parse_flame(GENOME_RICH, 248, 200)
        assert rec["kind"] == "genome"
        assert rec["name"] == "rich"
        assert rec["nick"] == "alice"
        assert rec["dims"] == "800 600"
        assert rec["rotate"] == 45.0
        assert rec["palette_mode"] == "linear"
        assert rec["background"] == [0.1, 0.0, 0.0]
        assert rec["supersample"] == 4
        assert rec["highlight_power"] == 1.0
        assert rec["has_symmetry"] is True
        assert rec["symmetry_kind"] == 2
        assert rec["has_final_xform"] is True
        assert rec["has_post_affine"] is True
        assert rec["has_chaos"] is True
        assert rec["negative_weight_xforms"] == 1
        # The final xform's linear should also be picked up
        assert "linear" in rec["variations"]
        assert "disc" in rec["variations"]
        assert "bubble" in rec["variations"]

    def test_animation_marked_with_frame_count(self):
        rec = parse_flame(ANIMATION, 244, 42746)
        assert rec["kind"] == "animation"
        assert rec["frame_count"] == 3

    def test_get_envelope_treated_as_genome(self):
        # Archive's <get>-wrapped envelope; inner flame is the canonical genome.
        # Test data deliberately omits the leading <?xml?> decl since it would
        # be inside <get>, where it's not valid XML.
        inner_flame = (
            b'<flame name="test" size="640 480">'
            b'  <xform weight="1" linear="1" coefs="1 0 0 1 0 0"/>'
            b'  <xform weight="0.5" julia="1" coefs="1 0 0 1 0 0"/>'
            b'</flame>'
        )
        wrapped = b'<get gen="244" id="100" job="test"><args/>' + inner_flame + b'</get>'
        rec = parse_flame(wrapped, 244, 100)
        assert rec["kind"] == "genome"
        assert rec["xform_count"] == 2


def _make_sealed_zip(zip_path: Path, gen: int, entries: dict[int, bytes]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("MANIFEST.csv", "id,sha256\n")  # placeholder
        for sheep_id, content in entries.items():
            zf.writestr(f"electricsheep.{gen}.{sheep_id:05d}.flam3", content)


class TestIterCorpusFlames:
    def test_walks_sealed_and_working(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        _make_sealed_zip(
            corpus / "244" / "00000-00099.zip",
            244,
            {1: GENOME_LINEAR, 2: ANIMATION},
        )
        # Working dir for 247
        working = corpus / "247" / "00000-09999"
        working.mkdir(parents=True)
        (working / "electricsheep.247.00050.flam3").write_bytes(GENOME_RICH)

        flames = list(iter_corpus_flames(corpus))
        assert len(flames) == 3
        sealed_flags = {(gen, sid): sealed for gen, sid, _, sealed in flames}
        assert sealed_flags[(244, 1)] is True
        assert sealed_flags[(244, 2)] is True
        assert sealed_flags[(247, 50)] is False


class TestBuildIndex:
    def test_emits_index_and_md(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        _make_sealed_zip(
            corpus / "244" / "00000-00099.zip",
            244,
            {1: GENOME_LINEAR, 2: ANIMATION, 3: b""},
        )
        out_dir = tmp_path / "out"
        summary = build_index(corpus, out_dir)

        assert summary["total"] == 3
        assert summary["genomes"] == 1
        assert summary["animations"] == 1
        assert summary["corrupt"] == 1
        assert summary["distinct_variations"] == 2  # linear + julia

        index_path = out_dir / "index.json"
        assert index_path.exists()
        records = json.loads(index_path.read_text())
        assert len(records) == 3
        ids = {r["id"] for r in records}
        assert ids == {"244/00001", "244/00002", "244/00003"}

        md = (out_dir / "INDEX.md").read_text()
        assert "Corpus shape" in md
        assert "Variation usage" in md
        assert "Query recipes" in md

    def test_empty_corpus(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        out_dir = tmp_path / "out"
        summary = build_index(corpus, out_dir)
        assert summary["total"] == 0
        assert (out_dir / "index.json").exists()
        assert (out_dir / "INDEX.md").exists()

    def test_pyr3_filter_query_works_on_output(self, tmp_path: Path):
        """The default pyr3-parity-friendly filter should pick GENOME_LINEAR
        but exclude GENOME_RICH (chaos, supersample>1, highlight_power)."""
        corpus = tmp_path / "corpus"
        _make_sealed_zip(
            corpus / "244" / "00000-00099.zip",
            244,
            {1: GENOME_LINEAR, 2: GENOME_RICH},
        )
        out_dir = tmp_path / "out"
        build_index(corpus, out_dir)
        records = json.loads((out_dir / "index.json").read_text())
        genomes = [r for r in records if r["kind"] == "genome"]
        parity_friendly = [
            r for r in genomes
            if not r["has_chaos"]
            and r["supersample"] == 1
            and r["highlight_power"] < 0
        ]
        assert {r["id"] for r in parity_friendly} == {"244/00001"}
