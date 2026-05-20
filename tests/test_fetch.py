"""Tests for electric_sheep_fold.fetch — state machine branches with MockTransport."""
from pathlib import Path

import httpx

from electric_sheep_fold.fetch import ensure_corpus_initialized, fetch_range
from electric_sheep_fold.layout import local_path
from electric_sheep_fold.manifest import MissingSet


def _build_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


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
        attr.write_text("custom content", encoding="utf-8")
        ensure_corpus_initialized(root)
        assert attr.read_text(encoding="utf-8") == "custom content"


class TestFetchRange200:
    def test_writes_file_on_200(self, tmp_path: Path):
        body = b"<flame name='electricsheep.248.00100' />"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body)

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=101,
            corpus_root=tmp_path, client=client,
            delay=0, jitter=0,
        )
        assert stats.downloaded == 1
        assert stats.newly_missing == 0
        dest = local_path(248, 100, tmp_path)
        assert dest.exists()
        assert dest.read_bytes() == body


class TestFetchRange404:
    def test_records_missing_and_persists(self, tmp_path: Path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=102, end=103,
            corpus_root=tmp_path, client=client,
            delay=0, jitter=0,
        )
        assert stats.newly_missing == 1
        assert stats.downloaded == 0
        assert not local_path(248, 102, tmp_path).exists()

        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.load()
        assert ms.contains(102)


class TestFetchRange5xx:
    def test_does_not_record_missing(self, tmp_path: Path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=200, end=201,
            corpus_root=tmp_path, client=client,
            delay=0, jitter=0,
        )
        assert stats.transient_errors == 1
        assert stats.newly_missing == 0
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.load()
        assert not ms.contains(200)


class TestSkipLocal:
    def test_skips_when_file_present(self, tmp_path: Path):
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, content=b"never-served")

        # Pre-populate the local file.
        dest = local_path(248, 100, tmp_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"already-here")

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=101,
            corpus_root=tmp_path, client=client, delay=0, jitter=0,
        )
        assert stats.skip_local == 1
        assert call_count["n"] == 0
        assert dest.read_bytes() == b"already-here"


class TestSkipKnownMissing:
    def test_skips_when_in_missing(self, tmp_path: Path):
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(200, content=b"never-served")

        # Pre-populate missing.txt.
        gen_root = tmp_path / "248"
        gen_root.mkdir(parents=True)
        ms = MissingSet(gen_root / "missing.txt")
        ms.add(102)
        ms.save_atomic()

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=102, end=103,
            corpus_root=tmp_path, client=client, delay=0, jitter=0,
        )
        assert stats.skip_known_missing == 1
        assert call_count["n"] == 0


class TestAtomicWrite:
    def test_no_tmp_left_after_success(self, tmp_path: Path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"body")

        client = _build_client(handler)
        fetch_range(
            gen=248, start=100, end=101,
            corpus_root=tmp_path, client=client, delay=0, jitter=0,
        )
        dest = local_path(248, 100, tmp_path)
        tmp_file = dest.with_suffix(dest.suffix + ".tmp")
        assert dest.exists()
        assert not tmp_file.exists()


class TestMultipleSheep:
    def test_mixed_200_and_404(self, tmp_path: Path):
        def handler(request: httpx.Request) -> httpx.Response:
            # 100 → 200, 101 → 404, 102 → 200
            if "/100/" in request.url.path:
                return httpx.Response(200, content=b"a")
            if "/101/" in request.url.path:
                return httpx.Response(404)
            if "/102/" in request.url.path:
                return httpx.Response(200, content=b"c")
            return httpx.Response(500)

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=100, end=103,
            corpus_root=tmp_path, client=client, delay=0, jitter=0,
        )
        assert stats.downloaded == 2
        assert stats.newly_missing == 1
        assert local_path(248, 100, tmp_path).exists()
        assert not local_path(248, 101, tmp_path).exists()
        assert local_path(248, 102, tmp_path).exists()
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.load()
        assert ms.contains(101)


class TestTransientException:
    def test_connect_error_counts_transient(self, tmp_path: Path):
        """Network-layer failures (timeout, connect refused) count as transient,
        do NOT add to missing.txt, and do NOT crash the loop."""
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("mock refused")

        client = _build_client(handler)
        stats = fetch_range(
            gen=248, start=300, end=301,
            corpus_root=tmp_path, client=client, delay=0, jitter=0,
        )
        assert stats.transient_errors == 1
        assert stats.downloaded == 0
        assert stats.newly_missing == 0
        # Crucially: not added to missing (transient ≠ permanent)
        ms = MissingSet(tmp_path / "248" / "missing.txt")
        ms.load()
        assert not ms.contains(300)
