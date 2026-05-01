/**
 * @fileoverview Core data structures and types shared across the application.
 * Defines the models for domain entities like Plants, Sensors, Alerts, and Actions.
 */

/** Defines the top-level views available in the application routing. */
export type ViewState = 'OVERVIEW' | 'ANALYTICS' | 'JOURNAL' | 'LOGIC_BUILDER' | 'SETTINGS';

/** Represents the general well-being of a plant derived from telemetry. */
export enum PlantHealthState {
  HEALTHY = 'HEALTHY',
  THIRSTY = 'THIRSTY',
  COLD = 'COLD',
  HOT = 'HOT',
}

/** Represents an automated routine attached to a plant. */
export interface Routine {
  id: number;
  name: string;
  condition: string;
  active: boolean;
  graph?: unknown;
  plant_id?: number;
}

/**
 * Represents a single raw or processed telemetry reading from a sensor.
 * Includes data quality metrics and preprocessing flags.
 */
export type Reading = {
  plant_id: number;
  sensor_id: number;
  time: number;
  topic?: string | null;
  unit?: string | null;
  value?: number | null;
  raw_value?: number | null;
  calibrated_value?: number | null;
  normalized_value?: number | null;
  dq_score?: number | null;
  imputed?: boolean | null;
  flags?: Record<string, boolean> | null;
  correlation_id?: string | null;
  calibration_profile_id?: string | null;
  normalization_profile_id?: string | null;
};

/**
 * Represents a time-bucketed aggregation of multiple sensor readings.
 * Used primarily for historical analytics and reducing data volume.
 */
export type AggregatedReading = {
  time: number;
  sensor_id: number;
  plant_id: number;
  topic: string;
  unit: string;
  mean_value: number;
  min_value: number;
  max_value: number;
  sample_count: number;
  avg_dq_score: number;
  imputed_count: number;
  avg_raw_value: number | null;
  avg_calibrated_value: number | null;
  avg_normalized_value: number | null;
  variance_value?: number | null;
  stddev_value?: number | null;
  skewness_value?: number | null;
};

/** Represents an image captured by a plant monitoring camera. */
export type CameraSnapshot = {
  plant_id: number;
  sensor_id: number;
  time: number;
  topic?: string | null;
  mime_type: string;
  image: string;
  width?: number | null;
  height?: number | null;
  correlation_id: string;
};

/** Represents a currently active alert that requires attention. */
export type ActiveAlert = {
  alert_id?: string | null;
  alert_key?: string | null;
  message?: string | null;
  status?: string | null;
  severity?: string | null;
  time?: number | null;
  correlation_id?: string | null;
  acknowledged_by?: string | null;
  acknowledged_ts?: number | null;
  cleared_ts?: number | null;
  plant_id?: number | null;
  sensor_id?: number | null;
};

/** Represents a historical record of an alert's lifecycle. */
export type AlertHistory = {
  id?: number | null;
  alert_key?: string | null;
  plant_id?: number | null;
  sensor_id?: number | null;
  status?: string | null;
  severity?: string | null;
  message?: string | null;
  time?: number | null;
  correlation_id?: string | null;
  acknowledged_by?: string | null;
  acknowledged_ts?: number | null;
  cleared_ts?: number | null;
};

/** Represents an actuator hardware component (e.g., pump, light). */
export type Actuator = {
  id: number;
  plant_id: number;
  name: string;
  relay_channel?: number | null;
  status?: string | null;
};

/** Represents a sensor hardware component. */
export type Sensor = {
  id: number;
  plant_id: number;
  name: string;
  pin: number;
  read_interval: number;
  status?: string | null;
};

/** Represents the current operational mode of a plant's control system. */
export type ControlMode = {
  plant_id: number;
  ai_autopilot_enabled: boolean;
  owner: string;
  updated_at?: string | null;
};

/** Payload for updating a plant's control mode. */
export type ControlModeUpdate = {
  plant_id: number;
  ai_autopilot_enabled: boolean;
  owner: string;
};

/** Database record representation of a routine. */
export type RoutineRecord = {
  id: number;
  plant_id?: number;
  name: string;
  enabled: boolean;
  graph?: unknown;
  compiled_rules?: unknown;
  created_at?: string | null;
  updated_at?: string | null;
};

/** Payload for creating or updating a routine. */
export type RoutineUpdatePayload = {
  plant_id?: number;
  name?: string;
  enabled?: boolean;
  graph?: unknown;
  compiled_rules?: unknown;
};

/** Payload representing a command sent to an actuator. */
export type ActionDispatchPayload = {
  plant_id: number;
  actuator_id: number;
  command: string;
  source: 'ai' | 'manual';
  duration?: number;
  reason?: string;
  action_id?: string;
  correlation_id?: string;
};

/** Represents a historical record of an action executed on an actuator. */
export type ActionHistoryRecord = {
  plant_id: number;
  execution_id: string;
  action_id: string;
  actuator_id: number;
  actuator_name?: string | null;
  event_at: number;
  duration: number;
  command: string;
  reason: string;
  correlation_id: string;
  source: string;
  routine_id?: number | null;
  status?: string | null;
  error_message?: string | null;
};

export type RecommendationModelMetadata = {
  model_name: string;
  model_version: string;
};

export type RecommendedAction = {
  capability: string;
  command: string;
  duration_seconds?: number | null;
};

export type ActionResult = {
  action_index: number;
  status: "accepted" | "advisory_only" | "rejected" | "failed";
};

export type Recommendation = {
  time: number;
  plant_id: number;
  correlation_id: string;
  reason: string;
  confidence: number;
  model_metadata?: RecommendationModelMetadata | null;
  actions: RecommendedAction[];
  action_results: ActionResult[];
};

export type HealthState = "healthy" | "stressed" | "critical" | "unknown";

export type HealthAssessment = {
  plant_id: number;
  timestamp: number;
  correlation_id: string;
  state: HealthState;
  score: number | null;
  confidence?: number | null;
  summary: string;
};

export type ForecastResult = {
  plant_id: number;
  time: number;
  correlation_id: string;
  metric: string;
  horizon_seconds: number;
  predicted_value: number;
  unit: string;
  model_metadata?: unknown;
  features_used?: string[];
  inference_metadata?: Record<string, unknown>;
};

export type HealthHistoryQuery = {
  plantId: number;
  since?: number;
  until?: number;
  limit?: number;
  correlationId?: string;
};

export type ForecastHistoryQuery = HealthHistoryQuery & {
  metric?: string;
  horizonSeconds?: number;
};

/** Parameters for querying historical reading data. */
export type ReadingQuery = {
  window?: 'raw' | '1h';
  sensorId?: number;
  plantId?: number;
  topic?: string;
  since?: number;
  until?: number;
};

/** Actuator config overrides */
export type ActuatorConfig = {
  max_duration_seconds: number | null;
  min_cooldown_seconds: number | null;
  allow_overlap: boolean | null;
  allowed_commands: string[] | null;
};

/** Plant-specific actuator overrides */
export type PlantActuatorConfig = {
  actuators: Record<string, ActuatorConfig>;
};

/** Global actuator policy configuration set */
export type ActuatorConfigSet = {
  defaults: ActuatorConfig;
  actuators: Record<string, ActuatorConfig>;
  plants: Record<string, PlantActuatorConfig>;
};

/** Parameters for querying historical camera snapshots. */
export type CameraSnapshotQuery = {
  plantId: number;
  since?: number;
  until?: number;
};

/** Parameters for exporting analytics data for model training. */
export type AnalyticsExportQuery = {
  plantId: number;
  since?: number;
  until?: number;
  limit?: number;
};

/** Browser-facing payload returned by the analytics export endpoint. */
export type AnalyticsExportPayload = {
  metadata: {
    format: string;
    plant_id: number;
    exported_at: number;
    since: number | null;
    until: number | null;
    limit: number | null;
  };
  plant: {
    sensors: Sensor[];
    actuators: Actuator[];
  };
  readings: {
    raw: Reading[];
    aggregates: AggregatedReading[];
  };
  alerts: {
    active: ActiveAlert[];
    history: AlertHistory[];
  };
  actions: Array<Record<string, unknown>>;
  recommendations: Recommendation[];
  health: Array<Record<string, unknown>>;
  forecasts: ForecastResult[];
};
