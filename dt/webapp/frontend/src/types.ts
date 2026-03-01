export type ViewState = 'OVERVIEW' | 'ANALYTICS' | 'JOURNAL' | 'LOGIC_BUILDER';

export enum PlantHealthState {
  HEALTHY = 'HEALTHY',
  THIRSTY = 'THIRSTY',
  COLD = 'COLD',
  HOT = 'HOT',
}

export interface Routine {
  id: string;
  name: string;
  condition: string;
  active: boolean;
}

export type Reading = {
  plant_id: number;
  sensor_id: number;
  time: number;
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

export type CameraSnapshot = {
  plant_id: number;
  sensor_id: number;
  time: number;
  mime_type: string;
  image: string;
  width?: number | null;
  height?: number | null;
  correlation_id: string;
};

export type ActiveAlert = {
  alert_id?: number | string | null;
  alert_key?: string | null;
  message?: string | null;
  status?: string | null;
  severity?: string | null;
  time?: number | null;
  plant_id?: number | null;
  sensor_id?: number | null;
};

export type Actuator = {
  id: number;
  plant_id: number;
  name: string;
  relay_channel?: number | null;
  status?: string | null;
};

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

export type RoutineUpdatePayload = {
  plant_id?: number;
  name?: string;
  enabled?: boolean;
  graph?: unknown;
  compiled_rules?: unknown;
};

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

export type ReadingQuery = {
  window?: 'raw' | '1h';
  sensorId?: number;
  plantId?: number;
  topic?: string;
  since?: number;
  until?: number;
};
