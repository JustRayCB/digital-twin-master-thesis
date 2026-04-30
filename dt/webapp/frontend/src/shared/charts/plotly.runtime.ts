/**
 * @fileoverview Concrete implementation of the `ChartRuntime` interface using Plotly.js.
 */

import type { ChartRuntime } from "./plot.types";

type PlotlyModule = {
  newPlot: ChartRuntime["newPlot"];
  react: ChartRuntime["react"];
  addTraces: ChartRuntime["addTraces"];
  purge: ChartRuntime["purge"];
  Plots: { resize: ChartRuntime["resize"] };
};

let runtimePromise: Promise<ChartRuntime | null> | null = null;

function toPlotlyModule(module: unknown): PlotlyModule {
  const candidate = module as { default?: unknown };
  return (candidate.default ?? module) as PlotlyModule;
}

/**
 * Creates a runtime wrapper around Plotly.js.
 * @returns The initialized runtime, or null when running server-side.
 */
export function createPlotlyRuntime(): Promise<ChartRuntime | null> {
  if (typeof window === "undefined") {
    return Promise.resolve(null);
  }

  if (!runtimePromise) {
    runtimePromise = import("plotly.js-cartesian-dist-min").then((module) => {
      const plotly = toPlotlyModule(module);

      return {
        newPlot: (element, data, layout, config) => Promise.resolve(plotly.newPlot(element, data, layout, config)),
        react: (element, data, layout, config) => Promise.resolve(plotly.react(element, data, layout, config)),
        resize: (element) => plotly.Plots.resize(element),
        purge: (element) => plotly.purge(element),
        addTraces: (element, traces) => Promise.resolve(plotly.addTraces(element, traces)),
      };
    });
  }

  return runtimePromise;
}
