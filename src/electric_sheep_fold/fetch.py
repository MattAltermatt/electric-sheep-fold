"""Polite orchestration loop for electric-sheep-fold (v0.2 chunk-aware)."""
from __future__ import annotations

import logging
import os
import random
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

import httpx

from electric_sheep_fold import __version__
from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.layout import chunk_for, remote_url
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import migrate_v0_1_if_needed

log = logging.getLogger(__name__)


USER_AGENT = (
    f"electric-sheep-fold/{__version__} (companion to pyr3; https://github.com/MattAltermatt/electric-sheep-fold)"
)


@dataclass
class FetchStats:
    downloaded: int = 0
    skip_local: int = 0
    skip_known_missing: int = 0
    newly_missing: int = 0
    transient_errors: int = 0
    chunks_sealed: int = 0


def ensure_corpus_initialized(corpus_root: Path) -> None:
    """Create corpus root + copy ATTRIBUTION.md template into place if absent."""
    corpus_root.mkdir(parents=True, exist_ok=True)
    attr_dest = corpus_root / "ATTRIBUTION.md"
    if not attr_dest.exists():
        template = resources.files("electric_sheep_fold.data").joinpath("ATTRIBUTION.md")
        attr_dest.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        log.info("wrote ATTRIBUTION.md to %s", attr_dest)


def _sleep_with_jitter(delay: float, jitter: float) -> None:
    if delay > 0:
        wait = delay + (random.uniform(0, jitter) if jitter > 0 else 0.0)
        time.sleep(wait)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


_FLAM3_ZIP_RE = re.compile(r"^electricsheep\.\d+\.(\d{5})\.flam3$")


def _known_ids_in_gen_zips(gen_root: Path, gen: int) -> set[int]:
    """Return all sheep_ids present in any sealed zip under gen_root.

    Walks every `NNNNN-NNNNN.zip` in the gen directory regardless of its
    range — supports both per-chunk (v0.2 / v0.2.1 live) and whole-gen
    (v0.2.1 dead / v0.2.2+) sealed-zip layouts. Filters by gen prefix
    inside the filename so a misplaced zip can't pollute the result.
    """
    known: set[int] = set()
    if not gen_root.exists():
        return known
    flam3_re = re.compile(rf"^electricsheep\.{gen}\.(\d{{5}})\.flam3$")
    for zp in gen_root.glob("?????-?????.zip"):
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                for name in zf.namelist():
                    m = flam3_re.match(name)
                    if m:
                        known.add(int(m.group(1)))
        except zipfile.BadZipFile:
            log.warning("skipping malformed zip %s", zp)
    return known


def fetch_range(
    gen: int,
    start: int,
    end: int,
    corpus_root: Path,
    client: httpx.Client,
    delay: float = 20.0,
    jitter: float = 5.0,
    timeout: float = 30.0,
) -> FetchStats:
    """Mirror sheep[start, end) for the given gen, chunk-aware.

    Local-first dedup (working dir + sealed zip) → known-missing dedup → GET →
    atomic write or record-missing. Seals chunks as their ranges complete.
    Skips cost zero server time and zero sleep.
    """
    ensure_corpus_initialized(corpus_root)
    migrate_v0_1_if_needed(corpus_root, gen)

    gen_root = corpus_root / str(gen)
    gen_root.mkdir(parents=True, exist_ok=True)

    missing = MissingSet(gen_root / "missing.txt")
    missing.load()

    stats = FetchStats()
    touched_chunks: dict[tuple[int, int], Chunk] = {}

    # Build the set of sheep_ids present in ANY sealed zip in gen_root, so
    # the skip-check works under both per-chunk and whole-gen layouts. The
    # chunk_for-derived `chunk.contains_id` only checks ONE chunk's zip
    # path, which misses ids stored in a wider whole-gen zip (v0.2.2+).
    known_in_zips = _known_ids_in_gen_zips(gen_root, gen)

    # Cache chunks across the loop to avoid re-stat'ing the zip every id
    def chunk_for_id_cached(sheep_id: int) -> Chunk:
        start_end = chunk_for(sheep_id)
        if start_end not in touched_chunks:
            touched_chunks[start_end] = Chunk(
                gen=gen, start=start_end[0], end=start_end[1], corpus_root=corpus_root,
            )
        return touched_chunks[start_end]

    for sheep_id in range(start, end):
        chunk = chunk_for_id_cached(sheep_id)

        if sheep_id in known_in_zips or chunk.contains_id(sheep_id):
            log.info("skip-local %d.%05d", gen, sheep_id)
            stats.skip_local += 1
            continue

        if missing.contains(sheep_id):
            log.info("skip-known-missing %d.%05d", gen, sheep_id)
            stats.skip_known_missing += 1
            continue

        url = remote_url(gen, sheep_id)
        try:
            response = client.get(url, timeout=timeout)
        except httpx.HTTPError as e:
            log.warning("transient error for %d.%05d: %s", gen, sheep_id, e)
            stats.transient_errors += 1
            _sleep_with_jitter(delay, jitter)
            continue

        status = response.status_code
        if status == 200:
            chunk.add_flam3(sheep_id, response.content)
            log.info("downloaded %d.%05d", gen, sheep_id)
            stats.downloaded += 1
        elif status == 404:
            missing.add(sheep_id)
            missing.save_atomic()
            log.info("missing %d.%05d (recorded)", gen, sheep_id)
            stats.newly_missing += 1
        else:
            log.warning(
                "unexpected status %d for %d.%05d — treating as transient",
                status, gen, sheep_id,
            )
            stats.transient_errors += 1

        _sleep_with_jitter(delay, jitter)

    # Seal sweep: every touched chunk whose range is now complete
    for chunk in touched_chunks.values():
        if chunk.status != "sealed" and chunk.is_range_complete(missing):
            chunk.seal(
                missing,
                source_url_for=lambda sid: remote_url(gen, sid),
                fetched_at_for=lambda sid: _now(),
            )
            stats.chunks_sealed += 1

    return stats


def fetch_all(
    gen: int,
    corpus_root: Path,
    client: httpx.Client,
    *,
    upper: int = 50_000,
    delay: float = 20.0,
    jitter: float = 5.0,
    timeout: float = 30.0,
) -> FetchStats:
    """Fetch the entire id range [0, upper) for one gen. Resumable; idempotent.

    Sticky-404 fills any tail of empty ids — re-running after a server topology
    change won't re-probe the tail.
    """
    return fetch_range(
        gen=gen, start=0, end=upper, corpus_root=corpus_root, client=client,
        delay=delay, jitter=jitter, timeout=timeout,
    )


def make_client() -> httpx.Client:
    """Build an httpx.Client carrying the polite User-Agent."""
    return httpx.Client(headers={"User-Agent": USER_AGENT})
