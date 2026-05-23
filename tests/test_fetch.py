"""Tests for electric_sheep_fold.fetch — v0.3 loose-corpus state machine."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from electric_sheep_fold.fetch import ensure_corpus_initialized, fetch_all, fetch_range
from electric_sheep_fold.layout import flam3_filename, flam3_path
from electric_sheep_fold.manifest import MissingSet


def _build_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


FLAM3 = b'<?xml version="1.0"?><flame name="t"><xform weight="1" linear="1"/></flame>'


class TestEnsureCorpusInitialized:
    def test_creates_root_and_attribution(self, tmp_path: Path):
        root = tmp_path / "corpus"
        ensure_corpus_initialized(root)
        assert root.exists()
        attr = root / "ATTRIBUTION.md"
        assert attr.exists()
        assert "Scott Draves" in attr.read_text(encoding="utf-8")

    def test_idempotent_no_overwrite(self, tmp_path: Path):
        root = tmp_path / "corpus"
        root.mkdir()
        attr = root / "ATTRIBUTION.md"
        attr.write_text("custom", encoding="utf-8")
        ensure_corpus_initialized(root)
        assert attr.read_text(encoding="utf-8") == "custom"


class TestFetchWritesChunked:
    def test_fetched_file_lands_at_chunked_path(self, tmp_path: Path):
        def handler(req):
            return httpx.Response(200, content=FLAM3)
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=101, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.downloaded == 1
        assert stats.files_written == 1
        dest = flam3_path(248, 100, tmp_path)
        # v0.4 invariant: corpus/{gen}/{bucket}/electricsheep.{gen}.{id}.flam3.
        assert dest == tmp_path / "248" / "00000" / "electricsheep.248.00100.flam3"
        assert dest.exists()
        assert dest.read_bytes() == FLAM3

    def test_only_bucket_subdir_created(self, tmp_path: Path):
        def handler(req):
            return httpx.Response(200, content=FLAM3)
        client = _build_client(handler)
        fetch_range(
            gen=248, start=100, end=101, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        gen_root = tmp_path / "248"
        # v0.4 invariant: exactly one bucket dir (per fetched id range), no
        # sealed zips, no legacy NNNNN-NNNNN chunks.
        subdirs = [p.name for p in gen_root.iterdir() if p.is_dir()]
        assert subdirs == ["00000"]
        zips = list(gen_root.glob("*.zip"))
        assert zips == []


class TestFetchRange404:
    def test_records_missing(self, tmp_path: Path):
        def handler(req):
            return httpx.Response(404)
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=102, end=103, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.newly_missing == 1
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.load()
        assert ms.contains(102)


class TestFetchRange5xx:
    def test_transient_not_recorded(self, tmp_path: Path):
        def handler(req):
            return httpx.Response(503)
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=200, end=201, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.transient_errors == 1
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.load()
        assert not ms.contains(200)


class TestSkipLocalHit:
    def test_no_network_when_loose_file_exists(self, tmp_path: Path):
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(200, content=b"never")
        # Pre-populate loose flam3 directly at v0.3 path.
        dest = flam3_path(248, 100, tmp_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"already")
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=101, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.skip_local == 1
        assert calls["n"] == 0


class TestSkipKnownMissing:
    def test_skip_when_in_missing(self, tmp_path: Path):
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        ms = MissingSet(gen_root / "missing.txt")
        ms.add(102)
        ms.save_atomic()
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(200, content=b"never")
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=102, end=103, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.skip_known_missing == 1
        assert calls["n"] == 0


class TestFetchResumeGuard:
    """Daemon-resume guard: fetch_range must refuse to start if the corpus
    has diverged from its post-unseal baseline (id count shrunk)."""

    def test_diverged_unseal_log_blocks_fetch(self, tmp_path: Path):
        # Record a verified baseline of (loose=10, missing=5) for gen 248,
        # but stage the corpus with NO files at all → divergence.
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        (tmp_path / "_unseal-verified.json").write_text(json.dumps([
            {
                "gen": 248,
                "loose_count": 10,
                "missing_count": 5,
                "source_sha256": "deadbeef",
                "snapshot_path": "/nowhere/gen-248.zip",
                "unsealed_at": "2026-05-22T00:00:00+00:00",
            }
        ]))
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(200, content=FLAM3)
        client = _build_client(handler)
        with pytest.raises(RuntimeError, match="consistency check failed"):
            fetch_range(
                gen=248, start=0, end=1, corpus_root=tmp_path,
                client=client, delay=0, jitter=0,
            )
        # And no requests went out.
        assert calls["n"] == 0

    def test_no_log_no_guard(self, tmp_path: Path):
        # Empty / absent verified log → consistency check passes trivially.
        def handler(req):
            return httpx.Response(404)
        client = _build_client(handler)
        # Should NOT raise.
        fetch_range(
            gen=248, start=0, end=1, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )


class TestMigrationRunsBeforeFetch:
    def test_v0_1_layout_migrated_on_first_fetch(self, tmp_path: Path):
        # Pre-create a v0.1 bucket with a sheep.
        gen_root = tmp_path / "248"
        bucket = gen_root / "00xxx"
        bucket.mkdir(parents=True)
        (bucket / flam3_filename(248, 100)).write_bytes(b"legacy")
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(404)
        client = _build_client(handler)
        # Fetch a different id — but migration should still have moved 100
        # into the v0.3 loose path.
        fetch_range(
            gen=248, start=200, end=201, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert not bucket.exists()
        assert flam3_path(248, 100, tmp_path).exists()


class TestFetchAll:
    def test_fetch_all_invokes_full_range(self, tmp_path: Path):
        seen_ids: list[int] = []
        def handler(req):
            parts = req.url.path.split("/")
            seen_ids.append(int(parts[3]))
            return httpx.Response(404)
        client = _build_client(handler)
        fetch_all(
            gen=248, corpus_root=tmp_path, client=client,
            upper=5, delay=0, jitter=0,
        )
        assert seen_ids == [0, 1, 2, 3, 4]
