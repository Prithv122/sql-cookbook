-- Benchmark: 09-sessionization
-- Variant: optimized
-- Note: two windows over one ordering -- LAG for the gap, cumulative SUM for the id.
--   Recipe 09 is this query plus a four-customer sample filter.

WITH flagged AS (
    SELECT
        event_id,
        customer_id,
        event_ts,
        CASE
            WHEN LAG(event_ts) OVER w IS NULL THEN 1
            WHEN event_ts - LAG(event_ts) OVER w > INTERVAL 30 MINUTE THEN 1
            ELSE 0
        END AS starts_session
    FROM page_events
    WINDOW w AS (PARTITION BY customer_id ORDER BY event_ts, event_id)
),

numbered AS (
    SELECT
        event_id,
        customer_id,
        event_ts,
        CAST(
            SUM(starts_session) OVER (
                PARTITION BY customer_id
                ORDER BY event_ts, event_id
                ROWS UNBOUNDED PRECEDING
            ) AS BIGINT
        ) AS session_number
    FROM flagged
)

SELECT
    customer_id,
    session_number,
    MIN(event_ts) AS session_start,
    MAX(event_ts) AS session_end,
    COUNT(*)      AS events,
    DATE_DIFF('second', MIN(event_ts), MAX(event_ts)) AS duration_seconds
FROM numbered
GROUP BY customer_id, session_number
ORDER BY customer_id, session_number;
