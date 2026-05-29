"""ESF-019: one version, no drift.

The package version is defined ONCE as `electric_sheep_fold.__version__`;
`pyproject.toml` derives it via hatch's dynamic version (no second literal to
drift). The User-Agent carries it (politeness invariant — identifiable client).
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import electric_sheep_fold
from electric_sheep_fold.fetch import USER_AGENT

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_pyproject_version_is_dynamic_single_source():
    pyproj = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    # No static literal in [project] …
    assert "version" not in pyproj["project"]
    # … it's declared dynamic …
    assert "version" in pyproj["project"]["dynamic"]
    # … and sourced from the one place that defines it.
    assert pyproj["tool"]["hatch"]["version"]["path"].endswith("__init__.py")


def test_version_is_well_formed():
    assert re.fullmatch(r"\d+\.\d+\.\d+", electric_sheep_fold.__version__)


def test_user_agent_embeds_version():
    assert f"electric-sheep-fold/{electric_sheep_fold.__version__}" in USER_AGENT
