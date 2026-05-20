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

## 🚧 Todos (next session)

- Drive the first chunk seals — `electric-sheep-fold fetch 7000..9000` then
  `fetch 13000..20000` to complete chunks 0 + 1 (overnight at 20s cadence;
  auto-seal triggers when ranges complete).
- Phase 3 (v0.3 pyr3-facing index) — start the design round with the
  BACKLOG question about whether the aggregator scans working dirs or
  only sealed zips. Pyr3's actual query patterns should shape the schema.
