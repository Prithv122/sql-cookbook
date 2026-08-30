"""Every recipe runs, and returns exactly what its fixture says it should.

Discovery is the point: the parametrisation walks ``recipes/*.sql`` rather than a hand
maintained list, so adding a recipe without a fixture fails the suite instead of
quietly shipping an untested query.
"""

from __future__ import annotations

import pytest

from sqlcookbook import recipes
from sqlcookbook.results import ResultSet, capture, diff

ALL_RECIPES = recipes.all_recipes()
RECIPE_IDS = [r.name for r in ALL_RECIPES]


def test_recipes_were_discovered() -> None:
    """A glob that silently matches nothing would make every test below vacuous."""
    assert len(ALL_RECIPES) >= 12, f"only found {len(ALL_RECIPES)} recipes"


@pytest.mark.parametrize("recipe", ALL_RECIPES, ids=RECIPE_IDS)
def test_recipe_has_a_header(recipe: recipes.Recipe) -> None:
    assert "Question" in recipe.header, f"{recipe.name} has no -- Question: line"
    assert "Pattern" in recipe.header, f"{recipe.name} has no -- Pattern: line"
    assert recipe.question.endswith("?"), f"{recipe.name}'s Question is not a question"


@pytest.mark.parametrize("recipe", ALL_RECIPES, ids=RECIPE_IDS)
def test_recipe_has_a_fixture(recipe: recipes.Recipe) -> None:
    assert recipe.fixture_path.exists(), (
        f"{recipe.name} has no expected-result fixture at {recipe.fixture_path.name}. "
        f"Generate it with `uv run python scripts/refresh_fixtures.py` and review the "
        f"result before committing it."
    )


@pytest.mark.parametrize("recipe", ALL_RECIPES, ids=RECIPE_IDS)
def test_recipe_matches_its_fixture(con, recipe: recipes.Recipe) -> None:
    expected = ResultSet.read(recipe.fixture_path)
    actual = capture(con, recipe.sql)
    assert actual == expected, f"{recipe.name} drifted from its fixture:\n{diff(expected, actual)}"


@pytest.mark.parametrize("recipe", ALL_RECIPES, ids=RECIPE_IDS)
def test_recipe_is_deterministic(con, recipe: recipes.Recipe) -> None:
    """Same query, same data, same rows in the same order -- every time.

    A recipe whose ORDER BY is not total can pass the fixture check by luck. Running it
    repeatedly is a cheap way to catch the obvious cases of that.
    """
    first = capture(con, recipe.sql)
    for _ in range(3):
        assert capture(con, recipe.sql) == first, f"{recipe.name} is not stable across runs"


@pytest.mark.parametrize("recipe", ALL_RECIPES, ids=RECIPE_IDS)
def test_recipe_declares_an_order(recipe: recipes.Recipe) -> None:
    """Fixtures compare row order, so every recipe must actually specify one."""
    assert "ORDER BY" in recipe.sql.upper(), f"{recipe.name} has no ORDER BY"
