# Build Notes — sql-cookbook

Working notes: what broke, what I tried, why X over Y.
Not for recruiters — for me, six months from now, in an interview.

---

## Log

### 2026-08-30 — the loader nearly killed the project

- **Tried:** the obvious thing — `con.executemany("INSERT ... VALUES (?,?,?)", rows)`
  for each of the 7 tables.
- **Broke:** building the 25k-row warehouse took **58 seconds**. Every test run, every
  CLI invocation. Unusable, and it would have made CI miserable.
- **First hypothesis (wrong):** foreign-key enforcement. I had declared FKs on six
  tables and assumed per-row constraint checking was the cost. Measured it three ways —
  PK+FK 73 s, PK only 65 s, no constraints at all 62 s. Constraints accounted for
  ~15% of the time. Not the problem.
- **Second measurement, the useful one:** a trivial `SELECT ?+?` took **2.4 ms**. A
  1M-row `CREATE TABLE AS SELECT ... FROM range(1000000)` took **0.096 s**. So DuckDB's
  engine is fine and the per-statement Python-boundary cost is enormous on this build.
- **Tested four strategies** on the 9,001-row `order_items`:

  | strategy | time |
  |---|---|
  | `executemany` | ~40 s extrapolated (8.6 s for 2,000 rows) |
  | 1000-row parameterised `VALUES` chunks | 50 s |
  | 50-row parameterised chunks | 24 s |
  | one `INSERT` with rendered literals | **0.38 s** |
  | CSV + `COPY` | **0.07 s** |

- **Fixed by:** rendering SQL literals, one `INSERT` per table. Build: 58 s → **1.4 s**.
- **Learned:** the cost is per **parameter bound**, not per statement — which is why
  batching from 1 row to 50 to 1000 barely moved it, and why the chunked version was
  *worse* (binding 5,000 parameters in one statement seems superlinear). That
  distinction is the whole diagnosis, and I only found it because chunking failed to
  help in the way statement-overhead would predict. Preserved as
  `scripts/bench_loader.py` so the claim in the README is reproducible.
- **Not chosen:** CSV + `COPY`, though it is 6× faster still. It drags temp-file
  handling into a library whose tests deliberately run entirely in memory. Wrong trade
  at 25k rows; noted in README §7 as the fix at 100× scale.
- **Also learned:** disabling the sandbox made no difference (72 s), so this is the
  machine/wheel, not the harness. Worth remembering before blaming tooling next time.

### 2026-08-30 — self-referencing FK vs. bulk insert

- **Broke:** switching to one `INSERT` per table immediately failed on `employees` with
  `Violates foreign key constraint because key "employee_id: 1" does not exist`.
- **Why:** DuckDB validates each new row against the table *as it stood before the
  statement*. Row-by-row `executemany` had accidentally been satisfying the
  self-reference because parents happened to be inserted first. One statement removes
  that accident.
- **Fixed by:** `_parents_first()` — split self-referencing rows into batches where each
  batch's parents already exist. Four statements for this org chart. Generic enough to
  be worth keeping, and unit-tested including the cycle case.

### 2026-08-30 — the recipe that demonstrated nothing

- **Broke (silently):** recipe 03 exists to contrast `RANK` / `DENSE_RANK` /
  `ROW_NUMBER`, which differ **only on ties**. My first slice — products in `Audio`
  across all time — had order counts 177, 157, 150, 143, 136, 135. All distinct. All
  three functions returned identical columns. The query ran, the fixture matched, and
  the recipe taught nothing.
- **Caught by:** reading the output. Nothing automated would have flagged it, because
  nothing was asserting the *point* of the recipe.
- **Fixed by:** narrowing to `Audio` in 2026-Q1, where counts are 27, 22, 20, 20, 14, 14
  — two tie groups. Now `RANK` gives 1,2,3,3,5,5 and `DENSE_RANK` gives 1,2,3,3,4,4.
- **Then added a test for it**: `test_ranking_recipe_still_contains_a_tie` fails if the
  slice ever stops producing a tie, or if `RANK` and `DENSE_RANK` ever agree throughout.
  This is the most valuable test in the repo and the one I would not have thought to
  write without hitting the bug.
- **Learned:** a fixture proves a query has not changed. It cannot prove the query was
  ever worth having. Those need different tests.

### 2026-08-30 — benchmark results were less dramatic than expected

- **Expected:** correlated-subquery running totals to be an order of magnitude slower
  than the window version. That is the folklore.
- **Measured:** 1.56×, 1.66×, 2.48×. Much smaller.
- **Why:** `EXPLAIN ANALYZE` shows a `DELIM_JOIN` in every naive plan — DuckDB
  decorrelates the subquery into a join instead of executing it per row. So it never
  goes quadratic here. The remaining gap is extra hash joins and aggregations (naive
  `01`: 3 `HASH_JOIN` + 3 `HASH_GROUP_BY`; optimized: 1 of each + 1 `WINDOW`).
- **Decision:** report the small numbers and explain them, rather than inflate the
  dataset until the folklore comes true. The plans are committed so anyone can check.
  A claim of "100× faster" that a reader could disprove in one command is worse than no
  claim at all.
- **Also:** absolute ms varied ~25% run to run on this laptop, so the README quotes the
  ratio and the observed range, and no timing gates CI.

### 2026-08-30 — small things

- `sqlcookbook run` prints `✓`, which Windows' legacy console code page cannot encode.
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` in `main()`.
- Recipe 11's header wrapped a parenthetical onto the continuation line, so the parsed
  `Question` ended in `)` and `test_recipe_has_a_header` failed. Moved it to `-- Note:`.
  The test was right; the header was wrong.
- `DATE + 1` adds a day in DuckDB and keeps the `DATE` type; `DATE + INTERVAL 1 DAY`
  promotes to `TIMESTAMP`, which would have broken the recursive date spine's type
  consistency between anchor and recursive member. Noted in the recipe.
- `SUM(INTEGER)` returns `HUGEINT` in DuckDB while `COUNT(*)` returns `BIGINT`. The
  benchmark pairs compare column *types*, so both variants cast session numbers and
  ranks to `BIGINT` explicitly. Found by the type comparison, which justified building it.

---

## Rejected approaches

| Approach | Why rejected |
|---|---|
| Naive query as a comment block inside each recipe | Recipes stop being copy-pasteable, and a commented query cannot be executed, so nothing can prove the two spellings agree |
| Generating data with DuckDB `setseed()` + `random()` | Far faster, but DuckDB does not promise RNG stability across versions. Every fixture depends on that stability; Python's `random` documents it |
| CSV + `COPY` for loading | 6× faster than rendered literals, but needs temp files in a library whose tests run in memory. Recorded as the 100×-scale fix instead |
| Asserting speedups in CI | Wall-clock thresholds fail on shared runners for reasons unrelated to the code |
| `DOUBLE` for money | Float formatting is not stable enough for byte-comparable fixtures, and it is wrong for money regardless |
| Full result fixtures for the benchmark queries | 2,485 rows of JSON per benchmark, reviewed by nobody. The pairs are checked against *each other* instead, which is the property that actually matters |

## Open questions

- [ ] Is `DELIM_JOIN` decorrelation guaranteed, or an optimizer heuristic that could
      change between DuckDB versions? If it changed, the benchmark ratios would move
      and the README's explanation would need revisiting. The plans are committed, so
      the check is a diff.
- [ ] Would the recipes survive a Postgres port unchanged? `QUALIFY` (recipes 04, 08)
      and `PIVOT` (10) definitely would not. Worth actually running rather than
      asserting from the docs — the headers currently claim portability from reading,
      not from testing.
