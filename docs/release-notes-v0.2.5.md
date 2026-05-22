# v0.2.5 — final sealed-shape snapshot (10 gens, ~143k flames)

The last Release of the v0.2 sealed-zip era. v0.3 (next) separates the
on-disk corpus from the release artifact: corpus becomes loose `.flam3`
files + `missing.txt`; release zips are built on demand. This v0.2.5
snapshot is the off-machine fallback for that migration.

## Quick download

```sh
# All gens in one file (~1.1GB compressed)
gh release download v0.2.5 -p corpus-all.zip
unzip corpus-all.zip

# OR pick a specific generation
gh release download v0.2.5 -p gen-244.zip
unzip gen-244.zip
```

`INDEX.md` is human/agent-readable and `index.json` is `jq`-queryable —
both attached to this Release as standalone assets.

## What's in here

10 generations of preserved `.flam3` genomes, one whole-gen zip per
generation:

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
| `gen-247.zip` | 9,861 | 4,501 | v3d0.sheepserver.net + electricsheep.com archive |
| `gen-248.zip` | 2,926 | 1,416 | v3d0.sheepserver.net (live) |
| **Σ** | **143,307** | **41,200** | |

Plus:

- `corpus-all.zip` — every gen + index files + attribution, bundled
- `INDEX.md` — per-gen counts, variation usage histogram, structural feature counts, `jq` query recipes
- `index.json` — one JSON record per flame
- `ATTRIBUTION.md` — Sheep-Pack attribution per the [Electric Sheep license](https://electricsheep.org/license/)

## What changed since v0.2.2

- **Gen 247 extended** from 9,006 to 9,861 sheep (+855 newly fetched
  from v3d0 between v0.2.2 and now). The v0.2.4 range-trust skip-check
  shipped between releases ensured no re-probe of already-known ids.
- **Sticky-404 data complete.** `corpus/247/missing.txt` and
  `corpus/248/missing.txt` accumulated 1,310 and 6,163 entries
  respectively; these are now embedded in the per-gen zips' MANIFEST as
  the "id known, file absent" signal. v0.3 will further surface this as
  an explicit `missing.txt` inside each release zip.
- **Whole-gen unification finalized.** Gen 247's prior 00000-29999 + active
  30000-39999/ working dir collapsed into one `00000-32085.zip` so all 10
  gens uniformly ship as a single sealed whole-gen zip. Matches the
  v0.2.2 unification policy.

## Why v0.2.5 exists

This Release is the **fallback artifact for the v0.3 migration**. v0.3
(branch `feature/v0.3-loose-corpus`) separates the corpus from the
release artifact:

- `corpus/{gen}/` becomes flat `.flam3` files + `missing.txt` (no more sealed zips on disk)
- `sheep-fold release-build` builds release zips on demand from loose corpus
- The "seal" + "chunk" concepts retire from the working path

The migration is non-destructive (corpus data is unsealed, not deleted),
but v0.2.5 is the durable off-machine snapshot if anything goes sideways.
**For most users this Release is functionally identical to v0.2.2 — just
with the gen-247 update.** Consumers can stay on v0.2.5 indefinitely; the
flame data inside is unchanged.

The next public Release will be **v0.3.0** with the loose-corpus shape.

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

# Inspect one flame in full
jq '.[] | select(.id == "247/00000")' index.json
```
