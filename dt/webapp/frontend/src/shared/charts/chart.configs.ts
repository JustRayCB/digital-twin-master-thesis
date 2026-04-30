/**
 * @fileoverview Default configurations for Plotly charts, organized by sensor topic.
 * Defines standard layouts, titles, axes bounds, and generic UI options.
 */

import { processedTopics } from "$shared/realtime/topics";
import type { PlotConfig, PlotLayout } from "./plot";

/** Central registry mapping a telemetry topic to its default visual representation. */
export const chartConfigByTopic: Partial<Record<string, { layout: PlotLayout; config: PlotConfig }>> = {
  [processedTopics.temperature]: {
    layout: { title: { text: "Temperature" }, xaxis: { type: "date" }, yaxis: { title: { text: "Value (°C)" } } },
    config: { displayModeBar: true, responsive: true, displaylogo: false },
  },
  [processedTopics.humidity]: {
    layout: {
      title: { text: "Humidity" },
      xaxis: { type: "date" },
      yaxis: { title: { text: "Value (%)" }, range: [0, 100] },
    },
    config: { displayModeBar: true, responsive: true, displaylogo: false },
  },
  [processedTopics.soilMoisture]: {
    layout: {
      title: { text: "Soil Moisture" },
      xaxis: { type: "date" },
      yaxis: { title: { text: "Value (%)" }, range: [0, 100] },
    },
    config: { displayModeBar: true, responsive: true, displaylogo: false },
  },
  [processedTopics.lightIntensity]: {
    layout: { title: { text: "Light Intensity" }, xaxis: { type: "date" }, yaxis: { title: { text: "Value (lux)" } } },
    config: { displayModeBar: true, responsive: true, displaylogo: false },
  },
};
