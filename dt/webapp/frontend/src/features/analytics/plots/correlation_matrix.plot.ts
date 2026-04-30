import type { PlotSpec } from "$shared/charts";
import type { CorrelationMethod } from "$features/analytics/correlation_math";

/**
 * Input data for building a correlation matrix heatmap specification.
 */
export type CorrelationMatrixSpecInput = {
	/** 2D array representing the correlation matrix values */
	matrix: number[][];
	/** Labels for both x and y axes (sensor names) */
	labels: string[];
	selectedPair: [string, string];
	method: CorrelationMethod;
};

function getSelectedPairShapes(labels: string[], selectedPair: [string, string]) {
	const firstIndex = labels.indexOf(selectedPair[0]);
	const secondIndex = labels.indexOf(selectedPair[1]);
	if (firstIndex < 0 || secondIndex < 0 || firstIndex === secondIndex) {
		return [];
	}

	const common = {
		type: "rect" as const,
		xref: "x" as const,
		yref: "y" as const,
		line: { color: "#1c1917", width: 3 },
		fillcolor: "rgba(0,0,0,0)",
	};

	return [
		{
			...common,
			x0: firstIndex - 0.5,
			x1: firstIndex + 0.5,
			y0: secondIndex - 0.5,
			y1: secondIndex + 0.5,
		},
		{
			...common,
			x0: secondIndex - 0.5,
			x1: secondIndex + 0.5,
			y0: firstIndex - 0.5,
			y1: firstIndex + 0.5,
		},
	];
}

/**
 * Builds a Plotly-compatible PlotSpec for a correlation matrix heatmap.
 *
 * The plot uses a heatmap to visualize correlations between multiple sensors,
 * with a color scale ranging from blue (negative correlation) to red (positive correlation).
 *
 * @param input - The matrix data and labels for the plot
 * @returns A PlotSpec object for rendering
 */
export function buildCorrelationMatrixSpec(
	input: CorrelationMatrixSpecInput,
): PlotSpec {
	const methodLabel = input.method === "spearman" ? "Spearman" : "Pearson";

	return {
		data: [
			{
				z: input.matrix,
				x: input.labels,
				y: input.labels,
				type: "heatmap",
				colorscale: [
					[0, "#3b82f6"],
					[0.5, "#ffffff"],
					[1, "#ef4444"],
				],
				zmid: 0,
				zmin: -1,
				zmax: 1,
				text: input.matrix.map((row) => row.map((value) => value.toFixed(3))),
				hovertemplate: "%{y} vs %{x}<br>r = %{z:.3f}<extra></extra>",
				showscale: true,
				colorbar: {
					title: "Correlation",
					titleside: "right",
				},
			},
		],
		layout: {
			title: {
				text: "Sensor Correlation Matrix",
				font: { size: 18, family: "'Space Grotesk', sans-serif" },
			},
			annotations: [
				{
					text: `Selected pair: ${input.selectedPair[0]} ↔ ${input.selectedPair[1]} · ${methodLabel}`,
					x: 0,
					y: 1.14,
					xref: "paper",
					yref: "paper",
					showarrow: false,
					align: "left",
				},
			],
			shapes: getSelectedPairShapes(input.labels, input.selectedPair),
			xaxis: {
				side: "bottom",
				tickfont: { size: 12 },
			},
			yaxis: {
				tickfont: { size: 12 },
			},
			margin: { l: 100, r: 100, t: 60, b: 80 },
			paper_bgcolor: "rgba(0,0,0,0)",
			plot_bgcolor: "rgba(255,255,255,1)",
		},
	};
}
