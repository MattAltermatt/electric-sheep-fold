# 📝 Changelog

## v0.2.1 — 2026-05-21

### Phase 10 — live-gen guard + gen 247 chunked ingest

`sheep-fold fetch` / `fetch-all` now hard-reject any `--gen` value not in
`LIVE_GENS = {247, 248}` with a hint to use `scripts/scrape_archive_gen.py +
import --whole-gen` for dead gens. Extending the set when ES rolls gen 249 is
a one-line edit in `layout.py`. 12 new CLI guard tests (160 total green).

Gen 247 ingested into the chunked 10k-id layout from `corpus/_scrape-247/`
(9007 flam3s preseeded from `~/dev/sheep/247/`, ids `0`–`25845`) → three
working chunks `00000-09999`, `10000-19999`, `20000-29999` in `corpus/247/`.
No auto-seal yet (no `missing.txt` to prove range completion); chunks will
seal naturally as `fetch-all --gen 247` against v3d0 fills the gaps. Source
`_scrape-247/` symlink dir removed post-import.

### Phase 9 — dead-gen whole-zip policy

Dead-preserved gens (sourced from the `electricsheep.com/archives` static
mirror) now seal as a single whole-gen zip spanning `[0, max_observed_id + 1)`
instead of synthetic 10k-id decade chunks. Live-preserved gens (247 / 248,
sourced via `v3d0.sheepserver.net`) keep their 10k-chunk layout — the gen's
biography is encoded in the chunk shape itself, and a gen's shape is fixed
at first preservation (no re-chunking when an upstream gen eventually dies).

Spec:
[`docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md`](docs/superpowers/specs/2026-05-21-electric-sheep-fold-v0.2.1-dead-gen-whole-zip.md).

Code changes:
- `layout.archive_url(gen, id)` — new helper for `electricsheep.com/archives`
  source URLs (used by whole-gen seals; `remote_url` continues to point at
  v3d0 for live-gen seals).
- `importer.import_dir(..., whole_gen=True, gen=N)` — new mode that scans the
  scrape dir for flam3s + `_missing_404.txt`, computes `max_id`, copies the
  missing set into `corpus/{gen}/missing.txt`, imports all flam3s into a
  single `Chunk(0, max_id+1)`, and seals.
- `sheep-fold import --whole-gen [--gen N]` — CLI flag plumbing; `gen` is
  inferred from filenames when omitted (errors if src has mixed gens).
- `CLAUDE.md` chunk-size invariant amended to describe the live/dead split.

13 importer tests + 3 layout tests added (148 total green).

### Phase 8b — all dead flam3 gens preserved + sealed

Eight dead flam3-bearing gens fully preserved + sealed under the v0.2.1
whole-gen policy. Every id in `[0, max_observed_id]` is accounted for as
either a `.flam3` on disk or a `missing.txt` entry:

| Gen | flam3s | sticky-404s | sealed zip            | size  |
|-----|-------:|------------:|-----------------------|------:|
| 165 |    998 |         100 | `00000-01097.zip`     | 0.6MB |
| 169 | 21,745 |         100 | `00000-21844.zip`     | 15.4MB |
| 191 | 21,743 |         107 | `00000-21849.zip`     | 20.9MB |
| 198 | 31,836 |         191 | `00000-32026.zip`     | 89.6MB |
| 242 |  3,388 |         306 | `00000-03693.zip`     | 14.2MB |
| 243 |  5,266 |      12,521 | `00000-17786.zip`     | 15.8MB |
| 244 | 33,594 |      52,982 | `00000-86575.zip`     | 204.5MB |
| 245 | 11,950 |         249 | `00000-12198.zip`     | 108.6MB |
| **Σ** | **130,520** | **66,556** | — | **~470MB** |

Gen 244 surfaced exactly one sweep-gap (id 67084 — no flam3, no missing
entry); a single HEAD probe against the archive returned 404, added to
`missing.txt`, re-seal completed cleanly. All MANIFEST.csv rows carry archive
`source_url`s; zero XML parse failures across all eight gens.

After seal, the raw `_scrape-{165,169,191,198,242,243,244,245}/` working
directories were removed — every flam3 is fully captured in the sealed zip
with provenance, so the raw dirs were ~1.8GB of redundant data. The
`_scrape-247/` symlink tree is preserved pending Phase 10's live-track
reconciliation.

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
