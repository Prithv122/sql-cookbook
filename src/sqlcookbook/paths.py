"""Locating the repo's SQL on disk.

The recipes and benchmarks are plain ``.sql`` files at the repo root, not package
data, because a cookbook you cannot open in a text editor is not a cookbook. That
means the package has to find the repo root at runtime: walk up from the current
directory, then fall back to walking up from this file.
"""

from __future__ import annotations

import os
from pathlib import Path

_MARKERS = ("recipes", "benchmarks", "pyproject.toml")


def _looks_like_root(path: Path) -> bool:
    return all((path / marker).exists() for marker in _MARKERS)


def project_root() -> Path:
    """Return the repo root, or raise if it cannot be found."""
    override = os.environ.get("SQL_COOKBOOK_ROOT")
    if override:
        candidate = Path(override).resolve()
        if _looks_like_root(candidate):
            return candidate
        raise FileNotFoundError(f"SQL_COOKBOOK_ROOT={candidate} is not a sql-cookbook checkout")

    for start in (Path.cwd().resolve(), Path(__file__).resolve()):
        for candidate in (start, *start.parents):
            if _looks_like_root(candidate):
                return candidate

    raise FileNotFoundError(
        "could not locate the sql-cookbook checkout; run from inside the repo "
        "or set SQL_COOKBOOK_ROOT"
    )


def recipes_dir() -> Path:
    return project_root() / "recipes"


def benchmarks_dir() -> Path:
    return project_root() / "benchmarks"


def plans_dir() -> Path:
    return benchmarks_dir() / "plans"


def fixtures_dir() -> Path:
    return project_root() / "tests" / "fixtures"


def default_database() -> Path:
    return project_root() / "data" / "warehouse.duckdb"
