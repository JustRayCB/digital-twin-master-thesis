-- Migration 003: Camera snapshots table
-- Stores snapshot metadata in PostgreSQL and raw image bytes on the filesystem.

CREATE TABLE IF NOT EXISTS camera_snapshots (
    id SERIAL, -- PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    sensor_id INTEGER NOT NULL, 
    plant_id INTEGER NOT NULL,
    topic VARCHAR(100) NOT NULL,
    mime_type VARCHAR(50) NOT NULL,
    file_ref TEXT NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    width INTEGER,
    height INTEGER,

    PRIMARY KEY (id),
    CONSTRAINT fk_camera_snapshots_sensor_id FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE,
    CONSTRAINT fk_camera_snapshots_plant_id FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);
