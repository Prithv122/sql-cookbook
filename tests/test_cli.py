"""The documented commands work, including the failure the README tells you to expect."""

from __future__ import annotations

import pytest

from sqlcookbook import recipes
from sqlcookbook.cli import main


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    from sqlcookbook import warehouse

    path = tmp_path_factory.mktemp("warehouse") / "warehouse.duckdb"
    warehouse.build(path)
    return path


def test_list_names_every_recipe(capsys) -> None:
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for recipe in recipes.all_recipes():
        assert recipe.name in out
        assert recipe.question in out


def test_run_reports_rows_and_columns(capsys, database) -> None:
    assert main(["--database", str(database), "run", "04-top-n-per-group"]) == 0
    out = capsys.readouterr().out
    assert "Recipe: 04-top-n-per-group" in out
    assert "Executed successfully" in out
    assert "Rows: 9" in out
    assert "Columns: customer_id, order_id, order_value, value_rank" in out


def test_run_accepts_a_numeric_prefix(capsys, database) -> None:
    assert main(["--database", str(database), "run", "04"]) == 0
    assert "Recipe: 04-top-n-per-group" in capsys.readouterr().out


def test_run_rejects_an_unknown_recipe(capsys, database) -> None:
    assert main(["--database", str(database), "run", "99-nope"]) == 2
    assert "no recipe matching" in capsys.readouterr().err


def test_run_without_a_warehouse_says_how_to_build_one(capsys, tmp_path) -> None:
    assert main(["--database", str(tmp_path / "missing.duckdb"), "run", "01"]) == 2
    assert "sql-cookbook build" in capsys.readouterr().err


def test_build_reports_row_counts(capsys, tmp_path) -> None:
    assert main(["--database", str(tmp_path / "fresh.duckdb"), "build"]) == 0
    out = capsys.readouterr().out
    assert "customers" in out
    assert "12,301" in out


def test_bench_runs_and_reports_identical_results(capsys, database) -> None:
    assert main(["--database", str(database), "bench", "01", "--repeats", "1"]) == 0
    out = capsys.readouterr().out
    assert "01-running-total" in out
    assert "identical" in out
    assert "DIVERGED" not in out


def test_summary_only_omits_the_table(capsys, database) -> None:
    assert main(["--database", str(database), "run", "01", "--summary-only"]) == 0
    out = capsys.readouterr().out
    assert "Rows: 15" in out
    assert "running_total" in out  # still named in the Columns line
    assert "----" not in out  # but no table rule
