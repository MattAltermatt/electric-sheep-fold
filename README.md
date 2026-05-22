# 🐑 electric-sheep-fold

> Polite, idempotent mirror of [Electric Sheep](https://electricsheep.org) `.flam3`
> genomes — companion to [pyr3](../pyr3).

## Install

```sh
uv pip install -e ".[dev]"
```

## Quickstart

```sh
sheep-fold fetch 0..100              # download sheep 0–99 in gen 248
sheep-fold fetch-all                 # download entire gen 248 (resumable)
sheep-fold import ~/Downloads/old    # import existing local .flam3s
sheep-fold status                    # show per-chunk state breakdown
sheep-fold index                     # build agent-queryable corpus/_index/{index.json,INDEX.md}
```

For **dead generations** (already-frozen flam3 archives — 165, 169, 191, 198,
242, 243, 244, 245), preserve via the archive scraper and seal as one zip
per gen:

```sh
python scripts/scrape_archive_gen.py --gen 244 --out corpus/_scrape-244
sheep-fold import corpus/_scrape-244 --whole-gen
```

## What it does

Walks a half-open `[START, END)` range of sheep IDs in generation 248 (or
`--gen N`) on the live ES v3d0 server, downloading any `.flam3` files not yet
in the local `corpus/` directory, at a polite 20-second cadence. Empty sheep
dirs (HTTP 404s) are recorded once in `corpus/248/missing.txt` and never
re-probed.

For dead gens the archive scraper hits `electricsheep.com/archives`
(static content, faster 2s cadence) via `time/N.html` enumeration + a
doubling-probe / binary-search upper-bound discovery + a gap sweep. The
`spex` endpoint returns multiple legal envelopes (bare `<flame>`,
multi-flame animation, `<get>`-wrapped) — all accepted.

Storage shape depends on the gen's biography:

- **Live-preserved gens (247, 248)** — chunked into 10k id-range `.zip`
  bundles (`corpus/248/00000-09999.zip` etc.), sealed as ranges complete.
- **Dead-preserved gens (165 / 169 / 191 / 198 / 242 / 243 / 244 / 245)** —
  one whole-gen zip per gen (`corpus/244/00000-86575.zip`), since the
  id space is frozen at the time of preservation.

Each sealed zip carries a `MANIFEST.csv` as its first entry (id, sha256,
xform_count, variations, designer nick, source URL, …) — the seam for the
v0.3 pyr3-facing index. Bundles open in macOS Finder / Windows Explorer /
Linux file managers out-of-the-box — no extra tool needed.

## Docs

- [VISION.md](VISION.md) — the why
- [ROADMAP.md](ROADMAP.md) — phases + live todos
- [CHANGELOG.md](CHANGELOG.md) · [BACKLOG.md](BACKLOG.md) · [CLAUDE.md](CLAUDE.md)
- Design specs:
  [v0.1](docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md) ·
  [v0.2 chunked-zip](docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md) ·
  [v0.2.1 dead-gen whole-zip](docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md)

## License

**Tool code (this repo):** [GPL-3.0-or-later](LICENSE).

**Corpus data (downloaded `.flam3` files):** Creative Commons, per
[electricsheep.org/license](https://electricsheep.org/license/). Algorithm-generated
sheep are CC BY-NC; human-designed sheep are CC BY. The Sheep-Pack attribution file
is auto-written to `corpus/ATTRIBUTION.md` on first `fetch`.
