"""Throwaway: preserve a dead Electric Sheep generation from electricsheep.com.

The archive's `time/N.html` pages are only a *partial* index — many sheep ids
exist beyond what the time view links to (e.g. gen 244 reaches id 86,435 even
though time pages cap around 32,000). To preserve *everything*, this script
runs in three phases per gen:

1. **Time-page enumeration** — walk `archives/generation-N/time/*.html` to
   harvest the indexed ids. Cached to `_enumerated_ids.txt`.
2. **Upper-bound discovery** — doubling probe + windowed binary search via the
   `spex` endpoint to find the highest sheep id that returns a valid flam3.
   Cached to `_discovered_max_id.txt`.
3. **Gap sweep** — for every id in `[0, max_id]` not already on disk and not
   already in `_missing_404.txt`, GET spex. Save valid flam3 content; 404 or
   non-flam3 200 (e.g. body `"none\n"`) → record missing.

Use for dead gens (165, 169, 191, 198, 242, 243, 244, 245, ...). For LIVE gens
(247, 248) prefer the main `sheep-fold fetch-all` against v3d0.

Output: flat directory of canonical-named files. Feed to `sheep-fold import`.

Usage:
    python scripts/scrape_archive_gen.py --gen 242 --out corpus/_scrape-242
    sheep-fold import corpus/_scrape-242

Resumable: re-running picks up where it left off (every cache + sticky-404
ledger is consulted; only true unknowns hit the network).

Politeness: 2s ±1s jitter per request to electricsheep.com. With multiple
gens running in parallel (see preserve_archived_sheep.sh) the aggregate is
still gentle.
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

# Allow `from electric_sheep_fold.extract import is_flam3_content` when run as a
# script (no editable install present).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
from electric_sheep_fold.extract import is_flam3_content  # noqa: E402

USER_AGENT = (
    "electric-sheep-fold/0.2 archive-preservation "
    "(https://github.com/muwamath/electric-sheep-fold)"
)
BASE = "https://electricsheep.com/archives"

_TIME_PAGE_RE = re.compile(r"time/(\d+)\.html")
_SHEEP_LINK_RE = re.compile(r"sheep/(\d+)/")

# Safety cap for upper-bound discovery — no real gen has come close to this.
_DISCOVERY_HARD_CAP = 10_000_000

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


def _fetch_spex(client: httpx.Client, gen: str, sheep_id: int) -> tuple[int, bytes]:
    """GET the spex endpoint for one sheep. Returns (status_code, body).

    Body is empty bytes for 404. For 2xx, body is the raw response — caller
    decides whether it's valid flam3 via is_flam3_content().
    """
    url = f"{BASE}/generation-{gen}/{sheep_id}/spex"
    r = client.get(url)
    if r.status_code == 404:
        return 404, b""
    r.raise_for_status()
    return r.status_code, r.content


def find_last_page(client: httpx.Client, gen: str) -> int | None:
    """Probe /time/index.html for the highest time/N.html link."""
    html = _fetch_text(client, f"{BASE}/generation-{gen}/time/index.html")
    if html is None:
        return None
    pages = [int(m.group(1)) for m in _TIME_PAGE_RE.finditer(html)]
    return max(pages) if pages else 0


def enumerate_via_time_pages(
    client: httpx.Client,
    gen: str,
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


def _probe_window(
    client: httpx.Client,
    gen: str,
    center: int,
    window: int,
    delay: float,
    jitter: float,
) -> tuple[int, int]:
    """Sample `window` consecutive ids starting at `center`. Returns (hits, last_hit).

    `hits` is the count of 200-OK + valid-flam3 responses. `last_hit` is the
    highest id that returned a valid flam3, or -1 if none did. Each probe
    sleeps per the politeness cadence.
    """
    hits = 0
    last_hit = -1
    for offset in range(window):
        sid = center + offset
        try:
            status, body = _fetch_spex(client, gen, sid)
        except httpx.HTTPError as e:
            log.warning("  probe %d transient: %s", sid, e)
            _sleep(delay, jitter)
            continue
        if status == 200 and is_flam3_content(body):
            hits += 1
            last_hit = sid
        _sleep(delay, jitter)
    return hits, last_hit


def discover_max_id(
    client: httpx.Client,
    gen: str,
    start_hint: int,
    delay: float,
    jitter: float,
    window: int = 10,
) -> int:
    """Find a safe upper bound for sheep_ids via doubling probe + bisection.

    Returns the highest id confirmed present (via 200 + valid flam3) during
    the discovery walk. The sweep phase will then probe [0, result + slack]
    to cover any ids just above the discovered hit.

    Algorithm:
      1. Lower = start_hint (assume present). Probe windows at 2x, 4x, 8x...
         until a window returns 0 hits. That's the upper-404 zone.
      2. Bisect [last_hit, upper_404]: probe windows at midpoints, narrowing
         until the gap is smaller than `window`.
      3. Return the highest hit id seen across all probes.
    """
    log.info("discover_max_id gen=%s start_hint=%d window=%d", gen, start_hint, window)

    # Phase 1: doubling search for an upper-404 zone
    lower = max(start_hint, 1)
    upper: int | None = None
    best_hit = -1
    probe_at = lower
    doublings = 0
    while True:
        if probe_at > _DISCOVERY_HARD_CAP:
            log.warning("hard-cap %d reached during doubling; treating as upper",
                        _DISCOVERY_HARD_CAP)
            upper = probe_at
            break
        hits, last = _probe_window(client, gen, probe_at, window, delay, jitter)
        log.info("  doubling probe @%d window=%d -> hits=%d last_hit=%d",
                 probe_at, window, hits, last)
        if hits > 0:
            best_hit = max(best_hit, last)
            lower = max(lower, probe_at + window - 1)
            probe_at *= 2
            doublings += 1
        else:
            upper = probe_at
            break

    if upper is None:
        # Doubling never found a 404 zone (or hit hard cap) — return best_hit
        return best_hit

    log.info("doubling found [lower=%d, upper=%d] in %d doublings", lower, upper, doublings)

    # Phase 2: bisect [lower, upper] to tighten
    while upper - lower > window:
        mid = (lower + upper) // 2
        hits, last = _probe_window(client, gen, mid, window, delay, jitter)
        log.info("  bisect probe @%d -> hits=%d last_hit=%d", mid, hits, last)
        if hits > 0:
            best_hit = max(best_hit, last)
            lower = mid + window - 1
        else:
            upper = mid

    log.info("discover_max_id gen=%s -> max_id=%d (probed up to %d)",
             gen, best_hit, upper)
    return best_hit


def atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _load_missing(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {int(x) for x in path.read_text().split() if x.strip()}


def _append_missing(path: Path, sheep_id: int) -> None:
    with path.open("a") as fh:
        fh.write(f"{sheep_id}\n")


def sweep_ids(
    client: httpx.Client,
    gen: str,
    ids_to_fetch: list[int],
    out_dir: Path,
    missing_path: Path,
    delay: float,
    jitter: float,
) -> tuple[int, int]:
    """For each id, fetch spex. Save valid flam3 → atomic write. Else record missing.

    Returns (n_fetched, n_missing). Skips ids whose file already exists (cheap,
    no network). Honors the sticky-404 invariant: ids already in missing_path
    are never re-probed.
    """
    n_total = len(ids_to_fetch)
    n_fetched = 0
    n_missing = 0
    n_done = 0
    already_missing = _load_missing(missing_path)
    if already_missing:
        log.info("loaded %d known-missing ids from %s",
                 len(already_missing), missing_path)

    for sheep_id in ids_to_fetch:
        n_done += 1
        dest = out_dir / f"electricsheep.{gen}.{sheep_id:05d}.flam3"
        if dest.exists():
            continue
        if sheep_id in already_missing:
            continue
        log.info("[%d/%d] fetching gen=%s id=%d", n_done, n_total, gen, sheep_id)
        try:
            status, body = _fetch_spex(client, gen, sheep_id)
        except httpx.HTTPError as e:
            log.warning("  transient error: %s; sleeping and continuing", e)
            _sleep(delay, jitter)
            continue
        if status == 404:
            log.info("  404 -> recording missing")
            _append_missing(missing_path, sheep_id)
            already_missing.add(sheep_id)
            n_missing += 1
        elif is_flam3_content(body):
            atomic_write(dest, body)
            n_fetched += 1
        else:
            preview = body[:32].decode("utf-8", errors="replace")
            log.info("  200 but not-flam3 (body starts %r) -> recording missing",
                     preview)
            _append_missing(missing_path, sheep_id)
            already_missing.add(sheep_id)
            n_missing += 1
        _sleep(delay, jitter)

    return n_fetched, n_missing


def scrape(
    gen: str,
    out_dir: Path,
    delay: float,
    jitter: float,
    discovery_window: int = 10,
    discovery_buffer: int = 100,
) -> None:
    """Run the full pipeline for one gen: enumerate → discover → sweep."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ids_cache = out_dir / "_enumerated_ids.txt"
    missing_path = out_dir / "_missing_404.txt"
    max_id_cache = out_dir / "_discovered_max_id.txt"

    with _client() as client:
        # Phase 1: time-page enumeration (cached)
        if ids_cache.exists():
            time_ids = sorted({int(line) for line in ids_cache.read_text().splitlines() if line.strip()})
            log.info("loaded %d time-page ids from cache %s", len(time_ids), ids_cache)
        else:
            last = find_last_page(client, gen)
            if last is None:
                log.error("gen %s: time/ view not reachable (404). aborting.", gen)
                return
            log.info("gen %s: time view spans pages 0..%d (~%d sheep)",
                     gen, last, (last + 1) * 64)
            time_ids = enumerate_via_time_pages(client, gen, last, delay, jitter)
            ids_cache.write_text("\n".join(str(i) for i in time_ids) + "\n")
            log.info("cached %d time-page ids to %s", len(time_ids), ids_cache)

        # Phase 2: upper-bound discovery (cached)
        if max_id_cache.exists():
            max_id = int(max_id_cache.read_text().strip())
            log.info("loaded discovered max_id=%d from cache %s", max_id, max_id_cache)
        else:
            on_disk_ids = _ids_on_disk(out_dir, gen)
            start_hint = max(
                max(time_ids, default=0),
                max(on_disk_ids, default=0),
                1,
            ) + 1
            max_id = discover_max_id(
                client, gen, start_hint=start_hint,
                delay=delay, jitter=jitter, window=discovery_window,
            )
            max_id_cache.write_text(f"{max_id}\n")
            log.info("cached discovered max_id=%d to %s", max_id, max_id_cache)

        # Phase 3: sweep [0, max_id + buffer]
        sweep_upper = max_id + discovery_buffer
        full_range = list(range(0, sweep_upper + 1))
        log.info("sweeping gen=%s range [0..%d] (incl. %d-id slack)",
                 gen, sweep_upper, discovery_buffer)
        n_fetched, n_missing = sweep_ids(
            client, gen, full_range, out_dir, missing_path,
            delay=delay, jitter=jitter,
        )

        on_disk_final = _ids_on_disk(out_dir, gen)
        log.info(
            "done. fetched=%d missing=%d on-disk-total=%d sweep-range=%d max-discovered=%d",
            n_fetched, n_missing, len(on_disk_final), sweep_upper, max_id,
        )


_FNAME_RE_TEMPLATE = r"^electricsheep\.{gen}\.(\d+)\.flam3$"


def _ids_on_disk(out_dir: Path, gen: str) -> set[int]:
    """Discover all sheep_ids for `gen` already living in out_dir as .flam3 files."""
    pat = re.compile(_FNAME_RE_TEMPLATE.format(gen=re.escape(gen)))
    found: set[int] = set()
    for f in out_dir.glob(f"electricsheep.{gen}.*.flam3"):
        m = pat.match(f.name)
        if m:
            try:
                found.add(int(m.group(1)))
            except ValueError:
                pass
    return found


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--gen", type=str, required=True,
                   help="generation name (e.g. 244, old, very-old)")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--delay", type=float, default=2.0,
                   help="seconds between requests (default 2.0 — archive politeness)")
    p.add_argument("--jitter", type=float, default=1.0,
                   help="additional uniform jitter on top of --delay")
    p.add_argument("--discovery-window", type=int, default=10,
                   help="how many consecutive ids to sample per discovery probe")
    p.add_argument("--discovery-buffer", type=int, default=100,
                   help="extra ids to sweep past the discovered max")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [gen=" + args.gen + "] %(message)s",
        datefmt="%H:%M:%S",
    )
    scrape(
        args.gen, args.out,
        delay=args.delay, jitter=args.jitter,
        discovery_window=args.discovery_window,
        discovery_buffer=args.discovery_buffer,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
