"""Tests for electric_sheep_fold.chunk — delivery-chunk math + artifact build.

The delivery chunk (256 consecutive ids) is intentionally INDEPENDENT of the
storage bucket (10000) in layout.py — different concern (transfer vs archive).
See docs/superpowers/specs/2026-05-28-corpus-share-url-and-chunk-delivery-design.md.
"""
import json
import tarfile
from pathlib import Path

import brotli

from electric_sheep_fold.chunk import (
    CHUNK_FORMAT_VERSION,
    CHUNK_SIZE,
    build_chunk_bytes,
    build_chunks_tar,
    build_gens_json,
    chunk_filename,
    chunk_lo,
    decode_avail,
    encode_avail,
)


def test_chunk_size_is_256():
    assert CHUNK_SIZE == 256


def test_chunk_lo_floors_to_multiple_of_256():
    assert chunk_lo(0) == 0
    assert chunk_lo(255) == 0
    assert chunk_lo(256) == 256
    assert chunk_lo(12345) == 12288


def test_chunk_filename_is_zero_padded_opaque():
    # Opaque extension on purpose (no .br) — prevents any host from setting
    # Content-Encoding: br and breaking the FE's manual brotli decode.
    assert chunk_filename(247, 12345) == "247/12288.flam3chunk"
    assert chunk_filename(247, 5) == "247/00000.flam3chunk"


def test_build_chunk_roundtrips():
    flames = {
        12288: "<flame name='a'>x</flame>",
        12290: "<flame name='b'>y</flame>",
    }
    raw = build_chunk_bytes(flames)
    obj = json.loads(brotli.decompress(raw))
    assert obj["_v"] == CHUNK_FORMAT_VERSION == 1
    assert obj["12288"] == "<flame name='a'>x</flame>"
    assert obj["12290"] == "<flame name='b'>y</flame>"
    assert "12289" not in obj  # gaps are simply absent


def test_build_chunk_preserves_non_ascii_xml():
    # ensure_ascii=False keeps bytes faithful; brotli handles the UTF-8.
    flames = {1: "<flame name='café ☕'>—</flame>"}
    obj = json.loads(brotli.decompress(build_chunk_bytes(flames)))
    assert obj["1"] == "<flame name='café ☕'>—</flame>"


# ---------------------------------------------------------------------------
# encode_avail / decode_avail — per-gen present-id availability manifest
# ---------------------------------------------------------------------------


def test_avail_roundtrips_sparse_clustered_ids():
    ids = sorted({0, 1, 2, 3, 100, 101, 40000, 41234})
    raw = encode_avail(ids)
    assert decode_avail(raw) == ids
    assert len(raw) < len(ids) * 4  # compact


def test_avail_empty_list():
    raw = encode_avail([])
    assert raw == brotli.compress(b"", quality=11)
    assert decode_avail(raw) == []


def test_avail_single_id():
    assert decode_avail(encode_avail([42])) == [42]
    assert decode_avail(encode_avail([0])) == [0]


def test_avail_large_clustered_range():
    ids = list(range(0, 5000)) + [40000, 41234]
    raw = encode_avail(ids)
    assert decode_avail(raw) == ids
    # sanity: brotli + delta should compress densely-packed ids well
    assert len(raw) < len(ids) * 2


def test_avail_deduplicates_and_sorts_input():
    # defensive: unsorted + dupes still round-trip to a sorted unique list
    ids_messy = [3, 1, 2, 1, 3, 100]
    expected = [1, 2, 3, 100]
    assert decode_avail(encode_avail(ids_messy)) == expected


# ---------------------------------------------------------------------------
# build_gens_json — browse summary for gens.json
# ---------------------------------------------------------------------------


def test_gens_json_shape():
    out = build_gens_json({247: [0, 5, 41234], 248: [10]}, build_date="2026-05-28")
    assert out["schema"] == 2 and out["chunk_size"] == 256
    assert out["build_date"] == "2026-05-28"
    assert out["kind"] == "all"  # ESF-039: default when no kind passed
    assert out["gens"][0] == {"gen": 247, "count": 3, "min_id": 0, "max_id": 41234}
    assert out["gens"][1]["gen"] == 248


def test_gens_json_empty_input():
    out = build_gens_json({}, "2026-05-28")
    assert out["gens"] == []


def test_gens_json_sorted_ascending():
    # Output gens must be sorted ascending regardless of dict insertion order.
    out = build_gens_json({248: [100], 247: [50], 165: [1]}, "2026-05-28")
    assert [g["gen"] for g in out["gens"]] == [165, 247, 248]


def test_gens_json_single_id_min_max_equal():
    out = build_gens_json({247: [99]}, "2026-05-28")
    entry = out["gens"][0]
    assert entry["count"] == 1
    assert entry["min_id"] == entry["max_id"] == 99


# ---------------------------------------------------------------------------
# build_chunks_tar — corpus-chunks-{date}.tar artifact assembly
# ---------------------------------------------------------------------------


def _write_flam3(corpus: Path, gen: int, sid: int, body: str):
    f = corpus / str(gen) / f"{(sid // 10000) * 10000:05d}" / f"electricsheep.{gen}.{sid}.flam3"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body)
    return f


def test_build_chunks_tar(tmp_path):
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, "<flame>five</flame>")
    _write_flam3(corpus, 247, 300, "<flame>threehundred</flame>")  # different 256-window
    out = tmp_path / "corpus-chunks-2026-05-28.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    names = set(tarfile.open(out).getnames())
    assert "gens.json" in names
    assert "247/avail.flam3idx" in names
    assert "247/00000.flam3chunk" in names   # id 5 -> window 0
    assert "247/00256.flam3chunk" in names   # id 300 -> window 256
    with tarfile.open(out) as t:
        obj = json.loads(brotli.decompress(t.extractfile("247/00000.flam3chunk").read()))
        assert obj["5"] == "<flame>five</flame>"


def test_build_chunks_tar_gens_json_plain(tmp_path):
    """gens.json is plain JSON, NOT brotli-compressed."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, "<flame>five</flame>")
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    with tarfile.open(out) as t:
        raw = t.extractfile("gens.json").read()
        obj = json.loads(raw)  # plain JSON — no brotli
    assert obj["schema"] == 2
    assert obj["build_date"] == "2026-05-28"
    assert obj["chunk_size"] == 256
    assert len(obj["gens"]) == 1
    assert obj["gens"][0]["gen"] == 247
    assert obj["gens"][0]["count"] == 1


def test_build_chunks_tar_avail_decodes(tmp_path):
    """247/avail.flam3idx decodes via decode_avail to the full sorted id list."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, "<flame>a</flame>")
    _write_flam3(corpus, 247, 300, "<flame>b</flame>")
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    with tarfile.open(out) as t:
        raw = t.extractfile("247/avail.flam3idx").read()
    assert decode_avail(raw) == [5, 300]


def test_build_chunks_tar_multiple_gens(tmp_path):
    """Multiple gens each get their own dir with avail + chunk members."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 10, "<flame>a</flame>")
    _write_flam3(corpus, 248, 20, "<flame>b</flame>")
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    names = set(tarfile.open(out).getnames())
    assert "247/avail.flam3idx" in names
    assert "248/avail.flam3idx" in names
    assert "247/00000.flam3chunk" in names
    assert "248/00000.flam3chunk" in names
    with tarfile.open(out) as t:
        obj_247 = json.loads(brotli.decompress(t.extractfile("247/00000.flam3chunk").read()))
        obj_248 = json.loads(brotli.decompress(t.extractfile("248/00000.flam3chunk").read()))
    assert obj_247["10"] == "<flame>a</flame>"
    assert obj_248["20"] == "<flame>b</flame>"


def test_build_chunks_tar_two_ids_same_window(tmp_path):
    """Two ids in the same 256-window land in ONE chunk containing both."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 100, "<flame>x</flame>")
    _write_flam3(corpus, 247, 200, "<flame>y</flame>")  # both in window 0
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    names = set(tarfile.open(out).getnames())
    # Only one chunk file — no 247/00256.flam3chunk
    chunk_names = [n for n in names if n.endswith(".flam3chunk")]
    assert chunk_names == ["247/00000.flam3chunk"]
    with tarfile.open(out) as t:
        obj = json.loads(brotli.decompress(t.extractfile("247/00000.flam3chunk").read()))
    assert obj["100"] == "<flame>x</flame>"
    assert obj["200"] == "<flame>y</flame>"


def test_build_chunks_tar_skips_non_utf8_file(tmp_path):
    """ESF-021: a single non-UTF-8 .flam3 must not abort the whole build. It is
    skipped — absent from BOTH avail and the chunk (so they stay consistent) —
    while the rest of the corpus still ships."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, "<flame>ok</flame>")
    bad = corpus / "247" / "00000" / "electricsheep.247.6.flam3"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\xff\xfe<flame>\x80\x81</flame>")  # invalid UTF-8
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")  # must NOT raise
    with tarfile.open(out) as t:
        avail = decode_avail(t.extractfile("247/avail.flam3idx").read())
        obj = json.loads(brotli.decompress(t.extractfile("247/00000.flam3chunk").read()))
    assert avail == [5]          # bad id 6 excluded from avail
    assert obj["5"] == "<flame>ok</flame>"
    assert "6" not in obj        # … and from the chunk


def test_build_chunks_tar_is_reproducible_mtime_zero(tmp_path):
    """All tar members carry mtime=0 — load-bearing for a reproducible
    artifact (no wall-clock leakage across rebuilds)."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, "<flame>five</flame>")
    _write_flam3(corpus, 247, 300, "<flame>three</flame>")
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    with tarfile.open(out) as t:
        for member in t.getmembers():
            assert member.mtime == 0, f"{member.name} has non-zero mtime"


# ---------------------------------------------------------------------------
# ESF-039 — genome-only bake (index-filtered + orphan-keyframe promotion)
# ---------------------------------------------------------------------------


def _write_index(corpus: Path, records: list[tuple[int, int, str]]) -> Path:
    """Write a minimal corpus/_index/index.json. records = [(gen, sheep_id, kind)]."""
    idx_dir = corpus / "_index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    idx = idx_dir / "index.json"
    idx.write_text(
        json.dumps(
            {
                "_schema_version": 6,
                "_build_date": "2026-05-29",
                "genomes": [
                    {"gen": g, "sheep_id": s, "kind": k} for g, s, k in records
                ],
            }
        ),
        encoding="utf-8",
    )
    return idx


def test_genome_only_excludes_animation_ids(tmp_path):
    """index_path → animation file ids are dropped; genome ids kept."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, '<flame name="electricsheep.247.5">g</flame>')
    _write_flam3(
        corpus, 247, 6,
        '<flame name="electricsheep.247.5" time="0">a0</flame>'
        '<flame name="electricsheep.247.5" time="160">a1</flame>',
    )
    idx = _write_index(corpus, [(247, 5, "genome"), (247, 6, "animation")])
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-29", index_path=idx)
    with tarfile.open(out) as t:
        avail = decode_avail(t.extractfile("247/avail.flam3idx").read())
    assert 5 in avail
    assert 6 not in avail  # animation file id dropped


def test_genome_only_promotes_orphan_keyframe(tmp_path):
    """A keyframe id referenced by an animation but absent from genomes is
    promoted to a standalone genome at its own id, with its <flame> body."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, '<flame name="electricsheep.247.5">g</flame>')
    _write_flam3(
        corpus, 247, 6,
        '<flame name="electricsheep.247.5" time="0">a0</flame>'
        '<flame name="electricsheep.247.99" time="160">ORPHAN</flame>',
    )
    idx = _write_index(corpus, [(247, 5, "genome"), (247, 6, "animation")])
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-29", index_path=idx)
    with tarfile.open(out) as t:
        avail = decode_avail(t.extractfile("247/avail.flam3idx").read())
        chunk = json.loads(brotli.decompress(t.extractfile("247/00000.flam3chunk").read()))
    assert 99 in avail
    assert "ORPHAN" in chunk["99"]  # the orphan keyframe's <flame> is served at id 99


def test_genome_only_dedups_shared_orphan(tmp_path):
    """An orphan keyframe shared by two animations is promoted exactly once."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, '<flame name="electricsheep.247.5">g</flame>')
    _write_flam3(
        corpus, 247, 6,
        '<flame name="electricsheep.247.99" time="0">SHARED</flame>'
        '<flame name="electricsheep.247.5" time="160">x</flame>',
    )
    _write_flam3(
        corpus, 247, 7,
        '<flame name="electricsheep.247.5" time="0">y</flame>'
        '<flame name="electricsheep.247.99" time="160">SHARED</flame>',
    )
    idx = _write_index(
        corpus, [(247, 5, "genome"), (247, 6, "animation"), (247, 7, "animation")]
    )
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-29", index_path=idx)
    with tarfile.open(out) as t:
        avail = decode_avail(t.extractfile("247/avail.flam3idx").read())
    assert sorted(avail) == [5, 99]  # 6,7 dropped; 99 promoted once


def test_genome_only_marks_gens_json_kind(tmp_path):
    """gens.json carries kind:'genome' so missing animation chunks are explicit."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, '<flame name="electricsheep.247.5">g</flame>')
    idx = _write_index(corpus, [(247, 5, "genome")])
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-29", index_path=idx)
    with tarfile.open(out) as t:
        gens = json.loads(t.extractfile("gens.json").read())
    assert gens["kind"] == "genome"


def test_all_files_mode_marks_kind_all_and_keeps_animations(tmp_path):
    """No index_path → unchanged all-files behavior, kind:'all'."""
    corpus = tmp_path / "corpus"
    _write_flam3(corpus, 247, 5, '<flame name="electricsheep.247.5">g</flame>')
    _write_flam3(corpus, 247, 6, '<flame>a0</flame><flame>a1</flame>')
    out = tmp_path / "out.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-29")
    with tarfile.open(out) as t:
        avail = decode_avail(t.extractfile("247/avail.flam3idx").read())
        gens = json.loads(t.extractfile("gens.json").read())
    assert sorted(avail) == [5, 6]  # both kept (all-files)
    assert gens["kind"] == "all"
