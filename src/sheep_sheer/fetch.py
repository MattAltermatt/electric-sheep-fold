"""Polite orchestration loop for electric-sheep-fold."""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import httpx

from electric_sheep_fold.layout import local_path, remote_url
from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)


USER_AGENT = (
    "electric-sheep-fold/0.1 (companion to pyr3; https://github.com/muwamath/electric-sheep-fold)"
)


@dataclass
class FetchStats:
    downloaded: int = 0
    skip_local: int = 0
    skip_known_missing: int = 0
    newly_missing: int = 0
    transient_errors: int = 0


def ensure_corpus_initialized(corpus_root: Path) -> None:
    """Create corpus root + copy ATTRIBUTION.md template into place if absent.

    Required by the ES Sheep-Pack license clause: any archive of sheep must
    carry an attribution file. We satisfy that here, the moment the corpus
    directory comes into existence.
    """
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
    """Mirror sheep[start, end) for the given gen.

    Local-first dedup -> known-missing dedup -> GET -> atomic write or
    record-missing. Skips cost zero server time and zero sleep.

    The caller owns `client`'s lifecycle; `fetch_range` does not close it.
    Prefer `with make_client() as client: fetch_range(...)`.
    """
    ensure_corpus_initialized(corpus_root)

    gen_root = corpus_root / str(gen)
    gen_root.mkdir(parents=True, exist_ok=True)

    missing = MissingSet(gen_root / "missing.txt")
    missing.load()

    stats = FetchStats()

    for sheep_id in range(start, end):
        dest = local_path(gen, sheep_id, corpus_root)

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
        except httpx.RequestError as e:
            log.warning("transient error for %d.%05d: %s", gen, sheep_id, e)
            stats.transient_errors += 1
            _sleep_with_jitter(delay, jitter)
            continue

        status = response.status_code
        if status == 200:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_bytes(response.content)
            os.replace(tmp, dest)
            log.info("downloaded %d.%05d", gen, sheep_id)
            stats.downloaded += 1
        elif status == 404:
            missing.add(sheep_id)
            missing.save_atomic()
            log.info("missing %d.%05d (recorded)", gen, sheep_id)
            stats.newly_missing += 1
        else:
            log.warning(
                "unexpected status %d for %d.%05d -- treating as transient",
                status, gen, sheep_id,
            )
            stats.transient_errors += 1

        _sleep_with_jitter(delay, jitter)

    return stats


def make_client() -> httpx.Client:
    """Build an httpx.Client carrying the polite User-Agent."""
    return httpx.Client(headers={"User-Agent": USER_AGENT})
