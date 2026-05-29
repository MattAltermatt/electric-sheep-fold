# Corpus Share-URL & Chunk-Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Tasks are **Claude-sized** (one
> logical increment, TDD red→green within the task, ending in passing tests
> + a commit) per the project's task-granularity convention — not decomposed
> into per-step plan entries.

**Goal:** Ship short, shareable corpus URLs (`pyr3.app/v1/gen/{gen}/id/{id}`)
that open in the pyr3 renderer and load the exact flame, delivered via
brotli chunks baked same-origin into the pyr3 GitHub Pages deploy.

**Architecture:** ESF's `release-build` emits a `corpus-chunks-{date}.tar`
Release asset (brotli `{id:xml}` chunks of 256 consecutive ids + per-gen
present-id manifests + `gens.json`). pyr3's Pages deploy bakes that asset
into `dist/chunks/`; the SPA parses `/v1/...` paths, fetches the one chunk
for a requested `(gen,id)`, brotli-decodes it natively, and renders.

**Tech Stack:** Python 3 + brotli + pytest (ESF); TypeScript + Vite +
Vitest + native `DecompressionStream("brotli")` (pyr3); GitHub Actions +
GitHub Pages.

**Canonical spec:** `docs/superpowers/specs/2026-05-28-corpus-share-url-and-chunk-delivery-design.md`
— read it before starting. Tasks tagged **[ESF]** or **[pyr3]** by repo;
both have a `feature/share-url-chunk-delivery` branch.

---

## File map

**[ESF]** (`/Users/matt/dev/MattAltermatt/electric-sheep-fold`)
- Create: `src/electric_sheep_fold/chunk.py` — chunk math, chunk build,
  availability manifest, `gens.json`, tar assembly. Single responsibility:
  "turn the corpus tree into the delivery chunk artifact."
- Modify: `src/electric_sheep_fold/release.py` — call the chunk builder
  during `release-build`.
- Modify: `src/electric_sheep_fold/cli.py` — add `sheep-fold chunk`
  subcommand (standalone build/debug).
- Create: `tests/test_chunk.py`.
- Modify docs: `CLAUDE.md` (invariants), `README.md`, `CHANGELOG.md`.

**[pyr3]** (`/Users/matt/dev/MattAltermatt/pyr3`)
- Create: `src/brotli.ts` — native-first brotli inflate with lazy wasm
  fallback.
- Create: `src/chunk-fetch.ts` — `(gen,id)` → fetch + inflate + extract XML.
- Create: `src/avail.ts` — per-gen present-id manifest client.
- Modify: `src/load-intent.ts` — parse `/v1/...` paths + legacy `?flame=`.
- Modify: `src/main.ts` — dispatch the parsed intent to fetch/render/browse.
- Create tests: `src/brotli.test.ts`, `src/chunk-fetch.test.ts`,
  `src/avail.test.ts`, `src/load-intent.test.ts` (extend existing).
- Create: `.github/workflows/deploy.yml`, `public/CNAME`.
- Modify docs: `README.md`, `CHANGELOG.md`.

---

## Phase 1 — [ESF] chunk build pipeline (Python · subagent-driven TDD)

### Task 1.1: Chunk grouping + path math

**Files:** Create `src/electric_sheep_fold/chunk.py`; Test `tests/test_chunk.py`.

- [ ] Write failing tests for the delivery-chunk math (independent of the
  storage bucket in `layout.py`):

```python
# tests/test_chunk.py
from electric_sheep_fold.chunk import CHUNK_SIZE, chunk_lo, chunk_filename

def test_chunk_size_is_256():
    assert CHUNK_SIZE == 256

def test_chunk_lo_floors_to_multiple_of_256():
    assert chunk_lo(0) == 0
    assert chunk_lo(255) == 0
    assert chunk_lo(256) == 256
    assert chunk_lo(12345) == 12288

def test_chunk_filename_is_zero_padded_opaque():
    # opaque extension on purpose (no .br) — see spec §6
    assert chunk_filename(247, 12345) == "247/12288.flam3chunk"
    assert chunk_filename(247, 5) == "247/00000.flam3chunk"
```

- [ ] Run `pytest tests/test_chunk.py -q` → fails (module missing).
- [ ] Implement `CHUNK_SIZE = 256`, `chunk_lo(id)`, `chunk_filename(gen, id)`
  in `chunk.py`.
- [ ] Run tests → pass.
- [ ] Commit: `feat(chunk): delivery-chunk path math (256-id granularity)`.

### Task 1.2: Build one chunk (brotli JSON map) — round-trip

**Files:** Modify `src/electric_sheep_fold/chunk.py`; Test `tests/test_chunk.py`.

- [ ] Write failing round-trip test: given a dict `{id: xml}`,
  `build_chunk_bytes` returns brotli bytes that decompress to JSON with the
  ids present, the `"_v"` version key, and byte-identical XML. Missing ids
  absent.

```python
import json, brotli
from electric_sheep_fold.chunk import build_chunk_bytes, CHUNK_FORMAT_VERSION

def test_build_chunk_roundtrips():
    flames = {12288: "<flame name='a'>x</flame>", 12290: "<flame name='b'>y</flame>"}
    raw = build_chunk_bytes(flames)
    obj = json.loads(brotli.decompress(raw))
    assert obj["_v"] == CHUNK_FORMAT_VERSION == 1
    assert obj["12288"] == "<flame name='a'>x</flame>"
    assert obj["12290"] == "<flame name='b'>y</flame>"
    assert "12289" not in obj  # gaps absent
```

- [ ] Run → fails. Implement `CHUNK_FORMAT_VERSION = 1` and
  `build_chunk_bytes(flames: dict[int,str]) -> bytes` = `brotli.compress(
  json.dumps({"_v": 1, **{str(k): v for k,v in sorted(flames.items())}},
  ensure_ascii=False).encode(), quality=11)`.
- [ ] Run → pass.
- [ ] Commit: `feat(chunk): build_chunk_bytes — brotli(JSON {id:xml}) round-trip`.

### Task 1.3: Per-gen availability manifest (present-id list) — round-trip

**Files:** Modify `src/electric_sheep_fold/chunk.py`; Test `tests/test_chunk.py`.

- [ ] Write failing round-trip test for a sorted delta-varint present-id
  encoder (brotli'd), decoded back to the exact sorted id set:

```python
from electric_sheep_fold.chunk import encode_avail, decode_avail

def test_avail_roundtrips_sparse_clustered_ids():
    ids = sorted({0, 1, 2, 3, 100, 101, 40000, 41234})
    raw = encode_avail(ids)
    assert decode_avail(raw) == ids
    assert len(raw) < len(ids) * 4  # compact
```

- [ ] Run → fails. Implement `encode_avail(ids)` = brotli of
  delta-varint(sorted ids); `decode_avail(raw)` inverse. (LEB128 varints
  over first-id + successive deltas.)
- [ ] Run → pass.
- [ ] Commit: `feat(chunk): per-gen present-id availability manifest`.

### Task 1.4: `gens.json` summary

**Files:** Modify `src/electric_sheep_fold/chunk.py`; Test `tests/test_chunk.py`.

- [ ] Write failing test: `build_gens_json(per_gen)` (mapping
  `gen -> sorted ids`) returns a dict with `schema`, `build_date`,
  `chunk_size`, and a `gens` list of `{gen,count,min_id,max_id}` sorted by
  gen.

```python
from electric_sheep_fold.chunk import build_gens_json

def test_gens_json_shape():
    out = build_gens_json({247: [0, 5, 41234], 248: [10]}, build_date="2026-05-28")
    assert out["schema"] == 1 and out["chunk_size"] == 256
    assert out["build_date"] == "2026-05-28"
    assert out["gens"][0] == {"gen": 247, "count": 3, "min_id": 0, "max_id": 41234}
    assert out["gens"][1]["gen"] == 248
```

- [ ] Run → fails. Implement `build_gens_json(per_gen, build_date)`.
- [ ] Run → pass.
- [ ] Commit: `feat(chunk): gens.json browse summary`.

### Task 1.5: Assemble `corpus-chunks-{date}.tar` from a corpus tree

**Files:** Modify `src/electric_sheep_fold/chunk.py`; Test `tests/test_chunk.py`.

- [ ] Write failing test using a tmp corpus tree (a couple of gens, a few
  `electricsheep.{gen}.{id}.flam3` files in the real chunked layout) →
  `build_chunks_tar(corpus_root, out_tar, build_date)` produces a tar whose
  members are exactly: `gens.json`, `{gen}/avail.flam3idx` per gen, and one
  `{gen}/{chunk_lo:05d}.flam3chunk` per non-empty 256-window; and each
  chunk decompresses to the right flames.

```python
import tarfile, json, brotli
from pathlib import Path
from electric_sheep_fold.chunk import build_chunks_tar

def _write(p, gen, sid, body):
    f = p / str(gen) / f"{(sid//10000)*10000:05d}" / f"electricsheep.{gen}.{sid}.flam3"
    f.parent.mkdir(parents=True, exist_ok=True); f.write_text(body); return f

def test_build_chunks_tar(tmp_path):
    corpus = tmp_path / "corpus"
    _write(corpus, 247, 5, "<flame>five</flame>")
    _write(corpus, 247, 300, "<flame>threehundred</flame>")  # different 256-window
    out = tmp_path / "corpus-chunks-2026-05-28.tar"
    build_chunks_tar(corpus, out, build_date="2026-05-28")
    names = set(tarfile.open(out).getnames())
    assert "gens.json" in names
    assert "247/avail.flam3idx" in names
    assert "247/00000.flam3chunk" in names   # id 5 → window 0
    assert "247/00256.flam3chunk" in names   # id 300 → window 256
    with tarfile.open(out) as t:
        obj = json.loads(brotli.decompress(t.extractfile("247/00000.flam3chunk").read()))
        assert obj["5"] == "<flame>five</flame>"
```

- [ ] Run → fails. Implement `build_chunks_tar` (walk corpus via the real
  layout, group by `chunk_lo`, build chunk bytes + avail + gens.json, write
  an uncompressed tar with those members).
- [ ] Run → pass.
- [ ] Commit: `feat(chunk): assemble corpus-chunks-{date}.tar artifact`.

### Task 1.6: Wire into `release-build` + `sheep-fold chunk` CLI

**Files:** Modify `src/electric_sheep_fold/release.py`,
`src/electric_sheep_fold/cli.py`; Test `tests/test_chunk.py` (+ existing
release tests if present).

- [ ] Write failing test: invoking the release builder (or a thin
  `build_release(..., chunks=True)`) over a tmp corpus emits
  `build/release/corpus-chunks-{date}.tar` alongside existing artifacts; and
  `sheep-fold chunk --date 2026-05-28` produces the same tar.
- [ ] Run → fails. Add the chunk step to `release.py`'s build (gated like
  other artifacts, written to `build/release/`, NOT `corpus/`) and a
  `chunk` subcommand in `cli.py` that calls `build_chunks_tar`.
- [ ] Run full suite `pytest -q` → pass (no regressions in the ~207 tests).
- [ ] Commit: `feat(release): emit corpus-chunks artifact in release-build + sheep-fold chunk`.

### Task 1.7: ESF docs (invariants + README + CHANGELOG)

**Files:** Modify `CLAUDE.md`, `README.md`, `CHANGELOG.md`.

- [ ] Add a load-bearing invariant to `CLAUDE.md`: the chunk artifact
  (`corpus-chunks-{date}.tar` = brotli `{id:xml}` chunks of `CHUNK_SIZE=256`
  + per-gen `avail.flam3idx` + `gens.json`); opaque `.flam3chunk` extension;
  delivery-chunk granularity independent of the storage bucket; `chunk.py`
  is the single source of truth for chunk math. Add `chunk` to the CLI
  command list. README: add the artifact + the `pyr3.app/v1/gen/{gen}/id/{id}`
  consumer. CHANGELOG: entry referencing the spec.
- [ ] Run `pytest -q` (sanity). Commit: `docs: chunk artifact invariants + README/CHANGELOG`.

---

## Phase 2 — [pyr3] chunk fetch + routing (TypeScript · subagent-driven TDD for logic; lead-inline for main.ts wiring)

> Switch repos: all Phase 2 work is in `/Users/matt/dev/MattAltermatt/pyr3`
> on branch `feature/share-url-chunk-delivery`. Tests: `npm test` (vitest).

### Task 2.1: Native-first brotli inflate (`src/brotli.ts`)

**Files:** Create `src/brotli.ts`; Test `src/brotli.test.ts`.

- [ ] Write failing test: `inflateBrotli(bytes)` returns the original string
  for a brotli-compressed input. (Generate the fixture bytes with Node's
  `zlib.brotliCompressSync` in the test so it's self-contained.)

```ts
import { describe, it, expect } from "vitest";
import { brotliCompressSync } from "node:zlib";
import { inflateBrotli } from "./brotli";

describe("inflateBrotli", () => {
  it("round-trips a brotli payload", async () => {
    const text = JSON.stringify({ _v: 1, "5": "<flame>five</flame>" });
    const bytes = brotliCompressSync(Buffer.from(text));
    const out = await inflateBrotli(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    expect(out).toBe(text);
  });
});
```

- [ ] Run `npm test src/brotli.test.ts` → fails.
- [ ] Implement `inflateBrotli(bytes: ArrayBuffer): Promise<string>`:
  feature-detect `new DecompressionStream("brotli")` (try/catch, cached);
  native path pipes bytes through it; fallback branch lazy-imports a
  decode-only wasm (leave a clearly-marked `loadWasmBrotli()` stub that
  throws "wasm fallback not bundled" until needed — native path is the 2026
  default and the test exercises it). Decode via `new Response(stream).text()`.
- [ ] Run → pass.
- [ ] Commit: `feat(pyr3): native-first brotli inflate util`.

### Task 2.2: Chunk fetch + extract (`src/chunk-fetch.ts`)

**Files:** Create `src/chunk-fetch.ts`; Test `src/chunk-fetch.test.ts`.

- [ ] Write failing tests: `chunkLo(id)` math mirrors ESF
  (`chunkLo(12345)===12288`); `chunkUrl(gen,id)` ===
  `/chunks/247/12288.flam3chunk`; `fetchFlameXml(gen,id, fetchImpl)` fetches
  that URL, inflates, parses, returns the id's XML; throws a typed
  `FlameNotFound` when the id is absent from the map. Use an injected
  `fetchImpl` returning a brotli'd JSON map (built with
  `brotliCompressSync` in the test).

```ts
import { describe, it, expect } from "vitest";
import { brotliCompressSync } from "node:zlib";
import { chunkLo, chunkUrl, fetchFlameXml, FlameNotFound } from "./chunk-fetch";

const blob = (obj: object) => {
  const b = brotliCompressSync(Buffer.from(JSON.stringify(obj)));
  return new Response(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
};

describe("chunk-fetch", () => {
  it("maps id → window + url", () => {
    expect(chunkLo(12345)).toBe(12288);
    expect(chunkUrl(247, 12345)).toBe("/chunks/247/12288.flam3chunk");
  });
  it("fetches + extracts the requested flame", async () => {
    const fetchImpl = async () => blob({ _v: 1, "12345": "<flame>hi</flame>" });
    expect(await fetchFlameXml(247, 12345, fetchImpl as any)).toBe("<flame>hi</flame>");
  });
  it("throws FlameNotFound for an absent id", async () => {
    const fetchImpl = async () => blob({ _v: 1, "12345": "<flame>hi</flame>" });
    await expect(fetchFlameXml(247, 12300, fetchImpl as any)).rejects.toBeInstanceOf(FlameNotFound);
  });
});
```

- [ ] Run → fails. Implement `chunkLo`, `chunkUrl` (zero-pad window to 5),
  `FlameNotFound`, and `fetchFlameXml(gen,id,fetchImpl=fetch)` using
  `inflateBrotli` + `JSON.parse` + lookup (ignore `_v`). Fetch as raw bytes
  (`res.arrayBuffer()`); never assume `Content-Encoding`.
- [ ] Run → pass.
- [ ] Commit: `feat(pyr3): chunk fetch + flame extraction`.

### Task 2.3: Availability client (`src/avail.ts`)

**Files:** Create `src/avail.ts`; Test `src/avail.test.ts`.

- [ ] Write failing test: `decodeAvail(bytes)` decodes the ESF delta-varint
  present-id format (build a fixture matching ESF's encoder), and
  `exists(ids, id)` binary-searches. Keep the decoder byte-compatible with
  `chunk.py::encode_avail`.

```ts
import { describe, it, expect } from "vitest";
import { decodeAvail, exists } from "./avail";
// fixture: brotli(delta-varint([0,5,300])) produced by the ESF encoder — paste real bytes here
// (generate once via: python -c "from electric_sheep_fold.chunk import encode_avail; import sys; sys.stdout.buffer.write(encode_avail([0,5,300]))" | base64)
const FIXTURE_B64 = "<<REPLACE_WITH_REAL_FIXTURE>>";

describe("avail", () => {
  it("decodes the ESF present-id format", async () => {
    const bytes = Uint8Array.from(atob(FIXTURE_B64), c => c.charCodeAt(0));
    const ids = await decodeAvail(bytes.buffer);
    expect(ids).toEqual([0, 5, 300]);
    expect(exists(ids, 5)).toBe(true);
    expect(exists(ids, 6)).toBe(false);
  });
});
```

> **Cross-repo contract note:** generate `FIXTURE_B64` from the real
> `chunk.py::encode_avail` (command in the comment) before implementing —
> this test is the conformance check that the TS decoder matches the Python
> encoder. Do not hand-fake the bytes.

- [ ] Run → fails. Implement `decodeAvail` (brotli-inflate via the byte
  path, read varints, undo deltas) + `exists`.
- [ ] Run → pass.
- [ ] Commit: `feat(pyr3): availability manifest client (ESF-conformant)`.

### Task 2.4: URL router (extend `src/load-intent.ts`)

**Files:** Modify `src/load-intent.ts`; Test `src/load-intent.test.ts`.

- [ ] Extend `LoadIntent` and write failing tests for `parseLoadIntent`
  taking `{ pathname, search }`:

```ts
// new LoadIntent variants:
//  | { kind: "corpus"; gen: number; id: number }
//  | { kind: "gen-list" }
//  | { kind: "gen-browse"; gen: number }
//  | { kind: "custom-reserved" }
//  | { kind: "flame"; payload: string }   // legacy ?flame=
//  | { kind: "default" }
import { describe, it, expect } from "vitest";
import { parseLoadIntent } from "./load-intent";

describe("parseLoadIntent paths", () => {
  const p = (pathname: string, search = "") => parseLoadIntent({ pathname, search });
  it("corpus leaf", () => expect(p("/v1/gen/247/id/12345")).toEqual({ kind: "corpus", gen: 247, id: 12345 }));
  it("gen list", () => expect(p("/v1/gen")).toEqual({ kind: "gen-list" }));
  it("gen browse", () => expect(p("/v1/gen/247")).toEqual({ kind: "gen-browse", gen: 247 }));
  it("custom reserved", () => expect(p("/v1/flame/abc")).toEqual({ kind: "custom-reserved" }));
  it("legacy ?flame=", () => expect(p("/", "?flame=v1:xyz")).toEqual({ kind: "flame", payload: "v1:xyz" }));
  it("root → default", () => expect(p("/")).toEqual({ kind: "default" }));
  it("garbage → default", () => expect(p("/v1/gen/abc/id/x")).toEqual({ kind: "default" }));
});
```

- [ ] Run → fails. Reimplement `parseLoadIntent` to accept
  `{pathname, search}` (update the existing call in `main.ts:353` to pass
  `window.location`), branch on the `/v1/...` segments with integer
  validation, keep the `?flame=` legacy branch, default otherwise. Update
  the file's top comment (currently says "exactly one share mechanism").
- [ ] Run → pass (including the existing leading-`?` test, adapted).
- [ ] Commit: `feat(pyr3): /v1 path router + legacy ?flame= in parseLoadIntent`.

### Task 2.5: Wire intents into the app (`src/main.ts`) — lead-inline

**Files:** Modify `src/main.ts`.

- [ ] In `main.ts`, dispatch the parsed intent:
  - `corpus` → `await fetchFlameXml(gen,id)` → existing flame-import →
    render; on `FlameNotFound` (or avail miss) render a "this sheep doesn't
    exist (lost upstream)" state.
  - `gen-list` → fetch `/chunks/gens.json`, render the list (each gen links
    to `/v1/gen/{gen}`).
  - `gen-browse` → fetch `/chunks/{gen}/avail.flam3idx`, render a "browse
    coming soon — N flames available" placeholder (visual gallery deferred).
  - `custom-reserved` → render "custom flame sharing not yet supported".
  - `flame` (legacy) / `default` → unchanged existing paths.
  - Optionally short-circuit a corpus click through `avail.exists` before
    fetching the 172 KB chunk.
- [ ] Verify: `npm run typecheck` clean; `npm test` green; `npm run dev`
  and manually hit `/v1/gen/247/id/<known-id>` against a locally-unpacked
  chunk tree in `public/chunks/` (copy a slice for dev). (Full live verify
  is Phase 4.)
- [ ] Commit: `feat(pyr3): dispatch /v1 intents — corpus load, gen-list, browse placeholder`.

### Task 2.6: pyr3 docs

**Files:** Modify `README.md`, `CHANGELOG.md` (pointer doc
`docs/corpus-share-url.md` already committed).

- [ ] README: add the `pyr3.app/v1/gen/{gen}/id/{id}` share form + the
  baked `/chunks/` layer + link the pointer doc. CHANGELOG entry.
- [ ] Commit: `docs(pyr3): share-URL + chunk consumer notes`.

---

## Phase 3 — [pyr3] deploy, bake-at-deploy, domain (lead-inline · shell/CI/gh)

> Lead-inline: needs `gh`, shell, and live GitHub Pages — outside subagent
> Bash perms.

### Task 3.1: De-risk probes (do FIRST — cheap, decisive)

- [ ] **Brotli round-trip:** in Chrome stable + Safari + Firefox, run
  `new DecompressionStream("brotli")` + decode one real chunk fetched as
  raw bytes. Confirm native path; note any browser needing the wasm
  fallback.
- [ ] **404 SPA-fallback probe:** deploy a throwaway with `404.html`
  (= copy of a stub index), `.nojekyll`, and one real
  `chunks/247/00000.flam3chunk`. Assert in DevTools: that chunk → **200** +
  bytes; `/v1/gen/247/id/5` → **404** + the SPA shell HTML.
- [ ] **Bake dry run:** a scratch Actions step that
  `gh release download` the existing ESF `corpus-all-*.tar.xz` (or, once
  Phase 1 ships, `corpus-chunks-*.tar`) and untars a slice into `dist/`.
  Confirm auth (`GITHUB_TOKEN`) + timing.
- [ ] Record findings in the spec's risk register if anything diverges. No
  commit (probes are throwaway) unless a fixture is worth keeping.

### Task 3.2: GH Pages deploy workflow

**Files:** Create `.github/workflows/deploy.yml`.

- [ ] Author the workflow per spec §10: `npm ci && npm run build` →
  **Bake** step (`gh release download "$CHUNK_RELEASE_TAG" --repo
  MattAltermatt/electric-sheep-fold --pattern 'corpus-chunks-*.tar'`, untar
  into `dist/chunks/`) → `cp dist/index.html dist/404.html` +
  `touch dist/.nojekyll` → `actions/upload-pages-artifact@v3` →
  `actions/deploy-pages@v4`. Pin `CHUNK_RELEASE_TAG` (env, e.g.
  `2026-05-28`). Permissions: `pages: write`, `id-token: write`,
  `contents: read`.
- [ ] Push the branch; confirm the Action runs green and the deployed site
  serves a real `/chunks/...` file at 200.
- [ ] Commit: `ci(pyr3): GH Pages deploy with bake-at-deploy + SPA 404 fallback`.

### Task 3.3: Custom domain `pyr3.app`

**Files:** Create `public/CNAME` (`pyr3.app`).

- [ ] Add `public/CNAME`; configure the repo's Pages custom domain; set DNS
  (user action — apex `A`/`AAAA` to GitHub Pages IPs or `CNAME` for a
  subdomain; enforce HTTPS). **This DNS step is manual and the user must do
  it.**
- [ ] Verify `https://pyr3.app/` serves the SPA over HTTPS.
- [ ] Commit: `ci(pyr3): pyr3.app custom domain (CNAME)`.

---

## Phase 4 — review + live verify

### Task 4.1: Fresh-reviewer code review (both repos)

- [ ] Dispatch a fresh reviewer agent (no implementation bias) over the ESF
  + pyr3 diffs against the spec: contract conformance (chunk format ↔ TS
  decoder, avail encoder ↔ decoder), invariants (opaque extension, no data
  in git, storage/delivery independence), test coverage, the `?flame=`
  legacy path. Address findings via `superpowers:receiving-code-review`.

### Task 4.2: Live verify on `pyr3.app`

- [ ] After deploy, open the live URL, watch the console:
  - `https://pyr3.app/v1/gen/247/id/<known-id>` → flame renders.
  - A known-missing id → "lost upstream" state (no 172 KB fetch if avail
    short-circuits).
  - A neighbour id in the same chunk → loads instantly (cache).
  - `https://pyr3.app/v1/gen` → gen list; `/v1/gen/247` → placeholder.
  - Legacy `?flame=v1:...` still renders.
- [ ] Hand off to user for manual inspection (user-verify before FF-merge).

---

## Self-review (done at authoring)

- **Spec coverage:** URL grammar → 2.4; addressing/chunk math → 1.1/2.2;
  chunk wire format → 1.2/2.1/2.2; availability manifest → 1.3/2.3; gens.json
  → 1.4/2.5; tar assembly → 1.5; release wiring → 1.6; bake-at-deploy → 3.2;
  routing/404 → 3.2 + probe 3.1; reconciliation/legacy `?flame=` → 2.4;
  docs → 1.7/2.6; risk de-risk → 3.1; edge cases (not-found, sparse) →
  2.2/2.3/2.5. Deferred phase (previews/gallery/custom) intentionally **not**
  tasked (spec §11/§12). No gaps for short-term scope.
- **Cross-repo contract:** ESF `encode_avail` (1.3) ↔ pyr3 `decodeAvail`
  (2.3) guarded by a real-bytes conformance fixture; chunk JSON `{_v, id:xml}`
  (1.2) ↔ `fetchFlameXml` (2.2) consistent (`_v` key skipped on lookup).
- **Naming consistency:** `CHUNK_SIZE`/`chunk_lo`/`chunkLo`,
  `.flam3chunk`, `avail.flam3idx`, `gens.json`, `corpus-chunks-{date}.tar`
  used consistently across tasks and the spec.

---

## Execution Handoff

Per-phase mode (project convention — subagent-driven for pure logic/test;
lead-inline where shell/CI/Chrome is needed):

```text
Phase 1 [ESF, Python logic]        → Subagent-Driven (TDD)
Phase 2 tasks 2.1–2.4 [pyr3 logic] → Subagent-Driven (TDD)
Phase 2 task 2.5 [main.ts wiring]  → lead-Inline (dev server)
Phase 3 [deploy/CI/gh/DNS]         → lead-Inline (shell + live; DNS = user)
Phase 4 [review + Chrome verify]   → lead-Inline (fresh reviewer + Chrome MCP)
```

Effort advisory: ⬇️ Phases 1–2 are mechanical impl of a locked spec —
suggest `medium`. Phase 3–4 stay `medium`/as-needed.
