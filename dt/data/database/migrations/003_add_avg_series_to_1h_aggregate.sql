-- Add average raw, calibrated, and normalized value columns to the 1-hour
-- continuous aggregate so that aggregated views preserve all four sensor series.
--
-- This migration is designed to be run without a transaction block, as it
-- involves dropping and recreating a materialized view, which cannot be done
-- inside a transaction. 

-- migrate: no-transaction
--
-- TimescaleDB continuous aggregates cannot be altered in place, so we must
-- drop the existing view and recreate it with the additional columns.

-- 1. Remove the automatic refresh policy
SELECT remove_continuous_aggregate_policy('sensor_readings_1h', if_exists => TRUE);

-- 2. Drop the existing materialized view
DROP MATERIALIZED VIEW IF EXISTS sensor_readings_1h;

-- 3. Recreate with the three new AVG columns
CREATE MATERIALIZED VIEW sensor_readings_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS bucket,
    plant_id,
    topic,
    MIN(unit) AS unit, -- Assuming unit is consistent within each group, we can take the MIN or MAX
    stats_agg(value) AS value_stats,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    COUNT(*) AS sample_count,
    AVG(dq_score) AS avg_dq_score,
    SUM(CASE WHEN imputed THEN 1 ELSE 0 END) AS imputed_count,
    AVG(raw_value) AS avg_raw_value,
    AVG(calibrated_value) AS avg_calibrated_value,
    AVG(normalized_value) AS avg_normalized_value
FROM sensor_readings
GROUP BY bucket, plant_id, topic
WITH NO DATA;

-- 4. Re-add the refresh policy (same parameters as the original)
SELECT add_continuous_aggregate_policy('sensor_readings_1h',
    start_offset => INTERVAL '3 hours',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);

-- 5. Backfill all existing raw data into the new aggregate
CALL refresh_continuous_aggregate('sensor_readings_1h', NULL, NULL);
