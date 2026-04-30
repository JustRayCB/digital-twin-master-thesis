import type { PlotSpec } from "$shared/charts";
import type { CorrelationMethod } from "$features/analytics/correlation_math";

/**
 * Input data for building a correlation scatter plot specification.
 */
export type CorrelationScatterSpecInput = {
	x: number[];
	y: number[];
	dq1: number[];
	dq2: number[];
	sensor1Label: string;
	sensor2Label: string;
	/** Calculated correlation coefficient (r) */
	correlation: number;
	method: CorrelationMethod;
	sampleCount: number;
};

/**
 * Builds a Plotly-compatible PlotSpec for a correlation scatter plot.
 *
 * The plot displays the relationship between two sensors, with markers colored
 * based on the minimum data quality (DQ) of the two sensors at each point.
 *
 * @param input - The data and configuration for the plot
 * @returns A PlotSpec object for rendering
 */
export function buildCorrelationScatterSpec(
	input: CorrelationScatterSpecInput,
): PlotSpec {
	// Determine marker colors based on the minimum data quality of both sensors.
	// Green: DQ >= 0.8, Yellow: DQ >= 0.6, Red: DQ < 0.6
	const markerColors = input.dq1.map((dq1, index) => {
		const minDq = Math.min(dq1, input.dq2[index]);
		if (minDq >= 0.8) return "#10b981";
		if (minDq >= 0.6) return "#fbbf24";
		return "#ef4444";
	});

	const methodLabel = input.method === "spearman" ? "Spearman" : "Pearson";

	return {
		data: [
			{
				x: input.x,
				y: input.y,
				mode: "markers",
				type: "scatter",
				marker: {
					size: 8,
					color: markerColors,
					line: { color: "#1c1917", width: 1 },
				},
				cliponaxis: false,
				text: input.dq1.map(
					(dq1, index) => `DQ: ${Math.min(dq1, input.dq2[index]).toFixed(3)}`,
				),
				hovertemplate: `${input.sensor1Label}: %{x:.2f}<br>${input.sensor2Label}: %{y:.2f}<br>%{text}<extra></extra>`,
			},
		],
		layout: {
			title: {
				text: `r = ${input.correlation.toFixed(3)}`,
				font: { size: 16, family: "'Space Grotesk', sans-serif" },
			},
			annotations: [
				{
					text: `${methodLabel} · ${input.sampleCount} matched samples`,
					x: 0,
					y: 1.12,
					xref: "paper",
					yref: "paper",
					showarrow: false,
					align: "left",
				},
			],
			xaxis: {
				title: { text: input.sensor1Label, standoff: 18 },
				automargin: true,
				showgrid: true,
				gridcolor: "rgba(0,0,0,0.05)",
			},
			yaxis: {
				title: { text: input.sensor2Label, standoff: 18 },
				automargin: true,
				showgrid: true,
				gridcolor: "rgba(0,0,0,0.05)",
			},
			margin: { l: 90, r: 40, t: 70, b: 90 },
			paper_bgcolor: "rgba(0,0,0,0)",
			plot_bgcolor: "rgba(255,255,255,1)",
			hovermode: "closest",
		},
	};
}
