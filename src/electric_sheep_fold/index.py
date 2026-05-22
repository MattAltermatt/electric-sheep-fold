"""Aggregate corpus index for agentic / pyr3 consumption.

Walks every sealed zip in `corpus/{gen}/`, parses each `.flam3`, and emits:
  - `index.json` — one record per flame (machine-queryable; JSON array on a
    single line for stream-friendly jq).
  - `INDEX.md` — aggregations + recipe table for agentic scanning.

Per-flame `kind`: `genome` (single-flame, fully indexed) · `animation`
(multi-flame morph; `frame_count` only) · `corrupt` (zero-byte or
unparseable). **Agentic lookups should default-filter `kind == "genome"`** to
get canonical, renderable flames; animations are interpolation snapshots
that pyr3 doesn't render directly, and corrupt files are unusable.

Re-runnable; overwrites outputs. Stdlib only.
"""
from __future__ import annotations

import json
import logging
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)

# Canonical flam3 variation enum (var_t indices 0..99 from flam3 upstream).
# Anything else seen as an `<xform>` attribute is either a scalar field
# (weight, color, opacity, ...) or a variation PARAMETER (julian_power,
# blob_low, ...). Exact membership is how we count variation usage.
VARIATIONS: frozenset[str] = frozenset({
    "linear", "sinusoidal", "spherical", "swirl", "horseshoe", "polar",
    "handkerchief", "heart", "disc", "spiral", "hyperbolic", "diamond",
    "ex", "julia", "bent", "waves", "fisheye", "popcorn", "exponential",
    "power", "cosine", "rings", "fan", "blob", "pdj", "fan2", "rings2",
    "eyefish", "bubble", "cylinder", "perspective", "noise", "julian",
    "juliascope", "blur", "gaussian_blur", "radial_blur", "pie", "ngon",
    "curl", "rectangles", "arch", "tangent", "square", "rays", "blade",
    "secant2", "twintrian", "cross", "disc2", "super_shape", "flower",
    "conic", "parabola", "bent2", "bipolar", "boarders", "butterfly",
    "cell", "cpow", "curve", "edisc", "elliptic", "escher", "foci",
    "lazysusan", "loonie", "pre_blur", "modulus", "oscilloscope",
    "polar2", "popcorn2", "scry", "separation", "split", "splits",
    "stripes", "wedge", "wedge_julia", "wedge_sph", "whorl", "waves2",
    "exp", "log", "sin", "cos", "tan", "sec", "csc", "cot", "sinh",
    "cosh", "tanh", "sech", "csch", "coth", "auger", "flux", "mobius",
    "hemisphere", "post_curl",
})

IDENTITY_POST = "1 0 0 1 0 0"

_XML_DECL_RE = re.compile(rb"^\s*<\?xml[^?]*\?>\s*", re.DOTALL)
_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")


def parse_flame(content: bytes, gen: int, sheep_id: int) -> dict:
    """Classify content and extract structural metadata for one .flam3.

    Returns a record dict. Genomes get the full structural breakdown;
    animations get `frame_count` only; corrupt files get an `error` field.
    """
    rec: dict = {
        "id": f"{gen}/{sheep_id:05d}",
        "gen": gen,
        "sheep_id": sheep_id,
        "byte_size": len(content),
    }
    if not content:
        rec.update(kind="corrupt", valid=False, error="zero-byte")
        return rec

    stripped = _XML_DECL_RE.sub(b"", content).lstrip()
    if not stripped:
        rec.update(kind="corrupt", valid=False, error="empty-after-decl")
        return rec

    try:
        root = ET.fromstring(stripped)
    except ET.ParseError as exc:
        msg = str(exc)
        if "junk after document element" in msg:
            return _index_animation(rec, stripped)
        # Archive sometimes wraps in <get>...</get>; try synthetic root.
        try:
            wrapper = ET.fromstring(b"<sheep>" + stripped + b"</sheep>")
        except ET.ParseError:
            rec.update(kind="corrupt", valid=False, error=f"parse: {msg[:80]}")
            return rec
        flames = wrapper.findall(".//flame")
        if len(flames) == 1:
            return _index_genome(rec, flames[0])
        if len(flames) > 1:
            return _index_animation(rec, stripped)
        rec.update(kind="corrupt", valid=False, error="no-flame-elements")
        return rec

    if root.tag == "flame":
        return _index_genome(rec, root)

    # Non-`<flame>` root (e.g. `<get>...</get>`) — search for inner flames.
    flames = root.findall(".//flame")
    if len(flames) == 1:
        return _index_genome(rec, flames[0])
    if len(flames) > 1:
        return _index_animation(rec, stripped)
    rec.update(kind="corrupt", valid=False, error=f"no-flame-in-{root.tag}")
    return rec


def _index_genome(rec: dict, root) -> dict:
    rec["kind"] = "genome"
    rec["valid"] = True
    rec["frame_count"] = 1
    rec["name"] = root.get("name", "")
    rec["nick"] = root.get("nick", "")
    rec["url"] = root.get("url", "")
    rec["dims"] = root.get("size", "")
    rec["rotate"] = _f(root.get("rotate", "0"))
    rec["brightness"] = _f(root.get("brightness", "4"))
    rec["palette_mode"] = root.get("palette_mode", "step")
    rec["filter_shape"] = root.get("filter_shape", "gaussian")
    rec["background"] = [_f(x) for x in root.get("background", "0 0 0").split()]
    rec["supersample"] = _i(root.get("supersample", "1"))
    rec["highlight_power"] = _f(root.get("highlight_power", "-1"))

    sym = root.find("symmetry")
    rec["has_symmetry"] = sym is not None
    if sym is not None:
        rec["symmetry_kind"] = _i(sym.get("kind", "0"))

    xforms = root.findall("xform")
    final = root.find("finalxform")
    rec["xform_count"] = len(xforms)
    rec["has_final_xform"] = final is not None

    variations: set[str] = set()
    has_post_affine = False
    has_chaos = False
    negative_weight_xforms = 0
    all_xforms = xforms + ([final] if final is not None else [])
    for xf in all_xforms:
        post = xf.get("post")
        if post and post.strip() != IDENTITY_POST:
            has_post_affine = True
        if xf.get("chaos") is not None:
            has_chaos = True
        weight = _f(xf.get("weight", "1"))
        if weight < 0:
            negative_weight_xforms += 1
        for attr in xf.attrib:
            if attr in VARIATIONS:
                variations.add(attr)
    rec["has_post_affine"] = has_post_affine
    rec["has_chaos"] = has_chaos
    rec["negative_weight_xforms"] = negative_weight_xforms
    rec["variations"] = sorted(variations)
    return rec


def _index_animation(rec: dict, raw: bytes) -> dict:
    rec["kind"] = "animation"
    rec["valid"] = True
    # `<flame ` (with attributes) and bare `<flame>` both count as a frame.
    rec["frame_count"] = raw.count(b"<flame ") + raw.count(b"<flame>")
    return rec


def _f(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _i(s: str) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def iter_corpus_flames(corpus_root: Path):
    """Yield (gen, sheep_id, content_bytes, sealed) for every .flam3 in the corpus.

    Walks both sealed zips AND working-dir chunks (in-progress live-track
    fetches). Records carry a `sealed: bool` flag so agents can filter if
    they only want frozen examples.
    """
    if not corpus_root.exists():
        return
    for gen_dir in sorted(corpus_root.iterdir()):
        if not gen_dir.is_dir() or not gen_dir.name.isdigit():
            continue
        gen = int(gen_dir.name)
        for zip_path in sorted(gen_dir.glob("?????-?????.zip")):
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    m = _FLAM3_RE.match(name)
                    if not m:
                        continue
                    yield gen, int(m.group(2)), zf.read(name), True
        for working in sorted(gen_dir.iterdir()):
            if not working.is_dir() or not re.match(r"^\d{5}-\d{5}$", working.name):
                continue
            for path in sorted(working.glob("electricsheep.*.flam3")):
                m = _FLAM3_RE.match(path.name)
                if not m:
                    continue
                yield gen, int(m.group(2)), path.read_bytes(), False


def build_index(corpus_root: Path, out_dir: Path) -> dict:
    """Walk every sealed zip, parse each flam3, emit `index.json` + `INDEX.md`.

    Returns a summary dict (total / genomes / animations / corrupt / variations
    distinct count) — useful for callers / tests / CLI feedback.
    """
    records: list[dict] = []
    for gen, sheep_id, content, sealed in iter_corpus_flames(corpus_root):
        rec = parse_flame(content, gen, sheep_id)
        rec["sealed"] = sealed
        records.append(rec)

    out_dir.mkdir(parents=True, exist_ok=True)
    index_json = out_dir / "index.json"
    with index_json.open("w") as f:
        json.dump(records, f, separators=(",", ":"))
        f.write("\n")

    md = _render_markdown(records)
    (out_dir / "INDEX.md").write_text(md)

    genomes = [r for r in records if r["kind"] == "genome"]
    var_hist: Counter[str] = Counter()
    for r in genomes:
        for v in r["variations"]:
            var_hist[v] += 1

    return {
        "total": len(records),
        "genomes": len(genomes),
        "animations": sum(1 for r in records if r["kind"] == "animation"),
        "corrupt": sum(1 for r in records if r["kind"] == "corrupt"),
        "distinct_variations": len(var_hist),
    }


def _render_markdown(records: list[dict]) -> str:
    L: list[str] = []
    L.append("# 🐑 electric-sheep-fold corpus index")
    L.append("")
    L.append(
        "Auto-generated by `sheep-fold index`. Companion file: "
        "[`index.json`](index.json) — one JSON record per flame, "
        "queryable with `jq`."
    )
    L.append("")
    L.append(
        "**File kinds:** each `.flam3` is classified as `genome` "
        "(single-flame, fully indexed), `animation` (multi-flame morph — "
        "`frame_count` only, derivative interpolation snapshots), or "
        "`corrupt` (zero-byte or unparseable). **Default agent queries "
        "filter `kind == \"genome\"`** to get canonical, renderable flames."
    )
    L.append("")

    # Per-gen breakdown
    gens = sorted({r["gen"] for r in records})
    L.append("## 📊 Corpus shape")
    L.append("")
    L.append("| Gen | Total | Genomes | Animations | Corrupt | Min KB | Max KB |")
    L.append("|-----|------:|--------:|-----------:|--------:|-------:|-------:|")
    for gen in gens:
        rows = [r for r in records if r["gen"] == gen]
        L.append(
            f"| {gen} | {len(rows):,} | "
            f"{sum(1 for r in rows if r['kind'] == 'genome'):,} | "
            f"{sum(1 for r in rows if r['kind'] == 'animation'):,} | "
            f"{sum(1 for r in rows if r['kind'] == 'corrupt'):,} | "
            f"{min((r['byte_size'] for r in rows), default=0) / 1024:.1f} | "
            f"{max((r['byte_size'] for r in rows), default=0) / 1024:.1f} |"
        )
    tot = len(records)
    tot_g = sum(1 for r in records if r["kind"] == "genome")
    tot_a = sum(1 for r in records if r["kind"] == "animation")
    tot_c = sum(1 for r in records if r["kind"] == "corrupt")
    L.append(
        f"| **total** | **{tot:,}** | **{tot_g:,}** | **{tot_a:,}** | "
        f"**{tot_c:,}** | | |"
    )
    L.append("")

    # Variation usage
    genomes = [r for r in records if r["kind"] == "genome"]
    var_hist: Counter[str] = Counter()
    for r in genomes:
        for v in r["variations"]:
            var_hist[v] += 1
    L.append("## 🎨 Variation usage (genomes only)")
    L.append("")
    L.append(
        f"{len(var_hist)} distinct variations across {tot_g:,} genomes. "
        "Counts = number of genomes using that variation in ≥1 xform."
    )
    L.append("")
    L.append("| Variation | Flames | Variation | Flames |")
    L.append("|-----------|-------:|-----------|-------:|")
    sv = var_hist.most_common()
    half = (len(sv) + 1) // 2
    left, right = sv[:half], sv[half:]
    for i in range(half):
        ln, lc = left[i]
        if i < len(right):
            rn, rc = right[i]
            L.append(f"| `{ln}` | {lc:,} | `{rn}` | {rc:,} |")
        else:
            L.append(f"| `{ln}` | {lc:,} | | |")
    L.append("")

    # Structural features
    feats: dict[str, int] = {
        "has_post_affine": sum(1 for r in genomes if r["has_post_affine"]),
        "has_final_xform": sum(1 for r in genomes if r["has_final_xform"]),
        "has_symmetry": sum(1 for r in genomes if r["has_symmetry"]),
        "has_chaos (xaos)": sum(1 for r in genomes if r["has_chaos"]),
        "has_nick (human-designed)": sum(1 for r in genomes if r["nick"]),
        "palette_mode_linear": sum(1 for r in genomes if r["palette_mode"] == "linear"),
        "palette_mode_step": sum(1 for r in genomes if r["palette_mode"] == "step"),
        "non_black_bg": sum(1 for r in genomes if any(c > 0.001 for c in r["background"])),
        "rotated": sum(1 for r in genomes if r["rotate"] != 0),
        "supersample_gt_1": sum(1 for r in genomes if r["supersample"] > 1),
        "highlight_power_set": sum(1 for r in genomes if r["highlight_power"] >= 0),
        "negative_weight_present": sum(1 for r in genomes if r["negative_weight_xforms"] > 0),
        "filter_shape_non_gaussian": sum(1 for r in genomes if r["filter_shape"] != "gaussian"),
    }
    L.append("## 🧬 Structural features (genomes only)")
    L.append("")
    L.append("| Feature | Count | Notes |")
    L.append("|---------|------:|-------|")
    notes = {
        "has_chaos (xaos)": "pyr3 doesn't model xaos; uniform-picks instead",
        "supersample_gt_1": "pyr3 needs supersample=1 override for parity",
        "highlight_power_set": "pyr3 NotImplementedError on HSV-desat branch",
    }
    for k, v in feats.items():
        L.append(f"| `{k}` | {v:,} | {notes.get(k, '')} |")
    L.append("")

    # Xform-count distribution
    xc = Counter(r["xform_count"] for r in genomes)
    L.append("## 🔢 Xform count distribution (genomes only)")
    L.append("")
    L.append("| Xforms | Flames |")
    L.append("|-------:|-------:|")
    for n in sorted(xc):
        L.append(f"| {n} | {xc[n]:,} |")
    L.append("")

    # Animation frame-count bins
    animations = [r for r in records if r["kind"] == "animation"]
    if animations:
        frame_hist = Counter(r["frame_count"] for r in animations)
        L.append("## 🎬 Animation frame counts (kind == \"animation\")")
        L.append("")
        L.append(
            f"{len(animations):,} multi-flame morph files. Frame-count "
            "distribution (binned):"
        )
        L.append("")
        L.append("| Frames | Files |")
        L.append("|-------:|------:|")
        bins = [(1, 1), (2, 10), (11, 50), (51, 100), (101, 500), (501, 100_000)]
        for lo, hi in bins:
            n = sum(c for k, c in frame_hist.items() if lo <= k <= hi)
            label = f"{lo}" if lo == hi else f"{lo}–{hi}"
            L.append(f"| {label} | {n:,} |")
        L.append("")

    # Corrupt summary
    corrupt = [r for r in records if r["kind"] == "corrupt"]
    if corrupt:
        L.append("## 💀 Corrupt / unparseable")
        L.append("")
        err = Counter(r.get("error", "?") for r in corrupt)
        L.append(f"{len(corrupt):,} files; top errors:")
        L.append("")
        for e, n in err.most_common(10):
            L.append(f"- {n:>4}× `{e[:80]}`")
        L.append("")

    # Recipes
    L.append("## 🛠️ Query recipes")
    L.append("")
    L.append(
        "**Default filter:** `kind == \"genome\"` — exclude animations + corrupt."
    )
    L.append("")
    L.append("Find genomes using a specific variation (e.g. `bipolar`):")
    L.append("```")
    L.append('jq -r \'.[] | select(.kind == "genome" and (.variations | index("bipolar"))) | .id\' index.json | head')
    L.append("```")
    L.append("")
    L.append("Find pyr3-parity-friendly genomes (no chaos, supersample=1, default highlight_power, has finalxform):")
    L.append("```")
    L.append('jq -r \'.[] | select(.kind == "genome" and (.has_chaos | not) and .supersample == 1 and .highlight_power < 0 and .has_final_xform) | .id\' index.json | head')
    L.append("```")
    L.append("")
    L.append("Find rare-variation candidates (variations with low usage counts in the table above are stress tests).")
    L.append("")
    L.append("Find low-complexity baseline genomes:")
    L.append("```")
    L.append('jq -r \'.[] | select(.kind == "genome" and .xform_count <= 2 and (.has_chaos | not)) | .id\' index.json | head')
    L.append("```")
    L.append("")
    L.append("Inspect one flame in full:")
    L.append("```")
    L.append('jq \'.[] | select(.id == "244/00016")\' index.json')
    L.append("```")
    L.append("")
    L.append("Regenerate: `sheep-fold index` (overwrites `index.json` + `INDEX.md`).")
    return "\n".join(L) + "\n"
