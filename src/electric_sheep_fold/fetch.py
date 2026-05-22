"""Polite orchestration loop for electric-sheep-fold (v0.2 chunk-aware)."""
from __future__ import annotations

import logging
import os
import random
import re
import time
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


_SEALED_ZIP_NAME_RE = re.compile(r"^(\d{5})-(\d{5})\.zip$")


def _sealed_ids_in_gen(gen_root: Path, gen: int) -> set[int]:
    """Return every sheep_id within any sealed zip's [start, end) for `gen`.

    Range-trust semantics: each sealed zip's filename-claimed range is
    authoritative. Once `corpus/{gen}/NNNNN-MMMMM.zip` exists, ids in
    [NNNNN, MMMMM+1) are considered decided — present in the zip namelist
    OR provably absent — and must skip without network. This honors the
    CLAUDE.md invariant "range-completion is the seal trigger": the seal
    is the commitment, the namelist + missing.txt are the bookkeeping.

    Filename uses end-1 inclusive (matches layout.chunk_range_str), so the
    half-open range is `[int(m1), int(m2) + 1)`. The `gen` argument is
    intentionally unused — gen scoping comes from `gen_root` — but kept
    in the signature for call-site readability.
    """
    del gen  # gen_root already scopes; arg preserved for readability
    decided: set[int] = set()
    if not gen_root.exists():
        return decided
    for zp in gen_root.glob("?????-?????.zip"):
        m = _SEALED_ZIP_NAME_RE.match(zp.name)
        if not m:
            log.warning("skipping unparseable sealed zip name %s", zp)
            continue
        start, end_inclusive = int(m.group(1)), int(m.group(2))
        decided.update(range(start, end_inclusive + 1))
    return decided


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

    # Range-trust skip set: every id inside any sealed zip's [start, end)
    # is decided (in zip OR known-absent). The chunk_for-derived
    # `chunk.contains_id` only inspects ONE chunk's zip path AND only its
    # namelist, missing both wider whole-gen zips (v0.2.2+) and sparse
    # ranges (where the zip claims [0, 30000) but only N << 30000 ids are
    # in the namelist). Range-trust covers both. See CLAUDE.md invariant
    # "range-completion is the seal trigger".
    sealed_ids = _sealed_ids_in_gen(gen_root, gen)

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

        if sheep_id in sealed_ids or chunk.contains_id(sheep_id):
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
