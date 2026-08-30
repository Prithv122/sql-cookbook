-- Benchmark: 04-top-n-per-group
-- Variant: naive
-- Note: also the PORTABLE version. No window function and no QUALIFY, so it runs on
--   Postgres and MySQL 5.7 as written: rank a row by counting how many rows beat it.
--   The tiebreaker in the correlated predicate has to mirror the optimized query's
--   ORDER BY exactly, or the two disagree on ties.

WITH order_value AS (
    SELECT
        o.order_id,
        o.customer_id,
        SUM(oi.quantity * oi.unit_price) AS order_value
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY o.order_id, o.customer_id
)

SELECT customer_id, order_id, order_value, value_rank
FROM (
    SELECT
        ov.customer_id,
        ov.order_id,
        ov.order_value,
        CAST((
            SELECT COUNT(*)
            FROM order_value better
            WHERE better.customer_id = ov.customer_id
              AND (
                    better.order_value > ov.order_value
                 OR (better.order_value = ov.order_value AND better.order_id < ov.order_id)
              )
        ) + 1 AS BIGINT) AS value_rank
    FROM order_value ov
) ranked
WHERE value_rank <= 3
ORDER BY customer_id, value_rank;
