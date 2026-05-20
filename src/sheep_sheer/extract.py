"""Pure XML → MANIFEST.csv row for electric-sheep-fold v0.2."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)


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

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        log.warning("flam3 %d XML parse failed: %s", sheep_id, e)
        return row

    # Root attributes (name/nick/url)
    row["name"] = root.get("name", "")
    row["nick"] = root.get("nick", "")
    row["url"] = root.get("url", "")

    # Xforms (the structural signal)
    xforms = root.findall("xform")
    row["xform_count"] = len(xforms)
    row["final_xform"] = root.find("finalxform") is not None

    # Variations: union of attribute keys across all xforms minus the non-variations
    variations: set[str] = set()
    for xform in xforms:
        for attr in xform.attrib:
            if attr not in _NON_VARIATION_ATTRS:
                variations.add(attr)
    row["variations"] = ";".join(sorted(variations))

    return row
