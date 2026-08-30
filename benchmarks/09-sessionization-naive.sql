-- Benchmark: 09-sessionization
-- Variant: naive
-- Note: the same rule expressed with correlated subqueries instead of windows -- once
--   to find the previous event, once more to number the sessions by counting the
--   session starts at or before each row. Both correlated predicates carry the same
--   (event_ts, event_id) tiebreaker as the window ORDER BY, without which the two
--   variants would disagree wherever a timestamp repeats.

WITH events AS (
    SELECT event_id, customer_id, event_ts FROM page_events
),

with_prev AS (
    SELECT
        e.event_id,
        e.customer_id,
        e.event_ts,
        (
            SELECT MAX(prior.event_ts)
            FROM events prior
            WHERE prior.customer_id = e.customer_id
              AND (prior.event_ts, prior.event_id) < (e.event_ts, e.event_id)
        ) AS prev_ts
    FROM events e
),

starts AS (
    SELECT
        event_id,
        customer_id,
        event_ts,
        CASE
            WHEN prev_ts IS NULL THEN 1
            WHEN event_ts - prev_ts > INTERVAL 30 MINUTE THEN 1
            ELSE 0
        END AS starts_session
    FROM with_prev
),

numbered AS (
    SELECT
        s.event_id,
        s.customer_id,
        s.event_ts,
        CAST((
            SELECT COUNT(*)
            FROM starts earlier
            WHERE earlier.customer_id = s.customer_id
              AND earlier.starts_session = 1
              AND (earlier.event_ts, earlier.event_id) <= (s.event_ts, s.event_id)
        ) AS BIGINT) AS session_number
    FROM starts s
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
