import { get, writable } from "svelte/store";

import { fetchReadings } from "../../api";
import type { AggregatedReadingPayload, DqHoverState, ProcessedReadingPayload } from "./realtime_types";
import { analyticsTopics, processedTopics, type ProcessedTopicName } from "./realtime_topics";
import { realtimeReadings, type BandPoint } from "./realtime_readings_store";

const HISTORICAL_WINDOW_MS = {
  day: 24 * 60 * 60 * 1000,
  week: 7 * 24 * 60 * 60 * 1000,
  month: 30 * 24 * 60 * 60 * 1000,
} as const;

const SERIES = [
  { key: "value", label: "processed", color: "#1c1917", dash: "solid" },
  { key: "raw_value", label: "raw", color: "#6b7280", dash: "dot" },
  { key: "calibrated_value", label: "calibrated", color: "#ffdac1", dash: "dash" },
  { key: "normalized_value", label: "normalized", color: "#c7cee3", dash: "dashdot" },
] as const;

type SeriesKey = (typeof SERIES)[number]["key"];

type PlotlyElement = HTMLElement & { on?: (event: string, handler: (data: any) => void) => void };
type TimeView = keyof typeof HISTORICAL_WINDOW_MS;

const BAND_COLOR = "rgba(100,100,100,0.12)";

function windowForView(view: TimeView): "raw" | "1h" {
  return view === "day" ? "raw" : "1h";
}

function dqToColor(dqScore: unknown) {
  const dq = Number(dqScore);
  if (!Number.isFinite(dq)) {
    return "#7f7f7f";
  }
  if (dq <= 0.5) {
    const t = dq / 0.5;
    const r = 255;
    const g = Math.round(255 * t);
    const b = 0;
    return `rgb(${r},${g},${b})`;
  }

  const t = (dq - 0.5) / 0.5;
  const r = Math.round(255 * (1 - t));
  const g = 255;
  const b = 0;
  return `rgb(${r},${g},${b})`;
}

function formatFlags(flags: unknown) {
  if (!flags || typeof flags !== "object") {
    return "";
  }
  const entries = Object.entries(flags as Record<string, unknown>);
  const violations = entries
    .filter(([key, value]) => key !== "valid_data_point" && value === true)
    .map(([key]) => key);
  return violations.length ? `flags: ${violations.join(", ")}` : "";
}

function getSeriesValue(reading: ProcessedReadingPayload, key: SeriesKey) {
  const value = Number((reading as any)?.[key]);
  return Number.isFinite(value) ? value : null;
}

function ensurePlotlyAvailable() {
  const plotly = window.Plotly;
  if (!plotly) {
    throw new Error("Plotly is not available on window.Plotly");
  }
  return plotly;
}

function schedulePlotlyResize(plotly: any, element: PlotlyElement) {
  const resize = () => {
    if (!element.isConnected) {
      return;
    }
    plotly.Plots.resize(element);
  };

  requestAnimationFrame(() => requestAnimationFrame(resize));
}

function observeElementResize(plotly: any, element: PlotlyElement) {
  if (!("ResizeObserver" in window)) {
    return null;
  }

  const observer = new ResizeObserver(() => schedulePlotlyResize(plotly, element));
  observer.observe(element);
  return observer;
}

type InitialSeriesData = { x: string[]; y: Array<number | null>; customdata: Array<[number | null, string]> };

function yieldToBrowser(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function initPlot(
  plotly: any,
  element: PlotlyElement,
  title: string,
  yAxisTitle: string,
  yAxisRange?: [number, number],
  initialData?: InitialSeriesData[],
  bandData?: BandPoint[],
) {
  const data = SERIES.map((s, idx) => {
    const seed = initialData?.[idx];
    const trace: Record<string, unknown> = {
      x: seed?.x ?? [],
      y: seed?.y ?? [],
      mode: "lines+markers",
      name: s.label,
      visible: true,
      marker: { size: 8, color: s.color, line: { color: "#1c1917", width: 2 } },
      line: { width: 4, color: s.color, dash: s.dash, shape: "spline" as const },
      customdata: seed?.customdata ?? [],
      hovertemplate: "%{x}<br>%{y}<extra>%{fullData.name}</extra>",
    };

    if (s.key === "normalized_value") {
      trace.yaxis = "y2";
    }

    return trace;
  });

  // Min/max band around the processed (mean) series for aggregated views
  if (bandData && bandData.length > 0) {
    const xs = bandData.map((p) => p.x);
    data.push({
      x: xs,
      y: bandData.map((p) => p.min),
      mode: "lines",
      name: "min",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    } as any);
    data.push({
      x: xs,
      y: bandData.map((p) => p.max),
      mode: "lines",
      name: "max",
      fill: "tonexty",
      fillcolor: BAND_COLOR,
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    } as any);
  }

  const layout = {
    title: { text: title },
    margin: { l: 40, r: 20, t: 40, b: 35 },
    xaxis: { title: { text: "Time" }, type: "date" as const },
    yaxis: { title: { text: yAxisTitle }, range: yAxisRange },
    yaxis2: {
      title: { text: "Normalized (0–1)" },
      overlaying: "y",
      side: "right",
      range: [0, 1],
    },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    showlegend: true,
    legend: { orientation: "h" as const },
  };

  const config = { displayModeBar: false, responsive: true };
  return plotly.newPlot(element, data, layout, config);
}

function applySeriesVisibility(plotly: any, element: PlotlyElement, visibility: Record<SeriesKey, boolean>) {
  const traceCount = Array.isArray((element as any).data) ? (element as any).data.length : SERIES.length;
  const visible: Array<boolean | "legendonly"> = SERIES.map((s) => (visibility[s.key] ? true : "legendonly"));
  // Band traces (if present) stay always visible
  for (let i = SERIES.length; i < traceCount; i++) {
    visible.push(true);
  }
  plotly.restyle(element, { visible });
}

export function createRealtimeMonitoringModel() {
  const dqHover = writable<DqHoverState>({ dqScore: null, flagsText: "" });

  const seriesVisibility = writable<Record<SeriesKey, boolean>>({
    value: true,
    raw_value: true,
    calibrated_value: true,
    normalized_value: true,
  });

  const chartElements = writable<Partial<Record<ProcessedTopicName, PlotlyElement>>>({});

  let resizeObservers: ResizeObserver[] = [];
  const unsubscribers: Array<() => void> = [];

  function setChartElement(topic: ProcessedTopicName, element: PlotlyElement | null) {
    if (!element) {
      return;
    }
    chartElements.update((current) => ({ ...current, [topic]: element }));
  }

  function bindHover(element: PlotlyElement) {
    if (!element.on) {
      return;
    }
    element.on("plotly_hover", (eventData: any) => {
      const point = eventData?.points?.[0];
      const customdata = point?.customdata;
      if (Array.isArray(customdata)) {
        dqHover.set({ dqScore: Number(customdata[0]), flagsText: String(customdata[1] ?? "") });
      } else {
        dqHover.set({ dqScore: null, flagsText: "" });
      }
    });
    element.on("plotly_unhover", () => dqHover.set({ dqScore: null, flagsText: "" }));
  }

  function cleanupObservers() {
    for (const observer of resizeObservers) {
      observer.disconnect();
    }
    resizeObservers = [];
  }

  async function fetchHistorical(view: TimeView) {
    const windowMs = HISTORICAL_WINDOW_MS[view];
    const until = Date.now();
    const since = until - windowMs;
    const aggregationWindow = windowForView(view);

    const topics = analyticsTopics;

    // Clear stale data from previous view
    for (const topic of topics) {
      realtimeReadings.clearTopic(topic);
    }

    const responses = await Promise.allSettled(
      topics.map((topic) => fetchReadings({ topic, since, until, window: aggregationWindow })),
    );

    responses.forEach((result, idx) => {
      if (result.status !== "fulfilled") {
        console.error("Failed to load historical readings", result.reason);
        return;
      }
      const topic = topics[idx];
      if (aggregationWindow === "raw") {
        realtimeReadings.hydrate(topic, result.value as ProcessedReadingPayload[]);
      } else {
        realtimeReadings.hydrateAggregated(topic, result.value as unknown as AggregatedReadingPayload[]);
      }
    });
  }

  async function initCharts() {
    const plotly = ensurePlotlyAvailable();
    const elements = get(chartElements);

    const configByTopic: Partial<Record<ProcessedTopicName, { title: string; yAxisTitle: string; yAxisRange?: [number, number] }>> =
      {
        [processedTopics.temperature]: { title: "Temperature", yAxisTitle: "Value (°C)" },
        [processedTopics.humidity]: { title: "Humidity", yAxisTitle: "Value (%)", yAxisRange: [0, 100] },
        [processedTopics.soilMoisture]: { title: "Soil Moisture", yAxisTitle: "Value (%)", yAxisRange: [0, 100] },
        [processedTopics.lightIntensity]: { title: "Light Intensity", yAxisTitle: "Value (lux)" },
      };

    const observers: ResizeObserver[] = [];
    for (const [topic, element] of Object.entries(elements) as Array<
      [ProcessedTopicName, PlotlyElement | undefined]
    >) {
      if (!element) {
        continue;
      }
      const cfg = configByTopic[topic];
      if (!cfg) {
        continue;
      }
      const snapshot = realtimeReadings.getSnapshot(topic);
      const initialData = SERIES.map((s) => ({
        x: snapshot[s.key].map((p) => p.x),
        y: snapshot[s.key].map((p) => p.y),
        customdata: snapshot[s.key].map((p) => p.customdata),
      }));

      const band = realtimeReadings.getBand(topic);
      await initPlot(plotly, element, cfg.title, cfg.yAxisTitle, cfg.yAxisRange, initialData, band.length > 0 ? band : undefined);
      bindHover(element);
      const observer = observeElementResize(plotly, element);
      if (observer) {
        observers.push(observer);
      }
      await yieldToBrowser();
    }
    resizeObservers = observers;

    for (const element of Object.values(elements)) {
      if (!element) continue;
      applySeriesVisibility(plotly, element, get(seriesVisibility));
      schedulePlotlyResize(plotly, element);
    }
  }

  let currentView: TimeView = "day";

  function bindReadings() {
    const plotly = ensurePlotlyAvailable();

    const unsubscribe = realtimeReadings.subscribe((topic: ProcessedTopicName, payload: ProcessedReadingPayload) => {
      // Live points only make sense in raw (day) mode
      if (currentView !== "day") return;

      const element = get(chartElements)[topic];
      if (!element) return;
      if (!Array.isArray((element as any).data)) return;

      const time = new Date(Number(payload.time)).toISOString();
      const flagsText = formatFlags(payload.flags);
      const customdata = [payload.dq_score ?? null, flagsText];

      const updatesX: any[] = [];
      const updatesY: any[] = [];
      const updatesCustom: any[] = [];

      for (const series of SERIES) {
        updatesX.push([time]);
        const yVal = getSeriesValue(payload, series.key);
        updatesY.push([yVal]);
        updatesCustom.push([customdata]);
      }

      plotly.extendTraces(
        element,
        { x: updatesX, y: updatesY, customdata: updatesCustom },
        SERIES.map((_, idx) => idx),
        600,
      );

      applySeriesVisibility(plotly, element, get(seriesVisibility));
    });

    unsubscribers.push(unsubscribe);
  }

  async function start(view: TimeView = "day") {
    currentView = view;
    realtimeReadings.start();
    await fetchHistorical(view);
    cleanupObservers();
    await initCharts();
    bindReadings();
  }

  function stop() {
    for (const unsubscribe of unsubscribers) {
      unsubscribe();
    }
    unsubscribers.length = 0;
    cleanupObservers();
  }

  function setSeriesVisible(key: SeriesKey, visible: boolean) {
    seriesVisibility.update((current) => ({ ...current, [key]: visible }));
    const plotly = ensurePlotlyAvailable();
    const elements = get(chartElements);
    for (const element of Object.values(elements)) {
      if (!element) continue;
      applySeriesVisibility(plotly, element, get(seriesVisibility));
    }
  }

  async function setTimeView(view: TimeView) {
    currentView = view;
    await fetchHistorical(view);
    cleanupObservers();
    await initCharts();
  }

  return {
    dqHover,
    seriesVisibility,
    setSeriesVisible,
    setChartElement,
    start,
    stop,
    setTimeView,
  };
}
