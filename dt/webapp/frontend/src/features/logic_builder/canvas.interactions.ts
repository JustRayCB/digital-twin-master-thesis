/**
 * @fileoverview Pure functions managing the complex user interactions on the infinite canvas.
 * Handles zooming, panning, node dragging, and edge (connector) drawing without mutating state directly.
 */

import { defaultNodeConfig } from "./graph.operations";
import type { LogicBuilderGraph, NodeData, NodeType, Viewport } from "./types";

/** Bounding box of the canvas DOM element used for projecting mouse coordinates. */
export interface CanvasBounds {
  left: number;
  top: number;
}

/** Represents the current state of any ongoing drag/pan operations. */
export interface CanvasInteractionState {
  isDraggingCanvas: boolean;
  draggedNodeId: string | null;
  lastMousePos: { x: number; y: number };
}

/** Payload transferred via the HTML5 Drag and Drop API when dragging items from the palette. */
export interface CanvasDragPayload {
  type: NodeType;
  name: string;
  bg: string;
  icon: string;
  inputs: boolean;
  outputs: boolean;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function createCanvasInteractionState(): CanvasInteractionState {
  return {
    isDraggingCanvas: false,
    draggedNodeId: null,
    lastMousePos: { x: 0, y: 0 },
  };
}

/**
 * Calculates a new viewport state based on mouse wheel events (zooming or panning).
 */
export function updateViewportFromWheel(
  viewport: Viewport,
  wheel: Pick<WheelEvent, "ctrlKey" | "metaKey" | "deltaX" | "deltaY">,
): {
  viewport: Viewport;
  shouldPreventDefault: boolean;
} {
  if (wheel.ctrlKey || wheel.metaKey) {
    return {
      shouldPreventDefault: true,
      viewport: {
        ...viewport,
        zoom: clamp(viewport.zoom - wheel.deltaY * 0.001, 0.5, 2),
      },
    };
  }

  return {
    shouldPreventDefault: false,
    viewport: {
      ...viewport,
      x: viewport.x - wheel.deltaX,
      y: viewport.y - wheel.deltaY,
    },
  };
}

/** Initiates a canvas panning operation if middle-click or background-click occurs. */
export function startCanvasPan(
  state: CanvasInteractionState,
  event: Pick<MouseEvent, "button" | "clientX" | "clientY"> & { targetIsCanvas: boolean },
): CanvasInteractionState {
  if (event.button !== 1 && !(event.button === 0 && event.targetIsCanvas)) {
    return state;
  }

  return {
    ...state,
    isDraggingCanvas: true,
    lastMousePos: { x: event.clientX, y: event.clientY },
  };
}

/** Updates the viewport offset while actively panning the canvas. */
export function moveCanvasPan(
  state: CanvasInteractionState,
  viewport: Viewport,
  event: Pick<MouseEvent, "clientX" | "clientY">,
): {
  state: CanvasInteractionState;
  viewport: Viewport;
} {
  if (!state.isDraggingCanvas) {
    return { state, viewport };
  }

  const dx = event.clientX - state.lastMousePos.x;
  const dy = event.clientY - state.lastMousePos.y;

  return {
    state: {
      ...state,
      lastMousePos: { x: event.clientX, y: event.clientY },
    },
    viewport: {
      ...viewport,
      x: viewport.x + dx,
      y: viewport.y + dy,
    },
  };
}

/** Initiates a node dragging operation. */
export function startNodeDrag(
  state: CanvasInteractionState,
  event: Pick<MouseEvent, "clientX" | "clientY"> & { nodeId: string },
): CanvasInteractionState {
  return {
    ...state,
    isDraggingCanvas: false,
    draggedNodeId: event.nodeId,
    lastMousePos: { x: event.clientX, y: event.clientY },
  };
}

/** Calculates new coordinates for a node currently being dragged, accounting for zoom scale. */
export function moveNodeDrag(
  state: CanvasInteractionState,
  graph: LogicBuilderGraph,
  viewport: Viewport,
  event: Pick<MouseEvent, "clientX" | "clientY">,
): {
  state: CanvasInteractionState;
  graph: LogicBuilderGraph;
} {
  if (!state.draggedNodeId) {
    return { state, graph };
  }

  const dx = (event.clientX - state.lastMousePos.x) / viewport.zoom;
  const dy = (event.clientY - state.lastMousePos.y) / viewport.zoom;

  return {
    state: {
      ...state,
      lastMousePos: { x: event.clientX, y: event.clientY },
    },
    graph: {
      ...graph,
      nodes: graph.nodes.map((node) =>
        node.id === state.draggedNodeId ? { ...node, x: node.x + dx, y: node.y + dy } : node,
      ),
    },
  };
}

/** Resets all dragging/panning states on mouse up. */
export function endCanvasInteractions(state: CanvasInteractionState): CanvasInteractionState {
  return {
    ...state,
    isDraggingCanvas: false,
    draggedNodeId: null,
  };
}

/** Marks a node as the starting point for drawing a new edge. */
export function startConnector(nodeId: string): string {
  return nodeId;
}

/** Completes the drawing of an edge if targeting a valid node. */
export function finishConnector(
  connectingSourceId: string | null,
  targetNodeId: string,
): {
  edge: { source: string; target: string } | null;
  nextConnectingSourceId: string | null;
} {
  if (!connectingSourceId || connectingSourceId === targetNodeId) {
    return {
      edge: null,
      nextConnectingSourceId: connectingSourceId,
    };
  }

  return {
    edge: {
      source: connectingSourceId,
      target: targetNodeId,
    },
    nextConnectingSourceId: null,
  };
}

/** Cancels drawing a connector if the user clicks empty canvas space. */
export function cancelConnectorOnCanvasClick(
  connectingSourceId: string | null,
  draggedNodeId: string | null,
): string | null {
  if (connectingSourceId && !draggedNodeId) {
    return null;
  }

  return connectingSourceId;
}

export function serializeCanvasDragPayload(payload: CanvasDragPayload): string {
  return JSON.stringify(payload);
}

/**
 * Instantiates a new node object when a palette item is dropped onto the canvas.
 * Correctly projects screen coordinates into the local canvas coordinate space.
 */
export function createDroppedNode(
  rawPayload: string | undefined,
  canvasBounds: CanvasBounds | null,
  viewport: Viewport,
  event: Pick<DragEvent, "clientX" | "clientY">,
  now: number = Date.now(),
): NodeData | null {
  if (!rawPayload || !canvasBounds) {
    return null;
  }

  let dropped: CanvasDragPayload;
  try {
    dropped = JSON.parse(rawPayload) as CanvasDragPayload;
  } catch {
    return null;
  }

  return {
    id: `n${now}`,
    type: dropped.type,
    x: (event.clientX - canvasBounds.left - viewport.x) / viewport.zoom - 128,
    y: (event.clientY - canvasBounds.top - viewport.y) / viewport.zoom - 40,
    label: dropped.name,
    config: defaultNodeConfig(dropped.type, dropped.name),
    icon: dropped.icon,
    bgClass: dropped.bg,
    inputs: dropped.inputs,
    outputs: dropped.outputs,
  };
}

/** Utility to project raw screen mouse coordinates into the zoom/panned canvas coordinate space. */
export function projectMouseToCanvas(
  event: Pick<MouseEvent, "clientX" | "clientY">,
  canvasBounds: CanvasBounds | null,
  viewport: Viewport,
  connectingSourceId: string | null,
): { x: number; y: number } | null {
  if (!connectingSourceId || !canvasBounds) {
    return null;
  }

  return {
    x: (event.clientX - canvasBounds.left - viewport.x) / viewport.zoom,
    y: (event.clientY - canvasBounds.top - viewport.y) / viewport.zoom,
  };
}
