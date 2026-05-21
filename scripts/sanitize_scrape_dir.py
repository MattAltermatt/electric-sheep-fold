"""Throwaway: scrub `none` placeholders and other non-flam3 artifacts from a
scrape working directory. For each file in `corpus/_scrape-<gen>/`:

  - If `is_flam3_content` returns False (empty, `none\\n`, HTML, malformed),
    append the id to `_missing_404.txt` and delete the file.
  - Otherwise leave alone.

Necessary because the prior scraper saved 200-OK responses verbatim without
content validation. Run once per affected scrape dir before re-importing.

Usage:
    python scripts/sanitize_scrape_dir.py --scrape corpus/_scrape-245
    python scripts/sanitize_scrape_dir.py --scrape corpus/_scrape-244 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
from electric_sheep_fold.extract import is_flam3_content  # noqa: E402

log = logging.getLogger("sanitize")

_FNAME_RE = re.compile(r"^electricsheep\.([^.]+)\.(\d+)\.flam3$")


def sanitize(scrape_dir: Path, dry_run: bool = False) -> dict[str, int]:
    """Walk scrape_dir; quarantine non-flam3 files into _missing_404.txt."""
    missing_path = scrape_dir / "_missing_404.txt"
    already_missing: set[int] = set()
    if missing_path.exists():
        already_missing = {
            int(x) for x in missing_path.read_text().split() if x.strip()
        }
    log.info("scrape_dir=%s already-missing=%d", scrape_dir, len(already_missing))

    new_missing: set[int] = set()
    scanned = 0
    deleted = 0
    skipped = 0

    for path in sorted(scrape_dir.glob("electricsheep.*.flam3")):
        scanned += 1
        m = _FNAME_RE.match(path.name)
        if not m:
            log.warning("unparseable name: %s — skipping", path.name)
            continue
        sheep_id = int(m.group(2))
        try:
            # Follow symlinks for the content read (the target file might be
            # the 'none' placeholder, even if our scrape dir entry is a link).
            content = path.read_bytes()
        except OSError as e:
            log.warning("read failed %s: %s", path, e)
            continue
        if is_flam3_content(content):
            skipped += 1
            continue
        # Non-flam3: quarantine
        preview = content[:32].decode("utf-8", errors="replace")
        log.info("quarantining id=%d (size=%d, starts %r)",
                 sheep_id, len(content), preview)
        if not dry_run:
            new_missing.add(sheep_id)
            path.unlink()
        deleted += 1

    if new_missing and not dry_run:
        combined = sorted(already_missing | new_missing)
        # Atomic write
        tmp = missing_path.with_suffix(missing_path.suffix + ".tmp")
        tmp.write_text("\n".join(str(i) for i in combined) + "\n")
        tmp.replace(missing_path)
        log.info("updated %s (+%d new, total %d)",
                 missing_path, len(new_missing), len(combined))

    return {
        "scanned": scanned,
        "quarantined": deleted,
        "kept": skipped,
        "new_missing": len(new_missing),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scrape", type=Path, required=True,
                   help="scrape dir, e.g. corpus/_scrape-244")
    p.add_argument("--dry-run", action="store_true",
                   help="report only; do not delete files or update missing.txt")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    if not args.scrape.is_dir():
        log.error("scrape dir not found: %s", args.scrape)
        return 1
    stats = sanitize(args.scrape, dry_run=args.dry_run)
    log.info("done: %s", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
