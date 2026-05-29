"""Typer entrypoint for electric-sheep-fold (v0.3 loose corpus)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import typer

from electric_sheep_fold.chunk import build_chunks_tar
from electric_sheep_fold.fetch import fetch_all, fetch_range, make_client
from electric_sheep_fold.importer import import_dir
from electric_sheep_fold.index import build_index
from electric_sheep_fold.layout import LIVE_GENS
from electric_sheep_fold.manifest import MissingSet
from electric_sheep_fold.migration import (
    migrate_v3_to_v4_chunked,
    verify_chunked_consistency,
)
from electric_sheep_fold.release import build_release
from electric_sheep_fold.unseal import (
    unseal_all,
    unseal_gen,
    verify_unseal_consistency,
)

app = typer.Typer(
    help="Polite mirror of Electric Sheep .flam3 genomes (loose-file corpus).",
    add_completion=False,
    no_args_is_help=True,
)


RANGE_RE = re.compile(r"^(\d+)\.\.(\d+)$")


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
    to the archive scraper + `import` flow; running a live fetch against them
    just wastes requests on a server that doesn't have them.
    """
    if gen not in LIVE_GENS:
        allowed = ", ".join(str(g) for g in sorted(LIVE_GENS))
        raise typer.BadParameter(
            f"--gen {gen} is not a live gen; v3d0.sheepserver.net only serves "
            f"{{{allowed}}}. To preserve a new dead gen, recover the "
            "archive-scrape scripts from git history (see "
            "docs/operations.md §Preserve a new dead generation)."
        )


@app.command()
def fetch(
    range_str: str = typer.Argument(..., metavar="START..END"),
    gen: int = typer.Option(248),
    delay: float = typer.Option(20.0),
    jitter: float = typer.Option(5.0),
    corpus: Path = typer.Option(Path("./corpus")),
) -> None:
    """Download .flam3 files for sheep[start, end) into the loose corpus."""
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
        f" · {stats.transient_errors} transient errors"
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
        f" · {stats.transient_errors} transient errors"
    )


@app.command("import")
def import_cmd(
    src: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    corpus: Path = typer.Option(Path("./corpus")),
    gen: int | None = typer.Option(
        None,
        "--gen",
        help="Generation number (required when src has multiple gens; "
        "inferred from filenames otherwise).",
    ),
) -> None:
    """Recursively import existing local electricsheep.*.flam3 files."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        stats = import_dir(src, corpus, gen=gen)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    typer.echo(
        f"\nimported {stats.imported} · skipped {stats.skipped}"
    )


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

    Walks every loose `.flam3` in each gen dir; classifies each flame
    into genome / animation / corrupt; emits per-flame structural
    metadata (variations, xform_count, pyr3-limitation flags).
    Re-runnable; overwrites.
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


@app.command("release-build")
def release_build_cmd(
    corpus: Path = typer.Option(Path("./corpus")),
    out: Path = typer.Option(
        Path("./build/release"),
        "--out",
        help="Where to write gen-*-DATE.zip + corpus-all-DATE.tar.xz + index + attribution.",
    ),
    gen: int | None = typer.Option(
        None,
        "--gen",
        help="Build only this gen's zip (skip mega-bundle + index regen).",
    ),
    date_str: str | None = typer.Option(
        None,
        "--date",
        help="Build date stamped into artifact filenames (YYYY-MM-DD). Defaults to today UTC.",
    ),
) -> None:
    """Build the v0.4 GitHub Release artifact set from corpus state.

    Reads v0.4 chunked corpus + missing.txt; emits ``gen-{N}-{date}.zip``
    per gen + ``corpus-all-{date}.tar.xz`` mega-bundle + INDEX.md +
    index.json + ATTRIBUTION.md to --out. Re-runnable; deterministic
    output (modulo zip member timestamps).
    """
    from datetime import date as _date
    from datetime import datetime as _dt

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not corpus.exists():
        raise typer.BadParameter(f"corpus dir not found: {corpus}")

    build_date: _date | None = None
    if date_str is not None:
        try:
            build_date = _dt.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as e:
            raise typer.BadParameter(f"--date must be YYYY-MM-DD: {e}") from e

    written = build_release(corpus, out, only_gen=gen, build_date=build_date)
    typer.echo(f"\nwrote {len(written)} files to {out}:")
    for p in written:
        typer.echo(f"  {p.name}")


@app.command()
def unseal(
    gen: int | None = typer.Option(
        None,
        "--gen",
        help="Unseal a single gen. Mutually exclusive with --all.",
    ),
    all_: bool = typer.Option(
        False,
        "--all",
        help="Unseal every gen subdir holding a sealed zip.",
    ),
    corpus: Path = typer.Option(Path("./corpus"), "--corpus"),
    snapshot_root: Path | None = typer.Option(
        None,
        "--snapshot-root",
        help="Snapshot dir for the pre-unseal v0.2 zips "
        "(default: <corpus parent>/build/v0.2-snapshot).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Report what would happen without touching disk.",
    ),
) -> None:
    """Migrate v0.2 sealed zips → v0.3 loose flam3 files (one-time).

    6-step SIGKILL-safe state machine per gen (snapshot → extract →
    verify → atomic-move → audit MANIFEST → commit). Idempotent and
    resumable; the ``.unseal-state`` marker carries crash recovery.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if gen is None and not all_:
        raise typer.BadParameter("must specify --gen N or --all")
    if gen is not None and all_:
        raise typer.BadParameter("--gen and --all are mutually exclusive")
    if not corpus.is_dir():
        raise typer.BadParameter(f"corpus dir not found: {corpus}")

    if dry_run:
        # Enumerate target gens; describe state without mutating disk.
        from electric_sheep_fold.unseal import (
            _GEN_DIR_RE,
            _find_sealed_zip,
            _read_state,
        )

        if gen is not None:
            target_gens = [gen]
        else:
            target_gens = sorted(
                int(p.name)
                for p in corpus.iterdir()
                if p.is_dir() and _GEN_DIR_RE.match(p.name)
            )

        for g in target_gens:
            gen_dir = corpus / str(g)
            if not gen_dir.is_dir():
                typer.echo(f"  gen {g}: SKIP (no gen dir)")
                continue
            sz = _find_sealed_zip(gen_dir)
            state = _read_state(gen_dir)
            if sz is None and state is None:
                typer.echo(f"  gen {g}: SKIP (already loose, no sealed zip)")
                continue
            typer.echo(
                f"  gen {g}: WOULD UNSEAL "
                f"(source={sz.name if sz else 'n/a'}, state={state or 'fresh'})"
            )
        return

    if gen is not None:
        result = unseal_gen(gen, corpus, snapshot_root=snapshot_root)
        if result.skipped:
            typer.echo(f"gen {result.gen}: skipped (already unsealed or no zip)")
        else:
            typer.echo(
                f"gen {result.gen}: unsealed → "
                f"{result.loose_count} loose · {result.missing_count} missing · "
                f"snapshot={result.snapshot_path}"
            )
        return

    results = unseal_all(corpus, snapshot_root=snapshot_root)
    typer.echo(f"\nunsealed {len(results)} gens:")
    for r in results:
        tag = "skipped" if r.skipped else "ok"
        typer.echo(
            f"  gen {r.gen}: {tag} · {r.loose_count} loose · "
            f"{r.missing_count} missing"
        )


@app.command("verify-unseal")
def verify_unseal_cmd(
    corpus: Path = typer.Option(Path("./corpus"), "--corpus"),
) -> None:
    """Compare current on-disk gen state to ``_unseal-verified.json``.

    Exits nonzero if any gen has shrunk in id count since unseal — the
    daemon-resume guard. Empty output + exit 0 = consistent.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not corpus.is_dir():
        raise typer.BadParameter(f"corpus dir not found: {corpus}")
    divergences = verify_unseal_consistency(corpus)
    if not divergences:
        typer.echo("ok: all gens consistent with _unseal-verified.json")
        return
    for gen, reason in divergences:
        typer.echo(f"  gen {gen}: {reason}")
    raise typer.Exit(code=1)


@app.command("migrate-chunked")
def migrate_chunked_cmd(
    corpus: Path = typer.Option(Path("./corpus"), "--corpus"),
) -> None:
    """v0.3 flat → v0.4 chunked layout. One-shot, idempotent.

    Moves every ``corpus/{gen}/electricsheep.{gen}.{id}.flam3`` into
    ``corpus/{gen}/{bucket}/`` (per-10k floor-bucket). Writes
    ``corpus/_chunked-verified.json`` as the daemon-resume baseline.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not corpus.is_dir():
        raise typer.BadParameter(f"corpus dir not found: {corpus}")
    results = migrate_v3_to_v4_chunked(corpus)
    for r in results:
        typer.echo(
            f"gen {r.gen}: moved {r.moved}, already_chunked {r.already_chunked}, "
            f"loose_total {r.loose_count}, missing {r.missing_count}, "
            f"buckets {r.bucket_count}"
        )
    typer.echo("ok: _chunked-verified.json written")


@app.command("verify-chunked")
def verify_chunked_cmd(
    corpus: Path = typer.Option(Path("./corpus"), "--corpus"),
) -> None:
    """Compare current on-disk state to ``_chunked-verified.json``.

    Exits nonzero if any gen has residual flat .flam3 files or has
    shrunk below the post-migrate baseline.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not corpus.is_dir():
        raise typer.BadParameter(f"corpus dir not found: {corpus}")
    divergences = verify_chunked_consistency(corpus)
    if not divergences:
        typer.echo("ok: all gens consistent with _chunked-verified.json")
        return
    for gen, reason in divergences:
        typer.echo(f"  gen {gen}: {reason}")
    raise typer.Exit(code=1)


@app.command()
def chunk(
    corpus: Path = typer.Option(Path("./corpus")),
    out: Path = typer.Option(
        Path("./build/release"),
        "--out",
        help="Directory to write corpus-chunks-DATE.tar into.",
    ),
    date_str: str | None = typer.Option(
        None,
        "--date",
        help="Build date stamped into artifact filename (YYYY-MM-DD). Defaults to today UTC.",
    ),
) -> None:
    """Build corpus-chunks-{date}.tar delivery artifact (standalone/debug).

    Walks the v0.4 chunked corpus; emits brotli'd 256-id delivery windows
    + per-gen availability manifests + gens.json browse summary.
    Use ``release-build`` to include this artifact in a full release.
    """
    from datetime import date as _date
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not corpus.exists():
        raise typer.BadParameter(f"corpus dir not found: {corpus}")

    build_date: _date
    if date_str is not None:
        try:
            build_date = _dt.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as e:
            raise typer.BadParameter(f"--date must be YYYY-MM-DD: {e}") from e
    else:
        build_date = _dt.now(tz=_tz.utc).date()

    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"corpus-chunks-{build_date.isoformat()}.tar"
    build_chunks_tar(corpus, dest, build_date.isoformat())
    typer.echo(f"\nwrote {dest}")


@app.command()
def status(
    gen: int = typer.Option(248),
    corpus: Path = typer.Option(Path("./corpus")),
) -> None:
    """Show corpus status: loose-file count + known-missing count."""
    gen_root = corpus / str(gen)
    if not gen_root.exists():
        typer.echo(f"{gen}: corpus not yet materialized (run `sheep-fold fetch` first)")
        return

    ms = MissingSet(gen_root / "missing.txt")
    ms.load()

    loose_count = sum(1 for _ in gen_root.rglob(f"electricsheep.{gen}.*.flam3"))

    typer.echo(
        f"{gen}: {loose_count} loose flam3 · {len(ms)} known-missing"
    )


if __name__ == "__main__":
    app()
