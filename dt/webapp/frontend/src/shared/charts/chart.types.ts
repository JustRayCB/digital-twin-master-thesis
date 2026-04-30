/**
 * @fileoverview Data types and shapes used specifically for rendering Plotly charts.
 */

/** Valid data access paths for selecting which metric variation to render on a chart. */
export type ChartSeriesKey = "value" | "raw_value" | "calibrated_value" | "normalized_value";

/** Standard data point format expected by Plotly scatter/line traces. */
export type SeriesPoint = {
  /** Usually the formatted date string. */
  x: string;
  /** The specific metric value. */
  y: number | null;
  /** Additional metadata attached to the point, useful for hover templates. [dq_score, flag_string] */
  customdata: [number | null, string];
};

/** Format used for rendering error bands or min/max envelopes around a primary series. */
export type BandPoint = {
  x: string;
  min: number | null;
  max: number | null;
  stddevLower?: number | null;
  stddevUpper?: number | null;
};

/** Represents a complete set of chartable series for a single topic/sensor. */
export type TopicSnapshot = Record<ChartSeriesKey, SeriesPoint[]>;
