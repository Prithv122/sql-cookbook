"""The benchmark pairs must answer the same question, or the comparison is meaningless.

No timing is asserted here. Wall-clock thresholds in CI fail on a noisy runner and tell
you nothing about the code, so speed is reported by ``sql-cookbook bench`` and recorded
in the README with the conditions attached; only correctness gates the build.
"""

from __future__ import annotations

import pytest

from sqlcookbook import benchmarks
from sqlcookbook.results import capture, diff

ALL_PAIRS = benchmarks.discover()
PAIR_IDS = [p.name for p in ALL_PAIRS]


def test_pairs_were_discovered() -> None:
    assert len(ALL_PAIRS) >= 3, f"only found {len(ALL_PAIRS)} benchmark pairs"


def test_every_benchmark_file_belongs_to_a_pair() -> None:
    """An orphaned -naive.sql with no -optimized.sql would never be run or compared."""
    from sqlcookbook import paths

    files = {p.name for p in paths.benchmarks_dir().glob("*.sql")}
    paired = {f"{p.name}{suffix}" for p in ALL_PAIRS for suffix in ("-naive.sql", "-optimized.sql")}
    assert files == paired, f"unpaired benchmark files: {sorted(files ^ paired)}"


@pytest.mark.parametrize("pair", ALL_PAIRS, ids=PAIR_IDS)
def test_naive_and_optimized_return_identical_results(con, pair: benchmarks.Pair) -> None:
    naive = capture(con, pair.naive_sql)
    optimized = capture(con, pair.optimized_sql)
    assert naive == optimized, (
        f"{pair.name}: the two spellings disagree, so any timing comparison between "
        f"them is meaningless.\n{diff(optimized, naive)}"
    )


@pytest.mark.parametrize("pair", ALL_PAIRS, ids=PAIR_IDS)
def test_benchmark_pairs_return_a_useful_number_of_rows(con, pair: benchmarks.Pair) -> None:
    """Benchmarks run over the full warehouse; a sample filter here would defeat them."""
    optimized = capture(con, pair.optimized_sql)
    assert len(optimized.rows) > 500, (
        f"{pair.name} returns only {len(optimized.rows)} rows -- too small to time"
    )


@pytest.mark.parametrize("pair", ALL_PAIRS, ids=PAIR_IDS)
def test_optimized_variant_uses_a_window_function(pair: benchmarks.Pair) -> None:
    """And the naive one must not -- otherwise the pair is not contrasting anything."""
    assert "OVER (" in pair.optimized_sql, f"{pair.name}-optimized has no window function"
    assert "OVER (" not in pair.naive_sql, f"{pair.name}-naive uses a window function"
