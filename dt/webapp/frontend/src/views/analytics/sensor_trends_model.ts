import { get, writable } from "svelte/store";

import type { ProcessedReadingPayload } from "./realtime_types";
import { processedTopics } from "./realtime_topics";

type PlotlyElement = HTMLElement & { on?: (event: string, handler: (data: any) => void) => void };

export type TimeView = "day" | "week" | "month";

function ensurePlotlyAvailable() {
  const plotly = window.Plotly;
  if (!plotly) {
    throw new Error("Plotly is not available on window.Plotly");
  }
  return plotly;
}

function ensureSocketIoAvailable() {
  const io = window.io;
  if (!io) {
    throw new Error("Socket.IO client is not available on window.io");
  }
  return io;
}

const commonLayout = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "'Space Grotesk', sans-serif", color: "#9ca3af" },
  margin: { t: 10, r: 10, b: 30, l: 30 },
  xaxis: {
    showgrid: false,
    zeroline: false,
    tickfont: { family: "'VT323', monospace", size: 14 },
  },
  yaxis: {
    showgrid: false,
    zeroline: false,
    tickfont: { family: "'VT323', monospace", size: 14 },
  },
  dragmode: false as const,
  displayModeBar: false,
};

function initTemperatureChart(plotly: any, element: PlotlyElement) {
  const trace = {
    x: [1, 2, 3, 4, 5, 6, 7],
    y: [20, 22, 21, 23, 25, 24, 23.5],
    type: "scatter" as const,
    mode: "lines+markers" as const,
    line: { color: "#ffdac1", width: 4, shape: "spline" as const },
    marker: { color: "#ffdac1", size: 8, line: { color: "#1c1917", width: 2 } },
  };
  return plotly.newPlot(
    element,
    [trace],
    {
      ...commonLayout,
      autosize: true,
    },
    { displayModeBar: false, responsive: true },
  );
}

function initMoistureChart(plotly: any, element: PlotlyElement) {
  const trace = {
    x: [1, 2, 3, 4, 5, 6, 7],
    y: [55, 52, 50, 48, 45, 42, 45],
    type: "scatter" as const,
    mode: "lines" as const,
    fill: "tozeroy" as const,
    fillcolor: "rgba(220, 214, 247, 0.4)",
    line: { color: "#1c1917", width: 3, shape: "spline" as const },
  };
  return plotly.newPlot(
    element,
    [trace],
    {
      ...commonLayout,
      autosize: true,
    },
    { displayModeBar: false, responsive: true },
  );
}

function initHumidityChart(plotly: any, element: PlotlyElement) {
  const trace = {
    x: [1, 2, 3, 4, 5, 6, 7],
    y: [44, 46, 45, 48, 47, 49, 46],
    type: "scatter" as const,
    mode: "lines+markers" as const,
    line: { color: "#c7cee3", width: 4, shape: "spline" as const },
    marker: { color: "#c7cee3", size: 8, line: { color: "#1c1917", width: 2 } },
  };
  return plotly.newPlot(
    element,
    [trace],
    {
      ...commonLayout,
      autosize: true,
    },
    { displayModeBar: false, responsive: true },
  );
}

function initLightExposureChart(plotly: any, element: PlotlyElement) {
  const trace = {
    x: ["6AM", "9AM", "12PM", "3PM", "6PM"],
    y: [10, 60, 85, 70, 30],
    type: "bar" as const,
    marker: {
      color: "#fdfd96",
      line: { color: "#1c1917", width: 2 },
    },
  };
  return plotly.newPlot(
    element,
    [trace],
    {
      ...commonLayout,
      margin: { t: 10, r: 10, b: 20, l: 20 },
      autosize: true,
    },
    { displayModeBar: false, responsive: true },
  );
}

export function createSensorTrendsModel() {
  const timeView = writable<TimeView>("day");

  const chartElements = writable<Partial<Record<string, PlotlyElement>>>({});

  let socket: any = null;

  function setChartElement(key: string, element: PlotlyElement | null) {
    if (!element) {
      return;
    }
    chartElements.update((current) => ({ ...current, [key]: element }));
  }

  async function initCharts() {
    const plotly = ensurePlotlyAvailable();
    const elements = get(chartElements);
    const tasks: Promise<unknown>[] = [];

    const temperatureElement = elements[processedTopics.temperature];
    if (temperatureElement) tasks.push(initTemperatureChart(plotly, temperatureElement));

    const moistureElement = elements[processedTopics.soilMoisture];
    if (moistureElement) tasks.push(initMoistureChart(plotly, moistureElement));

    const humidityElement = elements[processedTopics.humidity];
    if (humidityElement) tasks.push(initHumidityChart(plotly, humidityElement));

    const lightElement = elements[processedTopics.lightIntensity];
    if (lightElement) tasks.push(initLightExposureChart(plotly, lightElement));

    await Promise.all(tasks);
  }

  function connectSocket() {
    const io = ensureSocketIoAvailable();
    socket = io();

    const plotly = ensurePlotlyAvailable();

    const appendPoint = (elementKey: string, x: unknown, y: unknown) => {
      const element = get(chartElements)[elementKey];
      if (!element) return;
      if (!Array.isArray((element as any).data)) return;
      const yValue = Number(y);
      if (!Number.isFinite(yValue)) return;
      plotly.extendTraces(element, { x: [[x]], y: [[yValue]] }, [0], 120);
    };

    socket.on(processedTopics.temperature, (payload: ProcessedReadingPayload) => {
      appendPoint(processedTopics.temperature, new Date(payload.time), payload.value);
    });

    socket.on(processedTopics.humidity, (payload: ProcessedReadingPayload) => {
      appendPoint(processedTopics.humidity, new Date(payload.time), payload.value);
    });

    socket.on(processedTopics.soilMoisture, (payload: ProcessedReadingPayload) => {
      appendPoint(processedTopics.soilMoisture, new Date(payload.time), payload.value);
    });

    socket.on(processedTopics.lightIntensity, (payload: ProcessedReadingPayload) => {
      appendPoint(processedTopics.lightIntensity, new Date(payload.time), payload.value);
    });
  }

  async function start() {
    await initCharts();
    connectSocket();
  }

  function stop() {
    if (socket) {
      socket.disconnect();
      socket = null;
    }
  }

  return {
    timeView,
    setChartElement,
    start,
    stop,
  };
}
