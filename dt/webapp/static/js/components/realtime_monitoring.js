export function initRealTimeCharts() {
    console.log('Initializing real-time monitoring charts...')

    const tempHumidityChart = document.getElementById('temp-humidity-chart')
    const soilMoistureChart = document.getElementById('soil-chart')
    const lightIntensityChart = document.getElementById('light-chart')
    const growthProgressChart = document.getElementById('growth-chart')

    new Plotly.newPlot(
        tempHumidityChart,
        [
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Temperature',
                line: { color: '#17BECF' },
            },
            {
                x: [],
                y: [],
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Humidity',
                line: { color: '#7F7F7F' },
            },
        ],
        {
            title: 'Temperature and Humidity',
            xaxis: { title: 'Time' },
            yaxis: { title: 'Value' },
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
            yaxis: { title: 'Value' },
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
            yaxis: { title: 'Value' },
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
            yaxis: { title: 'Value' },
        }
    )

    const socket = io.connect('http://localhost:5000')

    socket.on('update_temp_humidity', (data) => {
        const tempHumidityChart = document.getElementById('temp-humidity-chart')
        Plotly.extendTraces(
            tempHumidityChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0, 1]
        )
    })

    socket.on('soil_moisture', (data) => {
        const soilMoistureChart = document.getElementById('soil-chart')
        console.log('Receivd data: ', data)
        // Plotly.update(soilMoistureChart, { x: [data.time], y: [data.soil_moisture] })
        Plotly.extendTraces(
            soilMoistureChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0],
            10 // Max number of points to keep on the chart
        )
    })

    socket.on('light_intensity', (data) => {
        const lightIntensityChart = document.getElementById('light-chart')
        Plotly.extendTraces(
            lightIntensityChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0]
        )
    })

    socket.on('update_growth_progress', (data) => {
        const growthProgressChart = document.getElementById('growth-chart')
        Plotly.extendTraces(
            growthProgressChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0]
        )
    })
}
