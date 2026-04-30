/**
 * @fileoverview Core abstractions and interfaces for the charting subsystem.
 * Decouples the application code from direct dependency on Plotly.js internals.
 */

export type PlotTrace = Record<string, unknown>;
export type PlotLayout = Record<string, unknown>;
export type PlotConfig = Record<string, unknown>;

/**
 * Contract defining the minimal required charting operations.
 * Allows dependency injection of the actual Plotly.js library (or a mock).
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
 * Abstract base class for wrapping chart implementations.
 * Manages the lifecycle of a chart instance bound to a specific DOM element.
 */
export abstract class Plot {
  public constructor(
    protected readonly element: HTMLElement,
    protected readonly runtime: ChartRuntime,
    protected layout: PlotLayout = {},
    protected config: PlotConfig = {},
  ) {}

  /** Performs the initial rendering of the chart. */
  public abstract render(data: PlotTrace[]): Promise<void>;

  /** Efficiently updates the existing chart with new data traces. */
  public abstract update(data: PlotTrace[]): Promise<void>;

  /** Triggers the runtime to recalculate dimensions and redraw. */
  public resize() {
    this.runtime.resize(this.element);
  }

  /** Fully cleans up the chart instance and DOM bindings. */
  public destroy() {
    this.runtime.purge(this.element);
  }
}
