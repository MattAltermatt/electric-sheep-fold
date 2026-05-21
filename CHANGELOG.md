# 📝 Changelog

## Unreleased — 2026-05-21 (live)

### Project rename: `electric-sheep-fold` → `electric-sheep-fold`

Original name was reaching for *shearing* (extract / clip wool) but the
work is *preservation* — and "fold" was English-ambiguous. `sheepfold`
captures the sanctuary framing. CLI binary stays short: `sheep-fold`.

- Python package: `electric_sheep_fold` → `electric_sheep_fold`
- CLI binary: `electric-sheep-fold` → `sheep-fold` (short for tab-completion)
- User-Agent, README, all docs, spec/plan filenames retargeted
- All 135 tests green after rename

### Phase 8 — comprehensive dead-gen preservation pipeline

Three bugs discovered + fixed after the Phase 7 import surfaced corrupt
sealed zips (73% empty extractions on gens 191/198):

1. **`extract.py` couldn't parse multi-flame .flam3 files** — animation
   keyframes use multiple `<flame>` sibling roots (valid flam3, invalid
   single-root XML). Fix: wrap in synthetic `<sheep>` root and aggregate
   across all flames. Variations now union across the whole animation.
2. **Scraper saved 200-OK responses with body `"none\n"`** as 5-byte
   placeholder .flam3 files. New: `is_flam3_content()` validator (in
   `extract.py`) — rejects empty, `none`, HTML, non-XML 200s. The scraper
   now records them as missing.
3. **Extractor didn't recognize `<get>`-envelope responses** — the archive
   sometimes serves `<get gen=... id=... job=...><args/><flame/></get>`
   wrappers around real flame data. Fix: search `.//flame` at any depth.

Scraper rewrite (`scripts/scrape_archive_gen.py`):
- Three phases per gen: time-page enum → upper-bound discovery (doubling
  probe + windowed bisection) → gap sweep across `[0, max_id]`.
- Time-page indexes are partial — gen 244 reaches id 86,435+ but its
  `time/*.html` view caps at 31,999. Discovery + sweep close the gap.
- `scripts/preserve_archived_sheep.sh` rewritten as parallel-worker driver
  (default 4 workers, configurable). Per-gen cadence stays at 2s±1s; total
  aggregate ~few req/s — gentle for the archive's AWS host.

Cleanup utilities:
- `scripts/sanitize_scrape_dir.py` — quarantines `none` / empty / HTML
  files from existing scrape dirs into `missing.txt`. Ran across six
  scrape dirs: 959 files quarantined (191: 4, 198: 81, 242: 208, 243: 290,
  244: 227, 245: 149). Surfaced an interesting find: gen 245 has 7,963
  `<get>`-envelope files that are real flame data (now correctly
  preserved, not garbage).

Invariants updated:
- **Politeness** now permits modest cross-gen parallelism for the archive
  endpoint (still strictly sequential for live v3d0).
- **Spex response shapes** — three legal envelopes documented in CLAUDE.md
  (bare flame, multi-flame, `<get>`-wrapped); all accepted by extract.

Rolled back this session's botched imports of gens 191/198/242/243/245 —
sealed zips were dropped before any code shipped that depended on them.

19 new tests (multi-flame, `<get>` envelope, content validation,
discovery probe, sweep skip-without-network). Total: **135 passing**.

## v0.2.0 — 2026-05-20

Storage refactor + ergonomics.

- Chunked `.zip` storage at 10k id-range per chunk; sealed-immutable once a
  chunk's range is fully probed
- Per-chunk `MANIFEST.csv` inside each sealed zip (id, sha256, fetched_at,
  source_url, name, nick, url, xform_count, final_xform, variations) — seam for
  the v0.3 pyr3-facing index
- Automatic v0.1 → v0.2 migration on first fetch (one-shot, idempotent)
- New: `sheep-fold fetch-all` — fetch entire gen range
- New: `sheep-fold import <dir>` — bulk-import existing local flames
- New: `sheep-fold seal --chunk NNNNN-NNNNN` — force-seal an incomplete chunk
- `status` extended to show per-chunk state breakdown
- All v0.1 invariants preserved (politeness, sticky-404, atomic writes,
  filename preservation, license obligations)

### Deferred to v0.3

- `corpus/{gen}/index.csv` chunk-overview file (spec §5.8). `status` covers
  the user-visible need via filesystem glob; v0.3's aggregated MANIFEST.csv
  reader likely subsumes this.

## v0.1.0 — 2026-05-19

Initial ship.

- Polite range-based mirror of `.flam3` files from `v3d0.sheepserver.net/gen/248/`
- Sticky 404 memory via `corpus/{gen}/missing.txt`
- Local-first dedup; skips cost zero server time
- Atomic writes (tmp + `os.replace`); SIGKILL-safe
- Bucket-by-thousand on-disk layout (`248/00xxx/`…`248/40xxx/`)
- Auto-copied `corpus/ATTRIBUTION.md` (Sheep-Pack obligation per
  [electricsheep.org/license](https://electricsheep.org/license/))
- Typer CLI: `sheep-fold fetch`, `sheep-fold status`
- pytest suites for `layout`, `manifest`, `fetch` (mock-transport, no real network)
