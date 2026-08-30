"""Discovering recipes on disk and reading their headers.

A recipe is a plain ``.sql`` file whose leading comment block carries ``-- Key: value``
metadata. Keeping the metadata inside the SQL comment means a recipe stays one file you
can paste straight into a DuckDB shell, with no sidecar manifest to fall out of sync.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import paths

_HEADER_LINE = re.compile(r"^--\s*([A-Z][A-Za-z -]*?):\s*(.*)$")
_CONTINUATION = re.compile(r"^--\s{2,}(\S.*)$")


@dataclass(frozen=True)
class Recipe:
    """One ``.sql`` file plus whatever its header block declares."""

    name: str
    path: Path
    sql: str
    header: dict[str, str]

    @property
    def question(self) -> str:
        return self.header.get("Question", "(no Question in header)")

    @property
    def pattern(self) -> str:
        return self.header.get("Pattern", "")

    @property
    def benchmark(self) -> str | None:
        return self.header.get("Benchmark")

    @property
    def fixture_path(self) -> Path:
        return paths.fixtures_dir() / f"{self.name}.json"


def parse_header(sql: str) -> dict[str, str]:
    """Read the ``-- Key: value`` block at the top of a recipe.

    Wrapped values continue on following comment lines indented by two or more spaces,
    which is what lets a Question run to a readable length without leaving the header.
    """
    header: dict[str, str] = {}
    current: str | None = None
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("--"):
            break
        if match := _HEADER_LINE.match(stripped):
            current = match.group(1)
            header[current] = match.group(2).strip()
        elif current and (match := _CONTINUATION.match(stripped)):
            header[current] = f"{header[current]} {match.group(1).strip()}".strip()
        else:
            current = None
    return header


def load_recipe(path: Path) -> Recipe:
    sql = path.read_text(encoding="utf-8")
    return Recipe(name=path.stem, path=path, sql=sql, header=parse_header(sql))


def all_recipes() -> list[Recipe]:
    """Every recipe on disk, in filename order."""
    return [load_recipe(p) for p in sorted(paths.recipes_dir().glob("*.sql"))]


def find(name: str) -> Recipe:
    """Look a recipe up by exact name, or by an unambiguous prefix such as ``04``."""
    recipes = all_recipes()
    for recipe in recipes:
        if recipe.name == name:
            return recipe

    matches = [r for r in recipes if r.name.startswith(name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"no recipe matching {name!r}; try `sql-cookbook list`")
    names = ", ".join(r.name for r in matches)
    raise KeyError(f"{name!r} is ambiguous: {names}")
