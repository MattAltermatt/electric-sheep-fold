# 🗺️ Roadmap

> Strategic milestones + the next concrete actions. This doc is **forward-looking**:
> full per-phase ship history lives in [`CHANGELOG.md`](CHANGELOG.md); deferred
> tickets live in [`BACKLOG.md`](BACKLOG.md).

## 📍 Where things are

The corpus is preserved and stable — **10 generations, ~166k flames / ~52k
genomes**, append-only chunked layout, published as ISO-date GitHub Releases
(latest [`2026-05-23`](https://github.com/MattAltermatt/electric-sheep-fold/releases/tag/2026-05-23)).
The `sheep-fold` toolchain is feature-complete for the **preserve → index →
release** loop: index schema v5, and the renderer-facing `corpus-chunks` delivery
artifact powering pyr3.app share-URLs. `main` is CI-gated (ruff + mypy + pytest
3.11–3.13), branch-protected, and supply-chain-pinned. Full history:
[CHANGELOG.md](CHANGELOG.md).

## 🔮 Next phases

### Live-track extension (continuous, routine)

Extend gens 247 + 248 against v3d0 over time. Sticky-404 + skip-without-network
keep the cadence efficient; no reseal needed on extension.

### Phase 13 — pyr3 parity consumption

pyr3 reads the corpus (loose files + AutoRoute index fields + the share-URL chunk
delivery) as its parity-test source — the point of the whole exercise. The
delivery seam shipped (CHANGELOG phase 12f); broader parity coverage is driven
from the pyr3 repo.

### Phase 14 — additional generations 🐑

When ES rolls gen 249+: one-line `LIVE_GENS` edit in `layout.py`, then
`fetch-all`. If a *dead* gen appears, recover the archive-scraper scripts from git
history (see operations.md). Tracked as [ESF-010] in BACKLOG.

### Index ergonomics (pull-forward)

SQLite query layer, palette-hash, curated examples, incremental rebuild —
[ESF-004–007] in BACKLOG. Pull forward when corpus growth slows or pyr3
integration demands faster queries.

## 🚧 Todos (next wake-up)

A corpus archive woken occasionally to fetch more sheep + ship a dated snapshot —
no continuous-daemon expectation.

- 🐑 **Routine refresh:** `./scripts/resume_live_fetch.sh <upper>` → `sheep-fold
  index` → `sheep-fold release-build --date YYYY-MM-DD` → `gh release create`.
  (`migrate-chunked` is a no-op on an already-chunked corpus.)
- 🔮 **New dead gen?** recover the scrapers via `git show v0.3.0:scripts/scrape_archive_gen.py`
  etc. — see [`docs/operations.md`](docs/operations.md) §"Preserve a new dead generation".
- 📈 **Index ergonomics** ([ESF-004–007]) when `index.json` scans get slow.
