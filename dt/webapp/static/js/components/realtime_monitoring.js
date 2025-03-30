import { DataType, plantStore } from '../store.js'

export function initRealTimeMonitoring() {
    console.log('Initializing real-time monitoring charts...')

    const tempChart = document.getElementById('temp-chart')
    const humidityChart = document.getElementById('humidity-chart')
    const soilMoistureChart = document.getElementById('soil-chart')
    const lightIntensityChart = document.getElementById('light-chart')
    const growthProgressChart = document.getElementById('growth-chart')

    initPlots()

    const max_points = 10 // Max number of points to keep on the chart

    plantStore.subscribe(DataType.TEMPERATURE, (data) => {
        if (data.type === 'historical') {
            pass
        } else {
            Plotly.extendTraces(
                tempChart,
                {
                    x: [[data.time]],
                    y: [[data.value]],
                },
                [0],
                max_points
            )
        }
    })

    plantStore.subscribe(DataType.HUMIDITY, (data) => {
        if (data.type === 'historical') {
            pass
        } else {
            Plotly.extendTraces(
                tempChart,
                {
                    x: [[data.time]],
                    y: [[data.value]],
                },
                [0],
                max_points
            )
        }
    })

    plantStore.subscribe(DataType.SOIL_MOISTURE, (data) => {
        if (data.type === 'historical') {
            pass
        } else {
            Plotly.extendTraces(
                tempChart,
                {
                    x: [[data.time]],
                    y: [[data.value]],
                },
                [0],
                max_points
            )
        }
    })

    plantStore.subscribe(DataType.LIGHT, (data) => {
        if (data.type === 'historical') {
            pass
        } else {
            Plotly.extendTraces(
                tempChart,
                {
                    x: [[data.time]],
                    y: [[data.value]],
                },
                [0],
                max_points
            )
        }
    })

    plantStore.subscribe(DataType.GROWTH, (data) => {
        if (data.type === 'historical') {
            pass
        } else {
            Plotly.extendTraces(
                tempChart,
                {
                    x: [[data.time]],
                    y: [[data.value]],
                },
                [0],
                max_points
            )
        }
    })

    // Add a listener to radio buttons that change the time range
    const radioButtons = document.querySelectorAll('input[name="data-period"]')
    for (const button of radioButtons) {
        button.addEventListener('change', (event) => {
            const value = event.target.value
            const startingPeriod = getRange(value)
            updatePlotRanges(startingPeriod)
        })
    }
}

/** Create a plot using Plotly library for every variable we want to track
 * In our case it would be plants/environment variable like:
 *      - Temperature
 *      - Humidity
 *      - Soil Moisture
 *      - Light Intensity
 *      - Growth Progress
 *      etc...
 **/
function initPlots() {
    const tempChart = document.getElementById('temp-chart')
    const humidityChart = document.getElementById('humidity-chart')
    const soilMoistureChart = document.getElementById('soil-chart')
    const lightIntensityChart = document.getElementById('light-chart')
    const growthProgressChart = document.getElementById('growth-chart')

    new Plotly.newPlot(
        tempChart,
        [
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Temperature',
                line: { color: '#17BECF' },
            },
        ],
        {
            title: 'Temperature',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value (°C)' },
        }
    )

    new Plotly.newPlot(
        humidityChart,
        [
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Humidity',
                line: { color: '#17BECF' },
            },
        ],
        {
            title: 'Humidity',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value (%)', range: [0, 100] },
        }
    )

    new Plotly.newPlot(
        soilMoistureChart,
        [
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Soil Moisture',
                line: { color: '#17BECF' },
            },
        ],
        {
            title: 'Soil Moisture',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value (%)', range: [0, 100] },
        }
    )

    new Plotly.newPlot(
        lightIntensityChart,
        [
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Light Intensity',
                line: { color: '#17BECF' },
            },
        ],
        {
            title: 'Light Intensity',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value (lux)' },
        }
    )

    new Plotly.newPlot(
        growthProgressChart,
        [
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Growth Progress',
                line: { color: '#17BECF' },
            },
        ],
        {
            title: 'Growth Progress',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value (%)', range: [0, 100] },
        }
    )
}

/**
 * Get the start date based on the selected time period.
 * This function calculates the start date based on the current time and the selected time period.
 * @param {string} timePeriod - The time period for which to get the start date
 * @returns {tuple} - A tuple containing the start date and end date
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

// Function to update the plot ranges
function updatePlotRanges(range) {
    console.log(`Updating plots to show data for: ${range}`)
    // Fetch new data based on the range and update the plots
    const [startTime, endTime] = range

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
