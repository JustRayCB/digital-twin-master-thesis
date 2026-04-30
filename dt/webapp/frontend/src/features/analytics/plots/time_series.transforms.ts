import type { AggregatedReading, Reading } from "$shared/types";
import { formatChartTime } from "$shared/utils/time";

export type AnalyticsSeriesKey =
	| "value"
	| "raw_value"
	| "calibrated_value"
	| "normalized_value"
	| "forecast";

export type AnalyticsReadingSeriesKey = Exclude<AnalyticsSeriesKey, "forecast">;

export type SeriesVisibility = Record<AnalyticsSeriesKey, boolean>;

export type SeriesPoint = {
	/** ISO timestamp string for the x-axis */
	x: string;
	y: number | null;
	/** Additional data for tooltips: [data_quality_score, formatted_flags] */
	customdata: [number | null, string];
};

/**
 * Represents a single data point for shaded range bands (min/max and standard deviation).
 */
export type BandPoint = {
	x: string;
	min: number | null;
	max: number | null;
	stddevLower: number | null;
	stddevUpper: number | null;
};

export type TimeSeriesTracePoints = {
	basePoints: SeriesPoint[];
	liveOverlayPoints: SeriesPoint[];
};

/**
 * Maps analytics series keys to the corresponding average/mean fields in aggregated data.
 */
const AGGREGATED_SERIES_MAP: Record<
	AnalyticsReadingSeriesKey,
	keyof AggregatedReading
> = {
	value: "mean_value",
	raw_value: "avg_raw_value",
	calibrated_value: "avg_calibrated_value",
	normalized_value: "avg_normalized_value",
};

/**
 * Builds the base and live overlay points for a time series plot based on raw readings and aggregated data.
 *
 * The function prioritizes aggregated points for the base layer of the plot. If no aggregates are available,
 * it falls back to using raw readings. The live overlay consists of raw points that occur after the latest aggregate timestamp.
 * This approach ensures that the plot reflects the most accurate historical data while also providing real-time updates as new readings come in.
 * @param readings - Array of raw sensor readings
 * @param aggregates - Array of aggregated sensor readings
 * @param key - The key indicating which value to plot (e.g., "value", "raw_value")
 * @returns An object containing base points for the plot and live overlay points for real-time updates
 */
export function buildTimeSeriesTracePoints(
	readings: Reading[],
	aggregates: AggregatedReading[],
	key: AnalyticsReadingSeriesKey,
): TimeSeriesTracePoints {
	const rawPoints = buildRawSeriesPoints(readings, key);

	if (aggregates.length === 0) {
		return {
			basePoints: rawPoints,
			liveOverlayPoints: [],
		};
	}

	const aggregatePoints = buildAggregatePoints(aggregates, key);

	if (rawPoints.length === 0) {
		return {
			basePoints: aggregatePoints,
			liveOverlayPoints: [],
		};
	}

	// Determine the latest timestamp
	const latestAggregateTime = aggregates.reduce(
		(latest, reading) => Math.max(latest, reading.time),
		Number.NEGATIVE_INFINITY,
	);
	const latestAggregateIso = formatChartTime(latestAggregateTime);
	// Filter raw points to include only those that occur after the latest aggregate timestamp for the live overlay
	const liveTailPoints = rawPoints.filter(
		(point) => point.x > latestAggregateIso,
	);
	const lastAggregatePoint = aggregatePoints[aggregatePoints.length - 1];

	return {
		basePoints: aggregatePoints,
		liveOverlayPoints:
			liveTailPoints.length > 0 && lastAggregatePoint
				? [lastAggregatePoint, ...liveTailPoints]
				: [],
	};
}

/**
 * Transforms raw sensor readings into a list of points for plotting, including data quality scores and formatted flags.
 * The function sorts the readings by time and maps each reading to a SeriesPoint object, which includes the timestamp, the value for the specified key, and custom data for tooltips.
 * @param readings - Array of raw sensor readings
 * @param key - The key indicating which value to extract from the readings (e.g., "value", "raw_value")
 * @returns An array of SeriesPoint objects sorted by time
 */
export function buildRawSeriesPoints(
	readings: Reading[],
	key: AnalyticsReadingSeriesKey,
): SeriesPoint[] {
	return [...readings]
		.sort((left, right) => left.time - right.time)
		.map(
			(reading): SeriesPoint => ({
				x: formatChartTime(reading.time),
				y: toFiniteNumber(reading[key]),
				customdata: [
					toFiniteNumber(reading.dq_score),
					formatFlags(reading.flags),
				],
			}),
		);
}

/**
 * Transforms aggregated sensor readings into a list of points for plotting, using the specified key to determine which value to extract.
 * The function sorts the aggregated readings by time and maps each reading to a SeriesPoint object, which includes the timestamp, the value for the specified key, and custom data for tooltips (average data quality score).
 * @param aggregates - Array of aggregated sensor readings
 * @param key - The key indicating which value to extract from the aggregated readings (e.g., "value", "raw_value")
 * @returns An array of SeriesPoint objects sorted by time
 */
export function buildAggregatePoints(
	aggregates: AggregatedReading[],
	key: AnalyticsReadingSeriesKey,
): SeriesPoint[] {
	return [...aggregates]
		.sort((left, right) => left.time - right.time)
		.map(
			(reading): SeriesPoint => ({
				x: formatChartTime(reading.time),
				y: toFiniteNumber(reading[AGGREGATED_SERIES_MAP[key]]),
				customdata: [toFiniteNumber(reading.avg_dq_score), ""],
			}),
		);
}

/**
 * Transforms aggregated readings into a list of points for range bands (min/max/stddev).
 *
 * @param aggregates - Array of aggregated sensor readings
 * @returns An array of BandPoint objects sorted by time
 */
export function buildTimeSeriesBandPoints(
	aggregates: AggregatedReading[],
): BandPoint[] {
	const sorted = [...aggregates].sort((left, right) => left.time - right.time);
	return sorted.map((reading) => {
		const meanValue = toFiniteNumber(reading.mean_value);
		const stddev = toFiniteNumber(reading.stddev_value);

		return {
			x: formatChartTime(reading.time),
			min: toFiniteNumber(reading.min_value),
			max: toFiniteNumber(reading.max_value),
			stddevLower:
				meanValue !== null && stddev !== null ? meanValue - stddev : null,
			stddevUpper:
				meanValue !== null && stddev !== null ? meanValue + stddev : null,
		};
	});
}

/**
 * Formats sensor flags into a comma-separated string of active violations.
 *
 * @param flags - The flags object from a reading
 * @returns A formatted string like "flags: out_of_range, stuck_value" or an empty string
 */
function formatFlags(flags: unknown): string {
	if (!flags || typeof flags !== "object") {
		return "";
	}

	const violations = Object.entries(flags as Record<string, unknown>)
		.filter(([key, value]) => key !== "valid_data_point" && value === true)
		.map(([key]) => key);

	return violations.length > 0 ? `flags: ${violations.join(", ")}` : "";
}

/**
 * Safely converts an unknown value to a finite number or null.
 *
 * @param value - The value to convert
 * @returns The numeric value if finite, otherwise null
 */
function toFiniteNumber(value: unknown): number | null {
	if (value === null) {
		return null;
	}

	const numeric = Number(value);
	return Number.isFinite(numeric) ? numeric : null;
}
