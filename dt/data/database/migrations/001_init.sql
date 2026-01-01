-- Migration 001: Initial schema for PostgreSQL + TimescaleDB
-- Creates base tables, hypertables, continuous aggregates, and policies
-- https://www.nihardaily.com/108-timescaledb-with-postgresql-the-ultimate-guide-to-time-series-data-management

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- RELATIONAL TABLES
-- ============================================================================

-- Plants table
CREATE TABLE IF NOT EXISTS plants (
    id SERIAL, 
    name VARCHAR(255) NOT NULL,
    notes TEXT,

    PRIMARY KEY (id)
);

-- Sensors table
CREATE TABLE IF NOT EXISTS sensors (
    id SERIAL,
    plant_id INTEGER NOT NULL, 
    name VARCHAR(255) NOT NULL,
    pin INTEGER NOT NULL,
    read_interval INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',

    PRIMARY KEY (id),
    CONSTRAINT fk_sensors_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);

-- Actuators table
CREATE TABLE IF NOT EXISTS actuators (
    id SERIAL,
    plant_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    relay_channel INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',

    PRIMARY KEY (id),
    CONSTRAINT fk_actuators_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE

);

-- Alert definitions table (invariant properties)
-- alert_key convention: <rule_slug>:<source_slug> (e.g., "high_temp:temperature")
-- Allowed characters: lowercase alphanumeric, -, _, :
-- Max length: 128 characters (enforced by application layer)
-- Immutability: alert_key is treated as immutable; renames create new alerts
CREATE TABLE IF NOT EXISTS alert_definitions (
    alert_key TEXT CHECK (length(alert_key) <= 128),
    plant_id INTEGER NOT NULL,
    sensor_id INTEGER, -- Used for sensor-specific alerts
    source VARCHAR(255) NOT NULL,
    rule_id VARCHAR(255), -- rule identifier in configuration
    rule_name VARCHAR(255), -- human-readable rule name
    kind VARCHAR(50) NOT NULL,
    persistence_count INTEGER NOT NULL,
    cooldown_seconds INTEGER NOT NULL,

    PRIMARY KEY (alert_key, plant_id),
    CONSTRAINT fk_alert_definitions_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
    CONSTRAINT fk_alert_definitions_sensor FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
);

-- Alert history table
CREATE TABLE IF NOT EXISTS alert_history (
    id SERIAL,
    alert_key TEXT NOT NULL,
    plant_id INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    status VARCHAR(50) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    acknowledged_by VARCHAR(255),
    acknowledged_ts TIMESTAMPTZ,
    cleared_ts TIMESTAMPTZ,

    PRIMARY KEY (id),
    CONSTRAINT fk_alert_history_def FOREIGN KEY (alert_key, plant_id) REFERENCES alert_definitions(alert_key, plant_id) ON DELETE CASCADE,
    CONSTRAINT alert_history_id_plant_key UNIQUE (id, plant_id) 
);

-- Alert reading snapshots (sensor reading context per history event)
CREATE TABLE IF NOT EXISTS alert_sensors (
    id SERIAL, 
    alert_history_id INTEGER NOT NULL, 

    sensor_id INTEGER NOT NULL,
    plant_id INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50) NOT NULL,
    topic VARCHAR(100) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    flags VARCHAR(100) NOT NULL,
    dq_score DOUBLE PRECISION NOT NULL,
    imputed BOOLEAN NOT NULL DEFAULT FALSE,
    raw_value DOUBLE PRECISION,
    calibrated_value DOUBLE PRECISION,
    normalized_value DOUBLE PRECISION,
    calibration_profile_id VARCHAR(255),
    normalization_profile_id VARCHAR(255),

    threshold_op VARCHAR(50),
    threshold_value DOUBLE PRECISION,
    range_min DOUBLE PRECISION,
    range_max DOUBLE PRECISION,

    PRIMARY KEY (id),
    CONSTRAINT fk_alert_sensors_history_plant FOREIGN KEY (alert_history_id, plant_id) REFERENCES alert_history(id, plant_id) ON DELETE CASCADE,
    CONSTRAINT fk_alert_sensors_sensor FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
);

-- Alert external (string key-value pairs per history event)
-- Used now for external alerting systems, Currently using JSON blobs but plan to migrate to key-value pairs
CREATE TABLE IF NOT EXISTS alert_external (
    id SERIAL, 
    alert_history_id INTEGER NOT NULL, 
    plant_id INTEGER NOT NULL,
    metadata JSONB NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT fk_alert_external_history_plant FOREIGN KEY (alert_history_id, plant_id) REFERENCES alert_history(id, plant_id) ON DELETE CASCADE
);

-- ============================================================================
-- TIME-SERIES TABLES (HYPERTABLES)
-- ============================================================================

-- Sensor measurements hypertable
-- Using the new HyperCore format for better performance and flexibility
-- https://www.tigerdata.com/docs/use-timescale/latest/hypercore
CREATE TABLE IF NOT EXISTS sensor_readings (
    timestamp TIMESTAMPTZ NOT NULL,
    sensor_id INTEGER NOT NULL,
    plant_id INTEGER NOT NULL,
    topic VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    dq_score DOUBLE PRECISION NOT NULL,
    imputed BOOLEAN NOT NULL DEFAULT FALSE,
    flags VARCHAR(100) NOT NULL,
    raw_value DOUBLE PRECISION,
    calibrated_value DOUBLE PRECISION,
    normalized_value DOUBLE PRECISION,
    calibration_profile_id VARCHAR(255),
    normalization_profile_id VARCHAR(255),

    CONSTRAINT fk_sensor FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE,
    CONSTRAINT fk_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
) WITH (
    timescaledb.hypertable,
    timescaledb.enable_columnstore,
    timescaledb.chunk_interval = '7 days', -- similar as add_compression_policy(..., compressed_after => INTERVAL '7 days')
    timescaledb.segmentby = 'sensor_id, plant_id, topic', -- segmentation columns for columnar storage
    timescaledb.orderby = 'timestamp DESC'
);

-- Add a custom columnstore compression policy to the sensor_readings hypertable
-- https://www.tigerdata.com/docs/api/latest/hypercore/add_columnstore_policy
-- CALL add_columnstore_policy(
--     'sensor_readings',
--     INTERVAL '30 days'
-- );

-- ============================================================================
-- CONTINUOUS AGGREGATES
-- ============================================================================

-- 1-hour aggregate
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS bucket,
    sensor_id,
    plant_id,
    topic,
    unit,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    COUNT(*) AS sample_count,
    AVG(dq_score) AS avg_dq_score,
    SUM(CASE WHEN imputed THEN 1 ELSE 0 END) AS imputed_count
FROM sensor_readings
GROUP BY bucket, sensor_id, plant_id, topic, unit
WITH NO DATA; -- We will populate data via policies

-- ============================================================================
-- POLICIES
-- ============================================================================

-- Refresh policy for 1-hour aggregate (refresh last 2 hours every 30 minutes)
SELECT add_continuous_aggregate_policy('sensor_readings_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);

-- Retention policy (keep raw data for 30 days by default)
-- NOTE: For now we keep only 30 days of raw data and rely on aggregates for longer-term analysis.
-- Later we could also implement downsampling policies if needed. See https://docs.tigerdata.com/api/latest/hyperfunctions/downsampling/
-- And set a longer retention for aggregates. (currently aggregates are kept indefinitely)
SELECT add_retention_policy('sensor_readings',
    INTERVAL '30 days',
    if_not_exists => TRUE
);
