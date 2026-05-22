# v0.2.2 — corpus snapshot (10 gens, ~142k flames)

This is the first **published-as-Release** snapshot of the electric-sheep-fold
corpus — a preserved collection of `.flam3` genomes from Scott Draves'
Electric Sheep distributed renderer project (2003–present).

## Quick download

```sh
# All gens in one file (~607MB compressed)
gh release download v0.2.2 -p corpus-all.zip
unzip corpus-all.zip

# OR pick a specific generation
gh release download v0.2.2 -p gen-244.zip
unzip gen-244.zip
```

Want to query before downloading? `INDEX.md` is human/agent-readable and
`index.json` is `jq`-queryable — both are attached to this Release as
standalone assets.

## What's in here

10 generations of preserved `.flam3` genomes, **one zip per generation**:

| Asset | Sheep | Genomes | Source |
|---|---:|---:|---|
| `gen-165.zip` | 998 | 242 | electricsheep.com archive |
| `gen-169.zip` | 21,745 | 5,299 | electricsheep.com archive |
| `gen-191.zip` | 21,743 | 5,999 | electricsheep.com archive |
| `gen-198.zip` | 31,836 | 8,800 | electricsheep.com archive |
| `gen-242.zip` | 3,388 | 1,168 | electricsheep.com archive |
| `gen-243.zip` | 5,266 | 5,132 | electricsheep.com archive |
| `gen-244.zip` | 33,594 | 7,430 | electricsheep.com archive |
| `gen-245.zip` | 11,950 | 1,213 | electricsheep.com archive |
| `gen-247.zip` | 9,006 | 4,090 | electricsheep.com archive |
| `gen-248.zip` | 2,926 | 1,416 | v3d0.sheepserver.net (live) |
| **Σ** | **142,452** | **40,789** | |

Plus:

- `corpus-all.zip` — every gen + index files + attribution, bundled
- `INDEX.md` — per-gen counts, variation usage histogram, structural feature
  counts, `jq` query recipes
- `index.json` — one JSON record per flame (schema: `id`, `gen`, `sheep_id`,
  `kind`, `variations`, `xform_count`, `has_post_affine`, `has_chaos`,
  `supersample`, `highlight_power`, `negative_weight_xforms`, …)
- `ATTRIBUTION.md` — Sheep-Pack attribution per the [Electric Sheep
  license](https://electricsheep.org/license)

## File classification (in `index.json`)

Every `.flam3` is classified as one of:

- **`genome`** (28.6% of files) — single-flame, fully indexed with
  structural metadata. **Default agent queries filter on this.**
- **`animation`** (71.4%) — multi-flame morphs between genomes; recorded
  with `frame_count` only. Derivative interpolation snapshots; not directly
  renderable by most flam3 tools.
- **`corrupt`** (0%) — zero-byte or unparseable. None in this Release.

## License

- **Corpus data:** Creative Commons per [electricsheep.org/license](https://electricsheep.org/license/). Algorithm-generated sheep are CC BY-NC; human-designed sheep (those with a `<flame nick=...>` attribute, 15,627 in this corpus) are CC BY.
- **`sheep-fold` tool code:** [GPL-3.0-or-later](https://github.com/MattAltermatt/electric-sheep-fold/blob/main/LICENSE), matching pyr3 and the upstream [flam3](https://github.com/scottdraves/flam3) lineage.

## Agent / `jq` recipes

See `INDEX.md` (Query Recipes section) for the full list. A few quick ones:

```sh
# Find genomes using a specific variation
jq -r '.[] | select(.kind == "genome" and (.variations | index("bipolar"))) | .id' index.json | head

# Find pyr3-parity-friendly genomes (no chaos, supersample=1, default highlight_power)
jq -r '.[] | select(.kind == "genome" and (.has_chaos | not) and .supersample == 1 and .highlight_power < 0) | .id' index.json | head

# Inspect one flame in full
jq '.[] | select(.id == "244/42746")' index.json
```

## What's new since v0.2.1

This is the first Release. v0.2.1 shipped the v0.2.1 whole-gen-for-dead-gens
chunking policy + the corpus indexer + the agentic skill (`.claude/skills/pyr3-corpus-index/SKILL.md`). v0.2.2 unifies chunk shape across all gens (everything is now whole-gen) and ships the corpus itself as Release assets.

## How this corpus was built

See [README.md](https://github.com/MattAltermatt/electric-sheep-fold/blob/main/README.md) and [VISION.md](https://github.com/MattAltermatt/electric-sheep-fold/blob/main/VISION.md). Briefly: archive-side gens (165 / 169 / 191 / 198 / 242 / 243 / 244 / 245) were preserved by scraping `electricsheep.com/archives` polite-mode (2s cadence). Live-track gens (247 / 248) were preseeded from a local mirror + extended via `v3d0.sheepserver.net` at 20s sequential cadence per the publicly-served polite protocol.

## Future releases

Future Release tags (v0.3.0, etc.) will publish corpus snapshots that include continued growth on live gens (247 / 248) as `sheep-fold fetch-all` finds new flames. Filenames stay stable; the Release tag is the version.
