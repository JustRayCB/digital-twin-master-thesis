/**
 * @fileoverview State and logic store for the Analytics feature.
 * Handles fetching historical data, processing realtime streams, calculating correlations, and updating the chart registry.
 */
import { derived, get, writable, type Readable } from "svelte/store";

import { dbClient } from "$shared/api";
import {
	analyticsTopics,
	analyticsSubscriptions,
	processedTopics,
	readingSubscriptions,
	type ProcessedTopicName,
} from "$shared/realtime";
import type { AggregatedReading, ForecastResult, Reading, ReadingQuery } from "$shared/types";
import {
	alignSensorData,
	calculateCorrelation,
	type CorrelationMethod,
	type SensorData,
} from "$features/analytics/correlation_math";
import {
	createAnalyticsChartRegistry,
	type AnalyticsChartRegistry,
} from "./chart.registry";
import { buildCorrelationMatrixSpec } from "./plots/correlation_matrix.plot";
import { buildCorrelationScatterSpec } from "./plots/correlation_scatter.plot";
import { analyticsChartConfigByTopic } from "./plots/analytics_chart.config";
import { buildTimeSeriesSpec } from "./plots/time_series.plot";
import type {
	AnalyticsSeriesKey,
	SeriesVisibility,
} from "./plots/time_series.transforms";
import {
	buildProcessedReadingCacheKey,
	mergeProcessedReadingIntoCache,
	normalizeProcessedReadings,
} from "$shared/readings/processed_readings";
import {
	filterReadingsByTopic,
	filterSensorDataByTimeRange,
	getReadingTopic,
	mapAggregatedReadings,
	mapRawReadings,
} from "./series.transforms";
import {
	buildReadingQuery,
	getTimeWindow,
	type AnalyticsTimeView,
} from "./time.utils";

export type LoadingState = "idle" | "loading" | "loaded" | "error" | "partial";

/**
 * Represents an error state with a user-friendly message and the original error.
 */
export type ErrorState = {
	message: string;
	cause: Error;
};

/**
 * Data captured during chart hover events, including Data Quality (DQ) scores.
 */
type HoverData = {
	dqScore: number | null;
	flagsText: string;
};

/**
 * Map of sensor data indexed by topic name, used for correlation calculations.
 */
type CorrelationData = Record<ProcessedTopicName, SensorData>;

/**
 * Represents a point in a Plotly chart during hover events.
 */
type PlotlyHoverPoint = { customdata?: unknown };

/**
 * Configuration for correlation plots.
 */
type CorrelationPlotConfig = Record<string, unknown>;

export type CorrelationSummary = {
	coefficient: number;
	sampleCount: number;
	method: CorrelationMethod;
	sensor1Label: string;
	sensor2Label: string;
	strength: "none" | "weak" | "moderate" | "strong";
	direction: "positive" | "negative" | "none";
};

/**
 * Represents a subscription that can be cleaned up.
 */
type SubscriptionLike = {
	cleanup: () => void;
};

/**
 * Port interface for fetching and subscribing to sensor readings.
 * Decouples the store from the specific API implementation.
 */
export interface AnalyticsReadingsPort {
	/** Loads historical data based on a time window query */
	loadHistoricalReadings(query: ReadingQuery): Promise<void>;
	/** Returns all currently cached raw readings */
	getCachedReadings(): Reading[];
	/** Returns cached aggregated readings for a specific topic */
	getCachedAggregatedReadings(topic: string): AggregatedReading[];
	/** Subscribes to incoming realtime readings */
	subscribeToLiveReadings(
		handler: (reading: Reading) => void,
	): SubscriptionLike;
	/** Optional cleanup method */
	destroy?(): void;
}

export interface AnalyticsForecastsPort {
  loadForecasts(query: ReadingQuery): Promise<void>;
  getCachedForecasts(topic: string): ForecastResult[];
  subscribeToLiveForecasts?(handler: (forecast: ForecastResult) => void): SubscriptionLike;
  destroy?(): void;
}

/**
 * Dependencies for the Analytics store, allowing for dependency injection in tests.
 */
export interface AnalyticsStoreDependencies {
	readingsPort?: AnalyticsReadingsPort;
	forecastsPort?: AnalyticsForecastsPort;
	chartRegistry?: AnalyticsChartRegistry;
	now?: () => number;
}

/**
 * The public API of the Analytics store.
 */
export interface AnalyticsStore {
	/** The currently selected time window (day, week, month) */
	currentTimeView: Readable<AnalyticsTimeView>;
	/** Current data loading status */
	loadingState: Readable<LoadingState>;
	/** Any error encountered during data operations */
	errorState: Readable<ErrorState | null>;
	/** Visibility toggles for different data series (raw, processed, etc.) */
	visibleSeries: Readable<SeriesVisibility>;
	/** Whether the UI is in correlation analysis mode */
	correlationMode: Readable<boolean>;
	/** Data for the currently hovered point across all charts */
	hoverData: Readable<HoverData>;

	/** Initializes the store by loading initial data and starting live updates */
	initialize(): Promise<void>;
	/** Cleans up subscriptions and chart instances */
	destroy(): void;

	/** Connects HTML elements to the chart registry for rendering */
	initializeCharts(elementRefs: Record<string, HTMLElement | null>): void;
	/** Changes the active time window and reloads data */
	setTimeView(view: AnalyticsTimeView): Promise<void>;

	/** Resumes realtime data processing */
	startLiveUpdates(): void;
	/** Pauses realtime data processing */
	stopLiveUpdates(): void;

	/** Toggles visibility of a specific series (e.g., 'raw_value') across all charts */
	toggleSeriesVisibility(series: AnalyticsSeriesKey, visible: boolean): void;
	/** Switches to correlation mode for the specified sensors */
	enterCorrelationMode(sensors: string[]): void;
	/** Returns to standard trend view */
	exitCorrelationMode(): void;

	/** Internal handler for Plotly hover events */
	handlePlotHover(point: PlotlyHoverPoint): void;
	/** Internal handler for Plotly unhover events */
	handlePlotUnhover(): void;

	/** Creates a scatter plot comparing two sensors */
	createScatterPlot(
		id: string,
		element: HTMLElement,
		sensor1: ProcessedTopicName,
		sensor2: ProcessedTopicName,
		method: CorrelationMethod,
	): Promise<CorrelationSummary>;
	/** Creates a correlation matrix for all primary sensors */
	createCorrelationMatrix(
		id: string,
		element: HTMLElement,
		selectedPair: [ProcessedTopicName, ProcessedTopicName],
		method: CorrelationMethod,
	): Promise<void>;
}

const CORRELATION_CONFIG: CorrelationPlotConfig = {
	displayModeBar: true,
	responsive: true,
	displaylogo: false,
};

const SENSOR_LABELS: Partial<Record<ProcessedTopicName, string>> = {
	[processedTopics.temperature]: "Temperature (°C)",
	[processedTopics.humidity]: "Humidity (%)",
	[processedTopics.soilMoisture]: "Soil Moisture (%)",
	[processedTopics.lightIntensity]: "Light Intensity (lux)",
	[processedTopics.greenRatio]: "Green Ratio",
	[processedTopics.leafCount]: "Leaf Count",
	[processedTopics.plantHeight]: "Plant Height (cm)",
};

const forecastMetricByTopic: Partial<Record<ProcessedTopicName, string>> = {
  [processedTopics.temperature]: "temperature",
  [processedTopics.humidity]: "humidity",
  [processedTopics.soilMoisture]: "soil_moisture",
  [processedTopics.lightIntensity]: "light_intensity",
  [processedTopics.greenRatio]: "green_ratio",
  [processedTopics.leafCount]: "leaf_count",
  [processedTopics.plantHeight]: "plant_height",
};

const forecastTopicByMetric = Object.entries(forecastMetricByTopic).reduce<Record<string, string>>(
	(map, [topic, metric]) => {
		if (metric) {
			map[metric] = topic;
		}
		return map;
	},
	{},
);

function defaultSeriesVisibility(): SeriesVisibility {
	return {
		value: true,
		raw_value: true,
		calibrated_value: true,
		normalized_value: true,
		forecast: true,
	};
}

function toErrorState(error: unknown): ErrorState {
	if (error instanceof Error) {
		return {
			message: error.message,
			cause: error,
		};
	}

	return {
		message: String(error),
		cause: new Error(String(error)),
	};
}

function normalizeForecast(payload: unknown): ForecastResult | null {
	if (!payload || typeof payload !== "object") {
		return null;
	}

	const record = payload as Partial<ForecastResult> & Record<string, unknown>;
	if (typeof record.metric !== "string") {
		return null;
	}

	const time = Number(record.time);
	const predictedValue = Number(record.predicted_value);
	if (!Number.isFinite(time) || !Number.isFinite(predictedValue)) {
		return null;
	}

	return {
		plant_id: Number(record.plant_id),
		time,
		correlation_id: typeof record.correlation_id === "string" ? record.correlation_id : "",
		metric: record.metric,
		horizon_seconds: Number(record.horizon_seconds),
		predicted_value: predictedValue,
		unit: typeof record.unit === "string" ? record.unit : "",
		model_metadata: record.model_metadata as ForecastResult["model_metadata"],
		features_used: Array.isArray(record.features_used) ? record.features_used : undefined,
		inference_metadata: record.inference_metadata as ForecastResult["inference_metadata"],
	};
}

function getCorrelationStrength(
	coefficient: number,
): CorrelationSummary["strength"] {
	const magnitude = Math.abs(coefficient);
	if (magnitude < 0.2) {
		return "none";
	}
	if (magnitude < 0.4) {
		return "weak";
	}
	if (magnitude < 0.7) {
		return "moderate";
	}
	return "strong";
}

function getCorrelationDirection(
	coefficient: number,
): CorrelationSummary["direction"] {
	if (Math.abs(coefficient) < 0.2) {
		return "none";
	}
	return coefficient > 0 ? "positive" : "negative";
}

/**
 * Helper to create a default readings port that manages data caching and live subscriptions.
 */
function createDefaultReadingsPort(): AnalyticsReadingsPort {
	let cachedReadings: Reading[] = [];
	const aggregatedByTopic = new Map<string, AggregatedReading[]>();
	const liveReadingCounts = new Map<string, number>();
	const liveReadingKeys = new Set<string>();
	let liveToken: SubscriptionLike | null = null;

	function pruneExpiredReadings(oneDayAgo: number): void {
		cachedReadings = cachedReadings.filter((reading) => reading.time > oneDayAgo);
		const activeKeys = new Set(
			cachedReadings
				.map((reading) => buildProcessedReadingCacheKey(reading))
				.filter((key): key is string => key !== null),
		);

		for (const key of liveReadingCounts.keys()) {
			if (!activeKeys.has(key)) {
				liveReadingCounts.delete(key);
				liveReadingKeys.delete(key);
			}
		}
	}

	function getRetainedLiveReadings(): Reading[] {
		return cachedReadings.filter((reading) => {
			const key = buildProcessedReadingCacheKey(reading);
			return key !== null && liveReadingKeys.has(key);
		});
	}

	function mergeRetainedLiveReadings(readings: Reading[]): void {
		for (const reading of readings) {
			const key = buildProcessedReadingCacheKey(reading);
			if (!key || cachedReadings.some((candidate) => buildProcessedReadingCacheKey(candidate) === key)) {
				continue;
			}

			cachedReadings = mergeProcessedReadingIntoCache(
				cachedReadings,
				liveReadingCounts,
				reading,
			);
			liveReadingKeys.add(key);
		}
	}

	/** Fetches historical data from the API and updates the local cache */
	async function loadHistoricalReadings(query: ReadingQuery): Promise<void> {
		const retainedLiveReadings = getRetainedLiveReadings();
		if (query.window === "1h") {
			const aggregatedReadings =
				await dbClient.fetchAggregatedReadings(query);
			aggregatedByTopic.clear();

			for (const reading of aggregatedReadings) {
				const topic = typeof reading.topic === "string" ? reading.topic : "";
				if (!aggregatedByTopic.has(topic)) {
					aggregatedByTopic.set(topic, []);
				}
				aggregatedByTopic.get(topic)?.push(reading);
			}

			return;
		}

		aggregatedByTopic.clear();
		liveReadingCounts.clear();
		const normalizedCache = normalizeProcessedReadings(
			await dbClient.fetchRawReadings(query),
		);
		cachedReadings = normalizedCache.readings;
		for (const [key, count] of normalizedCache.counts) {
			liveReadingCounts.set(key, count);
		}
		mergeRetainedLiveReadings(retainedLiveReadings);
	}

	/** Connects to the realtime data stream */
	function subscribeToLiveReadings(
		handler: (reading: Reading) => void,
	): SubscriptionLike {
		liveToken?.cleanup();
		liveToken = readingSubscriptions.subscribeToProcessedReadings((payload) => {
			const reading = payload as Reading;
			const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
			cachedReadings = mergeProcessedReadingIntoCache(
				cachedReadings,
				liveReadingCounts,
				reading,
			);
			const key = buildProcessedReadingCacheKey(reading);
			if (key) {
				liveReadingKeys.add(key);
			}

			pruneExpiredReadings(oneDayAgo);
			handler(reading);
		});

		return {
			cleanup: () => {
				if (!liveToken) {
					return;
				}
				liveToken.cleanup();
				liveToken = null;
			},
		};
	}

	/** Clears all cached data and subscriptions */
	function destroy(): void {
		liveToken?.cleanup();
		liveToken = null;
		cachedReadings = [];
		aggregatedByTopic.clear();
		liveReadingCounts.clear();
		liveReadingKeys.clear();
	}

	return {
		loadHistoricalReadings,
		getCachedReadings: () => cachedReadings,
		getCachedAggregatedReadings: (topic) => aggregatedByTopic.get(topic) ?? [],
		subscribeToLiveReadings,
		destroy,
	};
}

function createDefaultForecastsPort(): AnalyticsForecastsPort {
  const forecastsByTopic = new Map<string, ForecastResult[]>();
  let liveToken: SubscriptionLike | null = null;

  async function loadForecasts(query: ReadingQuery): Promise<void> {
    forecastsByTopic.clear();
    const entries = await Promise.all(
      Object.entries(forecastMetricByTopic).map(async ([topic, metric]) => {
        const forecasts = await dbClient.fetchForecastHistory({
          plantId: query.plantId ?? 1,
          metric,
          since: query.since,
          until: query.until,
          limit: 200,
        });
        return [
          topic,
          forecasts
            .map(normalizeForecast)
            .filter((forecast): forecast is ForecastResult => forecast !== null),
        ] as const;
      }),
    );

    for (const [topic, forecasts] of entries) {
      forecastsByTopic.set(topic, forecasts);
    }
  }

  function mergeForecast(forecast: ForecastResult): string | null {
    const topic = forecastTopicByMetric[forecast.metric];
    if (!topic) {
      return null;
    }

    const forecasts = forecastsByTopic.get(topic) ?? [];
    forecastsByTopic.set(
      topic,
      [...forecasts, forecast].sort((left, right) => left.time - right.time),
    );
    return topic;
  }

  function subscribeToLiveForecasts(handler: (forecast: ForecastResult) => void): SubscriptionLike {
    liveToken?.cleanup();
    liveToken = analyticsSubscriptions.subscribeToForecastResults((payload) => {
      const forecast = normalizeForecast(payload);
      if (!forecast || !mergeForecast(forecast)) {
        return;
      }

      handler(forecast);
    });

    return {
      cleanup: () => {
        liveToken?.cleanup();
        liveToken = null;
      },
    };
  }

  return {
    loadForecasts,
    getCachedForecasts: (topic) => forecastsByTopic.get(topic) ?? [],
    subscribeToLiveForecasts,
    destroy: () => {
      liveToken?.cleanup();
      liveToken = null;
      forecastsByTopic.clear();
    },
  };
}

function createEmptyForecastsPort(): AnalyticsForecastsPort {
  return {
    loadForecasts: async () => {},
    getCachedForecasts: () => [],
  };
}

/**
 * Factory function to create an Analytics store instance.
 * Encapsulates state management, data fetching, and chart rendering logic.
 *
 * @param dependencies Optional overrides for testing or custom behavior.
 * @returns An object implementing the AnalyticsStore interface.
 */
export function createAnalyticsStore(
	dependencies: AnalyticsStoreDependencies = {},
): AnalyticsStore {
	const readingsPort = dependencies.readingsPort ?? createDefaultReadingsPort();
	const forecastsPort = dependencies.forecastsPort ?? (
		dependencies.readingsPort ? createEmptyForecastsPort() : createDefaultForecastsPort()
	);
	const chartRegistry =
		dependencies.chartRegistry ?? createAnalyticsChartRegistry();
	const now = dependencies.now ?? (() => Date.now());

	// Reactive state containers
	const currentTimeViewData = writable<AnalyticsTimeView>("day");
	const loadingStateData = writable<LoadingState>("idle");
	const errorStateData = writable<ErrorState | null>(null);
	const visibleSeriesData = writable<SeriesVisibility>(
		defaultSeriesVisibility(),
	);
	const correlationModeData = writable<boolean>(false);
	const hoverDataData = writable<HoverData>({ dqScore: null, flagsText: "" });

	/** Tracks the current load request to prevent race conditions */
	let activeLoadRequestId = 0;
	const loadedTimeViews = new Set<AnalyticsTimeView>();
	let cachedTimeView: AnalyticsTimeView | null = null;
	/** Active subscription for realtime data */
	let liveSubscription: SubscriptionLike | null = null;
	let liveForecastSubscription: SubscriptionLike | null = null;

	/** Checks if the cache contains data relevant to the current query */
	function hasCachedDataForQuery(query: ReadingQuery): boolean {
		if (query.window === "raw") {
			return readingsPort.getCachedReadings().length > 0;
		}

		return analyticsTopics.some(
			(topic) => readingsPort.getCachedAggregatedReadings(topic).length > 0,
		);
	}

	/** Renders a specific time-series chart using cached data */
	function renderTimeSeriesChart(
		topic: string,
		since: number,
		until: number,
	): void {
		const chart = chartRegistry.get(topic);
		const chartConfig = analyticsChartConfigByTopic[topic];
		if (!chart || !chartConfig) {
			return;
		}

		const timeSeriesSpec = buildTimeSeriesSpec({
			readings: filterReadingsByTopic(
				readingsPort.getCachedReadings(),
				topic,
			),
			aggregates: readingsPort.getCachedAggregatedReadings(topic),
			forecasts: forecastsPort.getCachedForecasts(topic),
			layout: chartConfig.layout,
			config: chartConfig.config,
			visibleSeries: get(visibleSeriesData),
			timeRange: { start: new Date(since), end: new Date(until) },
			secondaryMetrics: ["normalized_value"],
			revision: `${topic}:${get(currentTimeViewData)}`,
		});
		void chart.render(timeSeriesSpec);
	}

	/** Refreshes all active time-series charts */
	function renderCurrentReadingsToCharts(
		_readings: Reading[],
		since: number,
		until: number,
	): void {
		chartRegistry.forEach("trends", (topic) => {
			renderTimeSeriesChart(topic, since, until);
		});
	}

	/** Handles rendering of a single incoming realtime reading */
	function renderLiveReading(reading: Reading): void {
		const topic = getReadingTopic(reading);
		if (!topic) {
			return;
		}
		const { since, until } = getTimeWindow(get(currentTimeViewData), now());
		renderTimeSeriesChart(topic, since, until);
	}

	function renderLiveForecast(forecast: ForecastResult): void {
		const topic = forecastTopicByMetric[forecast.metric];
		if (!topic) {
			return;
		}

		const { since, until } = getTimeWindow(get(currentTimeViewData), now());
		renderTimeSeriesChart(topic, since, until);
	}

	/** Retrieves sensor data from cache, preferring aggregated data if available */
	function getSensorDataFromCache(topicName: ProcessedTopicName): SensorData {
		const aggregatedReadings =
			readingsPort.getCachedAggregatedReadings(topicName);
		if (aggregatedReadings.length > 0) {
			return mapAggregatedReadings(aggregatedReadings);
		}

		const rawReadings = filterReadingsByTopic(
			readingsPort.getCachedReadings(),
			topicName,
		);
		return mapRawReadings(rawReadings);
	}

	/** Prepares and filters sensor data for correlation analysis */
	function prepareCorrelationData(
		topicNames: ProcessedTopicName[],
	): CorrelationData {
		const { since, until } = getTimeWindow(get(currentTimeViewData), now());
		const data = {} as CorrelationData;

		for (const topicName of topicNames) {
			const sensorData = getSensorDataFromCache(topicName);
			data[topicName] = filterSensorDataByTimeRange(sensorData, since, until);
		}

		const hasData = topicNames.some(
			(topicName) => data[topicName].values.length > 0,
		);
		if (!hasData) {
			const operationError = get(errorStateData);
			if (operationError) {
				throw new Error(operationError.message);
			}

			throw new Error("No data available for correlation charts");
		}

		return data;
	}

	function getSensorLabel(topic: ProcessedTopicName): string {
		return SENSOR_LABELS[topic] ?? topic;
	}

	/** Initializes the store by loading initial data and starting live updates */
	async function initialize(): Promise<void> {
		try {
			await setTimeView(get(currentTimeViewData));
		} catch (error) {
			console.error("Failed to load historical readings during initialization:", error);
		} finally {
			startLiveUpdates();
		}
	}

	/** Cleans up subscriptions and chart instances */
	function destroy(): void {
		chartRegistry.destroy();

		activeLoadRequestId += 1;
		correlationModeData.set(false);
		handlePlotUnhover();
		loadingStateData.set("idle");
		errorStateData.set(null);
	}

	/** Connects HTML elements to the chart registry for rendering */
	function initializeCharts(
		elementRefs: Record<string, HTMLElement | null>,
	): void {
		for (const [topic, element] of Object.entries(elementRefs)) {
			if (!element || !analyticsChartConfigByTopic[topic]) {
				continue;
			}

			chartRegistry.register(
				topic,
				"trends",
				element,
				(point) => handlePlotHover(point as PlotlyHoverPoint),
				handlePlotUnhover,
			);
		}

		const { since, until } = getTimeWindow(get(currentTimeViewData), now());
		renderCurrentReadingsToCharts(
			readingsPort.getCachedReadings(),
			since,
			until,
		);
	}

	/** Internal handler for Plotly hover events, extracting DQ scores and flags from customdata */
	function handlePlotHover(point: PlotlyHoverPoint): void {
		const customdata = point?.customdata;
		if (!Array.isArray(customdata)) {
			// If customdata is not in the expected format, reset hover data and exit
			hoverDataData.set({ dqScore: null, flagsText: "" });
			return;
		}

		const dqScore = Number(customdata[0]);
		hoverDataData.set({
			dqScore: Number.isFinite(dqScore) ? dqScore : null,
			flagsText: String(customdata[1] ?? ""),
		});
	}

	/** Internal handler for Plotly unhover events, resetting hover data */
	function handlePlotUnhover(): void {
		hoverDataData.set({ dqScore: null, flagsText: "" });
	}

	/** Changes the active time window and reloads data accordingly */
	async function setTimeView(view: AnalyticsTimeView): Promise<void> {
		currentTimeViewData.set(view);
		loadingStateData.set("loading");
		errorStateData.set(null);

		const requestId = ++activeLoadRequestId;
		const query = buildReadingQuery(view, now());

		if (
			loadedTimeViews.has(view) &&
			cachedTimeView === view &&
			hasCachedDataForQuery(query)
		) {
			renderCurrentReadingsToCharts(
				readingsPort.getCachedReadings(),
				query.since ?? now(),
				query.until ?? now(),
			);
			loadingStateData.set("loaded");
			return;
		}

		try {
			await Promise.all([
				readingsPort.loadHistoricalReadings(query),
				forecastsPort.loadForecasts(query),
			]);
			if (requestId !== activeLoadRequestId) {
				return;
			}

			loadedTimeViews.add(view);
			cachedTimeView = view;
			renderCurrentReadingsToCharts(
				readingsPort.getCachedReadings(),
				query.since ?? now(),
				query.until ?? now(),
			);
			loadingStateData.set("loaded");
		} catch (error) {
			if (requestId !== activeLoadRequestId) {
				return;
			}

			const operationError = toErrorState(error);
			const hasCachedData = hasCachedDataForQuery(query);
			loadingStateData.set(hasCachedData ? "partial" : "error");
			errorStateData.set(operationError);

			renderCurrentReadingsToCharts(
				readingsPort.getCachedReadings(),
				query.since ?? now(),
				query.until ?? now(),
			);

			throw error;
		}
	}

	function startLiveUpdates(): void {
		if (!liveSubscription) {
			liveSubscription = readingsPort.subscribeToLiveReadings((reading) => {
				renderLiveReading(reading);
			});
		}

		if (!liveForecastSubscription && forecastsPort.subscribeToLiveForecasts) {
			liveForecastSubscription = forecastsPort.subscribeToLiveForecasts((forecast) => {
				renderLiveForecast(forecast);
			});
		}
	}

	function stopLiveUpdates(): void {
		liveSubscription?.cleanup();
		liveSubscription = null;
		liveForecastSubscription?.cleanup();
		liveForecastSubscription = null;
	}

	/** Toggles visibility of a specific series (e.g., 'raw_value') across all charts and re-renders */
	function toggleSeriesVisibility(
		series: AnalyticsSeriesKey,
		visible: boolean,
	): void {
		// Update the visibility state for the specified series
		visibleSeriesData.update((current) => ({ ...current, [series]: visible }));

		const { since, until } = getTimeWindow(get(currentTimeViewData), now());
		renderCurrentReadingsToCharts(
			readingsPort.getCachedReadings(),
			since,
			until,
		);
	}

	function enterCorrelationMode(_sensors: string[]): void {
		correlationModeData.set(true);
	}

	function exitCorrelationMode(): void {
		correlationModeData.set(false);
	}

	/** Creates a scatter plot comparing two sensors, including correlation coefficient and DQ highlights */
	async function createScatterPlot(
		id: string,
		element: HTMLElement,
		sensor1: ProcessedTopicName,
		sensor2: ProcessedTopicName,
		method: CorrelationMethod,
	): Promise<CorrelationSummary> {
		const data = prepareCorrelationData([sensor1, sensor2]);
		const aligned = alignSensorData(data[sensor1], data[sensor2]);
		if (aligned.x.length === 0) {
			throw new Error("No data available for correlation charts");
		}
		const coefficient = calculateCorrelation(aligned.x, aligned.y, method);
		const sensor1Label = getSensorLabel(sensor1);
		const sensor2Label = getSensorLabel(sensor2);
		const summary: CorrelationSummary = {
			coefficient,
			sampleCount: aligned.x.length,
			method,
			sensor1Label,
			sensor2Label,
			strength: getCorrelationStrength(coefficient),
			direction: getCorrelationDirection(coefficient),
		};

		const chart = chartRegistry.register(
			id,
			"correlation-scatter",
			element,
			(point) => handlePlotHover(point as PlotlyHoverPoint),
			handlePlotUnhover,
		);
		await chart.render({
			...buildCorrelationScatterSpec({
				x: aligned.x,
				y: aligned.y,
				dq1: aligned.dq1,
				dq2: aligned.dq2,
				sensor1Label,
				sensor2Label,
				correlation: coefficient,
				method,
				sampleCount: aligned.x.length,
			}),
			config: CORRELATION_CONFIG,
		});

		return summary;
	}

	/** Creates a correlation matrix for all primary sensors, calculating pairwise correlations and rendering a heatmap */
	async function createCorrelationMatrix(
		id: string,
		element: HTMLElement,
		selectedPair: [ProcessedTopicName, ProcessedTopicName],
		method: CorrelationMethod,
	): Promise<void> {
		const topics: ProcessedTopicName[] = [...analyticsTopics];
		const data = prepareCorrelationData(topics);
		const labels = topics.map((topic) => getSensorLabel(topic));

		const matrix: number[][] = [];
		for (let i = 0; i < topics.length; i += 1) {
			const row: number[] = [];
			for (let j = 0; j < topics.length; j += 1) {
				if (i === j) {
					row.push(1);
					continue;
				}

				const aligned = alignSensorData(data[topics[i]], data[topics[j]]);
				row.push(calculateCorrelation(aligned.x, aligned.y, method));
			}
			matrix.push(row);
		}

		const selectedPairLabels: [string, string] = [
			getSensorLabel(selectedPair[0]),
			getSensorLabel(selectedPair[1]),
		];

		const chart = chartRegistry.register(
			id,
			"correlation-matrix",
			element,
			(point) => handlePlotHover(point as PlotlyHoverPoint),
			handlePlotUnhover,
		);
		await chart.render({
			...buildCorrelationMatrixSpec({
				matrix,
				labels,
				selectedPair: selectedPairLabels,
				method,
			}),
			config: CORRELATION_CONFIG,
		});
	}

	return {
		currentTimeView: derived(currentTimeViewData, ($value) => $value),
		loadingState: derived(loadingStateData, ($value) => $value),
		errorState: derived(errorStateData, ($value) => $value),
		visibleSeries: derived(visibleSeriesData, ($value) => $value),
		correlationMode: derived(correlationModeData, ($value) => $value),
		hoverData: derived(hoverDataData, ($value) => $value),
		initialize,
		destroy,
		initializeCharts,
		setTimeView,
		startLiveUpdates,
		stopLiveUpdates,
		toggleSeriesVisibility,
		enterCorrelationMode,
		exitCorrelationMode,
		handlePlotHover,
		handlePlotUnhover,
		createScatterPlot,
		createCorrelationMatrix,
	};
}

export const analyticsStore = createAnalyticsStore();

export type {
	AnalyticsSeriesKey,
	AnalyticsTimeView,
	HoverData,
	SeriesVisibility,
};
