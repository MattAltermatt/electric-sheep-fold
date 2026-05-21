"""Tests for scripts/scrape_archive_gen.py — discover-then-sweep mechanism.

The scraper drives multi-day preservation runs against electricsheep.com.
The discovery probe in particular is critical: if it terminates too early,
we lose sheep; if it overshoots, we waste ~hours of polite-cadence requests.
These tests pin its behavior against a controllable mock server.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

# scripts/ is not a package; add it to sys.path explicitly.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

import scrape_archive_gen as scraper  # noqa: E402


FLAM3 = (
    b'<flame name="t" time="0"><xform weight="1" linear="1"/></flame>'
)
NONE = b"none\n"


def _make_client(corpus: dict[int, bytes]) -> httpx.Client:
    """Build an httpx.Client whose GETs are served from an in-memory dict.

    Keys are sheep_ids that exist; missing keys 404. Values that are empty
    bytes simulate the 'none' placeholder (200-OK but not flam3).
    """
    def handler(request: httpx.Request) -> httpx.Response:
        # Parse `/archives/generation-X/<id>/spex` to recover the id.
        path = request.url.path
        if "/spex" not in path:
            return httpx.Response(404)
        parts = path.rstrip("/").split("/")
        # parts: ['', 'archives', 'generation-X', '<id>', 'spex']
        try:
            sid = int(parts[-2])
        except (ValueError, IndexError):
            return httpx.Response(404)
        if sid not in corpus:
            return httpx.Response(404)
        body = corpus[sid]
        if body == NONE:
            return httpx.Response(200, content=NONE)
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestDiscoverMaxId:
    def test_finds_simple_max(self):
        """Discovery should find a clear single-region upper bound."""
        # Gen with sheep at ids 0..199, nothing beyond.
        corpus = {i: FLAM3 for i in range(200)}
        with _make_client(corpus) as client:
            max_id = scraper.discover_max_id(
                client, gen="42", start_hint=10,
                delay=0.0, jitter=0.0, window=5,
            )
        # Must find at least one id near the true max (199). Allow some
        # imprecision because doubling + bisect samples in windows, not 1-by-1.
        assert max_id >= 100, f"discovered max {max_id} too low"
        assert max_id <= 250, f"discovered max {max_id} runaway"

    def test_treats_none_placeholders_as_missing(self):
        """200 + body 'none\\n' must NOT extend the discovered range."""
        # Real sheep at 0..49; 'none' placeholders at 50..200.
        corpus = {i: FLAM3 for i in range(50)}
        for i in range(50, 200):
            corpus[i] = NONE
        with _make_client(corpus) as client:
            max_id = scraper.discover_max_id(
                client, gen="42", start_hint=5,
                delay=0.0, jitter=0.0, window=5,
            )
        # Max should reflect the real sheep ceiling (~50), not the 'none' tail (200).
        assert max_id < 100, f"discovery extended into 'none' tail: max={max_id}"
        assert max_id >= 30, f"discovery undershot the real ceiling: max={max_id}"

    def test_handles_empty_gen(self):
        """A gen with zero sheep should return -1 (no hits)."""
        corpus: dict[int, bytes] = {}
        with _make_client(corpus) as client:
            max_id = scraper.discover_max_id(
                client, gen="empty", start_hint=10,
                delay=0.0, jitter=0.0, window=5,
            )
        assert max_id == -1

    def test_handles_high_max(self):
        """Discovery should reach into the tens of thousands via doubling."""
        corpus = {i: FLAM3 for i in range(80_000)}
        with _make_client(corpus) as client:
            max_id = scraper.discover_max_id(
                client, gen="244", start_hint=1000,
                delay=0.0, jitter=0.0, window=5,
            )
        assert max_id >= 60_000, f"doubling didn't reach high enough: max={max_id}"
        assert max_id <= 100_000, f"discovery overshot: max={max_id}"


class TestSweepRejectsNone:
    def test_sweep_writes_flam3_but_records_none_as_missing(self, tmp_path: Path):
        """Sweep must validate 200-OK content. 'none' bodies → missing.txt, no file."""
        corpus = {0: FLAM3, 1: NONE, 2: FLAM3, 3: NONE}
        out_dir = tmp_path
        missing_path = out_dir / "_missing_404.txt"
        with _make_client(corpus) as client:
            fetched, missing = scraper.sweep_ids(
                client, gen="99",
                ids_to_fetch=[0, 1, 2, 3, 4],
                out_dir=out_dir,
                missing_path=missing_path,
                delay=0.0, jitter=0.0,
            )
        assert (out_dir / "electricsheep.99.00000.flam3").exists()
        assert (out_dir / "electricsheep.99.00002.flam3").exists()
        # 'none' placeholders must NOT land on disk
        assert not (out_dir / "electricsheep.99.00001.flam3").exists()
        assert not (out_dir / "electricsheep.99.00003.flam3").exists()
        recorded = set(int(x) for x in missing_path.read_text().split())
        assert recorded == {1, 3, 4}, f"missing={recorded}"
        assert fetched == 2
        assert missing == 3

    def test_sweep_skips_existing_files_and_known_missing(self, tmp_path: Path):
        """Skip-without-network: on-disk + known-missing ids must cost zero network."""
        corpus = {i: FLAM3 for i in range(5)}
        out_dir = tmp_path
        (out_dir / "electricsheep.99.00000.flam3").write_bytes(FLAM3)
        missing_path = out_dir / "_missing_404.txt"
        missing_path.write_text("2\n")

        # Mock client that asserts no GET for ids 0 or 2
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path.rstrip("/")
            sid = int(path.split("/")[-2])
            assert sid not in {0, 2}, f"sweep contacted skip-without-network id {sid}"
            return httpx.Response(200, content=FLAM3) if sid in corpus else httpx.Response(404)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            fetched, missing = scraper.sweep_ids(
                client, gen="99",
                ids_to_fetch=[0, 1, 2, 3],
                out_dir=out_dir,
                missing_path=missing_path,
                delay=0.0, jitter=0.0,
            )
        assert fetched == 2  # ids 1, 3
        assert missing == 0


class TestScrapeWithoutTimeView:
    """Some dead gens (e.g. 165, 169) have no time/index.html in the archive.
    Discovery + sweep must still run — phase 1 (time enum) is a free preseed,
    not a precondition.
    """

    def test_falls_through_to_discovery_when_time_view_404s(
        self, tmp_path: Path, monkeypatch
    ):
        """Time-page 404 must NOT abort the pipeline — phase 2 + 3 still run."""
        corpus = {i: FLAM3 for i in range(50)}

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if "/time/" in path:
                return httpx.Response(404)
            if "/spex" not in path:
                return httpx.Response(404)
            try:
                sid = int(path.rstrip("/").split("/")[-2])
            except (ValueError, IndexError):
                return httpx.Response(404)
            if sid in corpus:
                return httpx.Response(200, content=corpus[sid])
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(scraper, "_client", lambda: client)

        scraper.scrape(
            gen="165",
            out_dir=tmp_path,
            delay=0.0,
            jitter=0.0,
            discovery_window=5,
            discovery_buffer=20,
        )

        files = list(tmp_path.glob("electricsheep.165.*.flam3"))
        assert len(files) >= 30, (
            f"phase 1 abort prevented preservation: only {len(files)} files written"
        )

    def test_cached_max_id_never_undershoots_on_disk(
        self, tmp_path: Path, monkeypatch
    ):
        """When start_hint window misses but files exist on disk, the cached
        max must reflect the on-disk floor — otherwise next-run sweep_upper
        collapses to (-1 + buffer) and we lose the ability to discover any
        future ids past the current on-disk max.
        """
        # Pre-seed three on-disk sheep; highest is id 100.
        for i in [10, 20, 100]:
            (tmp_path / f"electricsheep.99.{i:05d}.flam3").write_bytes(FLAM3)

        # Mock: every spex returns 404 (discovery finds nothing new).
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        monkeypatch.setattr(scraper, "_client", lambda: client)

        scraper.scrape(
            gen="99",
            out_dir=tmp_path,
            delay=0.0,
            jitter=0.0,
            discovery_window=5,
            discovery_buffer=20,
        )

        cached = (tmp_path / "_discovered_max_id.txt").read_text().strip()
        assert int(cached) >= 100, (
            f"cached max_id={cached} undershot on-disk floor 100; "
            f"future runs would collapse sweep range"
        )
