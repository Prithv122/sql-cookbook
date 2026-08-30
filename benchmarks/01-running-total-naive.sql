-- Benchmark: 01-running-total
-- Variant: naive
-- Note: the pre-window-function idiom -- re-aggregate every earlier row of the same
--   customer for each row. Correct, portable to any engine, and quadratic in the
--   number of orders per customer.

WITH order_value AS (
    SELECT
        o.order_id,
        o.customer_id,
        CAST(o.order_ts AS DATE)         AS order_date,
        SUM(oi.quantity * oi.unit_price) AS order_value
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY o.order_id, o.customer_id, o.order_ts
)

SELECT
    ov.customer_id,
    ov.order_id,
    ov.order_date,
    ov.order_value,
    (
        SELECT SUM(prior.order_value)
        FROM order_value prior
        WHERE prior.customer_id = ov.customer_id
          AND (prior.order_date, prior.order_id) <= (ov.order_date, ov.order_id)
    ) AS running_total
FROM order_value ov
ORDER BY ov.customer_id, ov.order_date, ov.order_id;
