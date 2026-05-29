"""Pure XML → MANIFEST.csv row for electric-sheep-fold v0.2."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime

import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException

log = logging.getLogger(__name__)

# Strip a leading <?xml ... ?> declaration so we can wrap content in a synthetic
# root to handle multi-flame animation files (multiple <flame> siblings).
_XML_DECL_RE = re.compile(rb"^\s*<\?xml[^?]*\?>\s*", re.DOTALL)


MANIFEST_COLUMNS: tuple[str, ...] = (
    "id",
    "sha256",
    "file_size_bytes",
    "fetched_at",
    "source_url",
    "name",
    "nick",
    "url",
    "xform_count",
    "final_xform",
    "variations",
)

# Attribute names on <xform> that are NOT variations (they're weights, indices, etc.)
_NON_VARIATION_ATTRS: frozenset[str] = frozenset({
    "weight", "color", "color_speed", "symmetry", "animate", "opacity",
    "var_color", "coefs", "post", "chaos", "plotmode", "name",
})


def is_flam3_content(content: bytes) -> bool:
    """True iff content contains >=1 valid <flame> element (any root, any depth).

    Defends against the archive's 200-OK + body 'none\\n' placeholder, empty bodies,
    HTML error pages, and other non-flame responses. Accepts multiple wrapper
    formats observed in the wild:
      - bare `<flame>...</flame>` (canonical .flam3)
      - multi-flame animation: `<flame>...</flame><flame>...</flame>`
      - `<get gen=... id=... job=...><args.../><flame>...</flame></get>` (archive
        render-job envelope; the inner flame is the real data)
    """
    if not content:
        return False
    stripped = _XML_DECL_RE.sub(b"", content).lstrip()
    # Cheap pre-check: must contain `<flame` at some depth.
    if b"<flame" not in stripped:
        return False
    try:
        wrapper = ET.fromstring(b"<sheep>" + stripped + b"</sheep>")
    except (ET.ParseError, DefusedXmlException):
        # Malformed XML, or a defused payload (entity/DTD/external bomb) — not
        # a flame either way (ESF-026).
        return False
    return wrapper.find(".//flame") is not None


def extract_metadata(
    *,
    content: bytes,
    sheep_id: int,
    source_url: str,
    fetched_at: datetime,
) -> dict[str, object]:
    """Parse flam3 XML; return a row dict matching MANIFEST_COLUMNS.

    Robust to parse failures: returns the row with xform_count=-1, variations=""
    when XML is malformed; identity fields (id, sha256, file_size_bytes) and
    provenance (fetched_at, source_url) always present.
    """
    sha256 = hashlib.sha256(content).hexdigest()
    file_size_bytes = len(content)

    row: dict[str, object] = {
        "id": sheep_id,
        "sha256": sha256,
        "file_size_bytes": file_size_bytes,
        "fetched_at": fetched_at.isoformat(),
        "source_url": source_url,
        "name": "",
        "nick": "",
        "url": "",
        "xform_count": -1,
        "final_xform": False,
        "variations": "",
    }

    # Flam3 files may contain multiple <flame> siblings (animation keyframes).
    # Wrap in a synthetic root so XML parsing accepts both single- and multi-flame
    # forms uniformly. Strip any leading <?xml?> declaration first.
    stripped = _XML_DECL_RE.sub(b"", content)
    try:
        wrapper = ET.fromstring(b"<sheep>" + stripped + b"</sheep>")
    except (ET.ParseError, DefusedXmlException) as e:
        log.warning("flam3 %d XML parse failed: %s", sheep_id, e)
        return row

    # `.//flame` so we also pick up flames wrapped in <get>...</get>
    # render-job envelopes that the archive served for some gens.
    flames = wrapper.findall(".//flame")
    if not flames:
        log.warning("flam3 %d has no <flame> elements", sheep_id)
        return row

    first = flames[0]

    # First-flame representative metadata (animations are typically self-consistent)
    row["name"] = first.get("name", "")
    row["nick"] = first.get("nick", "")
    row["url"] = first.get("url", "")

    xforms = first.findall("xform")
    row["xform_count"] = len(xforms)
    row["final_xform"] = any(
        f.find("finalxform") is not None or f.find(".//finalxform") is not None
        for f in flames
    )

    # Variations: union of attribute keys across every xform in every flame
    variations: set[str] = set()
    for flame in flames:
        for xform in flame.findall("xform"):
            for attr in xform.attrib:
                if attr not in _NON_VARIATION_ATTRS:
                    variations.add(attr)
    row["variations"] = ";".join(sorted(variations))

    return row
