# 🛠️ Operations runbook

Day-to-day tasks for the corpus + the `sheep-fold` toolchain. This is the
**how-do-I-...** doc; design rationale lives in [VISION](../VISION.md),
[ROADMAP](../ROADMAP.md), and the [specs](superpowers/specs/).

All commands assume `cwd = /Users/matt/dev/MattAltermatt/electric-sheep-fold`.

---

## Live-fetch daemon

The daemon is `sheep-fold fetch-all` wrapped in a `nohup` chain that
iterates gens 247 → 248 sequentially, honoring the 20s ± 5s polite cadence
against `v3d0.sheepserver.net`. State is captured in `.flam3` files on
disk + `corpus/{gen}/missing.txt`; resume is automatic via skip-local +
skip-known-missing.

### Start

```sh
scripts/resume_live_fetch.sh           # gens 247 then 248, upper 50000
scripts/resume_live_fetch.sh 60000     # custom upper for both gens
```

The script auto-detects an existing chain via `corpus/_live-fetch-logs/.chain.pid`
+ `pgrep`. If found, it tails the existing log (Ctrl-C exits tail but does
**not** stop the fetch). If not, it launches via `nohup`+`disown`, writes
the new wrapper PID to `.chain.pid`, then tails.

### Check status

```sh
ps -ef | grep 'sheep-fold fetch-all' | grep -v grep   # daemon alive?
cat corpus/_live-fetch-logs/.chain.pid                # wrapper PID
ls -t corpus/_live-fetch-logs/fetch-live-*.log | head -1  # latest log
tail -f "$(ls -t corpus/_live-fetch-logs/fetch-live-*.log | head -1)"

sheep-fold status --gen 247           # per-gen loose-file + missing counts
sheep-fold status --gen 248
```

### Stop

```sh
kill "$(cat corpus/_live-fetch-logs/.chain.pid)"      # kills wrapper + child
ps -ef | grep 'sheep-fold fetch-all' | grep -v grep || echo "(stopped)"
```

`kill -TERM` lets in-flight HTTP requests finish cleanly. Atomic writes
(`.tmp` + `os.replace`) make SIGKILL safe too, but TERM is the default.

### Manual launch (fallback)

If `scripts/resume_live_fetch.sh` misbehaves when backgrounded (the
attach-vs-launch branch can get confused under unusual redirect flows),
launch the chain directly:

```sh
LOG="corpus/_live-fetch-logs/fetch-live-$(date +%Y%m%d-%H%M).log"
nohup bash -c '
  for gen in 247 248; do
    echo "=== gen $gen — starting at $(date -u +%FT%TZ) ==="
    sheep-fold fetch-all --gen "$gen" --upper 50000 || echo "=== gen $gen — exited nonzero ==="
    echo "=== gen $gen — finished at $(date -u +%FT%TZ) ==="
  done
' > "$LOG" 2>&1 &
echo "$!" > corpus/_live-fetch-logs/.chain.pid
disown
```

### Survives shell exit but not reboot

`nohup` + `disown` decouple the daemon from the terminal session, so
closing the shell is fine. But power cycle / hard reboot terminates the
process. After a Mac reboot, just re-run the restart command — resume is
automatic via skip-local + skip-known-missing.

### What "done" looks like

The chain runs until both gens hit the configured `--upper` (default
50000), with each new id either fetched to a flat path or recorded in
`missing.txt`. Final lines in the log will be:

```
=== gen 248 — finished at YYYY-MM-DDTHH:MM:SSZ ===
=== chain complete at YYYY-MM-DDTHH:MM:SSZ ===
```

After completion, gens 247 + 248 each have `loose_count + missing_count
== upper` (modulo any genuine 404s the daemon discovers during the run).
Restart with a higher `--upper` when v3d0 extends the gen.

---

## Build a release artifact

The corpus on disk is loose `.flam3` files + `missing.txt`. Release zips
are built on demand:

```sh
scripts/build_release.sh                    # thin wrapper around sheep-fold release-build
sheep-fold release-build --out build/release/    # equivalent
sheep-fold release-build --gen 247          # single-gen mode (no mega-bundle / index regen)
```

Output goes to `build/release/`:

- `gen-{N}.zip` per gen — `MANIFEST.csv` + `missing.txt` + flat `.flam3` files
- `corpus-all.zip` — mega-bundle of all gen-zips + index + attribution
- `INDEX.md` + `index.json` — regenerated
- `ATTRIBUTION.md` — copied

### Publish to GitHub Releases

```sh
# Confirm logged in as MattAltermatt (the repo owner)
gh auth status

# Tag + push
git tag v0.X.Y
git push origin v0.X.Y

# Upload artifacts
gh release create v0.X.Y \
  --title 'v0.X.Y — corpus snapshot' \
  --notes-file docs/release-notes-v0.X.Y.md \
  build/release/*
```

Release filenames stay stable across versions (`gen-247.zip` always means
the latest snapshot of gen 247). The Release tag carries the version.

---

## Rebuild the corpus index

The agentic / pyr3 query layer lives at `corpus/_index/`. Regenerate
after any corpus mutation:

```sh
sheep-fold index                            # ~45s for ~140k flames
sheep-fold index --corpus /path/to/corpus   # custom corpus root
```

Outputs:

- `corpus/_index/index.json` — flat JSON, one record per flame, `jq`-queryable
- `corpus/_index/INDEX.md` — human/agent-readable aggregations + recipe table

See [`.claude/skills/pyr3-corpus-index/SKILL.md`](../.claude/skills/pyr3-corpus-index/SKILL.md)
for query patterns.

---

## Verify corpus consistency

After any migration or recovery operation:

```sh
sheep-fold verify-unseal                    # reads corpus/_unseal-verified.json
                                             # checks: loose count + missing count
                                             # matches recorded counts per gen
```

The check passes if all gens are consistent. Divergences are listed as
`(gen, reason)` tuples; the daemon refuses to start when divergences
exist (see CLAUDE.md "Daemon-verified id counts" invariant).

---

## Preserve a new dead generation

If ES rolls a new dead gen (numbered higher than 248 but no longer
served by `v3d0`), use the archive-scrape pipeline:

```sh
# 1. Scrape from electricsheep.com/archives (polite 2s cadence)
python scripts/scrape_archive_gen.py --gen N --out corpus/_scrape-N

# 2. Import into the loose corpus
sheep-fold import corpus/_scrape-N --gen N

# 3. Rebuild index
sheep-fold index

# 4. Tidy up the scrape staging dir
rm -rf corpus/_scrape-N
```

Dead-gen import writes flat `.flam3` files directly into `corpus/{N}/`
and merges `_missing_404.txt` → `corpus/{N}/missing.txt`. No sealing
involved (v0.3 retired the seal concept).

---

## Extend a live gen beyond its current cap

The live gens (247, 248) extend over time. To pull the next batch:

```sh
# Set a higher upper bound and restart the daemon
scripts/resume_live_fetch.sh 60000          # was 50000

# OR for one-shot for a single gen:
sheep-fold fetch-all --gen 247 --upper 60000
```

To extend `LIVE_GENS` (e.g. when ES rolls gen 249), edit
`src/electric_sheep_fold/layout.py`:

```python
LIVE_GENS = {247, 248, 249}   # add new live gen here
```

That's the only code change required — `fetch` / `fetch-all` will then
accept `--gen 249`.

---

## Bisect a regression

The branch git history is intentionally not squashed; each commit
represents a logical phase. `git bisect` will land cleanly on
phase-level introductions:

```sh
git bisect start
git bisect bad HEAD
git bisect good v0.2.5
pytest -q                                    # at each step
git bisect reset
```

Per-commit conventions: terse subject (no body unless genuinely
non-obvious), no `Co-Authored-By` trailer, identity is set
`--local` to `MattAltermatt <1435066+MattAltermatt@users.noreply.github.com>`.

---

## Common gotchas

- **`gh auth switch`** flips the gh CLI's active account but does NOT
  reconfigure git's credential helper. After switching, run
  `gh auth setup-git` or `git push` will still hit macOS Keychain's
  cached token for the previous account → 403.
- **`scripts/resume_live_fetch.sh` backgrounded with redirects** can
  stall on the attach-detect branch. Use the manual `nohup` launch
  above if the script doesn't actually start the chain.
- **Sticky-404 is sticky.** Once an id is in `missing.txt`, the daemon
  will never re-probe it. If ES ever changes numbering semantics
  (currently append-only — gaps stay gaps), the `--retry-missing`
  flag in the BACKLOG would be needed.
- **Local archive layout differs from corpus layout.** `/Users/matt/dev/sheep/247`
  uses stripped filenames (no `electricsheep.247.` prefix); the importer
  handles this automatically but be aware if doing manual diffs.

---

## Related docs

- [README](../README.md) — top-level project overview
- [VISION](../VISION.md) — why this corpus exists
- [ROADMAP](../ROADMAP.md) — phases shipped and planned
- [CLAUDE.md](../CLAUDE.md) — invariants + collaboration conventions
- [v0.3 spec](superpowers/specs/2026-05-22-v0.3-loose-corpus.md) — the
  current corpus shape and CLI surface
- [`.claude/skills/pyr3-corpus-index/SKILL.md`](../.claude/skills/pyr3-corpus-index/SKILL.md)
  — agentic queries against the index
