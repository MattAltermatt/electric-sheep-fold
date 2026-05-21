# 🗺️ Roadmap

> Phases are strategic milestones; the **🚧 Todos** block at the bottom is the
> living set of next concrete actions.

## Phases

### Phase 1 — v0.1 ship ✅ *(shipped 2026-05-19)*

Bootstrapped the tool: package + docs + four-module architecture (`layout`,
`manifest`, `fetch`, `cli`) + 52 tests + real-server smoke test.

### Phase 2 — v0.2 chunked-zip storage + ergonomics ✅ *(shipped 2026-05-20)*

Storage refactor: per-thousand bucket dirs → sealed-immutable 10k id-range
`.zip` chunks with per-chunk `MANIFEST.csv` seam for v0.3 + auto-fetch +
import + automatic v0.1→v0.2 migration. Eight modules, 116 tests, real-server
smoke confirmed migration of 2926 v0.1 files. Spec:
[`docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md`](docs/superpowers/specs/2026-05-20-electric-sheep-fold-v0.2-chunked-zip.md).

### Phase 3 — v0.3 pyr3-facing index / search 🔮

Aggregate per-chunk MANIFEST.csv into a corpus-wide searchable index. Query
interface: filter by xform_count, variations, has-nick, etc. Subsumes the old
"verify subcommand" phase (sha256 in MANIFEST.csv enables verify as a query)
and the BACKLOG `attribution.csv extractor` entry.

### Phase 4 — pyr3 integration 🔥

Pyr3 reads `corpus/{gen}/` (sealed zips + index) as parity-test source. The
point of the whole exercise.

### Phase 5 — public corpus repo (optional) 🌐

Push sealed chunks to a separate `muwamath/electric-sheep-fold-corpus` GitHub repo;
chunked zips are the natural distribution unit.

### Phase 6 — additional generations 🐑

Run `--gen 249` (etc.) as ES rolls over. Same script, no changes needed.

### Phase 7 — dead-gen archive preservation 🪦 *(in progress 2026-05-20)*

One-shot preservation of dead generations via `scripts/scrape_archive_gen.py`
(throwaway). For each gen with archived content on
`electricsheep.com/archives`: enumerate sheep ids by walking `time/N.html`
pages, fetch each via the `spex` endpoint, write canonical-named `.flam3`
files, then `sheep-fold import` + `seal --chunk` per chunk. Order: smallest
gens first (242 → 243 → 245 → 191 → 244 → 198 → 247-archived → 248-archived
→ 165 → 169 → 23/old/very-old). After all preserved, the scripts can be
deleted; the live tool stays focused on 247/248.

## 🚧 Todos (next session)

- **Live track** — continue `sheep-fold fetch-all --gen 248` to fill the
  remaining ~37k slots (sticky-404 + sealed chunks make this resumable).
  Then `--gen 247` for what v3d0 still serves live.
- **Preservation track** — finish gen 242 scrape (resumes at id 476/3584 in
  `corpus/_scrape-242/`), import, force-seal. Then 243, 245, 191, 244, 198.
- Phase 3 (v0.3 pyr3-facing index) — start the design round with the
  BACKLOG question about whether the aggregator scans working dirs or
  only sealed zips. Pyr3's actual query patterns should shape the schema.
