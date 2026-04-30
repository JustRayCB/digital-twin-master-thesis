/**
 * @fileoverview Manages the lifecycle and bindings of multiple charting components within the Analytics view.
 * Provides a unified interface to initialize, update, and destroy various types of charts.
 */

import {
  createPlotHandle,
  createPlotlyRuntime,
  type ChartRuntime,
  type PlotHandle,
} from "$shared/charts";

type PlotlyElement = HTMLElement & {
  on?: (event: string, handler: (eventData: unknown) => void) => void;
  __analyticsHoverBound?: boolean;
  __analyticsUnhoverBound?: boolean;
};

export type PlotHandlePort = Pick<PlotHandle, "destroy" | "render" | "resize">;

/** Supported chart types in the analytics view. */
export type AnalyticsChartType =
  | "trends"
  | "correlation-scatter"
  | "correlation-matrix";

/** Dependency injection interface for testing the chart registry. */
export interface AnalyticsChartRegistryDependencies {
  createRuntime?: () => ChartRuntime | Promise<ChartRuntime | null> | null;
  createPlotHandle?: (element: HTMLElement, runtime: ChartRuntime | Promise<ChartRuntime>) => PlotHandlePort;
}

export interface AnalyticsChartRegistry {
  /**
   * Registers a chart with a unique ID and optional hover handlers.
   * @param id - Unique identifier for the chart instance.
   * @param type - The category of the chart.
   * @param element - The DOM element to mount the chart on.
   * @param onHover - Optional callback for Plotly hover events.
   * @param onUnhover - Optional callback for Plotly unhover events.
   */
  register(
    id: string,
    type: AnalyticsChartType,
    element: HTMLElement,
    onHover?: (point: unknown) => void,
    onUnhover?: () => void,
  ): PlotHandlePort;

  /** Retrieves a managed chart handle by its unique ID. */
  get(id: string): PlotHandlePort | undefined;

  /** Executes a callback for every managed chart of a specific type. */
  forEach(type: AnalyticsChartType, callback: (id: string, plot: PlotHandlePort) => void): void;

  /** Safely tears down all managed charts and removes their DOM bindings. */
  destroy(): void;
}

/** Factory function to create a new instance of the AnalyticsChartRegistry. */
export function createAnalyticsChartRegistry(
  dependencies: AnalyticsChartRegistryDependencies = {},
): AnalyticsChartRegistry {
  const createRuntime = dependencies.createRuntime ?? createPlotlyRuntime;
  const createAnalyticsPlotHandle = dependencies.createPlotHandle ?? createPlotHandle;

  const handles = new Map<string, { type: AnalyticsChartType; element: HTMLElement; handle: PlotHandlePort }>();

  let runtimeReady = false;
  let runtime: ChartRuntime | Promise<ChartRuntime> | null = null;

  function getRuntime(): ChartRuntime | Promise<ChartRuntime> | null {
    if (runtimeReady) {
      return runtime as ChartRuntime | Promise<ChartRuntime> | null;
    }

    const createdRuntime = createRuntime();
    runtimeReady = true;

    if (createdRuntime && typeof (createdRuntime as Promise<ChartRuntime | null>).then === "function") {
      runtime = (createdRuntime as Promise<ChartRuntime | null>).then((resolvedRuntime) => {
        if (!resolvedRuntime) {
          throw new Error("Plotly runtime is not available");
        }
        return resolvedRuntime;
      });
      return runtime;
    }

    if (!createdRuntime) {
      runtime = null;
      return null;
    }

    runtime = createdRuntime;
    return runtime;
  }

  function bindHoverHandlers(
    element: HTMLElement,
    onHover?: (point: unknown) => void,
    onUnhover?: () => void,
  ): void {
    const plotlyElement = element as PlotlyElement;
    if (!plotlyElement.on) {
      return;
    }

    if (onHover && !plotlyElement.__analyticsHoverBound) {
      plotlyElement.on("plotly_hover", (eventData: unknown) => {
        const point = (eventData as { points?: unknown[] } | undefined)?.points?.[0];
        onHover(point);
      });
      plotlyElement.__analyticsHoverBound = true;
    }

    if (onUnhover && !plotlyElement.__analyticsUnhoverBound) {
      plotlyElement.on("plotly_unhover", () => {
        onUnhover();
      });
      plotlyElement.__analyticsUnhoverBound = true;
    }
  }

  function register(
    id: string,
    type: AnalyticsChartType,
    element: HTMLElement,
    onHover?: (point: unknown) => void,
    onUnhover?: () => void,
  ): PlotHandlePort {
    const existing = handles.get(id);
    if (existing) {
      if (existing.element === element) {
        return existing.handle;
      }

      existing.handle.destroy();
      handles.delete(id);
    }

    const runtime = getRuntime();
    if (!runtime) {
      throw new Error("Plotly runtime is not available");
    }

    const baseHandle = createAnalyticsPlotHandle(element, runtime);

    bindHoverHandlers(element, onHover, onUnhover);

    const handle: PlotHandlePort = {
      destroy: baseHandle.destroy,
      resize: baseHandle.resize,
      render: async (spec) => {
        await baseHandle.render(spec);
        bindHoverHandlers(element, onHover, onUnhover);
      },
    };

    handles.set(id, { type, element, handle });
    return handle;
  }

  function get(id: string): PlotHandlePort | undefined {
    return handles.get(id)?.handle;
  }

  function forEach(type: AnalyticsChartType, callback: (id: string, plot: PlotHandlePort) => void): void {
    for (const [id, entry] of handles.entries()) {
      if (entry.type === type) {
        callback(id, entry.handle);
      }
    }
  }

  function destroy(): void {
    for (const entry of handles.values()) {
      entry.handle.destroy();
    }
    handles.clear();
  }

  return {
    register,
    get,
    forEach,
    destroy,
  };
}
