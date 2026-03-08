/**
 * @file Manages the real-time monitoring charts on the dashboard.
 * This module uses the Plotly.js library to create and update charts for
 * temperature, humidity, soil moisture, and light intensity. It subscribes
 * to the central data store to receive both real-time and historical data.
 */
import { DataType, plantStore } from "../store.js";

const SERIES = [
    { key: "value", label: "processed", defaultColor: "#17BECF" },
    { key: "raw_value", label: "raw", defaultColor: "#7f7f7f" },
    { key: "calibrated_value", label: "calibrated", defaultColor: "#1f77b4" },
    { key: "normalized_value", label: "normalized", defaultColor: "#ff7f0e" },
];

/**
 * Converts a data quality score (0–1) to a color for visualization.
 * - 0 maps to red, 0.5 to yellow, 1 to green.
 * - If the score is invalid, returns gray.
 *
 * @param {number|string} dqScore - The data quality score (expected 0–1).
 * @returns {string} An RGB color string.
 */
function dqToColor(dqScore) {
    // Convert input to a number
    const dq = Number(dqScore);
    // If not a finite number, return gray
    if (!Number.isFinite(dq)) return "#7f7f7f";
    if (dq <= 0.5) {
        // Interpolate from red (0) to yellow (0.5)
        const t = dq / 0.5;
        const r = 255;
        const g = Math.round(255 * t);
        const b = 0;
        return `rgb(${r},${g},${b})`;
    }

    // Interpolate from yellow (0.5) to green (1)
    const t = (dq - 0.5) / 0.5;
    const r = Math.round(255 * (1 - t));
    const g = 255;
    const b = 0;
    return `rgb(${r},${g},${b})`;
}

/**
 * Formats a flags object into a human-readable string listing violated flags.
 * - Ignores the "valid_data_point" flag.
 * - Only includes flags with a value of true.
 *
 * @param {Object} flags - An object with flag names as keys and booleans as values.
 * @returns {string} A string like "flags: flag1, flag2" or "" if no violations.
 */
function formatFlags(flags) {
    // Return empty string if flags is not an object
    if (!flags || typeof flags !== "object") return "";
    // Collect all flag names (except "valid_data_point") where value is true
    const violations = Object.entries(flags)
        .filter(([key, value]) => key !== "valid_data_point" && value === true)
        .map(([key]) => key);
    // Return formatted string if there are violations
    return violations.length ? `flags: ${violations.join(", ")}` : "";
}

/**
 * Updates the DOM to display the current data quality score and any flags.
 * - If dqScore is invalid, displays a dash and clears flags.
 * - Otherwise, shows the score (2 decimals) and flags text.
 *
 * @param {number|string} dqScore - The data quality score.
 * @param {string} flagsText - The formatted flags string.
 */
function updateMonitoringDqDisplay(dqScore, flagsText) {
    // Get DOM elements for displaying DQ score and flags
    const dqElement = document.getElementById("monitoring-dq-score");
    const flagsElement = document.getElementById("monitoring-flags");
    if (!dqElement || !flagsElement) return;

    const dq = Number(dqScore);
    if (!Number.isFinite(dq)) {
        // Show dash if score is invalid
        dqElement.textContent = "—";
        flagsElement.textContent = "";
        return;
    }

    // Show score (rounded to 2 decimals) and flags
    dqElement.textContent = dq.toFixed(2);
    flagsElement.textContent = flagsText || "";
}

/**
 * Safely extracts a numeric value from a reading object.
 * - Returns null if the value is missing or not a finite number.
 *
 * @param {Object} reading - The data object (e.g., a sensor reading).
 * @param {string} key - The property name to extract.
 * @returns {number|null} The numeric value, or null if invalid.
 */
function getSeriesValue(reading, key) {
    const value = Number(reading?.[key]);
    return Number.isFinite(value) ? value : null;
}

/**
 * Determine how many points to keep in each Plotly trace based on the selected
 * time period. This caps memory growth from real-time streaming updates.
 *
 * This limit applies only to incremental Plotly.extendTraces calls. Historical
 * ranges are fetched separately and can contain more points.
 *
 * @param {string} timePeriod - One of: "1h", "24h", "7d", "30d".
 * @returns {number} Maximum points to retain per trace.
 */
function getMaxPointsForTimePeriod(timePeriod) {
    switch (timePeriod) {
        case "1h":
            return 600;
        case "24h":
            return 1500;
        case "7d":
            return 3000;
        case "30d":
            return 6000;
        default:
            return 1500;
    }
}

/**
 * @const {Object} CHART_CONFIG
 * @description A configuration object that defines the properties for each chart,
 * such as the DOM element ID, title, y-axis title, and line color.
 */
const CHART_CONFIG = {
    [DataType.TEMPERATURE]: {
        elementId: "temp-chart",
        title: { text: "Temperature" },
        yAxisTitle: { text: "Value (°C)" },
        lineColor: "#17BECF",
    },
    [DataType.HUMIDITY]: {
        elementId: "humidity-chart",
        title: { text: "Humidity" },
        yAxisTitle: { text: "Value (%)" },
        lineColor: "#17BECF",
        yAxisRange: [0, 100],
    },
    [DataType.SOIL_MOISTURE]: {
        elementId: "soil-chart",
        title: { text: "Soil Moisture" },
        yAxisTitle: { text: "Value (%)" },
        lineColor: "#17BECF",
        yAxisRange: [0, 100],
    },
    [DataType.LIGHT]: {
        elementId: "light-chart",
        title: { text: "Light Intensity" },
        yAxisTitle: { text: "Value (lux)" },
        lineColor: "#17BECF",
    },
};

/**
 * Initializes the real-time monitoring charts on the dashboard.
 * - Sets up Plotly charts for each sensor type.
 * - Subscribes to the plantStore for real-time and historical data updates.
 * - Handles toggling of chart series visibility.
 * - Handles hover events to display data quality and flags.
 * - Handles time period selection for historical data.
 */
export function initRealTimeMonitoring() {
    console.log("Initializing real-time monitoring charts...");

    // Get chart DOM elements for each sensor type
    const charts = {
        [DataType.TEMPERATURE]: document.getElementById("temp-chart"),
        [DataType.HUMIDITY]: document.getElementById("humidity-chart"),
        [DataType.SOIL_MOISTURE]: document.getElementById("soil-chart"),
        [DataType.LIGHT]: document.getElementById("light-chart"),
    };

    // Create initial empty plots for all charts
    initPlots();

    let currentTimePeriod = "24h"; // Default time period for historical data
    let maxPoints = getMaxPointsForTimePeriod(currentTimePeriod);

    // Track visibility state of each series (all visible by default)
    const seriesVisibility = Object.fromEntries(
        SERIES.map((s) => [s.key, true]),
    );

    /**
     * Applies the current series visibility settings to all charts.
     * Uses Plotly.restyle to show/hide traces based on user toggles.
     */
    function applySeriesVisibility() {
        for (const dataType of DataType.SENSORS) {
            const chartElement = charts[dataType];
            const visibility = SERIES.map((s) => seriesVisibility[s.key]);
            Plotly.restyle(chartElement, { visible: visibility });
        }
    }

    /**
     * Binds hover and unhover events to a chart element.
     * On hover, displays data quality and flags for the hovered point.
     * On unhover, clears the display.
     * @param {HTMLElement} chartElement - The Plotly chart DOM element.
     */
    function bindDqHover(chartElement) {
        chartElement.on("plotly_hover", (eventData) => {
            const point = eventData?.points?.[0];
            const customdata = point?.customdata;
            if (Array.isArray(customdata)) {
                updateMonitoringDqDisplay(customdata[0], customdata[1]);
            } else {
                updateMonitoringDqDisplay(null, "");
            }
        });
        chartElement.on("plotly_unhover", () => {
            updateMonitoringDqDisplay(null, "");
        });
    }

    // Attach hover handlers to all sensor charts
    for (const dataType of DataType.SENSORS) {
        bindDqHover(charts[dataType]);
    }

    // Set up event listeners for toggling trace (series) visibility
    const traceToggles = document.querySelectorAll(
        'input[name="trace-toggle"]',
    );
    for (const toggle of traceToggles) {
        toggle.addEventListener("change", (event) => {
            const key = event.target.value;
            seriesVisibility[key] = event.target.checked;
            applySeriesVisibility();
        });
    }

    /**
     * Creates a handler for plantStore subscription for a specific chart.
     * Handles both historical (full data replacement) and real-time (append) updates.
     * @param {DataType} dataType - The sensor type.
     * @param {HTMLElement} chartElement - The Plotly chart DOM element.
     * @returns {function} Handler for incoming data.
     */
    const createSubscriptionHandler = (dataType, chartElement) => {
        return (data) => {
            if (data.type === "historical") {
                // Replace chart data with historical data
                Plotly.purge(chartElement);
                const chartConfig = getChartConfigForDataType(dataType);

                if (data.data.length === 0) {
                    console.error("No data received for historical data");
                    initPlot(chartConfig, [], [], currentTimePeriod);
                    return;
                }
                // Prepare x (time) and y (series) values
                const xValues = data.data.map((item) => new Date(item.time));
                const seriesY = Object.fromEntries(
                    SERIES.map((s) => [s.key, []]),
                );
                const processedColors = [];
                const processedCustomData = [];

                // Populate y-values and colors
                for (const item of data.data) {
                    for (const series of SERIES) {
                        seriesY[series.key].push(
                            getSeriesValue(item, series.key),
                        );
                    }
                    processedColors.push(dqToColor(item.dq_score));
                    processedCustomData.push([
                        Number(item.dq_score),
                        formatFlags(item.flags),
                    ]);
                }

                // Initialize chart with new data
                initPlot(
                    chartConfig,
                    xValues,
                    seriesY.value,
                    currentTimePeriod,
                );

                // Update each trace with its y-values
                Plotly.restyle(chartElement, { y: [seriesY.value] }, [0]);
                Plotly.restyle(chartElement, { y: [seriesY.raw_value] }, [1]);
                Plotly.restyle(
                    chartElement,
                    { y: [seriesY.calibrated_value] },
                    [2],
                );
                Plotly.restyle(
                    chartElement,
                    { y: [seriesY.normalized_value] },
                    [3],
                );

                // Set marker color and hovertemplate for the main (processed) trace
                Plotly.restyle(
                    chartElement,
                    {
                        "marker.color": [processedColors],
                        customdata: [processedCustomData],
                        hovertemplate: [
                            "%{y}<br>DQ: %{customdata[0]:.2f}<br>%{customdata[1]}<extra></extra>",
                        ],
                    },
                    [0],
                );
                // Set hovertemplate for other traces
                Plotly.restyle(
                    chartElement,
                    { hovertemplate: "%{y}<extra></extra>" },
                    [1, 2, 3],
                );
                applySeriesVisibility();
            } else {
                // Real-time update: append new point to each trace
                const date = new Date(data.time);
                const values = SERIES.map((series) =>
                    getSeriesValue(data, series.key),
                );

                // Extend main trace (processed value) with DQ and flags
                Plotly.extendTraces(
                    chartElement,
                    {
                        x: [[date]],
                        y: [[values[0]]],
                        "marker.color": [[dqToColor(data.dq_score)]],
                        customdata: [
                            [[Number(data.dq_score), formatFlags(data.flags)]],
                        ],
                    },
                    [0],
                    maxPoints,
                );
                // Extend other traces (raw, calibrated, normalized)
                Plotly.extendTraces(
                    chartElement,
                    {
                        x: [[date], [date], [date]],
                        y: [[values[1]], [values[2]], [values[3]]],
                    },
                    [1, 2, 3],
                    maxPoints,
                );
            }
        };
    };

    // Subscribe each chart to its corresponding data type in the store
    for (const dataType of DataType.SENSORS) {
        plantStore.subscribe(
            dataType,
            createSubscriptionHandler(dataType, charts[dataType]),
        );
    }

    // Set up event listeners for time period radio buttons (historical data range)
    const radioButtons = document.querySelectorAll('input[name="data-period"]');
    for (const button of radioButtons) {
        button.addEventListener("change", (event) => {
            const value = event.target.value;
            currentTimePeriod = value;
            maxPoints = getMaxPointsForTimePeriod(currentTimePeriod);
            const range = getRange(value);
            updatePlotRanges(range);
        });
    }
}

/**
 * Create a plot using Plotly library for every variable we want to track
 * In our case it would be plants/environment variable like:
 *      - Temperature
 *      - Humidity
 *      - Soil Moisture
 *      - Light Intensity
 *      - Growth Progress
 */
function initPlots() {
    const chartConfigs = getChartConfigs();

    chartConfigs.forEach((config) => {
        initPlot(config);
    });
}

/**
 * Creates a single Plotly chart in a given DOM element.
 * @param {Object} config - The configuration object for the chart from `CHART_CONFIG`.
 * @param {Array<Date>} [xValues=[]] - The initial x-axis values (timestamps).
 * @param {Array<number>} [yValues=[]] - The initial y-axis values (sensor readings).
 * @param {string} [timePeriod='default'] - The initial time period to set the axis format.
 */
function initPlot(config, xValues = [], yValues = [], timePeriod = "default") {
    const element = document.getElementById(config.elementId);

    // Get appropriate time formatting based on current range
    const xAxisConfig = getTimeFormat(timePeriod);

    const layout = {
        // title: config.title,
        xaxis: xAxisConfig,
        yaxis: {
            title: config.yAxisTitle,
            range: config.yAxisRange,
        },
        // Normalized series is in [0, 1] and would be visually flattened on the main axis.
        // We plot it on a secondary axis to keep it readable.
        yaxis2: {
            title: { text: "Normalized (0–1)" },
            overlaying: "y",
            side: "right",
            range: [0, 1],
        },
    };

    const data = SERIES.map((series) => {
        const lineColor =
            series.key === "value" ? config.lineColor : series.defaultColor;
        const trace = {
            x: xValues,
            y: yValues,
            type: "scatter",
            mode: "lines+markers",
            name: series.label,
            line: { color: lineColor },
            hovertemplate: "%{y}<extra></extra>",
        };

        if (series.key === "value") {
            // Plotly.extendTraces can only extend marker.color if it already exists
            // and is an array on the trace.
            trace.marker = { size: 6, color: [] };
            // The processed trace uses customdata for DQ score and validation flags.
            // Plotly.extendTraces can only extend customdata if it exists as an array.
            trace.customdata = [];
            trace.hovertemplate =
                "%{y}<br>DQ: %{customdata[0]:.2f}<br>%{customdata[1]}<extra></extra>";
        }

        if (series.key === "normalized_value") {
            trace.yaxis = "y2";
        }

        return trace;
    });

    Plotly.newPlot(element, data, layout);
}

/**
 * Determines the appropriate time format for the x-axis based on the selected time period.
 * @param {string} timePeriod - The selected time period ('1h', '24h', '7d', '30d').
 * @returns {Object} A Plotly x-axis configuration object.
 */
function getTimeFormat(timePeriod) {
    switch (timePeriod) {
        case "1h":
            return {
                title: { text: "Time" },
                type: "date",
                tickformat: "%H:%M:%S", // Hours:Minutes:Seconds
                // dtick: 60 * 10 * 1000, // Tick every 10 minutes WARNING: BUG SLOWS DOWN THE PAGE
            };
        case "24h":
            return {
                title: { text: "Time" },
                type: "date",
                tickformat: "%H:%M", // Hours:Minutes
                // dtick: 60 * 60 * 2 * 1000, // Tick every 2 hours
            };
        case "7d":
            return {
                title: { text: "Date" },
                type: "date",
                tickformat: "%m-%d %H:%M", // Month-Day Hour:Minute
                // dtick: 60 * 60 * 24 * 1000, // Tick every day
            };
        case "30d":
            return {
                title: { text: "Date" },
                type: "date",
                tickformat: "%m-%d", // Month-Day
                // dtick: 60 * 60 * 24 * 5 * 1000, // Tick every 5 days
            };
        default:
            return {
                title: { text: "Time" },
                type: "date",
                tickformat: "%H:%M:%S",
            };
    }
}

/**
 * Calculates the start and end timestamps for a given time period string.
 * @param {string} timePeriod - The time period ('1h', '24h', '7d', '30d').
 * @returns {Array<number>} An array containing the start and end timestamps in milliseconds.
 */
function getRange(timePeriod) {
    const now = new Date();
    let startDate;

    switch (timePeriod) {
        // NOTE: The *1000 is used to convert seconds to milliseconds as js Date uses milliseconds
        case "1h":
            startDate = new Date(now.getTime() - 60 * 60 * 1000); // 1 hour ago
            break;
        case "24h":
            startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000); // 24 hours ago
            break;
        case "7d":
            startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000); // 7 days ago
            break;
        case "30d":
            startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000); // 30 days ago
            break;
        default:
            startDate = now; // Default to now if no valid period is selected
    }
    return [startDate.getTime(), now.getTime()];
}

/**
 * Retrieves the chart configuration for a specific data type.
 * @param {DataType} dataType - The data type to get the configuration for.
 * @returns {Object} The chart configuration object.
 */
function getChartConfigForDataType(dataType) {
    return (
        CHART_CONFIG[dataType] || {
            title: { text: "Unknown" },
            yAxisTitle: "Value",
            lineColor: "#17BECF",
        }
    );
}

/**
 * Gets all chart configurations from the `CHART_CONFIG` constant.
 * @returns {Array <Object>} An array of all chart configuration objects.
 */
function getChartConfigs() {
    return Object.values(CHART_CONFIG);
}

/**
 * Triggers an update of the plot ranges by fetching historical data for the new range.
 * @param {Array<number>} range - An array containing the start and end timestamps.
 */
function updatePlotRanges(range) {
    const [startTime, endTime] = range;
    console.log(
        `Updating plots to show data from ${new Date(startTime)} to ${new Date(endTime)}`,
    );

    // Fetch historical data for the selected time range
    plantStore
        .fetchHistoricalData(startTime, endTime)
        .then(() => {
            console.log(
                `Successfully updated plots to show data from ${new Date(startTime)} to ${new Date(endTime)}`,
            );
        })
        .catch((error) => {
            console.error("Error fetching historical data:", error);
        });
}
