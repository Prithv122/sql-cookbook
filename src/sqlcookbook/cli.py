"""Console entry point: list, run, build, bench."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import benchmarks, paths, recipes, warehouse
from .results import ResultSet, capture


def _stdout_utf8() -> None:
    """Windows consoles still default to a legacy code page that cannot encode U+2713."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _render_table(result: ResultSet, max_rows: int) -> str:
    header = result.column_names
    shown = [[("" if v is None else str(v)) for v in row] for row in result.rows[:max_rows]]
    widths = [len(name) for name in header]
    for row in shown:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    lines = [
        "  ".join(name.ljust(widths[i]) for i, name in enumerate(header)),
        "  ".join("-" * w for w in widths),
    ]
    lines += ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in shown]
    if len(result.rows) > max_rows:
        lines.append(f"... {len(result.rows) - max_rows} more rows (--max-rows to show more)")
    return "\n".join(lines)


def _require_database(path: Path) -> int | None:
    if path.exists():
        return None
    print(f"No warehouse at {path}.", file=sys.stderr)
    print("Build it first:  uv run sql-cookbook build", file=sys.stderr)
    return 2


def cmd_list(args: argparse.Namespace) -> int:
    for recipe in recipes.all_recipes():
        print(f"{recipe.name}\n    {recipe.question}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    database = Path(args.database)
    counts = warehouse.build(database, seed=args.seed)
    print(f"Built {database} (seed {args.seed})")
    for table, count in counts.items():
        print(f"  {table:<15} {count:>6,} rows")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    database = Path(args.database)
    if code := _require_database(database):
        return code

    recipe = recipes.find(args.recipe)
    with warehouse.connect(database) as con:
        result = capture(con, recipe.sql)

    print(f"Recipe: {recipe.name}")
    print(f"Question: {recipe.question}")
    print()
    print("✓ Executed successfully")
    print(f"Rows: {len(result.rows)}")
    print(f"Columns: {', '.join(result.column_names)}")
    if result.rows and not args.summary_only:
        print()
        print(_render_table(result, args.max_rows))
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    database = Path(args.database)
    if code := _require_database(database):
        return code

    pairs = [benchmarks.find(args.pair)] if args.pair else benchmarks.discover()
    if not pairs:
        print("No benchmark pairs found.", file=sys.stderr)
        return 1

    with warehouse.connect(database) as con:
        outcomes = [benchmarks.run_pair(con, p, args.repeats, args.save_plans) for p in pairs]

    print(f"Median of {args.repeats} runs after one warmup, on {database}.")
    print()
    print(f"{'benchmark':<24}{'naive':>12}{'optimized':>12}{'speedup':>10}{'rows':>8}  results")
    print("-" * 76)
    for outcome in outcomes:
        print(
            f"{outcome.name:<24}"
            f"{outcome.naive.median_ms:>9.1f} ms"
            f"{outcome.optimized.median_ms:>9.1f} ms"
            f"{outcome.speedup:>9.2f}x"
            f"{outcome.optimized.rows:>8,}"
            f"  {'identical' if outcome.identical else 'DIVERGED'}"
        )

    if args.save_plans:
        print(f"\nEXPLAIN ANALYZE plans written to {paths.plans_dir()}")
    return 0 if all(o.identical for o in outcomes) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sql-cookbook",
        description="Run and benchmark the SQL recipes against the synthetic DuckDB warehouse.",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="path to the DuckDB file (default: data/warehouse.duckdb)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list every recipe and the question it answers")
    p_list.set_defaults(func=cmd_list)

    p_build = sub.add_parser("build", help="(re)build the synthetic warehouse from the seed")
    p_build.add_argument("--seed", type=int, default=warehouse.SEED)
    p_build.set_defaults(func=cmd_build)

    p_run = sub.add_parser("run", help="run one recipe by name or unambiguous prefix")
    p_run.add_argument("recipe")
    p_run.add_argument("--max-rows", type=int, default=50)
    p_run.add_argument("--summary-only", action="store_true", help="omit the result table")
    p_run.set_defaults(func=cmd_run)

    p_bench = sub.add_parser("bench", help="time the naive/optimized benchmark pairs")
    p_bench.add_argument("pair", nargs="?", help="one pair name; default is all of them")
    p_bench.add_argument("--repeats", type=int, default=benchmarks.DEFAULT_REPEATS)
    p_bench.add_argument(
        "--save-plans",
        action="store_true",
        help="write EXPLAIN ANALYZE output to benchmarks/plans/",
    )
    p_bench.set_defaults(func=cmd_bench)

    return parser


def main(argv: list[str] | None = None) -> int:
    _stdout_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.database is None:
        args.database = paths.default_database()
    try:
        return int(args.func(args))
    except (KeyError, FileNotFoundError) as exc:
        print(str(exc).strip("'"), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
