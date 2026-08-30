"""Why the loader renders SQL literals instead of binding parameters.

The obvious way to load generated rows into DuckDB is ``executemany`` with placeholders.
On this machine that is pathologically slow -- slow enough that building the warehouse
dominated the test suite -- and the cost turns out to be per *parameter bound*, not per
statement, so batching the inserts does not help. Rendering the same rows into one
``INSERT ... VALUES`` statement per table sidesteps binding entirely.

This script measures all three on one real table so the claim in the README is
reproducible rather than remembered.

    uv run python scripts/bench_loader.py
"""

from __future__ import annotations

import time

import duckdb

from sqlcookbook import warehouse

DDL = "CREATE TABLE t (a INTEGER, b INTEGER, c INTEGER, d INTEGER, e DECIMAL(10,2))"
CHUNK = 50


def _fresh() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(DDL)
    return con


def time_executemany(rows: list[tuple], limit: int) -> tuple[float, int]:
    con = _fresh()
    sample = rows[:limit]
    start = time.perf_counter()
    con.executemany("INSERT INTO t VALUES (?, ?, ?, ?, ?)", sample)
    elapsed = time.perf_counter() - start
    con.close()
    return elapsed, len(sample)


def time_chunked_parameters(rows: list[tuple], limit: int) -> tuple[float, int]:
    con = _fresh()
    sample = rows[:limit]
    start = time.perf_counter()
    for i in range(0, len(sample), CHUNK):
        chunk = sample[i : i + CHUNK]
        placeholders = ",".join(["(?,?,?,?,?)"] * len(chunk))
        con.execute(f"INSERT INTO t VALUES {placeholders}", [v for row in chunk for v in row])
    elapsed = time.perf_counter() - start
    con.close()
    return elapsed, len(sample)


def time_rendered_literals(rows: list[tuple]) -> tuple[float, int]:
    con = _fresh()
    start = time.perf_counter()
    con.execute(warehouse._insert_statement("t", rows))
    elapsed = time.perf_counter() - start
    con.close()
    return elapsed, len(rows)


def main() -> int:
    rows = warehouse.generate().order_items
    # The parameterised strategies are measured on a subset; at full size they take
    # long enough to be tedious, and the per-row cost is already flat by 2000 rows.
    subset = 2000

    print(f"order_items: {len(rows):,} rows, DuckDB {duckdb.__version__}\n")
    print(f"{'strategy':<34}{'rows':>8}{'seconds':>10}{'us/row':>10}")
    print("-" * 62)

    for label, (elapsed, n) in (
        ("executemany, one row at a time", time_executemany(rows, subset)),
        (f"parameterised, {CHUNK}-row batches", time_chunked_parameters(rows, subset)),
        ("rendered literals, one statement", time_rendered_literals(rows)),
    ):
        print(f"{label:<34}{n:>8,}{elapsed:>10.2f}{elapsed / n * 1e6:>10.0f}")

    print("\nThe per-row cost barely moves between the first two: the expense is binding")
    print("each parameter, not issuing each statement, so batching does not help.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
