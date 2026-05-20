"""Throwaway: preserve a dead Electric Sheep generation from electricsheep.com.

Walks `archives/generation-N/time/0..LAST.html` to enumerate every sheep id
ever recorded for that gen, then fetches each via the `spex` endpoint which
returns the raw .flam3 XML.

Use for dead gens (165, 169, 191, 198, 242, 243, 244, 245). For LIVE gens
(247, 248) prefer the main `electric-sheep-fold fetch-all` against v3d0; this scraper
can backfill historical/archived ids those don't reach.

Output: flat directory of canonical-named files. Feed to `electric-sheep-fold import`.

Usage:
    python scripts/scrape_archive_gen.py --gen 242 --out /tmp/scrape-242
    electric-sheep-fold import /tmp/scrape-242

Resumable: re-running picks up where it left off (cached id list + skip
existing files). Polite 20s+jitter cadence by default.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

import httpx

USER_AGENT = (
    "electric-sheep-fold/0.2 archive-preservation "
    "(https://github.com/muwamath/electric-sheep-fold)"
)
BASE = "https://electricsheep.com/archives"

_TIME_PAGE_RE = re.compile(r'time/(\d+)\.html')
_SHEEP_LINK_RE = re.compile(r'sheep/(\d+)/')

log = logging.getLogger("scrape")


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    )


def _sleep(delay: float, jitter: float) -> None:
    if delay > 0:
        time.sleep(delay + (random.uniform(0, jitter) if jitter > 0 else 0.0))


def _fetch_text(client: httpx.Client, url: str) -> str | None:
    r = client.get(url)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


def _fetch_bytes(client: httpx.Client, url: str) -> bytes | None:
    r = client.get(url)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def find_last_page(client: httpx.Client, gen: int) -> int | None:
    """Probe /time/index.html for the highest time/N.html link."""
    html = _fetch_text(client, f"{BASE}/generation-{gen}/time/index.html")
    if html is None:
        return None
    pages = [int(m.group(1)) for m in _TIME_PAGE_RE.finditer(html)]
    return max(pages) if pages else 0


def enumerate_ids(
    client: httpx.Client,
    gen: int,
    max_page: int,
    delay: float,
    jitter: float,
) -> list[int]:
    """Walk every time/N.html page collecting unique sheep ids."""
    ids: set[int] = set()
    for p in range(max_page + 1):
        name = "index.html" if p == 0 else f"{p}.html"
        url = f"{BASE}/generation-{gen}/time/{name}"
        log.info("enum page %d/%d -> %s", p, max_page, url)
        html = _fetch_text(client, url)
        if html is None:
            log.warning("404 at page %d; stopping enumeration", p)
            break
        page_ids = {int(m.group(1)) for m in _SHEEP_LINK_RE.finditer(html)}
        new = page_ids - ids
        ids.update(page_ids)
        log.info("  +%d new ids (running total %d)", len(new), len(ids))
        if p < max_page:
            _sleep(delay, jitter)
    return sorted(ids)


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def scrape(
    gen: int,
    out_dir: Path,
    delay: float,
    jitter: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ids_cache = out_dir / "_enumerated_ids.txt"
    missing_log = out_dir / "_missing_404.txt"

    with _client() as client:
        if ids_cache.exists():
            ids = sorted({int(line) for line in ids_cache.read_text().splitlines() if line.strip()})
            log.info("loaded %d ids from cache %s", len(ids), ids_cache)
        else:
            last = find_last_page(client, gen)
            if last is None:
                log.error("gen %d: time/ view not reachable (404). aborting.", gen)
                return
            log.info("gen %d: time view spans pages 0..%d (~%d sheep)",
                     gen, last, (last + 1) * 64)
            ids = enumerate_ids(client, gen, last, delay, jitter)
            ids_cache.write_text("\n".join(str(i) for i in ids) + "\n")
            log.info("cached %d ids to %s", len(ids), ids_cache)

        already_missing: set[int] = set()
        if missing_log.exists():
            already_missing = {int(x) for x in missing_log.read_text().split() if x.strip()}
            log.info("loaded %d known-missing ids from %s", len(already_missing), missing_log)

        n_total = len(ids)
        n_done = 0
        n_fetched = 0
        n_missing = 0
        for sheep_id in ids:
            n_done += 1
            dest = out_dir / f"electricsheep.{gen}.{sheep_id:05d}.flam3"
            if dest.exists():
                continue
            if sheep_id in already_missing:
                continue
            url = f"{BASE}/generation-{gen}/{sheep_id}/spex"
            log.info("[%d/%d] fetching gen=%d id=%d", n_done, n_total, gen, sheep_id)
            try:
                content = _fetch_bytes(client, url)
            except httpx.HTTPError as e:
                log.warning("  transient error: %s; sleeping and continuing", e)
                _sleep(delay, jitter)
                continue
            if content is None:
                log.info("  404 -> recording missing")
                with missing_log.open("a") as fh:
                    fh.write(f"{sheep_id}\n")
                already_missing.add(sheep_id)
                n_missing += 1
            else:
                atomic_write(dest, content)
                n_fetched += 1
            _sleep(delay, jitter)

        log.info(
            "done. fetched=%d missing=%d already-on-disk=%d total-ids=%d",
            n_fetched, n_missing, n_total - n_fetched - n_missing, n_total,
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gen", type=int, required=True)
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--jitter", type=float, default=1.0)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    scrape(args.gen, args.out, args.delay, args.jitter)
    return 0


if __name__ == "__main__":
    sys.exit(main())
