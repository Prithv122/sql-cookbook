"""The generator's promises: determinism, referential integrity, and the planted shapes.

Determinism is the load-bearing one. Every fixture in this repo is only meaningful if
the same seed produces the same warehouse, so it is tested directly rather than assumed.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from sqlcookbook import warehouse


def test_same_seed_produces_identical_data() -> None:
    first = warehouse.generate()
    second = warehouse.generate()
    for table in warehouse.TABLES:
        assert getattr(first, table) == getattr(second, table), f"{table} is not deterministic"


def test_a_different_seed_produces_different_data() -> None:
    """Otherwise the seed is not actually wired up to anything."""
    assert warehouse.generate().orders != warehouse.generate(seed=1).orders


def test_row_counts_are_stable() -> None:
    """Pins the numbers the README quotes."""
    assert warehouse.generate().row_counts() == {
        "customers": 400,
        "products": 48,
        "employees": 35,
        "orders": 3000,
        "order_items": 9001,
        "page_events": 12301,
        "subscriptions": 530,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "NULL"),
        (42, "42"),
        (True, "TRUE"),
        (Decimal("19.90"), "19.90"),
        ("plain", "'plain'"),
        ("O'Brien", "'O''Brien'"),
        ("'; DROP TABLE customers; --", "'''; DROP TABLE customers; --'"),
        (dt.date(2026, 4, 1), "DATE '2026-04-01'"),
        (dt.datetime(2026, 4, 1, 9, 30, 15), "TIMESTAMP '2026-04-01 09:30:15'"),
    ],
)
def test_literal_escaping(value: object, expected: str) -> None:
    assert warehouse.literal(value) == expected


def test_literal_rejects_unknown_types() -> None:
    with pytest.raises(TypeError):
        warehouse.literal({"not": "renderable"})


def test_quote_in_a_string_survives_a_round_trip() -> None:
    """The escaper is only worth having if the value comes back out intact."""
    con = warehouse.connect(None)
    con.execute("CREATE TABLE t (v VARCHAR)")
    tricky = "O'Brien'); DROP TABLE t; --"
    con.execute(f"INSERT INTO t VALUES ({warehouse.literal(tricky)})")
    assert con.execute("SELECT v FROM t").fetchall() == [(tricky,)]
    con.close()


def test_parents_first_orders_a_self_referencing_table() -> None:
    rows = [
        (3, "c", "t", 2, None),
        (1, "a", "t", None, None),
        (2, "b", "t", 1, None),
    ]
    batches = warehouse._parents_first(rows)
    assert [[r[0] for r in batch] for batch in batches] == [[1], [2], [3]]


def test_parents_first_rejects_a_cycle() -> None:
    rows = [(1, "a", "t", 2, None), (2, "b", "t", 1, None)]
    with pytest.raises(ValueError, match="cycle or a missing parent"):
        warehouse._parents_first(rows)


def test_every_foreign_key_resolves(con) -> None:
    """DuckDB enforces these on insert; this catches a schema that stopped declaring them."""
    checks = {
        "orders -> customers": """
            SELECT COUNT(*) FROM orders o
            LEFT JOIN customers c USING (customer_id) WHERE c.customer_id IS NULL
        """,
        "order_items -> orders": """
            SELECT COUNT(*) FROM order_items oi
            LEFT JOIN orders o USING (order_id) WHERE o.order_id IS NULL
        """,
        "order_items -> products": """
            SELECT COUNT(*) FROM order_items oi
            LEFT JOIN products p USING (product_id) WHERE p.product_id IS NULL
        """,
        "employees -> employees": """
            SELECT COUNT(*) FROM employees e
            LEFT JOIN employees m ON m.employee_id = e.manager_id
            WHERE e.manager_id IS NOT NULL AND m.employee_id IS NULL
        """,
    }
    for label, sql in checks.items():
        assert con.execute(sql).fetchone()[0] == 0, f"dangling reference: {label}"


def test_the_org_chart_has_one_root_and_four_levels(con) -> None:
    roots = con.execute("SELECT COUNT(*) FROM employees WHERE manager_id IS NULL").fetchone()[0]
    assert roots == 1, "a recursive CTE anchored on manager_id IS NULL needs exactly one root"

    depth = con.execute("""
        WITH RECURSIVE org AS (
            SELECT employee_id, 1 AS depth FROM employees WHERE manager_id IS NULL
            UNION ALL
            SELECT e.employee_id, o.depth + 1
            FROM employees e JOIN org o ON e.manager_id = o.employee_id
        )
        SELECT MAX(depth), COUNT(*) FROM org
    """).fetchone()
    assert depth == (4, 35), "every employee should be reachable from the root, at depth <= 4"


def test_subscriptions_contain_overlaps_abutments_and_lapses(con) -> None:
    """Recipe 08 handles three cases; all three have to be present to be exercised."""
    kinds = con.execute("""
        WITH paired AS (
            SELECT customer_id, period_end,
                   LEAD(period_start) OVER (PARTITION BY customer_id ORDER BY period_start) AS nxt
            FROM subscriptions
        )
        SELECT
            COUNT(*) FILTER (WHERE nxt > period_end)  AS lapses,
            COUNT(*) FILTER (WHERE nxt = period_end)  AS abutments,
            COUNT(*) FILTER (WHERE nxt < period_end)  AS overlaps
        FROM paired WHERE nxt IS NOT NULL
    """).fetchone()
    lapses, abutments, overlaps = kinds
    assert lapses > 0 and abutments > 0 and overlaps > 0, f"missing a case: {kinds}"
