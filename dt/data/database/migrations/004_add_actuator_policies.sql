-- Migration 004: Create actuator_policies table and seed initial data

CREATE TABLE IF NOT EXISTS actuator_policies (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER REFERENCES plants(id) ON DELETE CASCADE,
    actuator_name VARCHAR(255),
    max_duration_seconds DOUBLE PRECISION,
    min_cooldown_seconds DOUBLE PRECISION,
    allow_overlap BOOLEAN,
    allowed_commands TEXT[],
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE NULLS NOT DISTINCT (plant_id, actuator_name)
);

-- Insert default base values (plant_id IS NULL, actuator_name IS NULL)
INSERT INTO actuator_policies (plant_id, actuator_name, max_duration_seconds, min_cooldown_seconds, allow_overlap, allowed_commands)
VALUES (NULL, NULL, 30, 10, FALSE, ARRAY['ON', 'OFF']);

-- Insert global actuator overrides (plant_id IS NULL)
INSERT INTO actuator_policies (plant_id, actuator_name, max_duration_seconds, min_cooldown_seconds, allow_overlap, allowed_commands)
VALUES
    (NULL, 'pump', 3, 21600, FALSE, NULL),
    (NULL, 'light', 28800, 0, FALSE, NULL),
    (NULL, 'fan', 7200, 0, NULL, NULL),
    (NULL, 'heater', 1800, 1800, NULL, NULL);
