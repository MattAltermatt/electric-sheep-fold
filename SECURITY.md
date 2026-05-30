# Security Policy

`electric-sheep-fold` is an archival toolchain (`sheep-fold`) plus the preserved
Electric Sheep `.flam3` corpus. Its attack surface is small but real: it makes
outbound HTTP requests to third-party servers and parses untrusted XML from them.

## Supported versions

Releases are corpus snapshots tagged by ISO build date (`YYYY-MM-DD`), not semver.
**Only the latest release** (and `main`) receives security fixes — older snapshots
are immutable historical archives.

## Reporting a vulnerability

Please report security issues **privately** via GitHub's
[Private Vulnerability Reporting](https://github.com/MattAltermatt/electric-sheep-fold/security/advisories/new)
("Report a vulnerability" under the repository's **Security** tab). Do **not** open
a public issue for a vulnerability.

You can expect an initial acknowledgement within a reasonable window for a
single-maintainer project. Fixes ship on `main` and in the next dated release.

## Known trust boundaries

These are documented, deliberate properties of the design — not undisclosed bugs:

- **Plaintext-HTTP live source (ESF-027).** The live sheep server is fetched over
  **`http://v3d0.sheepserver.net`** (a 2010-era lighttpd with no TLS). Fetched
  genome bytes are therefore **unauthenticated** — an on-path attacker could
  substitute content that then enters the preserved corpus. This is largely
  unavoidable (the upstream offers no TLS or signatures) and is mitigated by:
  - parsing all network XML with `defusedxml` (no entity/DTD/external expansion),
  - never executing fetched content (it is inert genome XML), and
  - treating any non-flam3 `200` body as a transient error, never writing it.
  The static archive (`electricsheep.com`) is fetched over HTTPS.
- **Corpus data is third-party content.** `.flam3` genomes are crowdsourced
  Electric Sheep submissions under the project's CC license; treat them as
  untrusted input to any downstream renderer.

## Dependencies

The dependency graph is pinned in `uv.lock` (hash-verified) and monitored by
Dependabot. The runtime footprint is intentionally small (`httpx`, `typer`,
`brotli`, `defusedxml`).
