"""Tests for electric_sheep_fold.manifest — MissingSet round-trips."""
from pathlib import Path

from electric_sheep_fold.manifest import MissingSet


def test_load_empty_when_file_absent(tmp_path: Path):
    ms = MissingSet(tmp_path / "missing.txt")
    ms.load()
    assert len(ms) == 0
    assert not ms.contains(42)


def test_add_then_contains(tmp_path: Path):
    ms = MissingSet(tmp_path / "missing.txt")
    ms.add(102)
    assert ms.contains(102)
    assert not ms.contains(103)


def test_save_atomic_creates_file(tmp_path: Path):
    path = tmp_path / "missing.txt"
    ms = MissingSet(path)
    ms.add(102)
    ms.save_atomic()
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "102\n"


def test_save_sorted_and_deduped(tmp_path: Path):
    path = tmp_path / "missing.txt"
    ms = MissingSet(path)
    ms.add(207)
    ms.add(105)
    ms.add(102)
    ms.add(105)  # dup
    ms.save_atomic()
    assert path.read_text(encoding="utf-8") == "102\n105\n207\n"


def test_round_trip(tmp_path: Path):
    path = tmp_path / "missing.txt"
    ms = MissingSet(path)
    ms.add(1)
    ms.add(42)
    ms.add(999)
    ms.save_atomic()

    ms2 = MissingSet(path)
    ms2.load()
    assert ms2.contains(1)
    assert ms2.contains(42)
    assert ms2.contains(999)
    assert not ms2.contains(2)
    assert len(ms2) == 3


def test_save_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "248" / "missing.txt"
    ms = MissingSet(path)
    ms.add(1)
    ms.save_atomic()
    assert path.exists()


def test_load_ignores_blank_lines(tmp_path: Path):
    path = tmp_path / "missing.txt"
    path.write_text("102\n\n105\n", encoding="utf-8")
    ms = MissingSet(path)
    ms.load()
    assert ms.contains(102)
    assert ms.contains(105)
    assert len(ms) == 2


def test_no_tmp_left_behind(tmp_path: Path):
    path = tmp_path / "missing.txt"
    ms = MissingSet(path)
    ms.add(1)
    ms.save_atomic()
    tmp = path.with_suffix(path.suffix + ".tmp")
    assert not tmp.exists()


def test_accumulate_across_sessions(tmp_path: Path):
    """Pre-existing missing.txt + new adds should accumulate, not replace."""
    path = tmp_path / "missing.txt"

    # Session 1: seed two ids
    ms1 = MissingSet(path)
    ms1.add(10)
    ms1.add(20)
    ms1.save_atomic()

    # Session 2: load prior state, add one more, save
    ms2 = MissingSet(path)
    ms2.load()
    ms2.add(30)
    ms2.save_atomic()

    # Verify all three survive
    ms3 = MissingSet(path)
    ms3.load()
    assert ms3.contains(10)
    assert ms3.contains(20)
    assert ms3.contains(30)
    assert len(ms3) == 3
