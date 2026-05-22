# 🐑 electric-sheep-fold

> A preserved corpus of [Electric Sheep](https://electricsheep.org) `.flam3`
> genomes — 10 generations, 142k+ flames, 99 distinct variations. Distributed
> via GitHub Releases. Companion to [pyr3](https://github.com/MattAltermatt/pyr3).

## Download the corpus

Each Release is a snapshot in time. Latest is **[v0.2.2](https://github.com/MattAltermatt/electric-sheep-fold/releases/tag/v0.2.2)**:

```sh
# Everything in one bundle (~607MB)
gh release download v0.2.2 -p corpus-all.zip
unzip corpus-all.zip

# OR pick a specific generation
gh release download v0.2.2 -p gen-244.zip
unzip gen-244.zip

# OR fetch the index first to see what's there
gh release download v0.2.2 -p INDEX.md
gh release download v0.2.2 -p index.json
```

`index.json` is `jq`-queryable; `INDEX.md` is human + agent-readable. See
[`.claude/skills/pyr3-corpus-index/SKILL.md`](.claude/skills/pyr3-corpus-index/SKILL.md)
for query recipes (find flames by variation, pyr3-parity filtering, etc.).

## What's in the corpus

| Gen | Sheep | Genomes | Animations | Source |
|---|---:|---:|---:|---|
| 165 | 998 | 242 | 756 | electricsheep.com archive |
| 169 | 21,745 | 5,299 | 16,446 | electricsheep.com archive |
| 191 | 21,743 | 5,999 | 15,744 | electricsheep.com archive |
| 198 | 31,836 | 8,800 | 23,036 | electricsheep.com archive |
| 242 | 3,388 | 1,168 | 2,220 | electricsheep.com archive |
| 243 | 5,266 | 5,132 | 134 | electricsheep.com archive |
| 244 | 33,594 | 7,430 | 26,164 | electricsheep.com archive |
| 245 | 11,950 | 1,213 | 10,737 | electricsheep.com archive |
| 247 | 9,006 | 4,090 | 4,915 | v3d0 + archive |
| 248 | 2,926 | 1,416 | 1,510 | v3d0.sheepserver.net (live) |
| **Σ** | **142,452** | **40,789** | **101,662** | |

**Kinds** (in `index.json`): each `.flam3` is `genome` (single-flame, fully
indexed — default for agentic / pyr3 lookups), `animation` (multi-flame
morph between genomes, frame-count only), or `corrupt` (zero-byte or
unparseable; currently none).

## The `sheep-fold` toolchain

The corpus is built and maintained by the `sheep-fold` CLI in this repo —
the toolchain is here because the corpus is here. For contributors and
corpus maintainers:

```sh
uv pip install -e ".[dev]"
sheep-fold --help
```

| Command | Purpose |
|---|---|
| `sheep-fold fetch RANGE` | Polite range fetch from v3d0 (live gens 247, 248 only) |
| `sheep-fold fetch-all` | Polite full-gen fetch from v3d0 (resumable) |
| `sheep-fold import DIR` | Import existing local `.flam3`s into the chunked corpus |
| `sheep-fold seal --chunk RANGE --gen N` | Force-seal a working chunk |
| `sheep-fold index` | Rebuild `corpus/_index/{index.json, INDEX.md}` (agent-queryable) |
| `sheep-fold status` | Show per-gen chunk + missing breakdown |
| `./scripts/build_release.sh` | Assemble `build/release/` for the next GH Release |

For dead generations (165 / 169 / 191 / 198 / 242 / 243 / 244 / 245), the
archive scraper handles preservation:

```sh
python scripts/scrape_archive_gen.py --gen 244 --out corpus/_scrape-244
sheep-fold import corpus/_scrape-244 --whole-gen
```

## Politeness

The live ES server (`v3d0.sheepserver.net`, lighttpd 1.4.33) and the
electricsheep.com archive (S3 backed) are volunteer / shared infrastructure
preserving 20+ years of crowdsourced generative art. `sheep-fold` treats
them accordingly: **20s ± 5s sequential** for v3d0, **2s ± 1s** per worker
for the archive (modest cross-gen parallelism OK). Identifiable User-Agent;
sticky-404 memory (`corpus/{gen}/missing.txt`) so we never re-probe known
gaps. The full politeness contract is documented in [CLAUDE.md](CLAUDE.md).

## Docs

- [VISION.md](VISION.md) — why this corpus exists
- [ROADMAP.md](ROADMAP.md) — shipped phases + planned Releases
- [CHANGELOG.md](CHANGELOG.md) · [BACKLOG.md](BACKLOG.md) · [CLAUDE.md](CLAUDE.md)
- Design specs:
  [v0.1](docs/superpowers/specs/2026-05-19-electric-sheep-fold-v0.1-design.md) ·
  [v0.2 chunked-zip](docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md) ·
  [v0.2.1 dead-gen whole-zip](docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md)

## License

**Corpus data:** Creative Commons per [electricsheep.org/license](https://electricsheep.org/license/).
Algorithm-generated sheep are CC BY-NC; human-designed sheep (those with a
`<flame nick=...>` attribute) are CC BY. `ATTRIBUTION.md` is bundled with
every Release per the Sheep-Pack clause.

**`sheep-fold` toolchain (this repo's code):** [GPL-3.0-or-later](LICENSE),
matching pyr3 and the upstream [flam3](https://github.com/scottdraves/flam3)
lineage from Scott Draves (2003).
