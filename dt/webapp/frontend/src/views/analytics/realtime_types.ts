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

export interface DqHoverState {
  dqScore: number | null;
  flagsText: string;
}

