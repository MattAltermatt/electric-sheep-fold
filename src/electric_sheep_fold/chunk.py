"""Delivery-chunk artifact for the corpus share-URL system.

Turns the corpus tree into the `corpus-chunks-{date}.tar` artifact consumed
by pyr3 at `pyr3.app/v1/gen/{gen}/id/{id}`: brotli `{id: xml}` chunks of
CHUNK_SIZE consecutive ids, per-gen present-id availability manifests, and a
`gens.json` browse summary.

The delivery chunk (CHUNK_SIZE = 256) is deliberately INDEPENDENT of the
storage bucket (10000) in `layout.py`: storage is an archival concern,
chunking a transfer concern. This module is the single source of truth for
delivery-chunk math. Spec:
docs/superpowers/specs/2026-05-28-corpus-share-url-and-chunk-delivery-design.md
"""
from __future__ import annotations

import io
import json
import logging
import re
import tarfile
from collections import defaultdict
from pathlib import Path

import brotli

log = logging.getLogger(__name__)

# Part of the /v1 URL contract: if this ever changes, every chunk's data path
# shifts, which is a /v1 -> /v2 event. Do not change casually.
CHUNK_SIZE = 256

# Chunk wire-format version, carried as the "_v" key inside each chunk's JSON.
# Independent of the /v1 URL grammar: a container change bumps this WITHOUT
# changing any shared link. pyr3's decoder reads it; v1 is the only format.
CHUNK_FORMAT_VERSION = 1

# brotli quality for chunk bodies; 11 is the measured sweet spot (~172 KB for a
# 256-flame chunk vs ~832 KB gzip). No shared dictionary — in-chunk redundancy
# already saturates brotli's window at this size.
_BROTLI_QUALITY = 11

# Schema version for gens.json; bumped when the shape changes (independent of
# CHUNK_FORMAT_VERSION and the /v1 URL grammar). v2 (ESF-039): added the `kind`
# field ("genome" | "all") marking whether the bake dropped animation frames.
GENS_JSON_SCHEMA = 2

# ESF-039 — extract a single <flame> element verbatim from a multi-flame
# animation file, read its name, and pull the sheep id off the name suffix.
# flam3 files are flat (no nested <flame>), so a non-greedy element match is
# safe. Byte-faithful: we keep the original element text (incl. time=) so the
# promoted keyframe is exactly what the morph encoded.
_FLAME_ELEMENT_RE = re.compile(r"<flame\b.*?</flame>", re.DOTALL)
_FLAME_NAME_RE = re.compile(r'<flame\b[^>]*\bname="([^"]*)"')
_NAME_ID_SUFFIX_RE = re.compile(r"\.(\d+)$")


def chunk_lo(sheep_id: int) -> int:
    """Floor a sheep id to the start of its CHUNK_SIZE-wide delivery window."""
    return (sheep_id // CHUNK_SIZE) * CHUNK_SIZE


def chunk_filename(gen: int, sheep_id: int) -> str:
    """Same-origin path of the chunk holding `sheep_id`, e.g.
    "247/12288.flam3chunk". Opaque extension (no .br) on purpose — keeps any
    static host from setting Content-Encoding: br, which would make the
    browser auto-decode and break the FE's manual brotli decode. 5-digit
    zero-pad is a minimum (ids >=100000 grow naturally to 6 digits)."""
    return f"{gen}/{chunk_lo(sheep_id):05d}.flam3chunk"


def _encode_varint(n: int) -> bytes:
    """Encode an unsigned integer as LEB128 (little-endian base-128 varint).

    Each byte carries 7 bits of value (little-endian); the high bit is set on
    every byte except the last. Zero encodes as a single 0x00 byte.
    """
    out = []
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _decode_varints(buf: bytes) -> list[int]:
    """Decode all LEB128 varints packed end-to-end in *buf*. Returns a list."""
    values: list[int] = []
    i = 0
    while i < len(buf):
        n = 0
        shift = 0
        while True:
            b = buf[i]
            i += 1
            n |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                break
        values.append(n)
    return values


def encode_avail(ids: list[int]) -> bytes:
    """Encode a set of present sheep ids as a compact availability manifest.

    Wire format (cross-repo contract — a TypeScript decoder in pyr3 must match
    this byte-for-byte):

        brotli_compress( varint(ids[0])  varint(ids[1]-ids[0])  ... )

    Where:
    - Input is sorted+deduplicated defensively before encoding.
    - Each integer is encoded as an unsigned LEB128 varint (7 bits per byte,
      little-endian groups, high bit set on all bytes except the last).
    - The first value is the raw first id; subsequent values are deltas
      (ids[i] - ids[i-1]), which are always >= 1 after dedup so they fit as
      unsigned varints.
    - There is NO leading count. The decoder reads varints until the
      brotli-decompressed buffer is exhausted, then reconstructs ids by
      cumulative sum.
    - Empty input encodes as brotli_compress(b"") -> decodes to [].
    - Compressed with quality=_BROTLI_QUALITY (11).

    The FE (pyr3) uses this to know which ids exist before fetching a chunk,
    enabling browse rendering and short-circuiting dead-link clicks.
    """
    ids = sorted(set(ids))
    if not ids:
        return brotli.compress(b"", quality=_BROTLI_QUALITY)
    parts = [_encode_varint(ids[0])]
    for i in range(1, len(ids)):
        parts.append(_encode_varint(ids[i] - ids[i - 1]))
    return brotli.compress(b"".join(parts), quality=_BROTLI_QUALITY)


def decode_avail(raw: bytes) -> list[int]:
    """Decode an availability manifest produced by encode_avail.

    Brotli-decompresses *raw*, reads all LEB128 varints, and reconstructs the
    original id list via cumulative sum of the first id + successive deltas.
    Returns a sorted list[int]; empty manifest returns [].
    """
    buf = brotli.decompress(raw)
    if not buf:
        return []
    values = _decode_varints(buf)
    ids: list[int] = [values[0]]
    for delta in values[1:]:
        ids.append(ids[-1] + delta)
    return ids


def build_gens_json(
    per_gen: dict[int, list[int]], build_date: str, kind: str = "all"
) -> dict:
    """Build the gens.json browse summary dict (caller serializes to JSON).

    Returns:
        {
            "schema": GENS_JSON_SCHEMA,
            "build_date": build_date,
            "chunk_size": CHUNK_SIZE,
            "kind": "genome" | "all",   # ESF-039
            "gens": [
                {"gen": g, "count": N, "min_id": lo, "max_id": hi},
                ...  # sorted ascending by gen
            ]
        }

    `kind` marks what the bake contains: "genome" = canonical single-flame
    genomes only (animation morph-frames dropped); "all" = every file. This
    makes a genome-only artifact self-describing, so the absence of animation
    chunks is an explicit, queryable state — not a silent gap — for whenever
    animation delivery is built (its own future epic).

    Assumes each gen's id list is non-empty; gens with zero ids should not
    be passed in. The returned dict is plain Python — ship it as-is with
    json.dumps() at the call site. Not brotli-compressed: gens.json is
    small and served uncompressed.
    """
    return {
        "schema": GENS_JSON_SCHEMA,
        "build_date": build_date,
        "chunk_size": CHUNK_SIZE,
        "kind": kind,
        "gens": [
            {
                "gen": g,
                "count": len(per_gen[g]),
                "min_id": min(per_gen[g]),
                "max_id": max(per_gen[g]),
            }
            for g in sorted(per_gen)
        ],
    }


def load_classification(
    index_path: Path,
) -> tuple[dict[int, set[int]], dict[int, set[int]]]:
    """Read `index.json` → (genome_ids, animation_ids), each gen -> set of ids.

    The index (`sheep-fold index`) is the source of truth for the
    genome/animation/corrupt classification — its logic is nuanced (corrupt
    detection, junk-after-document, ESF-022), so the chunk bake reads it rather
    than re-deriving. Records with any other `kind` (corrupt) are excluded from
    both sets and thus never baked.
    """
    data = json.loads(index_path.read_text(encoding="utf-8"))
    genome_ids: dict[int, set[int]] = defaultdict(set)
    animation_ids: dict[int, set[int]] = defaultdict(set)
    for rec in data.get("genomes", []):
        kind = rec.get("kind")
        if kind == "genome":
            genome_ids[rec["gen"]].add(rec["sheep_id"])
        elif kind == "animation":
            animation_ids[rec["gen"]].add(rec["sheep_id"])
    return genome_ids, animation_ids


def extract_orphan_keyframes(
    animation_xml: str, genome_ids: set[int]
) -> dict[int, str]:
    """Return {sheep_id: <flame> xml} for keyframes in `animation_xml` whose id
    is NOT already a standalone genome.

    Some morph keyframes are referenced only inside animation files and were
    never extracted to a standalone genome (their id is an empty gap). Promoting
    them keeps those canonical flames reachable under a genome-only bake. The
    shared junction keyframe between two consecutive morphs is byte-identical in
    both, so de-duplication (last write wins) is safe.
    """
    out: dict[int, str] = {}
    for flame_xml in _FLAME_ELEMENT_RE.findall(animation_xml):
        name_match = _FLAME_NAME_RE.search(flame_xml)
        if name_match is None:
            continue
        id_match = _NAME_ID_SUFFIX_RE.search(name_match.group(1))
        if id_match is None:
            continue
        kf_id = int(id_match.group(1))
        if kf_id not in genome_ids:
            out[kf_id] = flame_xml
    return out


def build_chunks_tar(
    corpus_root: Path,
    out_tar: Path,
    build_date: str,
    *,
    index_path: Path | None = None,
) -> None:
    """Assemble a corpus-chunks-{date}.tar delivery artifact from a corpus tree.

    Walks `corpus_root` for `.flam3` files matching the canonical filename
    pattern `electricsheep.{gen}.{id}.flam3`, groups them into 256-id delivery
    windows, and writes an uncompressed tar to `out_tar` containing:

    - `gens.json` — plain JSON browse summary (NOT brotli'd).
    - `{gen}/avail.flam3idx` per gen — brotli'd LEB128 availability manifest.
    - `{gen}/{chunk_lo:05d}.flam3chunk` per non-empty window — brotli'd JSON
      map of present {id: xml} pairs within that window.

    When `index_path` is given, the bake is **genome-only** (ESF-039): only
    `kind == "genome"` ids are included; animation files are dropped, but their
    orphan keyframes (ids absent from the genome set) are promoted to standalone
    genomes at their own id; corrupt files are excluded. `gens.json.kind` is set
    to "genome" so the artifact is self-describing. Without `index_path` the
    bake includes every file and marks `kind` "all" (the legacy behavior).

    Members are written in sorted name order for a reproducible artifact.
    mtime is set to 0 on all TarInfo entries to avoid wall-clock leakage.
    Creates `out_tar`'s parent directory if it does not exist.
    """
    genome_only = index_path is not None
    genome_ids, animation_ids = (
        load_classification(index_path) if index_path is not None else ({}, {})
    )

    # --- collect flames from the corpus tree --------------------------------
    # per_gen: gen -> {id: xml_text}
    per_gen: dict[int, dict[int, str]] = defaultdict(dict)

    for path in corpus_root.glob("*/*/electricsheep.*.flam3"):
        parts = path.name.split(".")
        # expect: electricsheep . {gen} . {id} . flam3  (4 parts)
        if len(parts) != 4 or parts[0] != "electricsheep" or parts[3] != "flam3":
            continue
        try:
            gen = int(parts[1])
            sid = int(parts[2])
        except ValueError:
            continue
        try:
            xml = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # A corrupt, non-UTF-8 .flam3 (flam3 XML is always UTF-8). Skip it
            # rather than abort the whole artifact — and skip it entirely so it
            # stays out of BOTH avail and the chunk (they must agree). Better an
            # absent id than mojibake the renderer can't parse.
            log.warning(
                "build_chunks_tar: %s is not valid UTF-8 — skipping "
                "(excluded from avail + chunk)",
                path,
            )
            continue

        if not genome_only:
            per_gen[gen][sid] = xml
            continue

        # genome-only mode (ESF-039)
        gset = genome_ids.get(gen, set())
        if sid in gset:
            per_gen[gen][sid] = xml
        elif sid in animation_ids.get(gen, set()):
            # Drop the animation file; promote any keyframe whose id isn't a
            # genome to a standalone genome at its own id. setdefault de-dups
            # the shared junction keyframe; a real genome file (processed in any
            # order) overwrites via the `sid in gset` branch above, so it wins.
            for kf_id, flame_xml in extract_orphan_keyframes(xml, gset).items():
                per_gen[gen].setdefault(kf_id, flame_xml)
        # else: corrupt / unclassified -> excluded

    if not per_gen:
        # Most likely a pre-v0.4 flat corpus (files at {gen}/...flam3, one
        # level up from the {gen}/{bucket}/ glob) or an empty/ wrong root. The
        # release-build path is guarded upstream by the chunked-consistency
        # check, but the standalone `sheep-fold chunk` command is not — warn
        # rather than silently emit a gens-only artifact.
        log.warning(
            "build_chunks_tar: no .flam3 files found under %s — is the corpus "
            "v0.4 chunked? Writing an artifact with no chunks.",
            corpus_root,
        )

    # --- build all members as (name, bytes) pairs, then sort ----------------
    members: list[tuple[str, bytes]] = []

    # gens.json — plain JSON, not brotli
    per_gen_ids: dict[int, list[int]] = {g: sorted(ids) for g, ids in per_gen.items()}
    gens_json_bytes = json.dumps(
        build_gens_json(per_gen_ids, build_date, kind="genome" if genome_only else "all"),
        ensure_ascii=False,
    ).encode("utf-8")
    members.append(("gens.json", gens_json_bytes))

    for gen in sorted(per_gen):
        flames = per_gen[gen]
        sorted_ids = sorted(flames)

        # avail index
        members.append((f"{gen}/avail.flam3idx", encode_avail(sorted_ids)))

        # group by delivery chunk window
        windows: dict[int, dict[int, str]] = defaultdict(dict)
        for sid in sorted_ids:
            windows[chunk_lo(sid)][sid] = flames[sid]

        for lo in sorted(windows):
            name = f"{gen}/{lo:05d}.flam3chunk"
            members.append((name, build_chunk_bytes(windows[lo])))

    # --- write tar in sorted-name order with mtime=0 ------------------------
    members.sort(key=lambda t: t[0])
    out_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_tar, "w") as tf:
        for name, data in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            tf.addfile(info, io.BytesIO(data))


def build_chunk_bytes(flames: dict[int, str]) -> bytes:
    """Encode one chunk: brotli(JSON {"_v": 1, "<id>": "<flam3 xml>", ...}).

    Ids are stringified and sorted; missing ids are simply absent. The FE
    brotli-decodes, JSON.parses, and looks up the requested id (skipping the
    "_v" key). ensure_ascii=False keeps the XML byte-faithful pre-compression.
    """
    obj: dict[str, object] = {"_v": CHUNK_FORMAT_VERSION}
    for sheep_id in sorted(flames):
        obj[str(sheep_id)] = flames[sheep_id]
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return brotli.compress(payload.encode("utf-8"), quality=_BROTLI_QUALITY)
