"""Typer entrypoint for electric-sheep-fold."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import typer

from electric_sheep_fold.fetch import fetch_range, make_client
from electric_sheep_fold.layout import local_path
from electric_sheep_fold.manifest import MissingSet

app = typer.Typer(
    help="Polite mirror of Electric Sheep .flam3 genomes.",
    add_completion=False,
    no_args_is_help=True,
)


RANGE_RE = re.compile(r"^(\d+)\.\.(\d+)$")


def _parse_range(range_str: str) -> tuple[int, int]:
    """Parse 'START..END' (half-open) → (start, end)."""
    m = RANGE_RE.match(range_str)
    if not m:
        raise typer.BadParameter(f"range must be START..END, got {range_str!r}")
    start, end = int(m.group(1)), int(m.group(2))
    if end <= start:
        raise typer.BadParameter(
            f"range must be non-empty: end ({end}) must exceed start ({start})"
        )
    return start, end


@app.command()
def fetch(
    range_str: str = typer.Argument(..., metavar="START..END", help="Half-open range, e.g., 0..2000"),
    gen: int = typer.Option(248, help="ES generation"),
    delay: float = typer.Option(20.0, help="Seconds between requests"),
    jitter: float = typer.Option(5.0, help="Random jitter added to delay (uniform 0..jitter)"),
    corpus: Path = typer.Option(Path("./corpus"), help="Corpus root directory"),
) -> None:
    """Download .flam3 files for sheep[start, end) into the corpus."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    start, end = _parse_range(range_str)

    with make_client() as client:
        stats = fetch_range(
            gen=gen, start=start, end=end,
            corpus_root=corpus, client=client,
            delay=delay, jitter=jitter,
        )

    typer.echo(
        f"\n{gen}: {stats.downloaded} downloaded · "
        f"{stats.newly_missing} newly missing · "
        f"{stats.skip_local} skip-local · "
        f"{stats.skip_known_missing} skip-known-missing · "
        f"{stats.transient_errors} transient errors"
    )


@app.command()
def status(
    gen: int = typer.Option(248, help="ES generation"),
    corpus: Path = typer.Option(Path("./corpus"), help="Corpus root directory"),
    range_str: str = typer.Option(
        None,
        "--range",
        metavar="START..END",
        help="Optional half-open range; if provided, output also includes 'untried' count for that range.",
    ),
) -> None:
    """Show corpus status: downloaded vs known-missing for the given gen.

    If --range is provided, also reports how many sheep in [START, END)
    have not yet been attempted (untried = range_size - downloaded - known-missing,
    both restricted to the range).
    """
    gen_root = corpus / str(gen)
    if not gen_root.exists():
        typer.echo(f"{gen}: corpus not yet materialized (run `electric-sheep-fold fetch` first)")
        return

    ms = MissingSet(gen_root / "missing.txt")
    ms.load()

    if range_str is None:
        downloaded = sum(1 for _ in gen_root.rglob("electricsheep.*.flam3"))
        typer.echo(f"{gen}: {downloaded} downloaded · {len(ms)} known-missing")
        return

    start, end = _parse_range(range_str)
    downloaded_in_range = sum(
        1 for sid in range(start, end) if local_path(gen, sid, corpus).exists()
    )
    known_missing_in_range = sum(1 for sid in range(start, end) if ms.contains(sid))
    untried = (end - start) - downloaded_in_range - known_missing_in_range
    typer.echo(
        f"{gen}: {downloaded_in_range} downloaded · "
        f"{known_missing_in_range} known-missing · "
        f"{untried} untried in {start}..{end}"
    )


if __name__ == "__main__":
    app()
