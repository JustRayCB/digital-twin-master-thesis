import { DataType, plantStore } from "../store.js";

export function initRealTimeMonitoring() {
    console.log("Initializing real-time monitoring charts...");

    const tempChart = document.getElementById("temp-chart");
    const humidityChart = document.getElementById("humidity-chart");
    const soilMoistureChart = document.getElementById("soil-chart");
    const lightIntensityChart = document.getElementById("light-chart");
    const growthProgressChart = document.getElementById("growth-chart");

    // new Plotly.newPlot(
    //     tempHumidityChart,
    //     [
    //         {
    //             x: [],
    //             y: [],
    //             type: "scatter",
    //             mode: "lines+markers",
    //             name: "Temperature",
    //             line: { color: "#17BECF" },
    //         },
    //         {
    //             x: [],
    //             y: [],
    //             type: "scatter",
    //             mode: "lines+markers",
    //             name: "Humidity",
    //             line: { color: "#7F7F7F" },
    //         },
    //     ],
    //     {
    //         title: "Temperature and Humidity",
    //         xaxis: { title: "Time" },
    //         yaxis: { title: "Value" },
    //     },
    // );

    new Plotly.newPlot(
        tempChart,
        [
            {
                x: [],
                y: [],
                type: "scatter",
                mode: "lines+markers",
                name: "Temperature",
                line: { color: "#17BECF" },
            },
        ],
        {
            title: "Temperature",
            xaxis: { title: "Time" },
            yaxis: { title: "Value (°C)" },
        },
    );

    new Plotly.newPlot(
        humidityChart,
        [
            {
                x: [],
                y: [],
                type: "scatter",
                mode: "lines+markers",
                name: "Humidity",
                line: { color: "#17BECF" },
            },
        ],
        {
            title: "Humidity",
            xaxis: { title: "Time" },
            yaxis: { title: "Value (%)", range: [0, 100] },
        },
    );

    new Plotly.newPlot(
        soilMoistureChart,
        [
            {
                x: [],
                y: [],
                type: "scatter",
                mode: "lines+markers",
                name: "Soil Moisture",
                line: { color: "#17BECF" },
            },
        ],
        {
            title: "Soil Moisture",
            xaxis: { title: "Time" },
            yaxis: { title: "Value (%)", range: [0, 100] },
        },
    );

    new Plotly.newPlot(
        lightIntensityChart,
        [
            {
                x: [],
                y: [],
                type: "scatter",
                mode: "lines+markers",
                name: "Light Intensity",
                line: { color: "#17BECF" },
            },
        ],
        {
            title: "Light Intensity",
            xaxis: { title: "Time" },
            yaxis: { title: "Value (lux)" },
        },
    );

    new Plotly.newPlot(
        growthProgressChart,
        [
            {
                x: [],
                y: [],
                type: "scatter",
                mode: "lines+markers",
                name: "Growth Progress",
                line: { color: "#17BECF" },
            },
        ],
        {
            title: "Growth Progress",
            xaxis: { title: "Time" },
            yaxis: { title: "Value (%)", range: [0, 100] },
        },
    );

    const max_points = 10; // Max number of points to keep on the chart

    plantStore.subscribe(DataType.TEMPERATURE, (data) => {
        const tempChart = document.getElementById("temp-chart");
        Plotly.extendTraces(
            tempChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0],
            max_points,
        );
    });

    plantStore.subscribe(DataType.HUMIDITY, (data) => {
        const humidityChart = document.getElementById("humidity-chart");
        Plotly.extendTraces(
            humidityChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0],
            max_points,
        );
    });

    plantStore.subscribe(DataType.SOIL_MOISTURE, (data) => {
        const soilMoistureChart = document.getElementById("soil-chart");
        Plotly.extendTraces(
            soilMoistureChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0],
            max_points,
        );
    });

    plantStore.subscribe(DataType.LIGHT, (data) => {
        const lightIntensityChart = document.getElementById("light-chart");
        Plotly.extendTraces(
            lightIntensityChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0],
            max_points,
        );
    });

    plantStore.subscribe(DataType.GROWTH, (data) => {
        const growthProgressChart = document.getElementById("growth-chart");
        Plotly.extendTraces(
            growthProgressChart,
            {
                x: [[data.time]],
                y: [[data.value]],
            },
            [0],
            max_points,
        );
    });
}
