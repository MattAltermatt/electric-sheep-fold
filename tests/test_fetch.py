"""Tests for electric_sheep_fold.fetch — v0.2 chunk-aware state machine."""
from __future__ import annotations

import zipfile
from pathlib import Path

import httpx

from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.fetch import ensure_corpus_initialized, fetch_all, fetch_range
from electric_sheep_fold.layout import flam3_filename, sealed_zip_path, working_path
from electric_sheep_fold.manifest import MissingSet


def _build_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


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


FLAM3 = b'<?xml version="1.0"?><flame name="t"><xform weight="1" linear="1"/></flame>'


class TestFetchRange200:
    def test_writes_into_working_dir(self, tmp_path: Path):
        def handler(req):
            return httpx.Response(200, content=FLAM3)
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=101, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.downloaded == 1
        dest = working_path(248, 100, tmp_path)
        assert dest.exists()
        assert dest.read_bytes() == FLAM3


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


class TestSkipWorkingDirHit:
    def test_no_network_when_in_working_dir(self, tmp_path: Path):
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(200, content=b"never")
        # Pre-populate working dir
        dest = working_path(248, 100, tmp_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"already")
        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=101, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        assert stats.skip_local == 1
        assert calls["n"] == 0


class TestSkipSealedZipHit:
    def test_no_network_when_in_sealed_zip(self, tmp_path: Path):
        # Pre-create a sealed zip containing sheep 100
        zip_path = sealed_zip_path(248, 0, 10_000, tmp_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("MANIFEST.csv", "id\n100\n")
            zf.writestr(flam3_filename(248, 100), b"sealed-content")
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(200, content=b"never")
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


class TestSealOnRangeCompletion:
    def test_seals_chunk_when_range_completes(self, tmp_path: Path):
        # Pre-populate missing.txt with everything in [0, 10) except 5
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        ms = MissingSet(gen_root / "missing.txt")
        for sid in (0, 1, 2, 3, 4, 6, 7, 8, 9):
            ms.add(sid)
        ms.save_atomic()
        def handler(req):
            return httpx.Response(200, content=FLAM3)
        client = _build_client(handler)
        fetch_range(
            gen=248, start=5, end=6, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        # Whole chunk 0..9 is now known; fetch_range's end-of-loop seal sweep should seal it
        # NOTE: chunk size is 10000 in production, so this test relies on monkey-patching or
        # falls back to verifying the working-dir state. We use a chunk-overriding test path:
        # since fetch_range itself uses production CHUNK_SIZE, this test asserts the
        # behavior in the typical case — write happened; sealing for the full-10k case is
        # exercised by test_chunks.py:TestSeal and via a dedicated integration test below.
        dest = working_path(248, 5, tmp_path)
        assert dest.exists()


class TestSealSweepFullChunkSize:
    """Integration test: exercises the production CHUNK_SIZE=10000 seal path."""

    def test_seals_full_chunk_and_cleans_working_dir(self, tmp_path: Path):
        # Pre-populate missing.txt with every id in [0, 10000) except 5000
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        ms = MissingSet(gen_root / "missing.txt")
        for sid in range(0, 10_000):
            if sid != 5000:
                ms.add(sid)
        ms.save_atomic()

        def handler(req):
            return httpx.Response(200, content=FLAM3)

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=5000, end=5001, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )

        assert stats.chunks_sealed == 1

        zip_path = sealed_zip_path(248, 0, 10_000, tmp_path)
        assert zip_path.exists()

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert "MANIFEST.csv" in names
        assert flam3_filename(248, 5000) in names

        # Working dir is cleaned up after seal
        assert not (tmp_path / "248" / "00000-09999").exists()


class TestMigrationRunsBeforeFetch:
    def test_v0_1_layout_migrated_on_first_fetch(self, tmp_path: Path):
        # Pre-create a v0.1 bucket with a sheep, plus an empty missing.txt
        gen_root = tmp_path / "248"
        bucket = gen_root / "00xxx"
        bucket.mkdir(parents=True)
        (bucket / flam3_filename(248, 100)).write_bytes(b"legacy")
        calls = {"n": 0}
        def handler(req):
            calls["n"] += 1
            return httpx.Response(404)
        client = _build_client(handler)
        # Fetch a different id (200) — but migration should still have moved 100
        fetch_range(
            gen=248, start=200, end=201, corpus_root=tmp_path,
            client=client, delay=0, jitter=0,
        )
        # The v0.1 bucket is gone, the file is in the v0.2 working dir
        assert not bucket.exists()
        assert working_path(248, 100, tmp_path).exists()


class TestFetchAll:
    def test_fetch_all_invokes_full_range(self, tmp_path: Path):
        seen_ids: list[int] = []
        def handler(req):
            # Parse id out of the URL path: /gen/248/{id}/electricsheep...
            parts = req.url.path.split("/")
            seen_ids.append(int(parts[3]))
            return httpx.Response(404)
        client = _build_client(handler)
        fetch_all(
            gen=248, corpus_root=tmp_path, client=client,
            upper=5, delay=0, jitter=0,
        )
        assert seen_ids == [0, 1, 2, 3, 4]
