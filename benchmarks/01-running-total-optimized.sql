-- Benchmark: 01-running-total
-- Variant: optimized
-- Note: one pass, one window. Recipe 01 is this query plus a sample filter.

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
    customer_id,
    order_id,
    order_date,
    order_value,
    SUM(order_value) OVER (
        PARTITION BY customer_id
        ORDER BY order_date, order_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM order_value
ORDER BY customer_id, order_date, order_id;
