# sql-cookbook — F1

**Tier:** 2 · **Category:** F — Querying & analysis · **Wave:** 1

Root rules in `../GUIDELINES.md` apply. This file is project-specific only — keep it under 40 lines.

## What this is

A tested cookbook of advanced SQL patterns — window functions, recursive CTEs,
gaps-and-islands, sessionization, pivots — against a synthetic but realistic DuckDB
warehouse. Every recipe is a `.sql` file with an expected-result fixture, executed by
pytest, so a broken query fails CI instead of quietly returning wrong rows.

## Stack

Python 3.13 · DuckDB (embedded, no server) · pytest · ruff · uv · GitHub Actions.

## Acceptance criteria

- [x] Recipes cover: window functions, recursive CTEs, gaps-and-islands, sessionization, pivots
- [x] Every recipe is runnable AND tested — expected results asserted, not eyeballed
- [x] Seeded, deterministic synthetic dataset built by a script in the repo
- [x] CLI runs any recipe against the warehouse and prints the result
- [x] Ship gate passes

## Project-specific notes

- No external service, no account, no env vars — DuckDB is an in-process library and the
  dataset is generated locally from a fixed seed. `.env.example` deliberately deleted.
- Dataset is **synthetic**. Any number in the README must say so.
- Local pytest needs `--basetemp=<scratchpad>/pt` (sandbox blocks `%TEMP%`). Never in `pyproject.toml`.
- The loader renders SQL literals rather than binding parameters — deliberate, measured,
  ~85x faster per row on this machine. See NOTES.md before "fixing" it.
