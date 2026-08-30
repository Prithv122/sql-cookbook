"""Regenerate the expected-result fixtures under tests/fixtures/.

Run this only when a recipe's output is *meant* to change, and read the diff before
committing it. A fixture regenerated from the same query it is meant to check proves
nothing on its own -- that is why the load-bearing recipes are also verified against
independent Python implementations in tests/test_semantics.py.

    uv run python scripts/refresh_fixtures.py            # all recipes
    uv run python scripts/refresh_fixtures.py 03 07      # just these
"""

from __future__ import annotations

import sys

from sqlcookbook import paths, recipes, warehouse
from sqlcookbook.results import ResultSet, capture


def main(argv: list[str]) -> int:
    wanted = argv or None
    selected = [recipes.find(name) for name in wanted] if wanted else recipes.all_recipes()

    fixtures = paths.fixtures_dir()
    fixtures.mkdir(parents=True, exist_ok=True)

    con = warehouse.in_memory()
    try:
        for recipe in selected:
            result = capture(con, recipe.sql)
            target = recipe.fixture_path
            previous = ResultSet.read(target) if target.exists() else None
            result.write(target)
            if previous is None:
                status = "created"
            elif previous == result:
                status = "unchanged"
            else:
                status = "CHANGED -- review the diff"
            print(f"{recipe.name:<40} {len(result.rows):>4} rows  {status}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
