# Resume Bullets — sql-cookbook

Form: **action → technical specifics → measured outcome.** Numbers or it doesn't go on the resume.

---

## Bullets

- Built a tested SQL pattern library — 12 analytical recipes (window functions,
  recursive CTEs, gaps-and-islands, 30-minute sessionization, `PIVOT` vs. portable
  conditional aggregation) over a seeded 25k-row DuckDB warehouse — where each query is
  pinned to a frozen expected result including column types and the load-bearing ones
  are independently re-implemented in Python and diffed, giving 107 tests at 90%
  coverage in 13.6 s and catching a ranking recipe whose data slice contained no ties
  and therefore demonstrated nothing.

- Profiled correlated-subquery vs. window-function spellings of the same three queries
  as separate executable files with committed `EXPLAIN ANALYZE` plans, measuring
  1.56–2.48× speedups (median of 15 runs) and tracing the smaller-than-expected gap to
  DuckDB's `DELIM_JOIN` decorrelation; separately diagnosed a 58 s warehouse build as
  per-parameter bind cost rather than the assumed FK enforcement, cutting it to 1.4 s
  (~85× per row) by rendering SQL literals.

## Which roles this supports

- [ ] Data Scientist / ML
- [ ] AI Engineer (LLM/NLP/CV)
- [x] Data Engineer
- [x] Data Analyst / Python Developer

## Keywords this project earns

SQL (window functions, `RANK`/`DENSE_RANK`/`ROW_NUMBER`, recursive CTEs, `QUALIFY`,
frame clauses, correlated subqueries, gaps-and-islands, sessionization, pivoting) ·
DuckDB · query plan reading (`EXPLAIN ANALYZE`, decorrelation, hash joins) · benchmark
methodology (warmup, median-of-N, variance reporting) · deterministic synthetic data
generation · pytest (parametrised discovery, fixtures, property tests) · Python 3.13 ·
uv · ruff · GitHub Actions CI.

---

### Bad vs good

❌ "Wrote advanced SQL queries using window functions and CTEs in DuckDB."
✅ The bullets above: they name the failure mode being defended against (queries that
keep running while returning wrong rows), the mechanism (frozen typed fixtures plus
independent Python re-implementation), and a measured outcome — including a bug the
method actually caught. The first invites "so what?"; these invite "how did the tie
thing fail?", which is a question with a good answer.
