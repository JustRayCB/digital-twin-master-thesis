-- Migration 004: Add analytics output persistence tables

CREATE TABLE IF NOT EXISTS analytics_health_assessments (
    id SERIAL,
    plant_id INTEGER NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL,
    state VARCHAR(50) NOT NULL,
    score DOUBLE PRECISION,
    summary TEXT NOT NULL,
    confidence DOUBLE PRECISION,
    model_metadata JSONB,

    PRIMARY KEY (id),
    CONSTRAINT fk_analytics_health_assessments_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analytics_health_assessments_plant_assessed_at
    ON analytics_health_assessments (plant_id, assessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_health_assessments_correlation_id
    ON analytics_health_assessments (correlation_id);

CREATE TABLE IF NOT EXISTS analytics_forecast_results (
    id SERIAL,
    plant_id INTEGER NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    forecast_at TIMESTAMPTZ NOT NULL,
    metric TEXT NOT NULL,
    horizon_seconds INTEGER NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    features_used JSONB,
    inference_metadata JSONB,
    model_metadata JSONB,

    PRIMARY KEY (id),
    CONSTRAINT fk_analytics_forecast_results_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analytics_forecast_results_plant_forecast_at
    ON analytics_forecast_results (plant_id, forecast_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_forecast_results_correlation_id
    ON analytics_forecast_results (correlation_id);

CREATE TABLE IF NOT EXISTS recommendation_lifecycle (
    id SERIAL,
    plant_id INTEGER NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    recommended_at TIMESTAMPTZ,
    actions JSONB,
    recommendation_confidence DOUBLE PRECISION,
    recommendation_reason TEXT,
    recommendation_model_metadata JSONB,
    action_results JSONB,
    decided_at TIMESTAMPTZ,

    PRIMARY KEY (id),
    CONSTRAINT fk_recommendation_lifecycle_plant FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
    CONSTRAINT uq_recommendation_lifecycle_plant_correlation UNIQUE (plant_id, correlation_id)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_lifecycle_plant_recommended_at
    ON recommendation_lifecycle (plant_id, recommended_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_lifecycle_correlation_id
    ON recommendation_lifecycle (correlation_id);
