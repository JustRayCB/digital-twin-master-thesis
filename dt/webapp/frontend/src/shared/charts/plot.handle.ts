/**
 * @fileoverview Generic element-bound Plotly handle.
 */

import type { ChartRuntime, PlotHandle, PlotSpec } from "./plot.types";

/**
 * Creates a PlotHandle for a given HTML element and chart runtime, allowing for rendering, resizing, and destruction of Plotly charts bound to that element.
 * @param element The HTML element to which the chart will be bound.
 * @param runtime The chart runtime providing methods for rendering and managing charts.
 * @returns A PlotHandle with methods to render, resize, and destroy the chart.
 * Note: The handle maintains internal state to track whether the chart has been rendered, ensuring that the appropriate Plotly method (newPlot vs. react) is called on subsequent renders.
 * This abstraction allows for flexible chart management without exposing the underlying Plotly API directly to consumers of the handle.
 * Example usage:
 * const element = document.getElementById("my-chart");
 * const runtime = createPlotlyRuntime();
 * const plotHandle = createPlotHandle(element, runtime);
 * plotHandle.render({ data: [...], layout: {...}, config: {...} });
 * plotHandle.resize();
 * plotHandle.destroy();
 * */
export function createPlotHandle(
	element: HTMLElement,
	runtime: ChartRuntime | Promise<ChartRuntime>,
): PlotHandle {
	const runtimeRef =
		typeof (runtime as Promise<ChartRuntime>).then === "function"
			? null
			: (runtime as ChartRuntime);
	const runtimePromise = runtimeRef
		? Promise.resolve(runtimeRef)
		: (runtime as Promise<ChartRuntime>);

	function withRuntime(callback: (activeRuntime: ChartRuntime) => void): void {
		if (runtimeRef) {
			if (!destroyed) {
				callback(runtimeRef);
			}
			return;
		}

		void runtimePromise.then((activeRuntime) => {
			if (!destroyed) {
				callback(activeRuntime);
			}
		}).catch(() => {
			// Runtime resolution errors are handled by render callers.
		});
	}
	let hasRendered = false;
	let destroyed = false;
	let isObserving = false;

	function canResizeElement(): boolean {
		if (element.isConnected === false) {
			return false;
		}

		if (typeof element.getClientRects === "function") {
			return element.getClientRects().length > 0;
		}

		return true;
	}

	function resizeElement(activeRuntime: ChartRuntime): void {
		if (!destroyed && canResizeElement()) {
			activeRuntime.resize(element);
		}
	}

	const observer =
		typeof ResizeObserver === "undefined"
			? null
			: new ResizeObserver(() => {
					if (!destroyed) {
						withRuntime((activeRuntime) => {
							resizeElement(activeRuntime);
						});
					}
				});

	function observeElement() {
		if (!observer || isObserving) {
			return;
		}

		observer.observe(element);
		isObserving = true;
	}

	observeElement();

	function scheduleResize() {
		if (typeof requestAnimationFrame !== "function") {
			setTimeout(() => {
				if (!destroyed) {
					withRuntime((activeRuntime) => {
						resizeElement(activeRuntime);
					});
				}
			}, 0);
			return;
		}

		requestAnimationFrame(() => {
			requestAnimationFrame(() => {
				if (!destroyed) {
					withRuntime((activeRuntime) => {
						resizeElement(activeRuntime);
					});
				}
			});
		});
	}

	return {
		render: async (spec: PlotSpec) => {
			if (destroyed) {
				return;
			}
			destroyed = false;
			observeElement();
			if (!hasRendered) {
				hasRendered = true;
				const activeRuntime = await runtimePromise;
				if (destroyed) {
					return;
				}
				await activeRuntime.newPlot(element, spec.data, spec.layout, spec.config);
				if (destroyed) {
					return;
				}
				scheduleResize();
				return;
			}

			const activeRuntime = await runtimePromise;
			if (destroyed) {
				return;
			}
			await activeRuntime.react(element, spec.data, spec.layout, spec.config);
		},
		resize: () => {
			if (destroyed) {
				return;
			}
			withRuntime((activeRuntime) => {
				resizeElement(activeRuntime);
			});
		},
		destroy: () => {
			hasRendered = false;
			destroyed = true;
			observer?.disconnect();
			isObserving = false;
			if (runtimeRef) {
				runtimeRef.purge(element);
				return;
			}

			void runtimePromise.then((activeRuntime) => {
				activeRuntime.purge(element);
			}).catch(() => {
				// Runtime resolution errors are handled by render callers.
			});
		},
	};
}
