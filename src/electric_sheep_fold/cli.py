"""Typer entrypoint for electric-sheep-fold (v0.2)."""
from __future__ import annotations

import logging
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import typer

from electric_sheep_fold.chunks import Chunk
from electric_sheep_fold.fetch import fetch_all, fetch_range, make_client
from electric_sheep_fold.importer import import_dir
from electric_sheep_fold.index import build_index
from electric_sheep_fold.layout import LIVE_GENS, chunk_for, remote_url, sealed_zip_path
from electric_sheep_fold.manifest import MissingSet

app = typer.Typer(
    help="Polite mirror of Electric Sheep .flam3 genomes (chunked .zip storage).",
    add_completion=False,
    no_args_is_help=True,
)


RANGE_RE = re.compile(r"^(\d+)\.\.(\d+)$")
CHUNK_RANGE_RE = re.compile(r"^(\d{5})-(\d{5})$")


def _parse_range(range_str: str) -> tuple[int, int]:
    m = RANGE_RE.match(range_str)
    if not m:
        raise typer.BadParameter(f"range must be START..END, got {range_str!r}")
    start, end = int(m.group(1)), int(m.group(2))
    if end <= start:
        raise typer.BadParameter(
            f"range must be non-empty: end ({end}) must exceed start ({start})"
        )
    return start, end


def _require_live_gen(gen: int) -> None:
    """Block fetch / fetch-all on gens not served by the live v3d0 server.

    Dead-preserved gens (165 / 169 / 191 / 198 / 242 / 243 / 244 / 245) belong
    to the archive scraper + `import --whole-gen` flow; running a live fetch
    against them just wastes requests on a server that doesn't have them.
    """
    if gen not in LIVE_GENS:
        allowed = ", ".join(str(g) for g in sorted(LIVE_GENS))
        raise typer.BadParameter(
            f"--gen {gen} is not a live gen; v3d0.sheepserver.net only serves "
            f"{{{allowed}}}. For dead gens, use "
            "`python scripts/scrape_archive_gen.py --gen N` followed by "
            "`sheep-fold import <scrape-dir> --whole-gen`."
        )


def _parse_chunk_range(chunk_str: str) -> tuple[int, int]:
    m = CHUNK_RANGE_RE.match(chunk_str)
    if not m:
        raise typer.BadParameter(f"chunk must be NNNNN-NNNNN, got {chunk_str!r}")
    start = int(m.group(1))
    end_inclusive = int(m.group(2))
    if end_inclusive < start:
        raise typer.BadParameter(
            f"chunk range must have end >= start, got {chunk_str!r}"
        )
    return start, end_inclusive + 1


@app.command()
def fetch(
    range_str: str = typer.Argument(..., metavar="START..END"),
    gen: int = typer.Option(248),
    delay: float = typer.Option(20.0),
    jitter: float = typer.Option(5.0),
    corpus: Path = typer.Option(Path("./corpus")),
) -> None:
    """Download .flam3 files for sheep[start, end) into the chunked corpus."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _require_live_gen(gen)
    start, end = _parse_range(range_str)
    with make_client() as client:
        stats = fetch_range(
            gen=gen, start=start, end=end, corpus_root=corpus,
            client=client, delay=delay, jitter=jitter,
        )
    typer.echo(
        f"\n{gen}: {stats.downloaded} downloaded · {stats.newly_missing} newly missing"
        f" · {stats.skip_local} skip-local · {stats.skip_known_missing} skip-known-missing"
        f" · {stats.chunks_sealed} chunks sealed · {stats.transient_errors} transient errors"
    )


@app.command("fetch-all")
def fetch_all_cmd(
    gen: int = typer.Option(248),
    upper: int = typer.Option(50_000, help="Upper bound for sheep ids (exclusive)"),
    delay: float = typer.Option(20.0),
    jitter: float = typer.Option(5.0),
    corpus: Path = typer.Option(Path("./corpus")),
) -> None:
    """Fetch the entire range [0, upper) for one gen. Resumable; idempotent."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _require_live_gen(gen)
    with make_client() as client:
        stats = fetch_all(
            gen=gen, corpus_root=corpus, client=client,
            upper=upper, delay=delay, jitter=jitter,
        )
    typer.echo(
        f"\n{gen}: {stats.downloaded} downloaded · {stats.newly_missing} newly missing"
        f" · {stats.skip_local} skip-local · {stats.skip_known_missing} skip-known-missing"
        f" · {stats.chunks_sealed} chunks sealed · {stats.transient_errors} transient errors"
    )


@app.command("import")
def import_cmd(
    src: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    corpus: Path = typer.Option(Path("./corpus")),
    whole_gen: bool = typer.Option(
        False,
        "--whole-gen",
        help="Seal as one whole-gen zip (for dead-preserved gens from "
        "electricsheep.com archive). Also copies _missing_404.txt → missing.txt.",
    ),
    gen: int | None = typer.Option(
        None,
        "--gen",
        help="Generation number (required with --whole-gen if src has multiple gens; "
        "inferred from filenames otherwise).",
    ),
) -> None:
    """Recursively import existing local electricsheep.*.flam3 files."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        stats = import_dir(src, corpus, whole_gen=whole_gen, gen=gen)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    typer.echo(
        f"\nimported {stats.imported} · skipped {stats.skipped} · sealed {stats.sealed} chunks"
    )


@app.command()
def seal(
    chunk: str = typer.Option(..., "--chunk", metavar="NNNNN-NNNNN", help="Chunk range, e.g. 20000-29999"),
    gen: int = typer.Option(248),
    corpus: Path = typer.Option(Path("./corpus")),
) -> None:
    """Force-seal a working chunk whose range isn't fully probed yet."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    start, end = _parse_chunk_range(chunk)
    c = Chunk(gen=gen, start=start, end=end, corpus_root=corpus)
    if c.status == "sealed":
        typer.echo(f"chunk {c.range_str} already sealed")
        raise typer.Exit(code=0)
    if c.status == "empty":
        typer.echo(f"chunk {c.range_str} is empty — nothing to seal")
        raise typer.Exit(code=1)
    missing = MissingSet(corpus / str(gen) / "missing.txt")
    missing.load()
    c.seal(
        missing,
        source_url_for=lambda sid: remote_url(gen, sid),
        fetched_at_for=lambda sid: datetime.now(tz=timezone.utc),
    )
    typer.echo(f"sealed chunk {c.range_str}")


@app.command()
def index(
    corpus: Path = typer.Option(Path("./corpus")),
    out: Path = typer.Option(
        None,
        "--out",
        help="Where to write index.json + INDEX.md (default: {corpus}/_index/).",
    ),
) -> None:
    """Build a machine-queryable corpus index (index.json + INDEX.md).

    Walks every sealed zip and working chunk dir; classifies each flam3 into
    genome / animation / corrupt; emits per-flame structural metadata
    (variations, xform_count, pyr3-limitation flags). Re-runnable; overwrites.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out_dir = out if out is not None else (corpus / "_index")
    summary = build_index(corpus, out_dir)
    typer.echo(
        f"\nindexed {summary['total']:,} flames "
        f"({summary['genomes']:,} genome · {summary['animations']:,} animation "
        f"· {summary['corrupt']:,} corrupt) · "
        f"{summary['distinct_variations']} distinct variations"
    )
    typer.echo(f"wrote {out_dir / 'index.json'}")
    typer.echo(f"wrote {out_dir / 'INDEX.md'}")


@app.command()
def status(
    gen: int = typer.Option(248),
    corpus: Path = typer.Option(Path("./corpus")),
) -> None:
    """Show corpus status: per-chunk state + known-missing count."""
    gen_root = corpus / str(gen)
    if not gen_root.exists():
        typer.echo(f"{gen}: corpus not yet materialized (run `sheep-fold fetch` first)")
        return

    sealed_zips = list(gen_root.glob("?????-?????.zip"))
    working_dirs = [
        p for p in gen_root.iterdir()
        if p.is_dir() and re.match(r"^\d{5}-\d{5}$", p.name)
    ]
    ms = MissingSet(gen_root / "missing.txt")
    ms.load()

    total_sheep = 0
    for zip_path in sealed_zips:
        with zipfile.ZipFile(zip_path, "r") as zf:
            total_sheep += sum(
                1 for n in zf.namelist() if n.startswith("electricsheep.")
            )
    for d in working_dirs:
        total_sheep += sum(1 for _ in d.glob("electricsheep.*.flam3"))

    typer.echo(
        f"{gen}: {len(sealed_zips)} sealed · {len(working_dirs)} working · "
        f"{total_sheep} sheep total · {len(ms)} known-missing"
    )


if __name__ == "__main__":
    app()
