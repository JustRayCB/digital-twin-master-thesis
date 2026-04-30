import { Plot, type ChartRuntime, type PlotConfig, type PlotLayout, type PlotTrace } from "./plot";

export class CorrelationPlot extends Plot {
  private highlightedSensors: string[] = [];

  public constructor(
    element: HTMLElement,
    runtime: ChartRuntime,
    layout: PlotLayout = {},
    config: PlotConfig = {},
  ) {
    super(element, runtime, layout, config);
  }

  public render(data: PlotTrace[]): Promise<void> {
    this.applyHighlightToLayout();
    return this.runtime.newPlot(this.element, data, this.layout, this.config);
  }

  public update(data: PlotTrace[]): Promise<void> {
    this.applyHighlightToLayout();
    return this.runtime.react(this.element, data, this.layout, this.config);
  }

  public renderScatterMatrix(data: PlotTrace[]): Promise<void> {
    return this.render(data);
  }

  public renderCorrelationMatrix(coefficients: number[][]): Promise<void> {
    return this.render([
      {
        z: coefficients,
        type: "heatmap",
      },
    ]);
  }

  public highlightCorrelation(sensors: string[]) {
    this.highlightedSensors = sensors;
  }

  public clearHighlight() {
    this.highlightedSensors = [];
  }

  private applyHighlightToLayout() {
    const layout = this.layout as Record<string, unknown>;
    if (this.highlightedSensors.length === 0) {
      if ("annotations" in layout) {
        delete layout.annotations;
      }
      return;
    }

    layout.annotations = [
      {
        text: `Highlighted: ${this.highlightedSensors.join(", ")}`,
        x: 0,
        y: 1.12,
        xref: "paper",
        yref: "paper",
        showarrow: false,
        align: "left",
      },
    ];
  }
}
