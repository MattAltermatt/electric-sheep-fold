# v0.3.0 — loose corpus, built release artifact (10 gens, ~143k flames)

First Release of the v0.3 era: the on-disk corpus is loose `.flam3` files,
release zips are built on demand from that state, and sticky-404
provenance now travels inside the release artifact. Same flame content
as [v0.2.5](https://github.com/MattAltermatt/electric-sheep-fold/releases/tag/v0.2.5);
new artifact shape.

## Quick download

```sh
# Everything in one bundle (~535MB)
gh release download v0.3.0 -p corpus-all.zip
unzip corpus-all.zip

# OR pick a specific generation
gh release download v0.3.0 -p gen-244.zip
unzip gen-244.zip
```

`INDEX.md` is human/agent-readable and `index.json` is `jq`-queryable —
both attached to this Release.

## What's in here

10 generations of preserved `.flam3` genomes, one zip per generation:

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
| `gen-247.zip` | 9,861 | 4,501 | v3d0.sheepserver.net + archive |
| `gen-248.zip` | 2,926 | 1,416 | v3d0.sheepserver.net (live) |
| **Σ** | **143,307** | **41,200** | |

Each per-gen zip contains:

- `MANIFEST.csv` — id, sha256, fetched_at, source_url, xform_count, variations, designer nick, etc. (11 columns)
- **`missing.txt`** — sticky-404 ids for that gen (one per line). **New in v0.3** — tells consumers which ids are confirmed-empty without probing.
- Flat `electricsheep.{gen}.{id}.flam3` files

Plus:

- `corpus-all.zip` — every gen + index files + attribution, bundled
- `INDEX.md` — per-gen counts, variation usage histogram, structural feature counts, `jq` query recipes
- `index.json` — one JSON record per flame
- `ATTRIBUTION.md` — Sheep-Pack attribution per the [Electric Sheep license](https://electricsheep.org/license/)

## What changed since v0.2.5

**Corpus shape (on disk):** previously sealed-immutable whole-gen zips
under `corpus/{gen}/{NNNNN}-{NNNNN}.zip`; now flat
`corpus/{gen}/electricsheep.{gen}.{id}.flam3` files plus a `missing.txt`.

**Release artifact shape (what you download):** the per-gen zips are a
**strict superset** of v0.2.5 — same MANIFEST.csv + same flat `.flam3`
files, plus a new `missing.txt`. Downstream consumers can ignore the new
file if they don't care about sticky-404 provenance. No compat layer
needed.

**Why the change.** v0.2.x's "sealed-immutable" model worked for the 8
truly-frozen dead gens but fought the 2 live gens (247, 248). v0.2.2's
chunk-shape collapse destroyed sticky-404 provenance because
`missing.txt` lived **outside** the sealed zip. v0.3 separates the
corpus from the release artifact: the corpus is the canonical state;
release zips are pure derivatives, deterministically rebuildable.

**Net effect for consumers:** smaller downloads (~535 MB vs ~607 MB at
v0.2.2 due to compression efficiency on flat layout), explicit sticky-404
provenance per gen, no behavior change on the indexing or query side.

**Net effect for the tool:** new commands — `sheep-fold release-build`,
`sheep-fold unseal`, `sheep-fold verify-unseal`. The `seal` command and
`--whole-gen` flag are retired (sealing was v0.2 working-dir ceremony;
flat-write is the default now).

See spec [`v0.3 loose-corpus`](https://github.com/MattAltermatt/electric-sheep-fold/blob/main/docs/superpowers/specs/2026-05-22-v0.3-loose-corpus.md)
for the full design rationale.

## License

- **Corpus data:** Creative Commons per [electricsheep.org/license](https://electricsheep.org/license/). Algorithm-generated sheep are CC BY-NC; human-designed sheep are CC BY.
- **`sheep-fold` tool code:** [GPL-3.0-or-later](https://github.com/MattAltermatt/electric-sheep-fold/blob/main/LICENSE), matching pyr3 and the upstream [flam3](https://github.com/scottdraves/flam3) lineage.

## Agent / `jq` recipes

See `INDEX.md` (Query Recipes section). Quick ones:

```sh
# Find genomes using a specific variation
jq -r '.[] | select(.kind == "genome" and (.variations | index("bipolar"))) | .id' index.json | head

# Find pyr3-parity-friendly genomes (no chaos, supersample=1, default highlight_power)
jq -r '.[] | select(.kind == "genome" and (.has_chaos | not) and .supersample == 1 and .highlight_power < 0) | .id' index.json | head

# Find ids confirmed-missing from a specific gen (now travels with the artifact)
unzip -p gen-247.zip missing.txt | head

# Inspect one flame in full (loose layout — direct path)
unzip -p gen-244.zip electricsheep.244.42746.flam3
```

## Future

`v0.4.x` Releases will continue extending live gens 247 + 248 as
`sheep-fold fetch-all` finds new flames. The corpus shape is now stable
for the foreseeable future; future iteration is on index ergonomics
(SQLite layer, incremental rebuild) and compression options (7z artifact
alternative — see [BACKLOG](https://github.com/MattAltermatt/electric-sheep-fold/blob/main/BACKLOG.md)).
