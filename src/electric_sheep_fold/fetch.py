"""Polite orchestration loop for electric-sheep-fold (v0.3 loose corpus)."""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import httpx

from electric_sheep_fold import __version__
from electric_sheep_fold.extract import is_flam3_content
from electric_sheep_fold.layout import flam3_path, remote_url
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import migrate_v0_1_if_needed
from electric_sheep_fold.migration import verify_chunked_consistency
from electric_sheep_fold.unseal import verify_unseal_consistency

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
    files_written: int = 0


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


def _atomic_write_flam3(dest: Path, content: bytes) -> None:
    """Write `content` to `dest` atomically via .tmp + os.replace."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(content)
    os.replace(tmp, dest)


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
    """Mirror sheep[start, end) for the given gen into the v0.3 loose corpus.

    Local-first dedup (flam3 file exists) → known-missing dedup → GET →
    atomic write or record-missing. Skips cost zero server time and zero
    sleep. Loose-corpus shape: each gen is a flat dir of `.flam3` files
    plus a `missing.txt` sticky-404 store.

    Daemon-resume guard: at the top of every call we run
    `verify_unseal_consistency` against ``corpus/_unseal-verified.json``.
    If any gen's accounted-for id count has shrunk since the post-unseal
    baseline, refuse to fetch — a missing.txt overwrite or unsealed-but-
    not-migrated state would otherwise silently re-fetch already-known ids.
    """
    ensure_corpus_initialized(corpus_root)

    divergences = verify_unseal_consistency(corpus_root)
    if divergences:
        raise RuntimeError(
            f"unseal consistency check failed: {divergences}. "
            "Run `sheep-fold unseal --all` first."
        )

    chunked_div = verify_chunked_consistency(corpus_root)
    if chunked_div:
        raise RuntimeError(
            f"chunked consistency check failed: {chunked_div}. "
            "Run `sheep-fold migrate-chunked` first."
        )

    migrate_v0_1_if_needed(corpus_root, gen)

    gen_root = corpus_root / str(gen)
    gen_root.mkdir(parents=True, exist_ok=True)

    missing = MissingSet(gen_root / "missing.txt")
    missing.load()

    stats = FetchStats()

    for sheep_id in range(start, end):
        dest = flam3_path(gen, sheep_id, corpus_root)
        if dest.exists():
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
        if status == 200 and is_flam3_content(response.content):
            _atomic_write_flam3(dest, response.content)
            log.info("downloaded %d.%05d", gen, sheep_id)
            stats.downloaded += 1
            stats.files_written += 1
        elif status == 200:
            # 200 OK but the body is not a flam3 (the `none\n` sentinel, an
            # HTML error page, an empty body). NEVER write it to the corpus —
            # a poisoned .flam3 would mark this id skip-local forever — and do
            # NOT record it missing (it isn't a 404). Retry-able transient.
            log.warning(
                "200 OK with non-flam3 body for %d.%05d — treating as transient",
                gen, sheep_id,
            )
            stats.transient_errors += 1
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
