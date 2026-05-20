# 🔮 Vision

## Why electric-sheep-fold exists

[pyr3](../pyr3) is a deterministic fractal-flame renderer on the JVM. It claims
byte-identical output across machines for any [flam3](https://github.com/scottdraves/flam3)
genome. To prove that claim broadly, pyr3 needs a corpus of real Electric Sheep
flames to render against — not just the single `244.00016` golden it ships with.

electric-sheep-fold is the tool that builds that corpus.

## What "done" looks like

- A local `corpus/248/` directory containing a meaningful fraction of gen 248's
  `.flam3` files, organized by thousand-bucket for git/filesystem friendliness.
- A sticky `missing.txt` recording which sheep IDs were confirmed empty on the
  server, so we never re-probe them.
- `corpus/ATTRIBUTION.md` in place per the ES license's Sheep-Pack clause.
- pyr3 consumes the corpus for parity testing (Phase 3 — outside electric-sheep-fold's
  scope but the reason the tool exists).

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

## What v0.2 changes

v0.1 stored each `.flam3` as a loose file under per-thousand bucket dirs. v0.2
chunks per generation into sealed-immutable 10k id-range `.zip` bundles, with a
per-chunk `MANIFEST.csv` that captures the structural metadata (xform_count,
variations, designer nick) needed by the future pyr3-facing index. New CLI
verbs: `fetch-all` (entire gen, resumable), `import` (bulk-ingest existing
local flames). The v0.1 → v0.2 migration is automatic on first run.

## License lineage

electric-sheep-fold (the tool) is GPL-3.0-or-later, matching pyr3 and the upstream flam3
lineage from Scott Draves (2003). The corpus data is Creative Commons per ES
policy — see [`README.md`](README.md) and (after first `fetch`)
`corpus/ATTRIBUTION.md`.
