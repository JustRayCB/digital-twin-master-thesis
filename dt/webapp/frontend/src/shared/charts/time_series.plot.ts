import { Plot, type ChartRuntime, type PlotConfig, type PlotLayout, type PlotTrace } from "./plot";
import type { AggregatedReading, Reading } from "$shared/types";
import { formatChartTime } from "$shared/utils/time";
import type { BandPoint, ChartSeriesKey, SeriesPoint } from "./chart.types";

export type TimeSeriesData = {
  x: Array<string | number | Date>;
  y: Array<number | null>;
};

export type SeriesStyle = {
  color?: string;
  dash?: string;
};

export class TimeSeriesPlot extends Plot {
  private readonly series = new Map<string, { data: TimeSeriesData; style: SeriesStyle }>();
  private readonly visibleSeries = new Set<string>();
  private timeRange: { start: Date; end: Date } | null = null;
  private liveUpdatesEnabled = false;
  private dualAxisEnabled = false;
  private secondaryMetrics: string[] = [];

  private static readonly SERIES: Array<{
    key: ChartSeriesKey;
    color: string;
    dash: string;
  }> = [
    { key: "value", color: "#1c1917", dash: "solid" },
    { key: "raw_value", color: "#6b7280", dash: "dot" },
    { key: "calibrated_value", color: "#ffdac1", dash: "dash" },
    { key: "normalized_value", color: "#c7cee3", dash: "dashdot" },
  ];

  private static readonly AGGREGATED_SERIES_MAP: Record<ChartSeriesKey, keyof AggregatedReading> = {
    value: "mean_value",
    raw_value: "avg_raw_value",
    calibrated_value: "avg_calibrated_value",
    normalized_value: "avg_normalized_value",
  };

  public constructor(
    element: HTMLElement,
    runtime: ChartRuntime,
    layout: PlotLayout = {},
    config: PlotConfig = {},
  ) {
    super(element, runtime, layout, config);
  }

  public render(data: PlotTrace[]): Promise<void> {
    this.applyTimeRangeToLayout();
    return this.runtime.newPlot(this.element, this.buildPlotData(data), this.layout, this.config);
  }

  public update(data: PlotTrace[]): Promise<void> {
    this.applyTimeRangeToLayout();
    return this.runtime.react(this.element, this.buildPlotData(data), this.layout, this.config);
  }

  public setTimeRange(start: Date, end: Date) {
    this.timeRange = { start, end };
  }

  public addSeries(name: string, data: TimeSeriesData, style: SeriesStyle = {}) {
    this.series.set(name, { data, style });
    this.visibleSeries.add(name);
  }

  public toggleSeriesVisibility(name: string, visible: boolean) {
    if (visible) {
      this.visibleSeries.add(name);
      return;
    }
    this.visibleSeries.delete(name);
  }

  public enableLiveUpdates(enabled: boolean) {
    this.liveUpdatesEnabled = enabled;
  }

  public setDualAxis(enabled: boolean, secondaryMetrics: string[] = []) {
    this.dualAxisEnabled = enabled;
    this.secondaryMetrics = secondaryMetrics;
  }

  public getVisibleSeries(): string[] {
    return Array.from(this.visibleSeries);
  }

  public formatReadingsForPlotly(readings: Reading[]): SeriesPoint[] {
    const sorted = [...readings].sort((left, right) => left.time - right.time);
    return sorted.map((reading) => ({
      x: formatChartTime(reading.time),
      y: this.toFiniteNumber(reading.value),
      customdata: [this.toFiniteNumber(reading.dq_score), this.formatFlags(reading.flags)],
    }));
  }

  public formatAggregatesForBands(aggregates: AggregatedReading[]): BandPoint[] {
    const sorted = [...aggregates].sort((left, right) => left.time - right.time);
    return sorted.map((reading) => {
      const meanValue = this.toFiniteNumber(reading.mean_value);
      const stddev = this.toFiniteNumber(reading.stddev_value);

      return {
        x: formatChartTime(reading.time),
        min: this.toFiniteNumber(reading.min_value),
        max: this.toFiniteNumber(reading.max_value),
        stddevLower: meanValue !== null && stddev !== null ? meanValue - stddev : null,
        stddevUpper: meanValue !== null && stddev !== null ? meanValue + stddev : null,
      };
    });
  }

  public renderReadings(
    _topic: string,
    readings: Reading[],
    aggregates: AggregatedReading[] = [],
  ): Promise<void> {
    for (const series of TimeSeriesPlot.SERIES) {
      const points = this.formatReadingsForSeries(readings, aggregates, series.key);
      this.addSeries(
        series.key,
        {
          x: points.map((point) => point.x),
          y: points.map((point) => point.y),
        },
        { color: series.color, dash: series.dash },
      );
    }

    const bandData = this.formatAggregatesForBands(aggregates);
    return this.update(this.buildBandTraces(bandData));
  }

  public async extendWithNewData(data: TimeSeriesData): Promise<void> {
    if (!this.liveUpdatesEnabled) {
      return;
    }
    await this.runtime.addTraces(this.element, [data as unknown as PlotTrace]);
  }

  private buildPlotData(data: PlotTrace[]): PlotTrace[] {
    if (this.series.size === 0) {
      return data;
    }

    const traces: PlotTrace[] = [];

    for (const [name, series] of this.series.entries()) {
      if (!this.visibleSeries.has(name)) {
        continue;
      }

      const points = series.data.x
        .map((x, idx) => ({ x, y: series.data.y[idx] ?? null }))
        .filter((point) => this.isInRange(point.x));

      traces.push({
        name,
        x: points.map((point) => point.x),
        y: points.map((point) => point.y),
        line: {
          color: series.style.color,
          dash: series.style.dash,
        },
        yaxis: this.dualAxisEnabled && this.secondaryMetrics.includes(name) ? "y2" : undefined,
      });
    }

    return [...traces, ...data];
  }

  private formatReadingsForSeries(
    readings: Reading[],
    aggregates: AggregatedReading[],
    key: ChartSeriesKey,
  ): SeriesPoint[] {
    if (readings.length > 0) {
      const sorted = [...readings].sort((left, right) => left.time - right.time);
      return sorted.map((reading) => ({
        x: formatChartTime(reading.time),
        y: this.toFiniteNumber(reading[key]),
        customdata: [this.toFiniteNumber(reading.dq_score), this.formatFlags(reading.flags)],
      }));
    }

    const sortedAggregates = [...aggregates].sort((left, right) => left.time - right.time);
    return sortedAggregates.map((reading) => {
      const value = reading[TimeSeriesPlot.AGGREGATED_SERIES_MAP[key]];
      return {
        x: formatChartTime(reading.time),
        y: this.toFiniteNumber(value),
        customdata: [this.toFiniteNumber(reading.avg_dq_score), ""],
      };
    });
  }

  private buildBandTraces(bands: BandPoint[]): PlotTrace[] {
    if (bands.length === 0) {
      return [];
    }

    const xs = bands.map((point) => point.x);
    const traces: PlotTrace[] = [];

    const hasStddev = bands.some(
      (point) => point.stddevLower !== undefined && point.stddevUpper !== undefined,
    );

    if (hasStddev) {
      traces.push({
        x: xs,
        y: bands.map((point) => point.stddevLower ?? null),
        mode: "lines",
        name: "σ lower",
        line: { width: 0 },
        showlegend: false,
        hoverinfo: "skip",
      });
      traces.push({
        x: xs,
        y: bands.map((point) => point.stddevUpper ?? null),
        mode: "lines",
        name: "σ upper",
        fill: "tonexty",
        fillcolor: "rgba(100,150,200,0.25)",
        line: { width: 0 },
        showlegend: false,
        hoverinfo: "skip",
      });
    }

    traces.push({
      x: xs,
      y: bands.map((point) => point.min),
      mode: "lines",
      name: "min",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    });
    traces.push({
      x: xs,
      y: bands.map((point) => point.max),
      mode: "lines",
      name: "max",
      fill: "tonexty",
      fillcolor: "rgba(100,100,100,0.12)",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    });

    return traces;
  }

  private formatFlags(flags: unknown): string {
    if (!flags || typeof flags !== "object") {
      return "";
    }

    const violations = Object.entries(flags as Record<string, unknown>)
      .filter(([key, value]) => key !== "valid_data_point" && value === true)
      .map(([key]) => key);

    return violations.length ? `flags: ${violations.join(", ")}` : "";
  }

  private toFiniteNumber(value: unknown): number | null {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  }

  private isInRange(timestamp: string | number | Date): boolean {
    if (!this.timeRange) {
      return true;
    }

    const value = this.toTimestamp(timestamp);
    if (value === null) {
      return true;
    }

    return value >= this.timeRange.start.getTime() && value <= this.timeRange.end.getTime();
  }

  private toTimestamp(value: string | number | Date): number | null {
    if (value instanceof Date) {
      return value.getTime();
    }
    if (typeof value === "number") {
      return value;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  private applyTimeRangeToLayout() {
    const layout = this.layout as Record<string, unknown>;
    const xaxis =
      typeof layout.xaxis === "object" && layout.xaxis !== null
        ? { ...(layout.xaxis as Record<string, unknown>) }
        : {};

    if (this.timeRange) {
      xaxis.range = [formatChartTime(this.timeRange.start.getTime()), formatChartTime(this.timeRange.end.getTime())];
      layout.xaxis = xaxis;
      return;
    }

    if ("range" in xaxis) {
      delete xaxis.range;
      layout.xaxis = xaxis;
    }
  }
}
