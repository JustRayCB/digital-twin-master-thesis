/**
 * @fileoverview Central state manager for the Logic Builder feature.
 * Handles the graph state (nodes and edges), viewport panning/zooming, validation rules,
 * and saving the compiled routine back to the backend API.
 */
import { derived, get, writable, type Readable } from "svelte/store";

import { controllerClient, dbClient } from "$shared/api";
import type { Actuator, RoutineRecord, RoutineUpdatePayload } from "$shared/types";
import { buildGraphPayload, deserializeGraphPayload, getValidationErrors } from "./graph.operations";
import type {
  Edge,
  LogicBuilderGraph,
  NodeConfig,
  NodeData,
  ValidationError,
  Viewport,
} from "./types";

export type LoadingState = "idle" | "loading" | "loaded" | "error" | "partial";

export type ErrorState = {
  message: string;
  cause: Error;
};

export type RoutinesPort = {
  fetchRoutines(plantId?: number): Promise<RoutineRecord[]>;
  createRoutine(payload: RoutineUpdatePayload): Promise<number | { id: number; status: string }>;
  updateRoutine(id: number, payload: RoutineUpdatePayload): Promise<void | { status: string }>;
  deleteRoutine(id: number): Promise<void | { status: string }>;
};

export type MetadataPort = {
  fetchActuators(plantId?: number): Promise<Actuator[]>;
};

export interface LogicBuilderStoreDependencies {
  plantId?: number;
  routinesPort?: RoutinesPort;
  metadataPort?: MetadataPort;
}

export interface LogicBuilderStore {
  loadingState: Readable<LoadingState>;
  errorState: Readable<ErrorState | null>;
  routineName: Readable<string>;
  routineId: Readable<number | null>;
  nodes: Readable<NodeData[]>;
  edges: Readable<Edge[]>;
  actuators: Readable<Actuator[]>;
  viewport: Readable<Viewport>;
  connectingSourceId: Readable<string | null>;
  mousePos: Readable<{ x: number; y: number }>;

  initialize(): Promise<void>;
  destroy(): void;

  newGraph(): void;
  setRoutineName(name: string): void;
  loadGraph(routineId: number): Promise<void>;

  addNode(node: NodeData): void;
  removeNode(nodeId: string): void;
  addEdge(source: string, target: string): boolean;
  removeEdge(edgeId: string): void;
  updateNodeConfig(nodeId: string, config: Partial<NodeConfig>): void;

  setViewport(viewport: Viewport): void;
  resetView(): void;
  setConnectingSourceId(nodeId: string | null): void;
  setMousePos(pos: { x: number; y: number }): void;
  resetCanvasState(): void;

  getGraph(): LogicBuilderGraph;
  setGraph(graph: LogicBuilderGraph): void;

  isGraphValid(): boolean;
  getValidationErrors(): ValidationError[];

  saveGraph(): Promise<number>;
  deleteGraph(routineId: number): Promise<void>;
}

function toErrorState(error: unknown): ErrorState {
  if (error instanceof Error) {
    return {
      message: error.message,
      cause: error,
    };
  }

  return {
    message: String(error),
    cause: new Error(String(error)),
  };
}

function combineLoadingStates(states: LoadingState[]): LoadingState {
  if (states.some((state) => state === "loading")) {
    return "loading";
  }
  if (states.some((state) => state === "error")) {
    return "error";
  }
  if (states.some((state) => state === "partial")) {
    return "partial";
  }
  if (states.every((state) => state === "loaded")) {
    return "loaded";
  }
  return "idle";
}

function combineErrors(errors: Array<ErrorState | null>): ErrorState | null {
  for (const error of errors) {
    if (error) {
      return error;
    }
  }
  return null;
}

function toCreatedRoutineId(response: number | { id: number; status: string }): number {
  if (typeof response === "number") {
    return response;
  }
  return response.id;
}

function nextEdgeId(edges: Edge[]): string {
  const nextNumber = edges.reduce((highest, edge) => {
    const match = /^e(\d+)$/.exec(edge.id);
    return match ? Math.max(highest, Number(match[1])) : highest;
  }, 0) + 1;
  return `e${nextNumber}`;
}

export function createLogicBuilderStore(dependencies: LogicBuilderStoreDependencies = {}): LogicBuilderStore {
  const plantId = dependencies.plantId ?? 1;
  const routinesPort = dependencies.routinesPort ?? controllerClient;
  const metadataPort = dependencies.metadataPort ?? dbClient;

  const loadingStateData = writable<LoadingState>("idle");
  const errorStateData = writable<ErrorState | null>(null);
  const routineNameData = writable<string>("Untitled Routine");
  const routineIdData = writable<number | null>(null);
  const graphData = writable<LogicBuilderGraph>({ nodes: [], edges: [] });
  const actuatorsData = writable<Actuator[]>([]);
  const routinesData = writable<RoutineRecord[]>([]);
  const viewportData = writable<Viewport>({ x: 0, y: 0, zoom: 1 });
  const connectingSourceIdData = writable<string | null>(null);
  const mousePosData = writable<{ x: number; y: number }>({ x: 0, y: 0 });

  let routinesOperationState: LoadingState = "idle";
  let routinesOperationError: ErrorState | null = null;
  let actuatorsOperationState: LoadingState = "idle";
  let actuatorsOperationError: ErrorState | null = null;

  function refreshOperationState(): void {
    loadingStateData.set(combineLoadingStates([routinesOperationState, actuatorsOperationState]));
    errorStateData.set(combineErrors([routinesOperationError, actuatorsOperationError]));
  }

  function setRoutinesOperationState(state: LoadingState, error: ErrorState | null = null): void {
    routinesOperationState = state;
    routinesOperationError = error;
    refreshOperationState();
  }

  function setActuatorsOperationState(state: LoadingState, error: ErrorState | null = null): void {
    actuatorsOperationState = state;
    actuatorsOperationError = error;
    refreshOperationState();
  }

  async function refreshRoutines(): Promise<void> {
    setRoutinesOperationState("loading");

    try {
      const routines = await routinesPort.fetchRoutines(plantId);
      routinesData.set(routines);
      setRoutinesOperationState("loaded");
    } catch (error) {
      const operationError = toErrorState(error);
      const hasCachedRoutines = get(routinesData).length > 0;
      setRoutinesOperationState(hasCachedRoutines ? "partial" : "error", operationError);
      throw error;
    }
  }

  async function refreshActuators(): Promise<void> {
    setActuatorsOperationState("loading");

    try {
      const actuators = await metadataPort.fetchActuators(plantId);
      actuatorsData.set(actuators);
      setActuatorsOperationState("loaded");
    } catch (error) {
      const operationError = toErrorState(error);
      const hasCachedActuators = get(actuatorsData).length > 0;
      setActuatorsOperationState(hasCachedActuators ? "partial" : "error", operationError);
      throw error;
    }
  }

  async function initialize(): Promise<void> {
    await Promise.all([refreshActuators(), refreshRoutines()]);
  }

  function destroy(): void {
    routineNameData.set("Untitled Routine");
    routineIdData.set(null);
    graphData.set({ nodes: [], edges: [] });
    actuatorsData.set([]);
    routinesData.set([]);
    resetCanvasState();

    routinesOperationState = "idle";
    routinesOperationError = null;
    actuatorsOperationState = "idle";
    actuatorsOperationError = null;
    refreshOperationState();
  }

  function newGraph(): void {
    routineIdData.set(null);
    routineNameData.set("Untitled Routine");
    graphData.set({ nodes: [], edges: [] });
  }

  function setRoutineName(name: string): void {
    routineNameData.set(name);
  }

  async function loadGraph(routineId: number): Promise<void> {
    const routine = get(routinesData).find((item) => item.id === routineId);
    if (!routine) {
      throw new Error(`Routine ${routineId} not found`);
    }

    const loadedGraph = deserializeGraphPayload(routine.graph, get(actuatorsData));

    routineIdData.set(routine.id);
    routineNameData.set(routine.name || "Untitled Routine");
    graphData.set(loadedGraph);
  }

  function addNode(node: NodeData): void {
    graphData.update((current) => ({ ...current, nodes: [...current.nodes, node] }));
  }

  function removeNode(nodeId: string): void {
    graphData.update((current) => ({
      nodes: current.nodes.filter((node) => node.id !== nodeId),
      edges: current.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
    }));
  }

  function addEdge(source: string, target: string): boolean {
    if (source === target) {
      return false;
    }

    const graph = get(graphData);
    const hasSource = graph.nodes.some((node) => node.id === source);
    const hasTarget = graph.nodes.some((node) => node.id === target);
    if (!hasSource || !hasTarget) {
      return false;
    }

    const exists = graph.edges.some((edge) => edge.source === source && edge.target === target);
    if (exists) {
      return false;
    }

    graphData.update((current) => ({
      ...current,
      edges: [...current.edges, { id: nextEdgeId(current.edges), source, target }],
    }));
    return true;
  }

  function removeEdge(edgeId: string): void {
    graphData.update((current) => ({
      ...current,
      edges: current.edges.filter((edge) => edge.id !== edgeId),
    }));
  }

  function updateNodeConfig(nodeId: string, config: Partial<NodeConfig>): void {
    graphData.update((graph) => ({
      ...graph,
      nodes: graph.nodes.map((node) =>
        node.id === nodeId ? { ...node, config: { ...node.config, ...config } } : node,
      ),
    }));
  }

  function setViewport(viewport: Viewport): void {
    viewportData.set({ ...viewport });
  }

  function resetView(): void {
    viewportData.set({ x: 0, y: 0, zoom: 1 });
  }

  function setConnectingSourceId(nodeId: string | null): void {
    connectingSourceIdData.set(nodeId);
  }

  function setMousePos(pos: { x: number; y: number }): void {
    mousePosData.set({ ...pos });
  }

  function resetCanvasState(): void {
    resetView();
    connectingSourceIdData.set(null);
    mousePosData.set({ x: 0, y: 0 });
  }

  function getGraph(): LogicBuilderGraph {
    return get(graphData);
  }

  function setGraph(graph: LogicBuilderGraph): void {
    graphData.set({
      nodes: [...graph.nodes],
      edges: [...graph.edges],
    });
  }

  function getStoreValidationErrors(): ValidationError[] {
    return getValidationErrors(get(routineNameData), get(graphData), get(actuatorsData));
  }

  function isGraphValid(): boolean {
    return getStoreValidationErrors().length === 0;
  }

  async function saveGraph(): Promise<number> {
    const errors = getStoreValidationErrors();
    if (errors.length > 0) {
      const firstError = errors[0];
      throw new Error(firstError.message);
    }

    const routineName = get(routineNameData).trim();
    const payload: RoutineUpdatePayload = {
      plant_id: plantId,
      name: routineName,
      enabled: true,
      graph: buildGraphPayload(get(graphData), get(actuatorsData), routineName, plantId),
    };

    const existingId = get(routineIdData);
    if (existingId === null) {
      const createdResponse = await routinesPort.createRoutine(payload);
      const createdId = toCreatedRoutineId(createdResponse);
      routineIdData.set(createdId);
      return createdId;
    }

    await routinesPort.updateRoutine(existingId, payload);
    return existingId;
  }

  async function deleteGraph(routineId: number): Promise<void> {
    await routinesPort.deleteRoutine(routineId);
    newGraph();
  }

  return {
    loadingState: derived(loadingStateData, ($loadingStateData) => $loadingStateData),
    errorState: derived(errorStateData, ($errorStateData) => $errorStateData),
    routineName: derived(routineNameData, ($routineNameData) => $routineNameData),
    routineId: derived(routineIdData, ($routineIdData) => $routineIdData),
    nodes: derived(graphData, ($graphData) => $graphData.nodes),
    edges: derived(graphData, ($graphData) => $graphData.edges),
    actuators: derived(actuatorsData, ($actuatorsData) => $actuatorsData),
    viewport: derived(viewportData, ($viewportData) => $viewportData),
    connectingSourceId: derived(connectingSourceIdData, ($connectingSourceIdData) => $connectingSourceIdData),
    mousePos: derived(mousePosData, ($mousePosData) => $mousePosData),

    initialize,
    destroy,

    newGraph,
    setRoutineName,
    loadGraph,

    addNode,
    removeNode,
    addEdge,
    removeEdge,
    updateNodeConfig,

    setViewport,
    resetView,
    setConnectingSourceId,
    setMousePos,
    resetCanvasState,

    getGraph,
    setGraph,

    isGraphValid,
    getValidationErrors: getStoreValidationErrors,

    saveGraph,
    deleteGraph,
  };
}

export const logicBuilderStore = createLogicBuilderStore();
