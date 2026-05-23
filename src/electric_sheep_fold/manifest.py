"""Persistent sticky-404 skip-set for electric-sheep-fold."""
from __future__ import annotations

import os
from pathlib import Path


class MissingSet:
    """Sorted, deduped set of sheep_ids known to be missing on the server.

    File format: one decimal sheep_id per line, sorted ascending, trailing newline.
    Stored at `corpus/{gen}/missing.txt`. Append-only in spirit — we never
    re-probe an id once it's in here.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._ids: set[int] = set()

    def load(self) -> None:
        """Load IDs from disk. Missing file = empty set (idempotent)."""
        if not self.path.exists():
            self._ids = set()
            return
        with self.path.open("r", encoding="utf-8") as f:
            self._ids = {
                int(line.strip())
                for line in f
                if line.strip()
            }

    def contains(self, sheep_id: int) -> bool:
        return sheep_id in self._ids

    def add(self, sheep_id: int) -> None:
        """Stage sheep_id into the in-memory set. Call save_atomic() to persist."""
        self._ids.add(sheep_id)

    def __len__(self) -> int:
        return len(self._ids)

    def sorted_ids(self) -> list[int]:
        """Return the missing sheep_ids as a sorted ascending list.

        Public seam for callers that need deterministic, ordered iteration
        (release-build manifest rendering, INDEX.md aggregations, etc.).
        Avoids reach-ins on the internal set.
        """
        return sorted(self._ids)

    def save_atomic(self) -> None:
        """Write to disk: tmp file → os.replace. Sorted, deduped, newline-terminated."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for sid in sorted(self._ids):
                f.write(f"{sid}\n")
        os.replace(tmp, self.path)
