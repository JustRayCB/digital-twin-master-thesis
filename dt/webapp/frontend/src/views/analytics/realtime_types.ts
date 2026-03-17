export interface ProcessedReadingPayload {
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
}

export interface AggregatedReadingPayload {
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
}

export interface DqHoverState {
  dqScore: number | null;
  flagsText: string;
}

