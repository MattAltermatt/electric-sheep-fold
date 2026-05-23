"""Tests for electric_sheep_fold.index — corpus aggregation for agentic / pyr3 use."""
from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

from electric_sheep_fold.index import (
    HYPER_TRIG_VARIATIONS,
    INDEX_SCHEMA_VERSION,
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
        assert rec["xform_var_counts"] == [1, 1]
        assert rec["max_var_per_xform"] == 1
        assert rec["mean_var_per_xform"] == 1.0
        assert rec["xforms_with_5plus_vars"] == 0
        assert rec["final_xform_var_count"] is None
        assert rec["has_post_affine_per_xform"] == [False, False]
        assert rec["max_xform_weight"] == 1.0

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
        # Per-xform shape: two regular xforms each with 1 variation;
        # finalxform separate with its own count.
        assert rec["xform_var_counts"] == [1, 1]
        assert rec["max_var_per_xform"] == 1
        assert rec["mean_var_per_xform"] == 1.0
        assert rec["xforms_with_5plus_vars"] == 0
        assert rec["final_xform_var_count"] == 1
        # Only the second regular xform has a non-identity post.
        assert rec["has_post_affine_per_xform"] == [False, True]
        # Largest pick-weight across regular xforms is 0.7 (-0.3 + 0.7); final
        # is excluded from the pick-weight max.
        assert rec["max_xform_weight"] == 0.7


GENOME_MULTI_VAR_PER_XFORM = (
    # xform 1: 4 variations (linear, spherical, disc, bubble); pdj_a-d are PARAMS not vars
    b'<flame name="dense" size="640 480">'
    b'  <xform weight="0.5" coefs="1 0 0 1 0 0" linear="0.1" spherical="0.2" '
    b'    disc="0.3" bubble="0.4" pdj_a="0.1" pdj_b="0.2"/>'
    # xform 2: 5 variations (over the pyr3:gpu cap of 4)
    b'  <xform weight="0.5" coefs="1 0 0 1 0 0" pdj="0.5" julia="0.5" '
    b'    blade="0.5" cross="0.5" curl="0.5" pdj_c="0.3" pdj_d="0.4"/>'
    # xform 3: 0 variations (purely affine)
    b'  <xform weight="0.5" coefs="1 0 0 1 0 0"/>'
    b'</flame>'
)


class TestPerXformVariationCounts:
    """Validate the variation-density fields added for pyr3:gpu UBO sizing."""

    def test_pdj_params_are_not_counted(self):
        rec = parse_flame(GENOME_MULTI_VAR_PER_XFORM, 248, 1)
        # xform 1: linear, spherical, disc, bubble (4); xform 2: pdj, julia,
        # blade, cross, curl (5); xform 3: none.
        assert rec["xform_var_counts"] == [4, 5, 0]

    def test_aggregates_match_array(self):
        rec = parse_flame(GENOME_MULTI_VAR_PER_XFORM, 248, 1)
        assert rec["max_var_per_xform"] == 5
        assert rec["mean_var_per_xform"] == 3.0
        assert rec["xforms_with_5plus_vars"] == 1

    def test_validation_invariants(self):
        """Validation rules from the hand-off spec."""
        rec = parse_flame(GENOME_MULTI_VAR_PER_XFORM, 248, 1)
        assert len(rec["xform_var_counts"]) == rec["xform_count"]
        # sum(xform_var_counts) >= len(variations[]) (sum counts each
        # occurrence; variations[] dedupes the union)
        assert sum(rec["xform_var_counts"]) >= len(rec["variations"])
        assert rec["max_var_per_xform"] == max(rec["xform_var_counts"])
        assert rec["mean_var_per_xform"] == round(
            sum(rec["xform_var_counts"]) / len(rec["xform_var_counts"]), 2
        )
        assert rec["xforms_with_5plus_vars"] == sum(
            1 for n in rec["xform_var_counts"] if n >= 5
        )

    def test_empty_xforms_safe(self):
        # Degenerate genome with no xforms (extreme edge case).
        empty = b'<flame name="empty" size="100 100"/>'
        rec = parse_flame(empty, 248, 1)
        assert rec["xform_count"] == 0
        assert rec["xform_var_counts"] == []
        assert rec["max_var_per_xform"] == 0
        assert rec["mean_var_per_xform"] == 0.0
        assert rec["xforms_with_5plus_vars"] == 0
        assert rec["final_xform_var_count"] is None

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
    def test_walks_loose_and_sealed_transit(self, tmp_path: Path):
        """v0.3: gen 244 carries a v0.2 transit zip (pre-unseal), gen 247 is loose."""
        corpus = tmp_path / "corpus"
        _make_sealed_zip(
            corpus / "244" / "00000-00099.zip",
            244,
            {1: GENOME_LINEAR, 2: ANIMATION},
        )
        # v0.3 loose: flat files in gen dir.
        loose_gen = corpus / "247"
        loose_gen.mkdir(parents=True)
        (loose_gen / "electricsheep.247.00050.flam3").write_bytes(GENOME_RICH)

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
        envelope = json.loads(index_path.read_text())
        # v0.4 envelope
        assert envelope["_schema_version"] == 4
        assert isinstance(envelope["_build_date"], str)
        records = envelope["genomes"]
        assert len(records) == 3
        ids = {r["id"] for r in records}
        assert ids == {"244/00001", "244/00002", "244/00003"}

        md = (out_dir / "INDEX.md").read_text()
        assert "Corpus shape" in md
        assert "Variation usage" in md
        assert "Query recipes" in md
        # v0.4 INDEX.md surfaces AutoRoute fields
        assert "AutoRoute" in md

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
        envelope = json.loads((out_dir / "index.json").read_text())
        records = envelope["genomes"]
        genomes = [r for r in records if r["kind"] == "genome"]
        parity_friendly = [
            r for r in genomes
            if not r["has_chaos"]
            and r["supersample"] == 1
            and r["highlight_power"] < 0
        ]
        assert {r["id"] for r in parity_friendly} == {"244/00001"}


# ----- v0.4 pyr3 AutoRoute GPU-safety fields ---------------------------------


GENOME_EDISC = (
    b'<flame name="edisc-test" size="640 480">'
    b'  <xform weight="1" edisc="1" coefs="1 0 0 1 0 0"/>'
    b'</flame>'
)

GENOME_HYPER_TRIG = (
    b'<flame name="tan-test" size="640 480">'
    b'  <xform weight="1" tan="1" coefs="1 0 0 1 0 0"/>'
    b'</flame>'
)

GENOME_WIDE_AFFINE = (
    b'<flame name="wide-coefs" size="640 480">'
    b'  <xform weight="1" linear="1" coefs="7.5 0 0 7.5 0 0"/>'
    b'</flame>'
)

GENOME_DENSITY_EST = (
    b'<flame name="density" size="640 480" estimator_radius="9">'
    b'  <xform weight="1" linear="1" coefs="1 0 0 1 0 0"/>'
    b'</flame>'
)


class TestHyperTrigSet:
    def test_canonical_membership(self):
        expected = {"tan", "sec", "csc", "cot", "tanh", "sech", "csch", "coth"}
        assert HYPER_TRIG_VARIATIONS == expected

    def test_all_in_main_variations_set(self):
        for v in HYPER_TRIG_VARIATIONS:
            assert v in VARIATIONS


class TestPyr3AutoRouteFields:
    def test_has_edisc_true(self):
        rec = parse_flame(GENOME_EDISC, 247, 1978)
        assert rec["has_edisc"] is True
        assert rec["has_hyper_trig"] is False

    def test_has_edisc_false_when_absent(self):
        rec = parse_flame(GENOME_LINEAR, 247, 100)
        assert rec["has_edisc"] is False

    def test_has_hyper_trig_true_for_tan(self):
        rec = parse_flame(GENOME_HYPER_TRIG, 247, 286)
        assert rec["has_hyper_trig"] is True
        assert rec["has_edisc"] is False

    def test_has_hyper_trig_false_for_linear_only(self):
        rec = parse_flame(GENOME_LINEAR, 247, 100)
        assert rec["has_hyper_trig"] is False

    def test_max_abs_affine_coef_clean(self):
        rec = parse_flame(GENOME_LINEAR, 247, 100)
        # coefs = "1 0 0 1 0 0" → max |coef| = 1.0
        assert rec["max_abs_affine_coef"] == 1.0

    def test_max_abs_affine_coef_wide(self):
        rec = parse_flame(GENOME_WIDE_AFFINE, 247, 50)
        # coefs = "7.5 0 0 7.5 0 0" → max |coef| = 7.5 (triggers >5 gate)
        assert rec["max_abs_affine_coef"] == 7.5

    def test_max_abs_affine_includes_post_affine(self):
        # GENOME_RICH has post="0.5 0 0 0.5 0 0" — max(1, 0.5) = 1.0
        rec = parse_flame(GENOME_RICH, 247, 1)
        assert rec["max_abs_affine_coef"] == 1.0

    def test_max_abs_affine_handles_negatives(self):
        flam3 = (
            b'<flame size="640 480">'
            b'  <xform weight="1" linear="1" coefs="-10.2 0 0 0.5 0 0"/>'
            b'</flame>'
        )
        rec = parse_flame(flam3, 247, 0)
        assert rec["max_abs_affine_coef"] == 10.2

    def test_xform_count_post_symmetry_no_symmetry(self):
        rec = parse_flame(GENOME_LINEAR, 247, 100)
        assert rec["xform_count_post_symmetry"] == 2  # 2 xforms, no symmetry

    def test_xform_count_post_symmetry_with_rotational(self):
        # GENOME_RICH has <symmetry kind="2"/> + 2 xforms → 2 + (2-1) = 3
        rec = parse_flame(GENOME_RICH, 247, 1)
        assert rec["xform_count_post_symmetry"] == 3

    def test_xform_count_post_symmetry_dihedral(self):
        flam3 = (
            b'<flame size="640 480">'
            b'  <symmetry kind="-3"/>'
            b'  <xform weight="1" linear="1" coefs="1 0 0 1 0 0"/>'
            b'  <xform weight="1" spherical="1" coefs="1 0 0 1 0 0"/>'
            b'</flame>'
        )
        rec = parse_flame(flam3, 247, 0)
        # 2 xforms + (2*3 - 1) = 2 + 5 = 7
        assert rec["xform_count_post_symmetry"] == 7

    def test_has_density_estimator_true(self):
        rec = parse_flame(GENOME_DENSITY_EST, 247, 0)
        assert rec["has_density_estimator"] is True

    def test_has_density_estimator_false_when_absent(self):
        rec = parse_flame(GENOME_LINEAR, 247, 100)
        assert rec["has_density_estimator"] is False

    def test_has_density_estimator_false_when_zero(self):
        flam3 = (
            b'<flame size="640 480" estimator_radius="0">'
            b'  <xform weight="1" linear="1" coefs="1 0 0 1 0 0"/>'
            b'</flame>'
        )
        rec = parse_flame(flam3, 247, 0)
        assert rec["has_density_estimator"] is False


class TestIndexSchemaV4:
    def test_envelope_has_schema_version_and_build_date(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        (corpus / "247" / "00000").mkdir(parents=True)
        (corpus / "247" / "00000" / "electricsheep.247.00100.flam3").write_bytes(
            GENOME_LINEAR
        )
        out_dir = tmp_path / "out"
        build_index(corpus, out_dir, build_date=date(2026, 5, 23))

        env = json.loads((out_dir / "index.json").read_text())
        assert env["_schema_version"] == INDEX_SCHEMA_VERSION == 4
        assert env["_build_date"] == "2026-05-23"
        assert "genomes" in env
        assert isinstance(env["genomes"], list)

    def test_default_build_date_is_today(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        out_dir = tmp_path / "out"
        build_index(corpus, out_dir)
        env = json.loads((out_dir / "index.json").read_text())
        # Just verify it parses as a date in the expected shape
        assert len(env["_build_date"]) == 10
        assert env["_build_date"][4] == "-"
