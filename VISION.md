# 🔮 Vision

## Why electric-sheep-fold exists

[pyr3](../pyr3) is a deterministic fractal-flame renderer on the JVM. It claims
byte-identical output across machines for any [flam3](https://github.com/scottdraves/flam3)
genome. To prove that claim broadly, pyr3 needs a corpus of real Electric Sheep
flames to render against — not just the single `244.00016` golden it ships with.

electric-sheep-fold is the tool that builds that corpus.

## What "done" looks like

The corpus is built from two tracks:

- **Live track** — `corpus/{247,248}/` filled from `v3d0.sheepserver.net` at
  a polite 20s cadence, organized as sealed 10k-id `.zip` chunks.
- **Preservation track** — `corpus/{165,169,191,198,242,243,244,245}/`
  filled from the `electricsheep.com/archives` static mirror, sealed as
  one whole-gen `.zip` per gen (the gen-id space is frozen, so synthetic
  decade chunks would be bookkeeping for nothing).

Every gen carries a sticky `missing.txt` so we never re-probe known-empty ids.
`corpus/ATTRIBUTION.md` is in place per the ES license's Sheep-Pack clause.

The end state is pyr3 consuming this corpus for parity testing (outside
electric-sheep-fold's scope but the reason the tool exists).

## Politeness as a design constraint

The live ES server (v3d0, lighttpd 1.4.33) is volunteer infrastructure preserving
20+ years of crowdsourced generative art. electric-sheep-fold treats it accordingly:

- **20-second default cadence** between requests; configurable but never
  parallelized.
- **Sticky 404 memory** so we never re-probe known-empty dirs (the worst form of
  rudeness is also the most pointless — re-asking after we already learned the
  answer).
- **Identifiable User-Agent** that names the project and links the repo, so server
  admins can reach us if our load is ever a problem.

## Storage shape

v0.1 stored each `.flam3` as a loose file under per-thousand bucket dirs. v0.2
chunks per generation into sealed-immutable 10k id-range `.zip` bundles, with a
per-chunk `MANIFEST.csv` that captures the structural metadata (xform_count,
variations, designer nick) needed by the future pyr3-facing index. v0.2.1 adds
a whole-gen seal mode for dead-preserved gens — the archive-side gens are
frozen, so one `00000-NNNNN.zip` per gen is the natural unit. CLI verbs:
`fetch` / `fetch-all` (live track), `import [--whole-gen]` (preservation
track). v0.1 → v0.2 migration is automatic on first run.

## License lineage

electric-sheep-fold (the tool) is GPL-3.0-or-later, matching pyr3 and the upstream flam3
lineage from Scott Draves (2003). The corpus data is Creative Commons per ES
policy — see [`README.md`](README.md) and (after first `fetch`)
`corpus/ATTRIBUTION.md`.
