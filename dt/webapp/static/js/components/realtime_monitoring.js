/**
 * @file Manages the real-time monitoring charts on the dashboard.
 * This module uses the Plotly.js library to create and update charts for
 * temperature, humidity, soil moisture, and light intensity. It subscribes
 * to the central data store to receive both real-time and historical data.
 */ 
 import { DataType, plantStore } from '../store.js'


/**
 * @const {Object} CHART_CONFIG
 * @description A configuration object that defines the properties for each chart,
 * such as the DOM element ID, title, y-axis title, and line color.
 */
const CHART_CONFIG = {
    [DataType.TEMPERATURE]: {
        elementId: 'temp-chart',
        title: { text: 'Temperature' },
        yAxisTitle: { text: 'Value (°C)' },
        lineColor: '#17BECF',
    },
    [DataType.HUMIDITY]: {
        elementId: 'humidity-chart',
        title: { text: 'Humidity' },
        yAxisTitle: { text: 'Value (%)' },
        lineColor: '#17BECF',
        yAxisRange: [0, 100],
    },
    [DataType.SOIL_MOISTURE]: {
        elementId: 'soil-chart',
        title: { text: 'Soil Moisture' },
        yAxisTitle: { text: 'Value (%)' },
        lineColor: '#17BECF',
        yAxisRange: [0, 100],
    },
    [DataType.LIGHT]: {
        elementId: 'light-chart',
        title: { text: 'Light Intensity' },
        yAxisTitle: { text: 'Value (lux)' },
        lineColor: '#17BECF',
    },
}

/**
 * Initializes the real-time monitoring component.
 * This function creates the initial empty plots, subscribes to data updates from the
 * `plantStore`, and sets up event listeners for the time period radio buttons.
 */
export function initRealTimeMonitoring() {
    console.log('Initializing real-time monitoring charts...')

    // Get chart DOM elements
    const charts = {
        [DataType.TEMPERATURE]: document.getElementById('temp-chart'),
        [DataType.HUMIDITY]: document.getElementById('humidity-chart'),
        [DataType.SOIL_MOISTURE]: document.getElementById('soil-chart'),
        [DataType.LIGHT]: document.getElementById('light-chart'),
    }

    // Initialize all charts
    initPlots()

    const max_points = 10 // Max number of points to keep on the chart
    let currentTimePeriod = '24h' // Default time period

    /**
     * Creates a subscription handler function for a specific chart.
     * The returned handler can process both historical data (which replaces the chart's data)
     * and real-time data (which extends the chart's traces).
     * @param {DataType} dataType - The data type for which to create the handler.
     * @param {HTMLElement} chartElement - The DOM element of the chart.
     * @returns {function} A handler function that takes data and updates the chart.
     */
    const createSubscriptionHandler = (dataType, chartElement) => {
        return (data) => {
            if (data.type === 'historical') {
                Plotly.purge(chartElement)
                // Get proper chart configuration based on data type
                const chartConfig = getChartConfigForDataType(dataType)

                if (data.data.length === 0) {
                    console.error('No data received for historical data')
                    // Revert to empty chart
                    initPlot(chartConfig, [], [], currentTimePeriod)
                    return
                }
                const xValues = data.data.map((item) => new Date(item.time * 1000))
                const yValues = data.data.map((item) => item.value)
                initPlot(chartConfig, xValues, yValues, currentTimePeriod)
            } else {
                Plotly.extendTraces(
                    chartElement,
                    {
                        x: [[new Date(data.time)]],
                        y: [[data.value]],
                    },
                    [0]
                    // max_points
                )
            }
        }
    }

    // Subscribe each chart to its corresponding data type in the store.
    for (const dataType of DataType.SENSORS) {
        plantStore.subscribe(
            dataType,
            createSubscriptionHandler(dataType, charts[dataType])
        )
    }

    // Add event listeners to the time period radio buttons.
    const radioButtons = document.querySelectorAll('input[name="data-period"]')
    for (const button of radioButtons) {
        button.addEventListener('change', (event) => {
            const value = event.target.value
            currentTimePeriod = value
            const range = getRange(value)
            updatePlotRanges(range)
        })
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
    const chartConfigs = getChartConfigs()

    chartConfigs.forEach((config) => {
        initPlot(config)
    })
}


/**
 * Creates a single Plotly chart in a given DOM element.
 * @param {Object} config - The configuration object for the chart from `CHART_CONFIG`.
 * @param {Array<Date>} [xValues=[]] - The initial x-axis values (timestamps).
 * @param {Array<number>} [yValues=[]] - The initial y-axis values (sensor readings).
 * @param {string} [timePeriod='default'] - The initial time period to set the axis format.
 */
function initPlot(config, xValues = [], yValues = [], timePeriod = 'default') {
    const element = document.getElementById(config.elementId)

    // Get appropriate time formatting based on current range
    const xAxisConfig = getTimeFormat(timePeriod)

    const layout = {
        // title: config.title,
        xaxis: xAxisConfig,
        yaxis: {
            title: config.yAxisTitle,
            range: config.yAxisRange,
        },
    }

    const data = [
        {
            x: xValues,
            y: yValues,
            type: 'scatter',
            mode: 'lines+markers',
            name: config.title,
            line: { color: config.lineColor },
        },
    ]

    Plotly.newPlot(element, data, layout)
}

/**
 * Determines the appropriate time format for the x-axis based on the selected time period.
 * @param {string} timePeriod - The selected time period ('1h', '24h', '7d', '30d').
 * @returns {Object} A Plotly x-axis configuration object.
 */
function getTimeFormat(timePeriod) {
    switch (timePeriod) {
        case '1h':
            return {
                title: { text: 'Time' },
                type: 'date',
                tickformat: '%H:%M:%S', // Hours:Minutes:Seconds
                // dtick: 60 * 10 * 1000, // Tick every 10 minutes WARNING: BUG SLOWS DOWN THE PAGE
            }
        case '24h':
            return {
                title: { text: 'Time' },
                type: 'date',
                tickformat: '%H:%M', // Hours:Minutes
                // dtick: 60 * 60 * 2 * 1000, // Tick every 2 hours
            }
        case '7d':
            return {
                title: { text: 'Date' },
                type: 'date',
                tickformat: '%m-%d %H:%M', // Month-Day Hour:Minute
                // dtick: 60 * 60 * 24 * 1000, // Tick every day
            }
        case '30d':
            return {
                title: { text: 'Date' },
                type: 'date',
                tickformat: '%m-%d', // Month-Day
                // dtick: 60 * 60 * 24 * 5 * 1000, // Tick every 5 days
            }
        default:
            return {
                title: { text: 'Time' },
                type: 'date',
                tickformat: '%H:%M:%S',
            }
    }
}


/**
 * Calculates the start and end timestamps for a given time period string.
 * @param {string} timePeriod - The time period ('1h', '24h', '7d', '30d').
 * @returns {Array<number>} An array containing the start and end timestamps in milliseconds.
 */
function getRange(timePeriod) {
    const now = new Date()
    let startDate

    switch (timePeriod) {
        // NOTE: The *1000 is used to convert seconds to milliseconds as js Date uses milliseconds
        case '1h':
            startDate = new Date(now.getTime() - 60 * 60 * 1000) // 1 hour ago
            break
        case '24h':
            startDate = new Date(now.getTime() - 24 * 60 * 60 * 1000) // 24 hours ago
            break
        case '7d':
            startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000) // 7 days ago
            break
        case '30d':
            startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000) // 30 days ago
            break
        default:
            startDate = now // Default to now if no valid period is selected
    }
    return [startDate.getTime(), now.getTime()]
}

/**
 * Retrieves the chart configuration for a specific data type.
 * @param {DataType} dataType - The data type to get the configuration for.
 * @returns {Object} The chart configuration object.
 */
function getChartConfigForDataType(dataType) {
    return (
        CHART_CONFIG[dataType] || {
            title: { text: 'Unknown' },
            yAxisTitle: 'Value',
            lineColor: '#17BECF',
        }
    )
}

/**
 * Gets all chart configurations from the `CHART_CONFIG` constant.
 * @returns {Array <Object>} An array of all chart configuration objects.
 */
function getChartConfigs() {
    return Object.values(CHART_CONFIG)
}

/**
 * Triggers an update of the plot ranges by fetching historical data for the new range.
 * @param {Array<number>} range - An array containing the start and end timestamps.
 */
function updatePlotRanges(range) {
    const [startTime, endTime] = range
    console.log(`Updating plots to show data from ${new Date(startTime)} to ${new Date(endTime)}`)

    // Fetch historical data for the selected time range
    plantStore
        .fetchHistoricalData(startTime, endTime)
        .then(() => {
            console.log(
                `Successfully updated plots to show data from ${new Date(startTime)} to ${new Date(endTime)}`
            )
        })
        .catch((error) => {
            console.error('Error fetching historical data:', error)
        })
}
