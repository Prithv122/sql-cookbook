"""Independent checks that the recipes compute what they claim.

A fixture proves a query has not *changed*. It cannot prove the query was ever right,
because the fixture was generated from that same query -- freeze a bug and the bug
passes forever. So the load-bearing recipes are re-implemented here in plain Python,
from the base tables, and the two answers are compared. Where re-implementation is not
meaningful, the check is a property the recipe must have instead: that recipe 10 and 11
agree, that recipe 03 still contains a tie, that recipe 12's ordering is total.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlcookbook import recipes, warehouse
from sqlcookbook.results import capture

SESSION_GAP_SECONDS = int(warehouse.SESSION_GAP.total_seconds())


def _rows(con, sql: str) -> list[tuple]:
    return con.execute(sql).fetchall()


def test_running_total_matches_a_python_cumulative_sum(con) -> None:
    """Recipe 01's window is checked against an accumulator written by hand."""
    per_order = _rows(
        con,
        """
        SELECT o.customer_id, o.order_id, CAST(o.order_ts AS DATE) AS order_date,
               SUM(oi.quantity * oi.unit_price) AS order_value
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.status = 'completed'
        GROUP BY o.customer_id, o.order_id, o.order_ts
        """,
    )
    counts: dict[int, int] = defaultdict(int)
    for customer_id, *_ in per_order:
        counts[customer_id] += 1
    sampled = sorted(c for c, n in counts.items() if 5 <= n <= 7)[:3]

    expected: list[tuple] = []
    for customer_id in sampled:
        running = Decimal("0.00")
        rows = sorted(
            (r for r in per_order if r[0] == customer_id),
            key=lambda r: (r[2], r[1]),
        )
        for _, order_id, order_date, order_value in rows:
            running += order_value
            expected.append(
                (customer_id, order_id, order_date.isoformat(), str(order_value), str(running))
            )

    actual = capture(con, recipes.find("01").sql)
    assert list(actual.rows) == expected
    assert expected, "the sample selected no customers, so this test proved nothing"


def test_sessionization_matches_a_python_thirty_minute_rule(con) -> None:
    """Recipe 09's LAG-and-cumulative-SUM is checked against a straight Python loop."""
    sampled = (1, 2, 3, 7)
    events = _rows(
        con,
        f"""
        SELECT customer_id, event_id, event_ts
        FROM page_events
        WHERE customer_id IN {sampled}
        ORDER BY customer_id, event_ts, event_id
        """,
    )

    sessions: dict[tuple[int, int], list[dt.datetime]] = {}
    session_number = 0
    previous_customer: int | None = None
    previous_ts: dt.datetime | None = None
    for customer_id, _event_id, event_ts in events:
        new_customer = customer_id != previous_customer
        gap = None if previous_ts is None else (event_ts - previous_ts).total_seconds()
        if new_customer:
            session_number = 1
        elif gap is not None and gap > SESSION_GAP_SECONDS:
            session_number += 1
        sessions.setdefault((customer_id, session_number), []).append(event_ts)
        previous_customer, previous_ts = customer_id, event_ts

    expected = [
        (
            customer_id,
            number,
            min(stamps).isoformat(sep=" "),
            max(stamps).isoformat(sep=" "),
            len(stamps),
            int((max(stamps) - min(stamps)).total_seconds()),
        )
        for (customer_id, number), stamps in sorted(sessions.items())
    ]

    actual = capture(con, recipes.find("09").sql)
    assert list(actual.rows) == expected


def test_exactly_thirty_minutes_does_not_start_a_new_session(con) -> None:
    """The boundary the recipe documents, pinned down by the one event planted for it.

    Customer 7 has two consecutive events exactly ``SESSION_GAP`` apart. Under the
    recipe's "strictly greater than" rule they belong to the same session; a ">=" rule
    would split them. Without this test the choice is just a comment.
    """
    gaps = _rows(
        con,
        f"""
        SELECT COUNT(*) FROM (
            SELECT event_ts - LAG(event_ts) OVER (ORDER BY event_ts, event_id) AS gap
            FROM page_events WHERE customer_id = {warehouse.BOUNDARY_CUSTOMER}
        ) WHERE gap = INTERVAL {SESSION_GAP_SECONDS} SECOND
        """,
    )
    assert gaps[0][0] >= 1, "the planted exactly-at-the-boundary gap is gone"

    result = capture(con, recipes.find("09").sql)
    boundary_sessions = [r for r in result.rows if r[0] == warehouse.BOUNDARY_CUSTOMER]
    assert len(boundary_sessions) == 1, (
        "customer 7's events split across sessions, so the > 30 minute boundary broke"
    )


def test_gaps_and_islands_matches_python_streak_detection(con) -> None:
    """Recipe 07's date-minus-row_number trick, checked against an explicit scan."""
    active = _rows(
        con,
        """
        SELECT DISTINCT customer_id, CAST(event_ts AS DATE) AS active_date
        FROM page_events ORDER BY customer_id, active_date
        """,
    )
    by_customer: dict[int, list[dt.date]] = defaultdict(list)
    for customer_id, active_date in active:
        by_customer[customer_id].append(active_date)

    streaks: list[tuple[int, dt.date, dt.date, int]] = []
    for customer_id, dates in by_customer.items():
        start = previous = dates[0]
        length = 1
        for current in dates[1:]:
            if (current - previous).days == 1:
                length += 1
            else:
                streaks.append((customer_id, start, previous, length))
                start, length = current, 1
            previous = current
        streaks.append((customer_id, start, previous, length))

    top = sorted(
        (s for s in streaks if s[3] >= 2),
        key=lambda s: (-s[3], s[0], s[1]),
    )[:15]
    expected = [(c, start.isoformat(), end.isoformat(), n) for c, start, end, n in top]

    actual = capture(con, recipes.find("07").sql)
    assert list(actual.rows) == expected
    assert expected, "no streaks found, so this test proved nothing"


def test_pivot_and_conditional_aggregation_agree(con) -> None:
    """Recipes 10 and 11 answer one question two ways; they must not drift apart."""
    pivoted = capture(con, recipes.find("10").sql)
    portable = capture(con, recipes.find("11").sql)
    assert pivoted == portable
    assert pivoted.column_names == ["month", "cancelled", "completed", "returned"]


def test_ranking_recipe_still_contains_a_tie(con) -> None:
    """Recipe 03 exists to show how RANK, DENSE_RANK and ROW_NUMBER differ on ties.

    If the underlying slice ever stops producing a tie the query still runs and still
    matches its fixture, but it has quietly stopped demonstrating anything. That is a
    failure worth catching.
    """
    result = capture(con, recipes.find("03").sql)
    counts = [row[2] for row in result.rows]
    assert len(counts) != len(set(counts)), "no tied order_count, so the recipe shows nothing"

    ranks = [row[4] for row in result.rows]
    dense = [row[5] for row in result.rows]
    assert ranks != dense, "RANK and DENSE_RANK are identical here, so the contrast is lost"


def test_tie_safe_ranking_is_reproducible_and_the_ties_are_real(con) -> None:
    """Recipe 12 only means something if duplicate timestamps actually exist."""
    duplicated = _rows(
        con,
        """
        SELECT COUNT(*) FROM (
            SELECT customer_id, event_ts FROM page_events
            GROUP BY customer_id, event_ts HAVING COUNT(*) > 1
        )
        """,
    )[0][0]
    assert duplicated > 0, "no duplicate timestamps, so recipe 12 demonstrates nothing"

    result = capture(con, recipes.find("12").sql)
    assert all(row[2] > 1 for row in result.rows), "recipe 12 returned a non-tied row"
    for _ in range(5):
        assert capture(con, recipes.find("12").sql) == result


def test_date_spine_has_no_missing_days(con) -> None:
    """Recipe 06's whole purpose is that every April day appears, including empty ones."""
    result = capture(con, recipes.find("06").sql)
    days = [row[0] for row in result.rows]
    assert len(days) == 30
    assert days[0] == "2026-04-01"
    assert days[-1] == "2026-04-30"
    assert days == sorted(days)
