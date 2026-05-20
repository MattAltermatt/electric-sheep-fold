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
electric-sheep-fold status                    # show what's downloaded vs missing
```

## What it does

Walks a half-open `[START, END)` range of sheep IDs in generation 248 (or `--gen N`)
on the live ES v3d0 server, downloading any `.flam3` files that aren't already in
the local `corpus/` directory, at a polite 20-second cadence (configurable). Empty
sheep dirs (HTTP 404s) are recorded once in `corpus/248/missing.txt` and never
re-probed.

The local layout groups files by thousand under `corpus/248/00xxx/` through
`corpus/248/40xxx/` — see [`VISION.md`](VISION.md) for why.

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
