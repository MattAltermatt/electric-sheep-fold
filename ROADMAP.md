# 🗺️ Roadmap

> Strategic milestones + the next concrete actions. This doc is **forward-looking**:
> full per-phase ship history lives in [`CHANGELOG.md`](CHANGELOG.md); deferred
> tickets live in [`BACKLOG.md`](BACKLOG.md).

## 📍 Where things are

The corpus is preserved and stable — **10 generations, ~166k flames / ~52k
genomes**, append-only chunked layout, published as ISO-date GitHub Releases
(latest [`2026-05-29`](https://github.com/MattAltermatt/electric-sheep-fold/releases/tag/2026-05-29)).
The `sheep-fold` toolchain is feature-complete for the **preserve → index →
release** loop: index schema v6, and the renderer-facing `corpus-chunks` delivery
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

### Index ergonomics — resolved

Audited 2026-05-29: the v6 `index.json` + the `jq` recipes in
[`SKILL.md`](.claude/skills/pyr3-corpus-index/SKILL.md) **are** the ergonomics
deliverable. The SQLite query layer (ESF-004), curated examples (ESF-005), and
palette-hash (ESF-006) were declined — no in-repo consumer, jq scans measure
~0.9s, and fixture curation / query caches belong to the consumer (pyr3), derived
from our canonical index. Only incremental rebuild ([ESF-007]) stays deferred,
revisitable if the corpus grows enough that the ~90s full rebuild becomes painful.

## 🚧 Todos (next wake-up)

A corpus archive woken occasionally to fetch more sheep + ship a dated snapshot —
no continuous-daemon expectation.

- 🐑 **Routine refresh:** `./scripts/resume_live_fetch.sh <upper>` → `sheep-fold
  index` → `sheep-fold release-build --date YYYY-MM-DD` → `gh release create`.
  (`migrate-chunked` is a no-op on an already-chunked corpus.)
- 🔮 **New dead gen?** recover the scrapers via `git show v0.3.0:scripts/scrape_archive_gen.py`
  etc. — see [`docs/operations.md`](docs/operations.md) §"Preserve a new dead generation".
- 📈 **Index rebuild speed** ([ESF-007]) only if the corpus grows enough that the
  ~90s full rebuild becomes painful. (The rest of "index ergonomics" was resolved
  2026-05-29 — see above.)
