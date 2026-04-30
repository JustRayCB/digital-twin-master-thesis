/**
 * @fileoverview Barrel export for the charting subsystem.
 * Provides generic Plotly interfaces and integrations.
 */

export { createPlotHandle } from "./plot.handle";
export type { ChartRuntime, PlotConfig, PlotHandle, PlotLayout, PlotSpec, PlotTrace } from "./plot.types";
export { createPlotlyRuntime } from "./plotly.runtime";
