import type {
	PlotConfig,
	PlotLayout,
	PlotSpec,
	PlotTrace,
} from "$shared/charts";
import type { AggregatedReading, ForecastResult, Reading } from "$shared/types";
import { formatChartTime } from "$shared/utils/time";

import {
	buildTimeSeriesTracePoints,
	buildTimeSeriesBandPoints,
	type AnalyticsReadingSeriesKey,
	type AnalyticsSeriesKey,
	type BandPoint,
	type SeriesVisibility,
} from "./time_series.transforms";

/**
 * Represents a time interval for filtering or displaying data.
 */
type TimeRange = {
	start: Date;
	end: Date;
};

type MarkerPoint = {
	symbol: "circle" | "square" | "diamond" | "triangle-up";
	size: number;
	color: string;
};

/**
 * Input configuration for building a time series plot specification.
 */
type BuildTimeSeriesSpecInput = {
	readings: Reading[];
	aggregates: AggregatedReading[];
	forecasts?: ForecastResult[];
	layout?: PlotLayout;
	config?: PlotConfig;
	/** Map of series keys to their visibility state */
	visibleSeries: SeriesVisibility;
	/** Optional time range to filter and display */
	timeRange?: TimeRange | null;
	/** Optional list of metrics to display on a secondary y-axis */
	secondaryMetrics?: AnalyticsSeriesKey[];
	/** Stable Plotly UI revision for preserving zoom during live updates */
	revision?: string;
};

/**
 * Configuration for the different data series available in the plot.
 */
const SERIES: Array<{ key: AnalyticsReadingSeriesKey; color: string; dash: string }> =
	[
		{ key: "value", color: "#1c1917", dash: "solid" },
		{ key: "raw_value", color: "#6b7280", dash: "dot" },
		{ key: "calibrated_value", color: "#ffdac1", dash: "dash" },
		{ key: "normalized_value", color: "#c7cee3", dash: "dashdot" },
	];

/**
 * Builds a Plotly-compatible PlotSpec for a time series visualization.
 *
 * This function processes raw and aggregated readings to create multiple traces,
 * including main value lines and shaded bands for min/max and standard deviation.
 *
 * @param input - The data and configuration for the plot
 * @returns A PlotSpec object for rendering
 */
export function buildTimeSeriesSpec({
	readings,
	aggregates,
	forecasts = [],
	layout = {},
	config,
	visibleSeries,
	timeRange = null,
	secondaryMetrics = [],
	revision,
}: BuildTimeSeriesSpecInput): PlotSpec {
	const traces: PlotTrace[] = [];
	let qualityHoverAssigned = false;

	// Iterate through predefined series and add traces for those that are visible.
	for (const series of SERIES) {
		if (!visibleSeries[series.key]) {
			continue;
		}

		const yaxis = secondaryMetrics.includes(series.key) ? "y2" : undefined;

		const { basePoints, liveOverlayPoints } = buildTimeSeriesTracePoints(
			readings,
			aggregates,
			series.key,
		);

		const includeQualityOnBaseTrace = !qualityHoverAssigned && basePoints.length > 0;
		traces.push(buildSeriesTrace({
			name: series.key,
			points: basePoints,
			color: series.color,
			dash: series.dash,
			yaxis,
			markerSeriesKey: series.key,
			includeQualityHover: includeQualityOnBaseTrace,
			showlegend: true,
		}));
		if (includeQualityOnBaseTrace) {
			qualityHoverAssigned = true;
		}

		if (liveOverlayPoints.length > 0) {
			const includeQualityOnLiveTrace = !qualityHoverAssigned;
			traces.push(buildSeriesTrace({
				name: series.key,
				points: liveOverlayPoints,
				color: series.color,
				lineWidth: 1.5,
				yaxis,
				markerSeriesKey: series.key,
				includeQualityHover: includeQualityOnLiveTrace,
				showlegend: false,
			}));
			if (includeQualityOnLiveTrace) {
				qualityHoverAssigned = true;
			}
		}
	}

	const bandPoints = buildTimeSeriesBandPoints(aggregates);

	return {
		// Combine main traces with shaded bands (min/max/stddev).
		data: [
			...traces,
			...buildBandTraces(bandPoints),
			...(visibleSeries.forecast ? buildForecastTraces(forecasts) : []),
		],
		layout: applyTimeRangeToLayout(layout, timeRange, revision),
		config,
	};
}

function buildForecastTraces(forecasts: ForecastResult[]): PlotTrace[] {
  if (forecasts.length === 0) {
    return [];
  }

  const forecastTime = (forecast: ForecastResult) =>
    forecast.time + forecast.horizon_seconds * 1_000;
  const sorted = [...forecasts].sort((left, right) => forecastTime(left) - forecastTime(right));
  return [{
    name: "forecast",
    x: sorted.map((forecast) => formatChartTime(forecastTime(forecast))),
    y: sorted.map((forecast) => forecast.predicted_value),
    mode: "lines+markers",
    line: { color: "#ef4444", dash: "dash" },
    marker: { color: "#ef4444", symbol: "diamond", size: 8 },
    hovertemplate: "%{y}<extra>forecast</extra>",
  }];
}

type BuildSeriesTraceInput = {
	name: string;
	points: Array<{ x: string; y: number | null; customdata: [number | null, string] }>;
	color: string;
	dash?: string;
	lineWidth?: number;
	yaxis?: string;
	markerSeriesKey: AnalyticsReadingSeriesKey;
	includeQualityHover: boolean;
	showlegend: boolean;
};

function buildSeriesTrace({
	name,
	points,
	color,
	dash,
	lineWidth,
	yaxis,
	markerSeriesKey,
	includeQualityHover,
	showlegend,
}: BuildSeriesTraceInput): PlotTrace {
	const trace: PlotTrace = {
		name,
		x: points.map((point) => point.x),
		y: points.map((point) => point.y),
		mode: "lines+markers",
		line: { color, dash, width: lineWidth },
		marker: buildMarkers(markerSeriesKey, points.map((point) => point.customdata[0])),
		yaxis,
		showlegend,
		hovertemplate: hoverTemplateForSeries(includeQualityHover),
	};

	if (includeQualityHover) {
		trace.customdata = points.map((point) => point.customdata);
	}

	return trace;
}

function hoverTemplateForSeries(includeQualityHover: boolean): string {
	if (!includeQualityHover) {
		return "%{y}<extra>%{fullData.name}</extra>";
	}

	return "%{y}<br>DQ: %{customdata[0]}<br>%{customdata[1]}<extra>%{fullData.name}</extra>";
}

function buildMarkers(seriesKey: AnalyticsReadingSeriesKey, dqScores: Array<number | null>) {
	const points = dqScores.map((dqScore) => markerForDq(seriesKey, dqScore));
	return {
		symbol: points.map((point) => point.symbol),
		size: points.map((point) => point.size),
		color: points.map((point) => point.color),
		line: { color: "#1c1917", width: 1 },
	};
}

function markerForDq(seriesKey: AnalyticsReadingSeriesKey, dqScore: number | null): MarkerPoint {
	const symbol = symbolForSeries(seriesKey);
	if (dqScore === null) {
		return { symbol, size: 6, color: "#7f7f7f" };
	}

	const dq = Number(dqScore);
	if (!Number.isFinite(dq)) {
		return { symbol, size: 6, color: "#7f7f7f" };
	}

	return {
		symbol,
		size: dq < 0.7 ? 10 : 6,
		color: dqToColor(dq),
	};
}

function symbolForSeries(seriesKey: AnalyticsReadingSeriesKey): MarkerPoint["symbol"] {
	if (seriesKey === "raw_value") {
		return "square";
	}
	if (seriesKey === "calibrated_value") {
		return "diamond";
	}
	if (seriesKey === "normalized_value") {
		return "triangle-up";
	}
	return "circle";
}

function dqToColor(dq: number): string {
	if (dq <= 0.5) {
		const progress = dq / 0.5;
		return `rgb(255,${Math.round(255 * progress)},0)`;
	}

	const progress = (dq - 0.5) / 0.5;
	return `rgb(${Math.round(255 * (1 - progress))},255,0)`;
}

/**
 * Creates shaded band traces for min/max and standard deviation ranges.
 *
 * @param bands - The calculated band points from aggregated data
 * @returns An array of Plotly traces for the shaded areas
 */
function buildBandTraces(bands: BandPoint[]): PlotTrace[] {
	if (bands.length === 0) {
		return [];
	}

	const xs = bands.map((point) => point.x);
	const traces: PlotTrace[] = [];
	const hasStddev = bands.some(
		(point) => point.stddevLower !== null && point.stddevUpper !== null,
	);

	// Add standard deviation band if data is available.
	if (hasStddev) {
		traces.push({
			x: xs,
			y: bands.map((point) => point.stddevLower),
			mode: "lines",
			name: "σ lower",
			line: { width: 0 },
			showlegend: false,
			hoverinfo: "skip",
		});
		traces.push({
			x: xs,
			y: bands.map((point) => point.stddevUpper),
			mode: "lines",
			name: "standard deviation band",
			fill: "tonexty",
			fillcolor: "rgba(100,150,200,0.25)",
			line: { width: 0 },
			showlegend: true,
			hoverinfo: "skip",
		});
	}

	// Add min/max band.
	traces.push({
		x: xs,
		y: bands.map((point) => point.min),
		mode: "lines",
		name: "min",
		line: { width: 0 },
		showlegend: false,
		hoverinfo: "skip",
	});
	traces.push({
		x: xs,
		y: bands.map((point) => point.max),
		mode: "lines",
		name: "min/max band",
		fill: "tonexty",
		fillcolor: "rgba(100,100,100,0.12)",
		line: { width: 0 },
		showlegend: true,
		hoverinfo: "skip",
	});

	return traces;
}

/**
 * Updates the plot layout with the specified time range.
 *
 * @param layout - The original layout
 * @param timeRange - The time range to apply
 * @returns A new layout object with updated xaxis range
 */
function applyTimeRangeToLayout(
	layout: PlotLayout,
	timeRange: TimeRange | null,
	revision?: string,
): PlotLayout {
	const nextLayout = { ...layout } as Record<string, unknown>;
	if (revision) {
		nextLayout.uirevision = revision;
	}
	// Ensure we have an xaxis object to modify, defaulting to an empty object if not present.
	const xaxis =
		typeof nextLayout.xaxis === "object" && nextLayout.xaxis !== null
			? { ...(nextLayout.xaxis as Record<string, unknown>) }
			: {};

	delete xaxis.range;
	xaxis.autorange = true;
	nextLayout.xaxis = xaxis;

	return nextLayout;
}
