# 🐑 electric-sheep-fold

> Polite, idempotent mirror of [Electric Sheep](https://electricsheep.org) `.flam3`
> genomes — companion to [pyr3](../pyr3).

## Install

```sh
uv pip install -e ".[dev]"
```

## Quickstart

```sh
electric-sheep-fold fetch 0..100              # download sheep 0–99 in gen 248
electric-sheep-fold fetch-all                 # download entire gen 248 (resumable)
electric-sheep-fold import ~/Downloads/old    # import existing local .flam3s
electric-sheep-fold status                    # show per-chunk state breakdown
```

For **dead generations** (165, 191, 198, 242, 243, 244, 245, etc.) use the
throwaway preservation script (Phase 7):

```sh
python scripts/scrape_archive_gen.py --gen 242 --out corpus/_scrape-242
electric-sheep-fold import corpus/_scrape-242
electric-sheep-fold seal --chunk 00000-09999 --gen 242   # force-seal each chunk
```

## What it does

Walks a half-open `[START, END)` range of sheep IDs in generation 248 (or
`--gen N`) on the live ES v3d0 server, downloading any `.flam3` files not yet
in the local `corpus/` directory, at a polite 20-second cadence. Empty sheep
dirs (HTTP 404s) are recorded once in `corpus/248/missing.txt` and never
re-probed.

For dead gens the throwaway scraper hits `electricsheep.com/archives`
(static content, faster 2s cadence) via `time/N.html` enumeration + the
per-sheep `spex` endpoint. Output feeds the same `import` flow.

Storage is per-generation, chunked into 10k id-range `.zip` bundles
(`corpus/248/00000-09999.zip` etc.), with a per-chunk `MANIFEST.csv` inside.
Bundles open in macOS Finder / Windows Explorer / Linux file managers
out-of-the-box — no extra tool needed.

## Docs

- [VISION.md](VISION.md) — the why
- [ROADMAP.md](ROADMAP.md) — phases + live todos
- [CHANGELOG.md](CHANGELOG.md) · [BACKLOG.md](BACKLOG.md) · [CLAUDE.md](CLAUDE.md)
- Design spec: [`docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md`](docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md)

## License

**Tool code (this repo):** [GPL-3.0-or-later](LICENSE).

**Corpus data (downloaded `.flam3` files):** Creative Commons, per
[electricsheep.org/license](https://electricsheep.org/license/). Algorithm-generated
sheep are CC BY-NC; human-designed sheep are CC BY. The Sheep-Pack attribution file
is auto-written to `corpus/ATTRIBUTION.md` on first `fetch`.
