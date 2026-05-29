# Corpus Share-URL & Chunk-Delivery — Design Spec

**Status:** Approved (brainstorm 2026-05-28, refined by a 4-agent design duel)
**Supersedes:** the *URL layer* of `../../../flame-url-codec-spec.md` (the
`?s=` corpus form and the routing assumptions; the binary wire format +
dictionary survive, reshaped — see §11).
**Spans two repos:** `electric-sheep-fold` (ESF — corpus data + build
pipeline) and `pyr3` (the WebGPU renderer SPA). This spec is
canonical for both; `pyr3/docs/corpus-share-url.md` is a pointer to it.

> **🔧 Deployment update (2026-05-29, LIVE).** This spec was written assuming
> pyr3 deploys to the apex `pyr3.app`. It first shipped as a project-Pages
> site (`github.io/pyr3/`, base `/pyr3/`), then **flipped to the apex
> `https://pyr3.app/` (base `/`) — now LIVE + verified**, Enforce-HTTPS on,
> `github.io/pyr3/` 301-redirecting to it. How it holds together:
> - **All in-app URLs are base-aware** via `import.meta.env.BASE_URL` — the
>   `/v1/...` router strips the base prefix; `/chunks/...`, help links, and
>   the welcome fixture are `${BASE_URL}`-prefixed. The `/pyr3/`→`/` apex flip
>   was therefore a **one-line `vite.config.ts` change** (`base: '/'`) +
>   `public/CNAME` = `pyr3.app`. (Project-Pages `/pyr3/` and apex `/` are
>   mutually exclusive — one base per build.)
> - **Static assets not processed by Vite** (the help `*.html` files) use
>   **relative** links (`../`) since they can't read `import.meta.env`.
> - **Routing:** the deploy ships a `404.html` SPA-fallback
>   (`cp dist/index.html dist/404.html`) so `/v1/...` paths resolve; the
>   document returns a 404 *status* (cosmetic — page renders fine).
> - **Brotli decode reality:** Chromium has **no** native
>   `DecompressionStream("brotli")` (verified Chrome 148) — Chrome/Edge use a
>   code-split `brotli-dec-wasm` decoder (~200 KB); Safari 18.4+/FF 147+ use
>   the native path. (The original spec's "native brotli everywhere"
>   assumption was wrong; gzip is native but brotli's 5× win justifies the
>   wasm.)
> - **Deploy = manual force-push of `dist/` to `gh-pages`** (build → bake
>   chunks → `404.html` → `git -C dist push -f`). CI automation is deferred
>   (`PYR3-038`, needs a published chunk Release).

---

## 🎯 What we are building

A short, shareable URL for every flame in the corpus, that opens in the
`pyr3` renderer at `pyr3.app` and loads that exact flame — fast, even on a
cold click from a stranger. Example:

```
https://pyr3.app/v1/gen/247/id/12345
```

The corpus stays where it is (GitHub Releases, ISO-date tags). We **add** a
compact, brotli-compressed *chunk* layer that the renderer fetches
on-demand, baked into the `pyr3.app` deploy so it serves **same-origin**
with no CORS, no third-party CDN, and no data committed to either repo's
git history.

This spec covers the **short-term scope (ship now)** in full detail, and
**documents the deferred future phase** (per-flame social previews + visual
gallery) completely enough that it is not lost — see §12.

---

## 🧭 Goals (verbatim from the brainstorm)

**Long term**
1. Share **any** custom flame (not just corpus flames).
2. **No compression in the URL** unless absolutely necessary.
3. OK to invent our own schema.

**Short term**
1. Only corpus flames are linkable.
2. The corpus form **must be distinguishable** from the future custom form.
3. Nice-to-have browse: `pyr3.app` = the normal renderer; `pyr3.app/v1/gen`
   = list of available generations; `pyr3.app/v1/gen/{gen}` = the flames
   available in that gen (ids are **sparse** — show what exists); click a
   flame → it opens in the app, loaded.

**Hard constraints:** `$0` (no paid services), **low maintenance**, prefer
GitHub Pages, rendering is client-side **WebGPU**.

---

## 📐 Architecture overview

```text
                       SHARE / OPEN
  https://pyr3.app/v1/gen/247/id/12345
        │
        │  (GH Pages serves the SPA — real path via 404.html SPA-fallback)
        ▼
  pyr3 SPA router  ── parse path → (gen=247, id=12345)
        │
        │  chunk_lo = (12345 // 256) * 256 = 12288     ← pure arithmetic, no manifest
        ▼
  GET  https://pyr3.app/chunks/247/12288.flam3chunk     (~172 KB, brotli(JSON))
        │            (same-origin static file, baked into the deploy)
        ▼
  brotli-decode  →  JSON.parse  →  map["12345"]  →  .flam3 XML
        │            (DecompressionStream("brotli"), native in 2026)
        ▼
  existing flame-import → render on WebGPU
        └─ 255 neighbour ids now in memory → next nearby click is instant


  BUILD / PUBLISH (recurring, ~automated)
  fetch more sheep → sheep-fold release-build → corpus-chunks-{date}.tar  (new Release asset)
                                                + per-gen availability manifests
                                                + gens.json
        │
        ▼  (pyr3 GH Pages deploy Action, bake-at-deploy)
  gh release download --repo …/electric-sheep-fold corpus-chunks-{date}.tar
        → tar -xf into dist/chunks/ → upload-pages-artifact → pyr3.app
```

Two layers, two owners:
- **ESF owns the data + the chunk math.** Its `release-build` emits the
  chunk artifact + manifests as ordinary Release assets, alongside the
  existing per-gen zips and `corpus-all-{date}.tar.xz`. The raw 3.1 GB
  corpus stays gitignored and Release-only, exactly as today.
- **pyr3 owns the renderer + the URL surface.** Its deploy bakes the latest
  chunk artifact into the static site. No corpus data ever enters git.

---

## 🔢 Decisive facts (measured / verified this session)

- **Corpus:** 166,614 `.flam3` files, **3.1 GB uncompressed**, 10 gens
  (165, 169, 191, 198, 242, 243, 244, 245, 247, 248). Per-flame ~14–27 KB
  XML.
- **Brotli beats gzip ~5× on chunks** (cross-flame redundancy — shared
  palettes, variation names, xform structure — that gzip's small window
  misses). Measured on real `corpus/247/10000` flames:

  ```text
  chunk size   raw        gzip-9     brotli-11    brotli/flame
  32 flames    622 KB     84 KB      29 KB        ~919 B
  64 flames    1.3 MB     191 KB     56 KB        ~877 B
  128 flames   2.8 MB     416 KB     101 KB       ~791 B
  256 flames   5.5 MB     832 KB     172 KB       ~672 B
  ```

  ⇒ full corpus ≈ **110–120 MB** brotli'd. Fits free anywhere; ~650 chunks
  at size 256.
- **Native in-browser brotli is real in 2026** (this invalidates the prior
  codec spec's central caveat): `DecompressionStream("brotli")` ships in
  **Safari 18.4** (Mar 2025), **Firefox 147**, and recent **Chrome**
  (spec-tracked; exact version unpinned → feature-detect). So brotli chunks
  cost **~0 bundle**; a ~200 KB decode-only wasm (`brotli-dec-wasm`) is a
  *lazy fallback* for ancient browsers only.
- **Social unfurlers do NOT run JS** (Slack, X/Twitter, iMessage, Discord,
  Facebook, WhatsApp, Telegram — confirmed). A client-side WebGPU canvas is
  invisible to them; per-flame previews require a *pre-rendered static PNG*
  named in `og:image` at fetch time. This is why previews are a deferred
  phase that needs a thumbnail bake + an edge worker (§12).
- **`pyr3` ships only `?flame=v1:<gzip+base64url>` today.** The prior codec
  spec's `?s=` / `?fd=` forms were designed but **never shipped** — there
  are zero live links of those shapes to preserve. Clean slate.

---

## 🔗 URL grammar (full)

All app routes live under `/v1/`. The **first segment after `/v1/`** is the
*kind* discriminator. A bare integer is never a kind, so there is no
ambiguity.

```text
pyr3.app/                              the normal renderer (default flame / welcome)
pyr3.app/v1/gen                        BROWSE: list available gens + counts
pyr3.app/v1/gen/{gen}                  BROWSE: flames available in {gen}   (deferred UI — §12)
pyr3.app/v1/gen/{gen}/id/{id}          CORPUS flame — load & render it      ← the share link
pyr3.app/v1/flame/{token}              CUSTOM flame — RESERVED, not built  (long-term — §11)
```

- `{gen}` — generation integer (e.g. `247`). `{id}` — the native Electric
  Sheep sheep id (e.g. `12345`), the integer in
  `electricsheep.{gen}.{id}.flam3`.
- **Verbose `/gen/.../id/...` chosen over terse `/c/{gen}/{id}`** on
  purpose: the corpus URL's length is already trivial (integers), so
  legibility + a clean drill-down hierarchy (`/v1/gen` → `/v1/gen/{gen}` →
  `/v1/gen/{gen}/id/{id}`) wins over saving 4 characters.
- **`/gen/` vs `/flame/` is the short-term↔long-term boundary** (short-term
  goal #2). Short-term simply does **not implement** the `/flame/` branch;
  its absence *is* the boundary. Requesting `/v1/flame/...` today renders a
  "not yet supported" state.
- **Legacy:** `?flame=v1:<gzip+base64url>` (the only shipped form) keeps
  decoding indefinitely — one branch in the loader. Old pyr3-peek links
  keep working.

### Versioning — two independent version axes (load-bearing)

| Axis | Where | Bumps when | Effect |
|---|---|---|---|
| **URL grammar** | path prefix `/v1` | the kind taxonomy, addressing scheme, or chunk-size contract changes | new links use `/v2`; old `/v1` links must keep resolving |
| **Chunk wire format** | a version byte *inside* each chunk | the chunk container/encoding changes | re-encode chunks; **does NOT change any URL** |

These MUST stay independent: re-encoding chunk internals must never
invalidate a shared link, and a URL-grammar change must not force a
re-encode. `CHUNK_SIZE = 256` is part of the `/v1` contract — if it ever
changes, every chunk's data path shifts, so that is a `/v2` event.

---

## 🧮 Addressing — `(gen, id)` → chunk, pure arithmetic

No hashing, no manifest lookup to *resolve* a link (only to *validate
existence*, see §8). `(gen, id)` is the corpus's primary key.

```python
CHUNK_SIZE = 256
def chunk_lo(sheep_id: int) -> int:
    return (sheep_id // CHUNK_SIZE) * CHUNK_SIZE
# chunk file (same-origin, served from the pyr3 deploy):
#   /chunks/{gen}/{chunk_lo:05d}.flam3chunk
```

This is a **delivery** granularity, intentionally **independent** of the
corpus's on-disk **storage** bucket (`(id // 10000) * 10000`, see
`layout.py::bucket_for`). Storage buckets are an archival concern; chunks
are a transfer concern. They do not need to match and must not be coupled.

**Why no hash (kills the prior spec's `?s={gen}/{hash10}`):** the corpus
already has a stable integer id; `(gen,id)→file` is deterministic; so a hash
buys nothing and adds a manifest lookup + a ~1.25% birthday-collision
surface. Integer addressing has **zero** collision surface and is
human-legible.

---

## 📦 Chunk wire format

A chunk file contains every present flame whose id is in
`[chunk_lo, chunk_lo + CHUNK_SIZE)`.

- **Container:** brotli-compressed **JSON object** mapping id→XML:
  ```jsonc
  // brotli( JSON.stringify( { "12288": "<flame …>…</flame>", "12290": "…", … } ) )
  ```
  Missing ids (404s, gaps) are simply **absent** from the map.
- **Chosen over** a custom indexed binary (`[magic][ver][count][index][bodies]`)
  and over `tar.br`. JSON-map is the least code on both sides
  (`json.dumps` in Python, `JSON.parse` in TS), debuggable, and JSON's
  escaping overhead (~3–5% pre-compression) is eaten by brotli. The custom
  indexed-binary remains a documented drop-in optimization if profiling
  ever shows `JSON.parse` of a ~5.5 MB string is a bottleneck (it is not
  expected to be).
- **No corpus dictionary on chunks.** The codec spec's brotli dictionary
  exists to give a *cold single-flame* compressor cross-flame context;
  inside a 256-flame chunk that context is already present (brotli's LZ77
  window spans the whole chunk), so a ~108 KB dictionary against a 5.5 MB
  stream is noise. The dictionary is reserved **only** for the future
  single-flame custom form (§11).
- **`CHUNK_SIZE = 256`** is the knee: 172 KB/chunk (one snappy fetch),
  ~650 chunk files total (a fine GH Pages deploy), and 256-wide
  neighbour-caching makes next/prev-sheep browsing an in-memory hit.
- **Chunk version byte:** the JSON object carries a reserved key
  `"_v": 1` (chunk-format version) so a future container change is
  detectable without touching URLs.
- **Filename extension is intentionally opaque** (`.flam3chunk`, *not*
  `.json.br`): this guarantees no static host ever sets
  `Content-Encoding: br` from the extension, which would make the browser
  auto-decode and break our manual brotli decode (the "double-decode trap").
  The FE always fetches **raw bytes** and decodes explicitly.

### FE decode path (pyr3)

```ts
async function inflateChunk(bytes: ArrayBuffer): Promise<Record<string,string>> {
  let stream: ReadableStream;
  if ("DecompressionStream" in globalThis && brotliSupported()) {
    stream = new Response(bytes).body!.pipeThrough(new DecompressionStream("brotli"));
  } else {
    stream = await lazyWasmBrotli(bytes);     // ~200 KB, loaded only on this branch
  }
  const text = await new Response(stream).text();
  return JSON.parse(text);                     // { id: xml, …, "_v": 1 }
}
```
`brotliSupported()` is a one-time feature-detect (try/catch constructing
`new DecompressionStream("brotli")`). Most 2026 users hit the native path
→ ~0 bundle cost.

---

## 🗂️ Availability manifest (sparse-id awareness)

The FE needs to know **which ids exist** in a gen — to render the browse
view (short-term goal #3) and to avoid fetching a 172 KB chunk for a
dead-link click. ES ids are append-only and clustered (long present runs,
occasional 404 gaps), so:

- **Per-gen manifest:** `/chunks/{gen}/avail.flam3idx` — brotli of a
  **sorted delta-varint list of present ids**. ~15–40 KB per gen
  (gen 248, ~40k ids); fetched lazily on first browse/lookup of that gen,
  cached immutably. FE holds it as a sorted array (binary-search existence)
  or a Set.
  - *Acceptable alternative:* a dense **bitmap** over `[0, max_id]`
    (~`max_id/8` bytes raw, brotli'd to ~1–2 KB since runs compress well;
    O(1) existence test). Either is tiny; pick at implementation time.
    Delta-varint is preferred for graceful behaviour as future gens get
    large/sparse.
- This artifact **repurposes** the prior spec's per-gen manifest: it stops
  being a hash→path resolver and becomes a present-id index. (Integrity
  hashes still live in the release `MANIFEST.csv`, not in URLs.)

### `gens.json` (browse landing)

Small, plain (un-brotli'd) JSON at `/chunks/gens.json`, drives `/v1/gen`:

```jsonc
{ "schema": 1, "build_date": "2026-05-28", "chunk_size": 256,
  "gens": [ { "gen": 247, "count": 30000, "min_id": 0, "max_id": 41234 }, … ] }
```

---

## 🚚 Delivery — bake-at-deploy

The chunk layer is generated by ESF and **baked into the pyr3 Pages deploy**
so it serves same-origin, with **no data in either git history**.

**ESF side** — `sheep-fold release-build` gains a step (or a `sheep-fold
chunk` subcommand it calls) that emits a single Release asset:

```text
corpus-chunks-{date}.tar           (members, uncompressed tar — bodies already brotli'd)
├── gens.json
├── 247/avail.flam3idx
├── 247/00000.flam3chunk
├── 247/00256.flam3chunk
│   …
└── 248/…
```

Built into `build/release/`, uploaded as an ordinary asset on the dated
GitHub Release (alongside the existing per-gen zips + `corpus-all-{date}.tar.xz`).
The raw corpus and the existing artifacts are untouched.

**pyr3 side** — the GitHub Pages deploy workflow (Actions →
`upload-pages-artifact`) inserts one step between `npm run build` and the
artifact upload:

```yaml
      - name: Build app
        run: npm ci && npm run build            # → dist/
      - name: Bake in corpus chunks
        run: |
          gh release download "$CHUNK_RELEASE_TAG" \
            --repo MattAltermatt/electric-sheep-fold \
            --pattern 'corpus-chunks-*.tar' --dir /tmp
          mkdir -p dist/chunks
          tar -xf /tmp/corpus-chunks-*.tar -C dist/chunks
        env: { GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with: { path: dist }
```

- **Pin `CHUNK_RELEASE_TAG`** (e.g. `2026-05-28`) so a deploy is
  reproducible; bumping it is the deliberate one-line "ship the new corpus"
  action.
- `gh release download` from another **public** repo with `GITHUB_TOKEN`
  works; ~110 MB download + unpack is seconds. `dist/` total (~110 MB)
  stays far under the GH Pages **1 GB** site cap.

---

## 🧭 Routing — path URLs via the GH Pages 404.html SPA-fallback

GitHub Pages has no server-side router, so real paths resolve via the
standard SPA-fallback: GH Pages serves **`404.html`** for any path that is
not a real file; we make `404.html` a copy of `index.html`, so it boots the
same SPA, which reads `location.pathname` and routes.

```text
deploy step:   cp dist/index.html dist/404.html      (+ touch dist/.nojekyll)
```

- **Real files bypass the fallback.** `/chunks/247/12288.flam3chunk` and
  `/assets/*.js` exist → served directly at HTTP 200. Only unknown paths
  (`/v1/gen/247/id/5`) hit `404.html`. Verified GH Pages behaviour.
- **`.nojekyll`** prevents Jekyll from interfering with the static tree and
  odd extensions.
- The FE router parses `location.pathname` exactly as it would parse a
  query string — the SPA-fallback cost is identical to a query-param shape;
  we choose the path shape for legibility, the browse hierarchy, **and**
  because it preserves the per-flame-preview upgrade path (§12).

### 🚪 The one-way door (why path, not hash)

The share-URL **shape** decides whether per-flame social previews are *ever*
possible — and changing the shape later breaks every link in the wild, so
this is decided up front:

```text
URL shape         GH Pages    per-flame preview ever?      chosen?
                  status
───────────────   ─────────   ──────────────────────────   ───────
#/v1/gen/247/…    200         NEVER — fragment is stripped   no
  (hash)                      before any unfurler bot sees it
/v1/gen/247/id/…  404 *       YES — a worker can serve 200   ✅ YES
  (path)                      + per-flame og:image later
?g=247&i=…        200         YES, but ugly + awkward         no
  (query)                     browse hierarchy
```

\* The 404 *status* is the only interim cost of path routing on bare GH
Pages. It is **invisible to humans using the app**; it only means
deep-link unfurls show no card until the worker phase (§12) — and previews
aren't built yet anyway. The bare `pyr3.app/` (200) still carries a generic
card. **Hash routing was rejected** because the `#fragment` never reaches a
server, permanently foreclosing per-flame previews — the one capability the
user explicitly asked about.

---

## 🔄 Reconciliation with `flame-url-codec-spec.md`

| Prior spec element | Fate |
|---|---|
| `?s={gen}/{hash10}` corpus form | **Replaced** by `/v1/gen/{gen}/id/{id}` (integer addressing, no hash, no manifest). Nothing live to migrate. |
| Per-gen hash manifest `manifest-{gen}.csv.br` | **Repurposed** as the present-id availability manifest (§8). SHA256 stays in release `MANIFEST.csv` for integrity, not in URLs. |
| `?fd=b1:{base64url}` universal form | **Reshaped + deferred** → future `/v1/flame/{token}` (§11). |
| Binary wire format (§"Wire format") | **Kept** as the durable contract for the future custom form; maps cleanly onto pyr3's `Genome`/`Xform`. |
| Brotli corpus dictionary | **Kept, but only** for the single-flame custom form; never applied to chunks. |
| `?flame=v1:` (the only shipped form) | **Kept as legacy** — decode indefinitely. |

---

## 🧬 §11 — Future custom-flame form (long-term, reserved, NOT built now)

Documented so the seam is right. `/v1/flame/{token}` where `{token}` =
base64url of the codec spec's binary schema. Honoring long-term goal #2
("no URL compression unless necessary"):

- **Uncompressed own-schema** is ~1.4–2 KB for a typical flame — *shorter
  than today's `?flame=` gzip-XML* (~2.1 KB), because the binary schema
  already strips XML's structural noise (tag/attr names, whitespace).
  Outlier-large flames ~4–6 KB.
- The binary's first byte (`format_version`) carries a **flag bit** for
  opt-in brotli(+dictionary) — so a user who wants a *tweetable* (~200–400
  char) URL can opt into compression, while the default stays
  uncompressed. No URL-shape change between the two.
- Build this when custom-flame sharing is actually scoped; reserve the
  namespace now.

---

## 🖼️ §12 — Deferred future phase: social previews + visual gallery

**Not in short-term scope. Documented in full so it is not lost.** Both
features share one dependency: **offline-baked thumbnails** (there is no
`$0` way to render a flame → PNG on demand — WebGPU-in-Workers is not
production; a 10 ms edge CPU budget can't render; the original flam3 CPU
render takes seconds/frame).

### Thumbnail bake pipeline
- Render every flame to a small PNG (e.g. 1200×630 for `summary_large_image`,
  + a smaller grid thumb) using **pyr3's existing headless `npm run render`**
  (`bin/pyr3-render.ts`). ~166k renders = hours of batch compute; run
  rarely, store the output.
- **Storage:** ~1–2.5 GB of PNGs **exceeds the GH Pages 1 GB cap** → host on
  **Cloudflare R2** (free 10 GB, `$0` egress). Custom-domain or `r2.dev`.
- Output as a dated artifact (`thumbs-{date}/…`) so it is reproducible.

### Per-flame social previews (the worker)
- A **Cloudflare Worker** ($0 free tier: 100k req/day, 10 ms CPU) sits in
  front of `pyr3.app` and **branches on `User-Agent`**: known unfurler bots
  get a ~1 KB HTML stub with flame-specific `og:`/`twitter:` tags +
  `og:image` → the prebaked R2 thumbnail; humans get the untouched SPA.
- The worker also upgrades path routing to a clean **HTTP 200** (removing
  the 404-status interim cost) and could later host the custom-flame
  short-code redirect (long-term goal #1).
- **Maintenance note:** the bot User-Agent allowlist *rots* — new bots need
  occasional human top-ups. This is the only rotting part of the whole
  system and it lives entirely in this deferred phase.
- *All-Cloudflare alternative:* Cloudflare Pages can host the SPA + chunks +
  run Functions on one platform, replacing GH Pages. Cleaner than
  GH-Pages-plus-bolt-on-worker if previews are adopted, at the cost of
  moving off GitHub. Decide if/when this phase is scoped.

### Visual gallery (`/v1/gen/{gen}`)
- A virtualized grid of the gen's available ids. Two image strategies:
  **(a)** prebaked R2 thumbnails, or **(b)** on-the-fly client-side WebGPU
  render of only-visible cells (~5–30 flames/sec; viable for an interactive
  grid, but useless for unfurlers, which see no canvas).
- The route is **reserved now**; short-term renders a "browse coming soon —
  N flames available" placeholder fed by the availability manifest.

---

## 🧩 Edge cases

- **Animation / multi-frame `.flam3`:** addressed by `/v1/gen/{gen}/id/{id}`
  like any flame; the chunk stores raw XML bytes (frame count invisible to
  the chunk layer). pyr3 renders frame 0 until temporal interpolation ships.
  No special-casing at the addressing or chunk layer.
- **Gens growing (249+):** purely additive — new `gen` value, new chunks,
  new availability manifest, new `gens.json` row. No grammar change, no
  version bump. Orthogonal to ESF's `LIVE_GENS` edit.
- **Missing id inside a present chunk** (e.g. a 404 gap): absent from the
  JSON map; the availability manifest lets the FE know **before** fetching,
  so a dead-link click never costs a 172 KB download. Render a clean "this
  sheep doesn't exist (lost upstream)" state.
- **Id collisions:** impossible — `(gen, id)` is a primary key; no hashing,
  no birthday surface.
- **`CHUNK_SIZE` change:** a `/v1`→`/v2` event (data paths shift). Don't
  change it casually.
- **Content-Encoding double-decode:** prevented by the opaque
  `.flam3chunk` extension + always fetching raw bytes (§6).

---

## ⚠️ Risk register (from the feasibility duel, verified 2026-05-28)

```text
risk                                          conf   mitigation
────────────────────────────────────────────  ─────  ─────────────────────────────────
GH Pages 404 SPA-fallback still works,         High   keep ?flame= legacy as a fallback
 real files bypass it                                 entry; verify with a deploy probe
GH Pages 404 *status* hostile to bots/SEO      High   accepted interim; worker phase (§12)
 on deep links                                        serves 200 + meta
Native brotli decode not in some browser       Med-   feature-detect → lazy ~200 KB wasm
                                               High   fallback (brotli-dec-wasm)
GH Pages 1 GB / 100 GB-mo limits               High   chunks ~110 MB OK; thumbnails MUST
                                                      live on R2, never on Pages
bake-at-deploy cross-repo download             High   GITHUB_TOKEN; pin by tag; ~seconds
no $0 on-demand flame→PNG render               High   bake thumbnails offline (pyr3 render)
thumbnails (1–2.5 GB) exceed Pages cap         High   R2 free tier (deferred phase only)
```

**Cheapest things to prototype first (de-risk before full build):**
1. Feature-detect + one-chunk brotli round-trip in Chrome/Safari/Firefox.
2. Deploy a 404.html SPA-fallback probe: assert `/chunks/.../X.flam3chunk`
   → 200 + bytes, `/v1/gen/247/id/5` → 404 + SPA shell.
3. Bake-at-deploy dry run (`gh release download` an existing ESF asset →
   untar a slice into `dist/`).

---

## 📊 Effort & automation summary

**Short-term build ≈ L** (one focused phase, ~5–10 Claude-sized tasks).
ESF: chunk builder (**M**) + availability manifest (**S**) + `gens.json`
(**XS**) + tests (**S**). pyr3: router (**S–M**) + chunk fetch/decode (**M**)
+ 404.html/.nojekyll (**XS**) + not-found handling (**S**) + `/v1/gen`
landing (**S**) + deploy workflow (**S–M**) + custom domain (**XS–S**,
one-time manual DNS).

**Deferred phase ≈ L–XL**, gated by the thumbnail bake (the only heavy
compute) + worker + R2 + gallery grid.

**Automation:** the recurring corpus-refresh loop is ~hands-off —
`fetch → release-build (auto-builds chunks + manifests + gens.json) → push
Release → pyr3 redeploys (auto-bakes chunks)`. One-time manual: DNS, the
deploy yaml, and (deferred) the Cloudflare/R2 setup. Only the bot allowlist
(deferred phase) rots. Short-term steady state has **zero** rotting parts.

---

## ✅ Short-term scope checklist (what "done" means)

- [ ] ESF: `corpus-chunks-{date}.tar` + per-gen `avail.flam3idx` +
      `gens.json` emitted by `release-build`; tests; docs (CLAUDE.md
      invariants, README, CHANGELOG).
- [ ] pyr3: `/v1/gen/{gen}/id/{id}` loads & renders a corpus flame from a
      baked chunk; `/v1/gen` landing lists gens; `/v1/gen/{gen}` reserved
      placeholder; not-found state; `?flame=v1:` legacy still decodes.
- [ ] pyr3: brotli decode with native + lazy-wasm-fallback; opaque chunk
      extension; raw-bytes fetch.
- [ ] pyr3: GH Pages deploy workflow with bake-at-deploy (pinned tag) +
      `404.html` copy + `.nojekyll`; `pyr3.app` custom domain.
- [ ] Verified live: a real `pyr3.app/v1/gen/247/id/{id}` link opens and
      renders; a missing id shows the not-found state; a deep link's
      neighbour loads instantly (chunk cache).

**Deferred (documented, not built):** per-flame social previews, thumbnail
bake pipeline, Cloudflare worker, R2, the `/v1/gen/{gen}` visual gallery,
the `/v1/flame/{token}` custom form.
