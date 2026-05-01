/**
 * @fileoverview Default Plotly configs for Analytics topic charts.
 */

import { processedTopics } from "$shared/realtime/topics";
import type { PlotConfig, PlotLayout } from "$shared/charts";

const baseLayout: PlotLayout = {
  autosize: true,
  margin: { l: 60, r: 60, t: 50, b: 50 },
  xaxis: {
    title: { text: "Time" },
    type: "date",
    showgrid: true,
    gridcolor: "rgba(0,0,0,0.08)",
  },
  yaxis: {
    showgrid: true,
    gridcolor: "rgba(0,0,0,0.08)",
    rangemode: "tozero",
  },
  yaxis2: {
    title: { text: "Normalized (0–1)" },
    overlaying: "y",
    side: "right",
    range: [0, 1],
    showgrid: false,
  },
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  hovermode: "x unified",
  showlegend: true,
  legend: { orientation: "h" },
};

const baseConfig: PlotConfig = {
  displayModeBar: false,
  responsive: true,
  displaylogo: false,
};

function topicLayout(title: string, yAxisTitle: string, range?: [number, number]): PlotLayout {
  return {
    ...baseLayout,
    title: { text: title },
    yaxis: {
      ...(baseLayout.yaxis as Record<string, unknown>),
      title: { text: yAxisTitle },
      ...(range ? { range } : {}),
    },
  };
}

export const analyticsChartConfigByTopic: Partial<Record<string, { layout: PlotLayout; config: PlotConfig }>> = {
  [processedTopics.temperature]: {
    layout: topicLayout("Temperature", "Value (°C)"),
    config: baseConfig,
  },
  [processedTopics.humidity]: {
    layout: topicLayout("Humidity", "Value (%)", [0, 100]),
    config: baseConfig,
  },
  [processedTopics.soilMoisture]: {
    layout: topicLayout("Soil Moisture", "Value (%)", [0, 100]),
    config: baseConfig,
  },
  [processedTopics.lightIntensity]: {
    layout: topicLayout("Light Intensity", "Value (lux)"),
    config: baseConfig,
  },
  [processedTopics.greenRatio]: {
    layout: topicLayout("Green Ratio", "Value (%)", [0, 100]),
    config: baseConfig,
  },
  [processedTopics.leafCount]: {
    layout: topicLayout("Leaf Count", "Leaves"),
    config: baseConfig,
  },
  [processedTopics.plantHeight]: {
    layout: topicLayout("Plant Height", "Value (cm)"),
    config: baseConfig,
  },
};
