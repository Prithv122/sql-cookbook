-- Benchmark: 04-top-n-per-group
-- Variant: optimized
-- Note: rank once in a window, then filter the ranked rows with QUALIFY.

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

SELECT
    customer_id,
    order_id,
    order_value,
    CAST(
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_value DESC, order_id)
        AS BIGINT
    ) AS value_rank
FROM order_value
QUALIFY value_rank <= 3
ORDER BY customer_id, value_rank;
