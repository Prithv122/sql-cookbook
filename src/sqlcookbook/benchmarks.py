"""Timing the naive and optimized spellings of the same question against each other.

Two rules this module exists to enforce. The pair must return *identical* results --
a faster query that answers a slightly different question is not a comparison, and
``tests/test_benchmarks.py`` fails the build if a pair ever diverges. And the timing is
a median over repeated runs after a warmup, because a single run on a cold cache
measures the cache, not the query.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb

from . import paths
from .results import ResultSet, capture

NAIVE_SUFFIX = "-naive.sql"
OPTIMIZED_SUFFIX = "-optimized.sql"

DEFAULT_REPEATS = 7


@dataclass(frozen=True)
class Pair:
    """A naive/optimized pair of ``.sql`` files answering one question."""

    name: str
    naive_path: Path
    optimized_path: Path

    @property
    def naive_sql(self) -> str:
        return self.naive_path.read_text(encoding="utf-8")

    @property
    def optimized_sql(self) -> str:
        return self.optimized_path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class Timing:
    variant: str
    median_ms: float
    min_ms: float
    max_ms: float
    rows: int


@dataclass(frozen=True)
class PairResult:
    name: str
    naive: Timing
    optimized: Timing
    identical: bool

    @property
    def speedup(self) -> float:
        """How many times faster the optimized spelling ran. Below 1.0 means slower."""
        if self.optimized.median_ms == 0:
            return float("inf")
        return self.naive.median_ms / self.optimized.median_ms


def discover() -> list[Pair]:
    """Every complete naive/optimized pair in ``benchmarks/``, in filename order."""
    directory = paths.benchmarks_dir()
    pairs: list[Pair] = []
    for naive_path in sorted(directory.glob(f"*{NAIVE_SUFFIX}")):
        name = naive_path.name[: -len(NAIVE_SUFFIX)]
        optimized_path = directory / f"{name}{OPTIMIZED_SUFFIX}"
        if optimized_path.exists():
            pairs.append(Pair(name=name, naive_path=naive_path, optimized_path=optimized_path))
    return pairs


def find(name: str) -> Pair:
    pairs = discover()
    for pair in pairs:
        if pair.name == name:
            return pair
    matches = [p for p in pairs if p.name.startswith(name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"no benchmark matching {name!r}")
    raise KeyError(f"{name!r} is ambiguous: {', '.join(p.name for p in matches)}")


def time_query(
    con: duckdb.DuckDBPyConnection, sql: str, repeats: int = DEFAULT_REPEATS
) -> list[float]:
    """Run ``sql`` once to warm up, then ``repeats`` more times, returning milliseconds."""
    con.execute(sql).fetchall()
    samples: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        con.execute(sql).fetchall()
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def _timing(con: duckdb.DuckDBPyConnection, variant: str, sql: str, repeats: int) -> Timing:
    samples = time_query(con, sql, repeats)
    rows = len(con.execute(sql).fetchall())
    return Timing(
        variant=variant,
        median_ms=statistics.median(samples),
        min_ms=min(samples),
        max_ms=max(samples),
        rows=rows,
    )


def explain_analyze(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """The profiled plan DuckDB actually executed."""
    rows = con.execute(f"EXPLAIN ANALYZE {sql}").fetchall()
    return "\n".join(str(row[-1]) for row in rows)


def results_agree(con: duckdb.DuckDBPyConnection, pair: Pair) -> tuple[bool, ResultSet, ResultSet]:
    naive = capture(con, pair.naive_sql)
    optimized = capture(con, pair.optimized_sql)
    return naive == optimized, naive, optimized


def run_pair(
    con: duckdb.DuckDBPyConnection,
    pair: Pair,
    repeats: int = DEFAULT_REPEATS,
    save_plans: bool = False,
) -> PairResult:
    identical, _, _ = results_agree(con, pair)
    naive = _timing(con, "naive", pair.naive_sql, repeats)
    optimized = _timing(con, "optimized", pair.optimized_sql, repeats)

    if save_plans:
        directory = paths.plans_dir()
        directory.mkdir(parents=True, exist_ok=True)
        for variant, sql in (("naive", pair.naive_sql), ("optimized", pair.optimized_sql)):
            plan = explain_analyze(con, sql)
            target = directory / f"{pair.name}-{variant}.txt"
            target.write_text(plan + "\n", encoding="utf-8", newline="\n")

    return PairResult(name=pair.name, naive=naive, optimized=optimized, identical=identical)
