"""v0.2 → v0.3 migration: unseal sealed-zip-per-gen → loose-file corpus.

The one-time migration tool. For every gen subdir holding a v0.2-shape
sealed ``NNNNN-NNNNN.zip``:

  1. snapshot zip → ``build/v0.2-snapshot/gen-{N}.zip`` (idempotent on sha256)
  2. extract zip → ``corpus/{gen}/.unseal-tmp/``
  3. verify file count + per-file sha256 against the manifest inside
  4. ``os.replace`` each ``.flam3`` into ``corpus/{gen}/`` (per-file atomic)
  5. ``os.replace`` ``MANIFEST.csv`` into ``corpus/{gen}/`` (audit trail)
  6. commit — delete source zip + ``.unseal-tmp/``, append a row to
     ``corpus/_unseal-verified.json``, delete state marker

Each phase is idempotent. The state marker file ``.unseal-state`` at
``corpus/{gen}/.unseal-state`` carries the source of truth between steps:
``extracted`` / ``verified`` / ``committed``. A resume after SIGKILL
inspects the marker (not the filesystem) to decide where to pick up.

All disk writes are atomic (``.tmp`` + ``os.replace``), including the
marker file itself. Sticky-404 ``missing.txt`` is NEVER overwritten or
reformatted by this tool; it carries through unchanged.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from electric_sheep_fold.manifest import MissingSet

log = logging.getLogger(__name__)

_FLAM3_RE = re.compile(r"^electricsheep\.(\d+)\.(\d{5})\.flam3$")
_SEALED_ZIP_RE = re.compile(r"^\d{5}-\d{5}\.zip$")
_GEN_DIR_RE = re.compile(r"^\d+$")

_STATE_MARKER = ".unseal-state"
_UNSEAL_TMP_DIR = ".unseal-tmp"

_STATE_EXTRACTED = "extracted"
_STATE_VERIFIED = "verified"
_STATE_COMMITTED = "committed"


@dataclass(frozen=True)
class UnsealResult:
    """Outcome of one ``unseal_gen`` call."""

    gen: int
    loose_count: int
    missing_count: int
    source_sha256: str
    snapshot_path: Path
    skipped: bool


# ----- Helpers ---------------------------------------------------------------


def _default_snapshot_root(corpus_root: Path) -> Path:
    """Default snapshot root: ``<repo>/build/v0.2-snapshot/`` next to corpus."""
    return corpus_root.parent / "build" / "v0.2-snapshot"


def _default_verified_log_path(corpus_root: Path) -> Path:
    return corpus_root / "_unseal-verified.json"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write bytes atomically via ``.tmp`` + ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _sha256_of_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _find_sealed_zip(gen_dir: Path) -> Path | None:
    """Return the single sealed-zip path in ``gen_dir`` (or None)."""
    candidates = sorted(
        p for p in gen_dir.glob("?????-?????.zip") if _SEALED_ZIP_RE.match(p.name)
    )
    if not candidates:
        return None
    if len(candidates) > 1:
        raise RuntimeError(
            f"gen {gen_dir.name}: expected one sealed zip, found {len(candidates)}: "
            f"{[p.name for p in candidates]}"
        )
    return candidates[0]


def _read_state(gen_dir: Path) -> str | None:
    marker = gen_dir / _STATE_MARKER
    if not marker.exists():
        return None
    return marker.read_text(encoding="utf-8").strip()


def _write_state(gen_dir: Path, state: str) -> None:
    _atomic_write_text(gen_dir / _STATE_MARKER, state)


def _clear_state(gen_dir: Path) -> None:
    marker = gen_dir / _STATE_MARKER
    if marker.exists():
        marker.unlink()


def _read_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    """Read MANIFEST.csv → list of row dicts. Header row required."""
    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_manifest_rows_from_bytes(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def _load_verified_log(path: Path) -> list[dict[str, object]]:
    """Load the unseal-verified log (list of per-gen records)."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    if not isinstance(loaded, list):
        raise RuntimeError(f"{path}: expected JSON list, got {type(loaded).__name__}")
    return loaded


def _save_verified_log(path: Path, records: list[dict[str, object]]) -> None:
    """Atomic write of the verified log."""
    _atomic_write_text(path, json.dumps(records, indent=2, sort_keys=True) + "\n")


def _append_verified_record(
    path: Path, record: dict[str, object]
) -> None:
    """Append-or-update a per-gen record in the verified log (idempotent)."""
    records = _load_verified_log(path)
    gen = record["gen"]
    records = [r for r in records if r.get("gen") != gen]
    records.append(record)
    records.sort(key=lambda r: int(r["gen"]))
    _save_verified_log(path, records)


# ----- Step (a): snapshot ----------------------------------------------------


def _snapshot_sealed_zip(
    source_zip: Path, snapshot_root: Path, gen: int
) -> tuple[Path, str]:
    """Copy source zip → ``snapshot_root/gen-{N}.zip``; idempotent on sha256.

    Returns (snapshot_path, source_sha256). Raises ``RuntimeError`` if the
    snapshot already exists at a DIFFERENT sha256 (refusing to overwrite a
    prior snapshot that may belong to a different corpus state).
    """
    snapshot_root.mkdir(parents=True, exist_ok=True)
    dest = snapshot_root / f"gen-{gen}.zip"
    source_sha = _sha256_of_file(source_zip)

    if dest.exists():
        existing_sha = _sha256_of_file(dest)
        if existing_sha != source_sha:
            raise RuntimeError(
                f"snapshot sha256 mismatch for gen {gen}: "
                f"{dest} has {existing_sha}, source {source_zip} has {source_sha}. "
                "Refusing to overwrite — investigate whether the existing snapshot "
                "belongs to a different corpus state."
            )
        log.info("snapshot already current: %s", dest)
        return dest, source_sha

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    shutil.copy2(source_zip, tmp)
    os.replace(tmp, dest)
    log.info("snapshotted gen %d: %s → %s", gen, source_zip.name, dest)
    return dest, source_sha


# ----- Step (b): extract -----------------------------------------------------


def _extract_zip_to_tmp(source_zip: Path, tmp_dir: Path) -> int:
    """Extract every member of source_zip → tmp_dir. Returns extracted file count.

    Only ``MANIFEST.csv`` and ``electricsheep.*.flam3`` members are extracted;
    other members (none expected from a v0.2 sealed zip) are skipped.
    Atomic per file: write to ``<name>.tmp`` then ``os.replace``.
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(source_zip, "r") as zf:
        for name in zf.namelist():
            if name != "MANIFEST.csv" and not _FLAM3_RE.match(name):
                log.debug("skipping non-flam3 zip member: %s", name)
                continue
            dest = tmp_dir / name
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            with zf.open(name) as src, tmp.open("wb") as out:
                shutil.copyfileobj(src, out)
            os.replace(tmp, dest)
            count += 1
    return count


# ----- Step (c): verify ------------------------------------------------------


def _verify_unseal_tmp(tmp_dir: Path, gen: int) -> None:
    """Sanity-check ``.unseal-tmp/`` against its own MANIFEST.csv.

    For each MANIFEST row: a ``.flam3`` with that name exists, its file size
    matches the row, and its sha256 matches. The MANIFEST row count must
    equal the count of ``.flam3`` files in the directory. Raises
    ``RuntimeError`` on any divergence; does NOT delete ``.unseal-tmp/``.
    """
    manifest = tmp_dir / "MANIFEST.csv"
    if not manifest.exists():
        raise RuntimeError(f"gen {gen}: MANIFEST.csv missing from {tmp_dir}")

    rows = _read_manifest_rows(manifest)
    flam3_files = sorted(tmp_dir.glob(f"electricsheep.{gen}.*.flam3"))
    if len(rows) != len(flam3_files):
        raise RuntimeError(
            f"gen {gen}: manifest has {len(rows)} rows but {len(flam3_files)} "
            f".flam3 files in {tmp_dir}"
        )

    by_id = {int(r["id"]): r for r in rows}
    for path in flam3_files:
        m = _FLAM3_RE.match(path.name)
        if not m:
            raise RuntimeError(f"gen {gen}: malformed flam3 name {path.name}")
        sheep_id = int(m.group(2))
        if sheep_id not in by_id:
            raise RuntimeError(
                f"gen {gen}: sheep {sheep_id} present on disk but not in MANIFEST.csv"
            )
        row = by_id[sheep_id]
        expected_sha = row["sha256"]
        expected_size = int(row["file_size_bytes"])
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise RuntimeError(
                f"gen {gen}: sheep {sheep_id} size mismatch "
                f"(expected {expected_size}, got {actual_size})"
            )
        actual_sha = _sha256_of_file(path)
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"gen {gen}: sheep {sheep_id} sha256 mismatch "
                f"(expected {expected_sha}, got {actual_sha})"
            )


# ----- Step (d) + (e): atomic move to gen dir --------------------------------


def _move_flam3s_into_gen_dir(tmp_dir: Path, gen_dir: Path, gen: int) -> int:
    """``os.replace`` every flam3 in tmp_dir into gen_dir. Per-file atomic.

    Returns the count of files moved. Idempotent: if a file is already at
    the destination AND not at the source (because a prior crash got
    halfway through step d), it's silently counted as already-moved.
    """
    moved = 0
    for src in sorted(tmp_dir.glob(f"electricsheep.{gen}.*.flam3")):
        dest = gen_dir / src.name
        os.replace(src, dest)
        moved += 1
    return moved


def _move_manifest_into_gen_dir(tmp_dir: Path, gen_dir: Path) -> None:
    """``os.replace`` MANIFEST.csv into gen_dir (preserves audit timestamps)."""
    src = tmp_dir / "MANIFEST.csv"
    dest = gen_dir / "MANIFEST.csv"
    os.replace(src, dest)


# ----- The state machine -----------------------------------------------------


def unseal_gen(
    gen: int,
    corpus_root: Path,
    *,
    snapshot_root: Path | None = None,
    verified_log_path: Path | None = None,
) -> UnsealResult:
    """6-step SIGKILL-safe migration of one gen from v0.2 sealed → v0.3 loose.

    See module docstring for the full state machine. Idempotent and
    resumable: the ``.unseal-state`` marker is the source of truth for
    resume; the filesystem alone is not trusted unless the marker is
    absent (which means either pre-(b) or already-committed).
    """
    if snapshot_root is None:
        snapshot_root = _default_snapshot_root(corpus_root)
    if verified_log_path is None:
        verified_log_path = _default_verified_log_path(corpus_root)

    gen_dir = corpus_root / str(gen)
    if not gen_dir.is_dir():
        raise FileNotFoundError(f"gen dir not found: {gen_dir}")

    tmp_dir = gen_dir / _UNSEAL_TMP_DIR
    source_zip = _find_sealed_zip(gen_dir)
    state = _read_state(gen_dir)

    # ---- Fast-path: already done OR nothing to do --------------------------
    # No source zip + no marker + no tmp dir → either fully committed (step
    # f deletes everything) or never had a sealed zip (fresh-fetched v0.3
    # gen). Both cases mean "nothing to do".
    if source_zip is None and state is None and not tmp_dir.exists():
        # If the verified log already has a record, hand it back.
        records = _load_verified_log(verified_log_path)
        for r in records:
            if r.get("gen") == gen:
                snap = Path(str(r["snapshot_path"]))
                return UnsealResult(
                    gen=gen,
                    loose_count=int(r["loose_count"]),
                    missing_count=int(r["missing_count"]),
                    source_sha256=str(r["source_sha256"]),
                    snapshot_path=snap,
                    skipped=True,
                )
        # Never sealed in the first place — also a no-op skip.
        return UnsealResult(
            gen=gen,
            loose_count=0,
            missing_count=0,
            source_sha256="",
            snapshot_path=snapshot_root / f"gen-{gen}.zip",
            skipped=True,
        )

    # ---- Pre-(b) crash recovery -------------------------------------------
    # `.unseal-tmp/` exists but no marker → step (b) crashed mid-extract.
    # Nuke and restart from step (a).
    if tmp_dir.exists() and state is None:
        log.warning(
            "gen %d: pre-state .unseal-tmp/ found; treating as pre-extract crash, "
            "removing and restarting",
            gen,
        )
        shutil.rmtree(tmp_dir)

    # ---- Step (a): snapshot ----------------------------------------------
    # Always run; idempotent on sha256. Requires a source zip to exist.
    if source_zip is None:
        raise RuntimeError(
            f"gen {gen}: no sealed zip to unseal in {gen_dir}, but state marker "
            f"reports {state!r}. Inconsistent — bailing rather than guessing."
        )

    snapshot_path, source_sha = _snapshot_sealed_zip(source_zip, snapshot_root, gen)

    # ---- Step (b): extract -----------------------------------------------
    # If we have an `extracted` marker AND a tmp dir AND its file count
    # matches the source-zip member count, skip step (b). Otherwise:
    # nuke any partial tmp dir and re-extract. The "partial fine; just
    # continue" alternative is rejected — step (c) verifies sha256 anyway,
    # but re-extracting is cheap and removes a class of subtle bugs
    # (truncated `.tmp` files left mid-write, etc.).
    state = _read_state(gen_dir)
    need_extract = True
    if state == _STATE_EXTRACTED and tmp_dir.exists():
        # Compare tmp-dir file count vs source-zip member count.
        with zipfile.ZipFile(source_zip, "r") as zf:
            expected_members = sum(
                1 for n in zf.namelist()
                if n == "MANIFEST.csv" or _FLAM3_RE.match(n)
            )
        actual = sum(
            1 for p in tmp_dir.iterdir()
            if p.is_file() and (p.name == "MANIFEST.csv" or _FLAM3_RE.match(p.name))
        )
        if actual == expected_members:
            log.info(
                "gen %d: extracted-state marker matches; skipping re-extract", gen
            )
            need_extract = False
        else:
            log.warning(
                "gen %d: extracted-state marker but partial tmp dir (%d/%d files); "
                "nuking and re-extracting",
                gen, actual, expected_members,
            )

    if need_extract and state in (None, _STATE_EXTRACTED):
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        _extract_zip_to_tmp(source_zip, tmp_dir)
        _write_state(gen_dir, _STATE_EXTRACTED)
        state = _STATE_EXTRACTED

    # ---- Step (c): verify ------------------------------------------------
    if state == _STATE_EXTRACTED:
        _verify_unseal_tmp(tmp_dir, gen)
        _write_state(gen_dir, _STATE_VERIFIED)
        state = _STATE_VERIFIED

    # ---- Step (d): atomic-move flam3s ------------------------------------
    # State stays VERIFIED across step (d) — partial completion is fine
    # because step (d) is per-file atomic and re-runnable (already-moved
    # files have no source to move from).
    if state == _STATE_VERIFIED:
        # Read manifest BEFORE moving — once we move MANIFEST.csv in step
        # (e) we lose access to row data for the loose_count.
        manifest_rows = _read_manifest_rows(tmp_dir / "MANIFEST.csv")
        _move_flam3s_into_gen_dir(tmp_dir, gen_dir, gen)

        # ---- Step (e): audit MANIFEST.csv ---------------------------------
        _move_manifest_into_gen_dir(tmp_dir, gen_dir)
        _write_state(gen_dir, _STATE_COMMITTED)
        state = _STATE_COMMITTED
    else:
        manifest_rows = _read_manifest_rows(gen_dir / "MANIFEST.csv")

    # ---- Step (f): commit cleanup ----------------------------------------
    if state == _STATE_COMMITTED:
        # Source zip + tmp dir both deletable. Both idempotent.
        if source_zip.exists():
            source_zip.unlink()
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)

        # Counts.
        loose_count = sum(
            1 for _ in gen_dir.glob(f"electricsheep.{gen}.*.flam3")
        )
        ms = MissingSet(gen_dir / "missing.txt")
        ms.load()
        missing_count = len(ms)

        # Sanity: loose count should match manifest row count (we just
        # moved them all in). If it doesn't, something's gone wrong; fail
        # loud rather than write a misleading audit row.
        if loose_count != len(manifest_rows):
            raise RuntimeError(
                f"gen {gen}: post-move loose count {loose_count} does not match "
                f"manifest row count {len(manifest_rows)}"
            )

        record = {
            "gen": gen,
            "loose_count": loose_count,
            "missing_count": missing_count,
            "source_sha256": source_sha,
            "snapshot_path": str(snapshot_path),
            "unsealed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        _append_verified_record(verified_log_path, record)
        _clear_state(gen_dir)

        return UnsealResult(
            gen=gen,
            loose_count=loose_count,
            missing_count=missing_count,
            source_sha256=source_sha,
            snapshot_path=snapshot_path,
            skipped=False,
        )

    # Unreachable: state must be COMMITTED here, but guard anyway.
    raise RuntimeError(f"gen {gen}: unseal state machine ended in state {state!r}")


def unseal_all(
    corpus_root: Path,
    *,
    snapshot_root: Path | None = None,
    verified_log_path: Path | None = None,
) -> list[UnsealResult]:
    """Iterate every numeric gen subdir and ``unseal_gen`` each.

    Skips ``_index``, ``_live-fetch-logs``, and other underscore-prefixed
    metadata dirs. Order: ascending gen number.
    """
    if not corpus_root.is_dir():
        raise FileNotFoundError(f"corpus root not found: {corpus_root}")
    gens = sorted(
        int(p.name)
        for p in corpus_root.iterdir()
        if p.is_dir() and _GEN_DIR_RE.match(p.name)
    )
    results: list[UnsealResult] = []
    for gen in gens:
        results.append(
            unseal_gen(
                gen,
                corpus_root,
                snapshot_root=snapshot_root,
                verified_log_path=verified_log_path,
            )
        )
    return results


# ----- Consistency check (daemon-resume guard) -------------------------------


def verify_unseal_consistency(
    corpus_root: Path,
    *,
    verified_log_path: Path | None = None,
) -> list[tuple[int, str]]:
    """Compare current on-disk gen state to the verified-log baseline.

    For each gen recorded in ``_unseal-verified.json``, asserts that
    ``len(glob(*.flam3)) + len(missing) == loose_count + missing_count``.
    Returns a list of (gen, reason) for divergences; empty list means all
    gens are consistent with their post-unseal baseline.

    Used by ``fetch-all`` startup as a daemon-resume guard against silent
    re-fetch of previously-known ids (e.g. if a gen's ``missing.txt`` was
    overwritten between sessions).
    """
    if verified_log_path is None:
        verified_log_path = _default_verified_log_path(corpus_root)
    records = _load_verified_log(verified_log_path)
    divergences: list[tuple[int, str]] = []

    for r in records:
        gen = int(r["gen"])
        expected_loose = int(r["loose_count"])
        expected_missing = int(r["missing_count"])
        gen_dir = corpus_root / str(gen)
        if not gen_dir.is_dir():
            divergences.append((gen, f"gen dir missing: {gen_dir}"))
            continue
        actual_loose = sum(
            1 for _ in gen_dir.glob(f"electricsheep.{gen}.*.flam3")
        )
        ms = MissingSet(gen_dir / "missing.txt")
        ms.load()
        actual_missing = len(ms)
        # Live gens (247, 248) grow over time, so loose count can be >=
        # baseline; only DROPS indicate corruption. Missing count is
        # similarly append-only. The invariant we actually check is
        # "total accounted-for ids did not shrink".
        actual_total = actual_loose + actual_missing
        expected_total = expected_loose + expected_missing
        if actual_total < expected_total:
            divergences.append((
                gen,
                f"id count drift: have {actual_loose} loose + {actual_missing} "
                f"missing = {actual_total}; expected at least "
                f"{expected_loose} + {expected_missing} = {expected_total}",
            ))

    return divergences
