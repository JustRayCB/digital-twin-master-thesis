import { DataType, plantStore } from '../store.js'

// Chart configuration constants
const CHART_CONFIG = {
    [DataType.TEMPERATURE]: {
        elementId: 'temp-chart',
        title: 'Temperature',
        yAxisTitle: 'Value (°C)',
        lineColor: '#17BECF',
    },
    [DataType.HUMIDITY]: {
        elementId: 'humidity-chart',
        title: 'Humidity',
        yAxisTitle: 'Value (%)',
        lineColor: '#17BECF',
        yAxisRange: [0, 100],
    },
    [DataType.SOIL_MOISTURE]: {
        elementId: 'soil-chart',
        title: 'Soil Moisture',
        yAxisTitle: 'Value (%)',
        lineColor: '#17BECF',
        yAxisRange: [0, 100],
    },
    [DataType.LIGHT]: {
        elementId: 'light-chart',
        title: 'Light Intensity',
        yAxisTitle: 'Value (lux)',
        lineColor: '#17BECF',
    },
}

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

    // Create a reusable subscription handler
    const createSubscriptionHandler = (dataType, chartElement) => {
        return (data) => {
            if (data.type === 'historical') {
                Plotly.purge(chartElement)
                // Get proper chart configuration based on data type
                const chartConfig = getChartConfigForDataType(dataType)

                if (!data.data) {
                    console.error('No data received for historical data')
                    // Revert to empty chart
                    initPlot(chartConfig)
                    return
                }
                const xValues = data.data.map((item) => item.time)
                const yValues = data.data.map((item) => item.value)
                initPlot(chartConfig, xValues, yValues)
            } else {
                Plotly.extendTraces(
                    chartElement,
                    {
                        x: [[data.time]],
                        y: [[data.value]],
                    },
                    [0],
                    max_points
                )
            }
        }
    }

    // Subscribe to all data types
    plantStore.subscribe(
        DataType.TEMPERATURE,
        createSubscriptionHandler(DataType.TEMPERATURE, charts[DataType.TEMPERATURE])
    )
    plantStore.subscribe(
        DataType.HUMIDITY,
        createSubscriptionHandler(DataType.HUMIDITY, charts[DataType.HUMIDITY])
    )
    plantStore.subscribe(
        DataType.SOIL_MOISTURE,
        createSubscriptionHandler(DataType.SOIL_MOISTURE, charts[DataType.SOIL_MOISTURE])
    )
    plantStore.subscribe(
        DataType.LIGHT,
        createSubscriptionHandler(DataType.LIGHT, charts[DataType.LIGHT])
    )

    // Add a listener to radio buttons that change the time range
    const radioButtons = document.querySelectorAll('input[name="data-period"]')
    for (const button of radioButtons) {
        button.addEventListener('change', (event) => {
            const value = event.target.value
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

function initPlot(config, xValues = [], yValues = []) {
    const element = document.getElementById(config.elementId)

    const layout = {
        title: config.title,
        xaxis: { title: 'Time' },
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
 * Get the start date based on the selected time period.
 * This function calculates the start date based on the current time and the selected time period.
 * @param {string} timePeriod - The time period for which to get the start date
 * @returns {Array} - An array containing the start date and end date timestamps
 */
function getRange(timePeriod) {
    const now = new Date()
    let startDate

    switch (timePeriod) {
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
 * Get chart configuration for the specified data type
 * @param {string} dataType - The data type to get configuration for
 * @returns {Object} - The chart configuration
 */
function getChartConfigForDataType(dataType) {
    return (
        CHART_CONFIG[dataType] || {
            title: dataType,
            yAxisTitle: 'Value',
            lineColor: '#17BECF',
        }
    )
}

/**
 * Get all chart configurations
 * @returns {Array} - Array of chart configurations
 */
function getChartConfigs() {
    return Object.values(CHART_CONFIG)
}

/**
 * Update the plot ranges based on the selected time period
 * @param {Array} range - An array containing start and end timestamps
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
