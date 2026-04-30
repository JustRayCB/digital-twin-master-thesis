/**
 * @fileoverview Generic Plotly-facing types used by the shared chart layer.
 */

export type PlotTrace = Record<string, unknown>;
export type PlotLayout = Record<string, unknown>;
export type PlotConfig = Record<string, unknown>;

/**
 * Represents the complete specification for a Plotly chart, including data traces, layout configuration, and additional settings.
 */
export type PlotSpec = {
  data: PlotTrace[];
  layout?: PlotLayout;
  config?: PlotConfig;
};

/**
 * Defines the interface for a chart runtime, abstracting the underlying plotting library (e.g., Plotly.js) and providing methods for rendering, updating, resizing, and managing charts.
 */
export type ChartRuntime = {
  newPlot: (
    element: HTMLElement,
    data: PlotTrace[],
    layout?: PlotLayout,
    config?: PlotConfig,
  ) => Promise<void>;
  react: (
    element: HTMLElement,
    data: PlotTrace[],
    layout?: PlotLayout,
    config?: PlotConfig,
  ) => Promise<void>;
  resize: (element: HTMLElement) => void;
  purge: (element: HTMLElement) => void;
  addTraces: (element: HTMLElement, traces: PlotTrace[]) => Promise<void>;
};

/**
 * Represents a handle for managing a Plotly chart bound to a specific HTML element, providing methods to render, resize, and destroy the chart.
 */
export type PlotHandle = {
  render: (spec: PlotSpec) => Promise<void>;
  resize: () => void;
  destroy: () => void;
};
