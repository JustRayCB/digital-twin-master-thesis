import { get, writable } from "svelte/store";

import { autoPilotEnabled } from "../../stores/auto_pilot";
import type { RoutineRecord } from "../../types";

import type { Edge, NodeConfig, NodeData, NodeType, Viewport } from "./types";

const INITIAL_NODES: NodeData[] = [
  {
    id: "n1",
    type: "TRIGGER",
    x: 150,
    y: 200,
    label: "Moisture Level",
    config: { triggerKind: "sensor", operator: "<", value: 40, unit: "%" },
    icon: "water_drop",
    bgClass: "bg-cozy-lavender",
    inputs: false,
    outputs: true,
  },
  {
    id: "n2",
    type: "ACTION",
    x: 520,
    y: 200,
    label: "Pump",
    config: { duration: 5, unit: "s" },
    icon: "shower",
    bgClass: "bg-cozy-mint",
    inputs: true,
    outputs: false,
  },
];

const INITIAL_EDGES: Edge[] = [{ id: "e1", source: "n1", target: "n2" }];

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export interface DragPaletteItem {
  name: string;
  desc: string;
  icon: string;
  bg: string;
  type: NodeType;
  inputs: boolean;
  outputs: boolean;
  iconBg?: string;
}

export const triggerPalette: DragPaletteItem[] = [
  {
    name: "Moisture Level",
    desc: "Value Input",
    icon: "water_drop",
    bg: "bg-cozy-lavender",
    type: "TRIGGER",
    inputs: false,
    outputs: true,
  },
  {
    name: "Temperature",
    desc: "Value Input",
    icon: "thermostat",
    bg: "bg-cozy-peach",
    type: "TRIGGER",
    inputs: false,
    outputs: true,
  },
  {
    name: "Light Level",
    desc: "Value Input",
    icon: "wb_sunny",
    bg: "bg-cozy-yellow",
    type: "TRIGGER",
    inputs: false,
    outputs: true,
  },
  {
    name: "Time of Day",
    desc: "Clock Event",
    icon: "schedule",
    bg: "bg-cozy-yellow",
    type: "TRIGGER",
    inputs: false,
    outputs: true,
  },
  {
    name: "Specific Date",
    desc: "Calendar Event",
    icon: "event",
    bg: "bg-cozy-blue",
    type: "TRIGGER",
    inputs: false,
    outputs: true,
  },
  {
    name: "Every N Days",
    desc: "Interval Trigger",
    icon: "repeat",
    bg: "bg-cozy-peach",
    type: "TRIGGER",
    inputs: false,
    outputs: true,
  },
];

export const logicActionPalette: DragPaletteItem[] = [
  {
    name: "Pump",
    desc: "Action",
    icon: "shower",
    bg: "bg-cozy-mint",
    type: "ACTION",
    inputs: true,
    outputs: false,
  },
  {
    name: "Fan",
    desc: "Action",
    icon: "air",
    bg: "bg-cozy-blue",
    type: "ACTION",
    inputs: true,
    outputs: false,
  },
  {
    name: "Grow Light",
    desc: "Toggle State",
    icon: "lightbulb",
    bg: "bg-cozy-yellow",
    type: "ACTION",
    inputs: true,
    outputs: false,
  },
  {
    name: "PTC Heater",
    desc: "Action",
    icon: "local_fire_department",
    bg: "bg-cozy-peach",
    type: "ACTION",
    inputs: true,
    outputs: false,
  },
];

export function getConnectorPos(node: NodeData, type: "input" | "output") {
  const width = 256;
  const heightOffset = 65;
  if (type === "input") {
    return { x: node.x - 8, y: node.y + heightOffset };
  }
  return { x: node.x + width + 8, y: node.y + heightOffset };
}

export function renderPath(x1: number, y1: number, x2: number, y2: number) {
  const dx = Math.abs(x1 - x2) * 0.5;
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

type GraphTrigger = {
  type?: string;
  topic?: string;
  op?: string;
  value?: number;
  time?: string;
  date?: string;
  every_days?: number;
  at?: string;
};

type GraphAction = {
  actuator_id?: number;
  command?: string;
  duration?: number;
};

type GraphNode = {
  id?: string;
  kind?: string;
  trigger?: GraphTrigger;
  action?: GraphAction;
};

type GraphEdge = {
  source?: string;
  target?: string;
};

type GraphUiNode = {
  x?: number;
  y?: number;
  label?: string;
};

type RoutineGraphPayload = {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  ui?: Record<string, GraphUiNode>;
};

export function createLogicBuilderModel() {
  const nodes = writable<NodeData[]>(INITIAL_NODES);
  const edges = writable<Edge[]>(INITIAL_EDGES);
  const viewport = writable<Viewport>({ x: 0, y: 0, zoom: 1 });
  const routineName = writable<string>("Untitled Routine");
  const routineId = writable<number | null>(null);
  const actuators = writable<Record<string, number>>({});
  const actuatorNames = writable<Record<number, string>>({});

  const connectingSourceId = writable<string | null>(null);
  const mousePos = writable({ x: 0, y: 0 });

  let canvasElement: HTMLDivElement | null = null;

  let isDraggingCanvas = false;
  let draggedNodeId: string | null = null;
  let lastMousePos = { x: 0, y: 0 };

  function setCanvasElement(element: HTMLDivElement | null) {
    canvasElement = element;
  }

  function updateViewport(updater: (current: Viewport) => Viewport) {
    viewport.update(updater);
  }

  function setViewportValue(next: Viewport) {
    viewport.set(next);
  }

  function handleWheel(event: WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      updateViewport((current) => ({
        ...current,
        zoom: clamp(current.zoom - event.deltaY * 0.001, 0.5, 2),
      }));
      return;
    }

    updateViewport((current) => ({
      ...current,
      x: current.x - event.deltaX,
      y: current.y - event.deltaY,
    }));
  }

  function startPan(event: MouseEvent) {
    if (event.button === 1 || (event.button === 0 && event.target === canvasElement)) {
      isDraggingCanvas = true;
      lastMousePos = { x: event.clientX, y: event.clientY };
    }
  }

  function startDragNode(event: MouseEvent, id: string) {
    event.stopPropagation();
    draggedNodeId = id;
    lastMousePos = { x: event.clientX, y: event.clientY };
  }

  function handleWindowMouseMove(event: MouseEvent) {
    if (isDraggingCanvas) {
      const dx = event.clientX - lastMousePos.x;
      const dy = event.clientY - lastMousePos.y;
      updateViewport((current) => ({ ...current, x: current.x + dx, y: current.y + dy }));
      lastMousePos = { x: event.clientX, y: event.clientY };
    }

    if (draggedNodeId) {
      const currentZoom = get(viewport).zoom;
      const dx = (event.clientX - lastMousePos.x) / currentZoom;
      const dy = (event.clientY - lastMousePos.y) / currentZoom;
      nodes.update((current) =>
        current.map((node) =>
          node.id === draggedNodeId ? { ...node, x: node.x + dx, y: node.y + dy } : node,
        ),
      );
      lastMousePos = { x: event.clientX, y: event.clientY };
    }

    const sourceId = get(connectingSourceId);
    if (sourceId && canvasElement) {
      const rect = canvasElement.getBoundingClientRect();
      const currentViewport = get(viewport);
      mousePos.set({
        x: (event.clientX - rect.left - currentViewport.x) / currentViewport.zoom,
        y: (event.clientY - rect.top - currentViewport.y) / currentViewport.zoom,
      });
    }
  }

  function handleWindowMouseUp() {
    isDraggingCanvas = false;
    draggedNodeId = null;
  }

  function handleCanvasClick() {
    const sourceId = get(connectingSourceId);
    if (sourceId && !draggedNodeId) {
      connectingSourceId.set(null);
    }
  }

  function handleDragStart(
    event: DragEvent,
    type: NodeType,
    label: string,
    bgClass: string,
    icon: string,
    inputs: boolean,
    outputs: boolean,
  ) {
    if (!event.dataTransfer) {
      return;
    }
    event.dataTransfer.setData("nodeType", type);
    event.dataTransfer.setData("label", label);
    event.dataTransfer.setData("bgClass", bgClass);
    event.dataTransfer.setData("icon", icon);
    event.dataTransfer.setData("inputs", String(inputs));
    event.dataTransfer.setData("outputs", String(outputs));
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    if (!canvasElement || !event.dataTransfer) {
      return;
    }
    const rect = canvasElement.getBoundingClientRect();
    const type = event.dataTransfer.getData("nodeType") as NodeType;
    const label = event.dataTransfer.getData("label");
    const bgClass = event.dataTransfer.getData("bgClass");
    const icon = event.dataTransfer.getData("icon");
    const inputs = event.dataTransfer.getData("inputs") === "true";
    const outputs = event.dataTransfer.getData("outputs") === "true";

    if (!type) {
      return;
    }

    const currentViewport = get(viewport);

    const x = (event.clientX - rect.left - currentViewport.x) / currentViewport.zoom;
    const y = (event.clientY - rect.top - currentViewport.y) / currentViewport.zoom;

    let defaultConfig: NodeConfig = {};
    if (type === "TRIGGER") {
      if (label === "Time of Day") {
        defaultConfig = { triggerKind: "time", operator: "=", time: "08:00" };
      } else if (label === "Specific Date") {
        defaultConfig = { triggerKind: "date", date: "2026-02-14" };
      } else if (label === "Every N Days") {
        defaultConfig = { triggerKind: "interval", everyDays: 2, at: "19:00" };
      } else {
        const unit = label === "Temperature" ? "°C" : label === "Light Level" ? "lx" : "%";
        defaultConfig = {
          triggerKind: "sensor",
          operator: "<",
          value: 50,
          unit,
        };
      }
    } else if (type === "ACTION") {
      if (label.includes("Light")) {
        defaultConfig = { actionState: true };
      } else {
        defaultConfig = { duration: 10, unit: "s" };
      }
    }

    const newNode: NodeData = {
      id: `n${Date.now()}`,
      type,
      x,
      y,
      label,
      config: defaultConfig,
      icon,
      bgClass,
      inputs,
      outputs,
    };

    nodes.update((current) => [...current, newNode]);
  }

  function handleConnectStart(event: MouseEvent, nodeId: string) {
    event.stopPropagation();
    connectingSourceId.set(nodeId);

    if (!canvasElement) {
      return;
    }
    const rect = canvasElement.getBoundingClientRect();
    const currentViewport = get(viewport);
    mousePos.set({
      x: (event.clientX - rect.left - currentViewport.x) / currentViewport.zoom,
      y: (event.clientY - rect.top - currentViewport.y) / currentViewport.zoom,
    });
  }

  function handleConnectEnd(event: MouseEvent, targetId: string) {
    event.stopPropagation();
    const sourceId = get(connectingSourceId);

    if (sourceId && sourceId !== targetId) {
      edges.update((current) => {
        const exists = current.some(
          (edge) => edge.source === sourceId && edge.target === targetId,
        );
        if (exists) {
          return current;
        }
        return [...current, { id: `e${Date.now()}`, source: sourceId, target: targetId }];
      });
    }

    connectingSourceId.set(null);
  }

  function deleteNode(id: string) {
    nodes.update((current) => current.filter((node) => node.id !== id));
    edges.update((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
  }

  function clearCanvas() {
    nodes.set([]);
    edges.set([]);
  }

  function updateNodeConfig(id: string, updates: Partial<NodeConfig>) {
    nodes.update((current) =>
      current.map((node) =>
        node.id === id ? { ...node, config: { ...node.config, ...updates } } : node,
      ),
    );
  }

  function normalizeActuatorName(name: string) {
    return name.trim().toLowerCase().replace(/\s+/g, "_");
  }

  function actionKeyForLabel(label: string) {
    if (label.toLowerCase().includes("pump") || label.toLowerCase().includes("mist")) {
      return "pump";
    }
    if (label.toLowerCase().includes("fan")) {
      return "fan";
    }
    if (label.toLowerCase().includes("light")) {
      return "light";
    }
    if (label.toLowerCase().includes("heater")) {
      return "heater";
    }
    return normalizeActuatorName(label);
  }

  function triggerNodeFromTopic(topic: string) {
    const normalizedTopic = topic.toLowerCase();
    if (normalizedTopic.includes("temperature")) {
      return {
        label: "Temperature",
        icon: "thermostat",
        bgClass: "bg-cozy-peach",
        unit: "°C",
      };
    }
    if (normalizedTopic.includes("light")) {
      return {
        label: "Light Level",
        icon: "wb_sunny",
        bgClass: "bg-cozy-yellow",
        unit: "lx",
      };
    }
    return {
      label: "Moisture Level",
      icon: "water_drop",
      bgClass: "bg-cozy-lavender",
      unit: "%",
    };
  }

  function actionNodeDisplay(label: string) {
    const normalizedLabel = label.toLowerCase();
    if (normalizedLabel.includes("pump") || normalizedLabel.includes("mist")) {
      return { icon: "shower", bgClass: "bg-cozy-mint" };
    }
    if (normalizedLabel.includes("fan")) {
      return { icon: "air", bgClass: "bg-cozy-blue" };
    }
    if (normalizedLabel.includes("light")) {
      return { icon: "lightbulb", bgClass: "bg-cozy-yellow" };
    }
    if (normalizedLabel.includes("heater")) {
      return { icon: "local_fire_department", bgClass: "bg-cozy-peach" };
    }
    return { icon: "bolt", bgClass: "bg-cozy-white" };
  }

  async function loadActuators() {
    const response = await fetch("/api/actuators");
    if (!response.ok) {
      return;
    }
    const data: Array<{ id: number; name: string }> = await response.json();
    const lookup: Record<string, number> = {};
    const names: Record<number, string> = {};
    for (const actuator of data) {
      lookup[normalizeActuatorName(actuator.name)] = actuator.id;
      names[actuator.id] = actuator.name;
    }
    actuators.set(lookup);
    actuatorNames.set(names);
  }

  function toEditorNode(node: GraphNode, index: number, graphUi: Record<string, GraphUiNode>): NodeData | null {
    const nodeId = node.id;
    if (!nodeId || (node.kind !== "trigger" && node.kind !== "action")) {
      return null;
    }

    const ui = graphUi[nodeId];
    const x = Number(ui?.x ?? (node.kind === "trigger" ? 150 : 520));
    const y = Number(ui?.y ?? (120 + index * 120));
    const uiLabel = typeof ui?.label === "string" ? ui.label : undefined;

    if (node.kind === "trigger" && node.trigger) {
      const trigger = node.trigger;
      if (trigger.type === "time") {
        return {
          id: nodeId,
          type: "TRIGGER",
          x,
          y,
          label: uiLabel ?? "Time of Day",
          config: { triggerKind: "time", time: trigger.time ?? "08:00" },
          icon: "schedule",
          bgClass: "bg-cozy-yellow",
          inputs: false,
          outputs: true,
        };
      }
      if (trigger.type === "date") {
        return {
          id: nodeId,
          type: "TRIGGER",
          x,
          y,
          label: uiLabel ?? "Specific Date",
          config: { triggerKind: "date", date: trigger.date ?? "2026-02-14" },
          icon: "event",
          bgClass: "bg-cozy-blue",
          inputs: false,
          outputs: true,
        };
      }
      if (trigger.type === "interval") {
        return {
          id: nodeId,
          type: "TRIGGER",
          x,
          y,
          label: uiLabel ?? "Every N Days",
          config: {
            triggerKind: "interval",
            everyDays: trigger.every_days ?? 2,
            at: trigger.at ?? "19:00",
          },
          icon: "repeat",
          bgClass: "bg-cozy-peach",
          inputs: false,
          outputs: true,
        };
      }
      if (trigger.type === "sensor") {
        const topicDisplay = triggerNodeFromTopic(trigger.topic ?? "");
        return {
          id: nodeId,
          type: "TRIGGER",
          x,
          y,
          label: uiLabel ?? topicDisplay.label,
          config: {
            triggerKind: "sensor",
            operator: trigger.op ?? "<",
            value: trigger.value ?? 50,
            unit: topicDisplay.unit,
          },
          icon: topicDisplay.icon,
          bgClass: topicDisplay.bgClass,
          inputs: false,
          outputs: true,
        };
      }
    }

    if (node.kind === "action" && node.action && Number.isFinite(node.action.actuator_id)) {
      const action = node.action;
      const actuatorId = Number(action.actuator_id);
      const fallbackLabel = `Actuator ${actuatorId}`;
      const actuatorLabel = get(actuatorNames)[actuatorId] ?? fallbackLabel;
      const label = uiLabel ?? actuatorLabel;
      const display = actionNodeDisplay(label);
      return {
        id: nodeId,
        type: "ACTION",
        x,
        y,
        label,
        config: label.toLowerCase().includes("light")
          ? { actionState: action.command !== "OFF" }
          : { duration: Number(action.duration ?? 0), unit: "s" },
        icon: display.icon,
        bgClass: display.bgClass,
        inputs: true,
        outputs: false,
      };
    }

    return null;
  }

  function loadRoutine(routine: RoutineRecord | null) {
    if (!routine) {
      routineName.set("Untitled Routine");
      routineId.set(null);
      nodes.set(INITIAL_NODES);
      edges.set(INITIAL_EDGES);
      return;
    }

    const graph = routine.graph as RoutineGraphPayload | undefined;
    const graphNodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
    const graphEdges = Array.isArray(graph?.edges) ? graph.edges : [];
    const graphUi = graph?.ui && typeof graph.ui === "object" ? graph.ui : {};

    const loadedNodes = graphNodes
      .map((node, index) => toEditorNode(node, index, graphUi))
      .filter((node): node is NodeData => node !== null);

    const loadedNodeIds = new Set(loadedNodes.map((node) => node.id));
    const loadedEdges = graphEdges
      .filter(
        (edge): edge is { source: string; target: string } =>
          typeof edge.source === "string" && typeof edge.target === "string",
      )
      .filter((edge) => loadedNodeIds.has(edge.source) && loadedNodeIds.has(edge.target))
      .map((edge, index) => ({ id: `e${index + 1}`, source: edge.source, target: edge.target }));

    routineName.set(routine.name);
    routineId.set(routine.id);
    if (loadedNodes.length === 0) {
      nodes.set(INITIAL_NODES);
      edges.set(INITIAL_EDGES);
      return;
    }
    nodes.set(loadedNodes);
    edges.set(loadedEdges);
  }

  function buildGraphPayload() {
    const currentNodes = get(nodes);
    const currentEdges = get(edges);
    const ui: Record<string, { x: number; y: number; label: string }> = {};

    const graphNodes = currentNodes.map((node) => {
      ui[node.id] = { x: node.x, y: node.y, label: node.label };
      if (node.type === "TRIGGER") {
        const triggerKind = node.config.triggerKind ?? "sensor";
        if (triggerKind === "time") {
          return { id: node.id, kind: "trigger", trigger: { type: "time", time: node.config.time } };
        }
        if (triggerKind === "date") {
          return { id: node.id, kind: "trigger", trigger: { type: "date", date: node.config.date } };
        }
        if (triggerKind === "interval") {
          return {
            id: node.id,
            kind: "trigger",
            trigger: {
              type: "interval",
              every_days:
                node.config.everyDays === undefined ? undefined : Number(node.config.everyDays),
              at: node.config.at,
            },
          };
        }
        const label = node.label.toLowerCase();
        const topic = label.includes("temp")
          ? "dt.sensors.temperature"
          : label.includes("light")
            ? "dt.sensors.light_intensity"
            : "dt.sensors.soil_moisture";
        return {
          id: node.id,
          kind: "trigger",
          trigger: {
            type: "sensor",
            topic,
            op: node.config.operator,
            value: node.config.value === undefined ? undefined : Number(node.config.value),
          },
        };
      }

      const labelKey = actionKeyForLabel(node.label);
      const actuatorId = get(actuators)[labelKey];
      const command =
        node.label.toLowerCase().includes("light") && node.config.actionState === false ? "OFF" : "ON";
      return {
        id: node.id,
        kind: "action",
        action: {
          actuator_id: actuatorId,
          command,
          duration: Number(node.config.duration ?? 0),
        },
      };
    });

    return {
      nodes: graphNodes,
      edges: currentEdges.map((edge) => ({ source: edge.source, target: edge.target })),
      name: get(routineName),
      plant_id: 1,
      ui,
    };
  }

  async function saveRoutine() {
    const name = get(routineName).trim();
    if (!name) {
      throw new Error("Routine name is required");
    }
    const graph = buildGraphPayload();
    for (const node of graph.nodes) {
      if (node.kind === "action" && !node.action.actuator_id) {
        throw new Error("Action node actuator_id is missing");
      }
    }
    const payload = { plant_id: 1, name, graph, enabled: true };
    const existingId = get(routineId);
    const response = existingId
      ? await fetch(`/api/routines/${existingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      : await fetch("/api/routines", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "Failed to save routine");
    }
    if (!existingId) {
      const data = await response.json();
      routineId.set(data.id);
    }
  }

  return {
    nodes,
    edges,
    viewport,
    routineName,
    routineId,
    autoPilotEnabled,
    connectingSourceId,
    mousePos,
    setCanvasElement,
    setViewportValue,
    updateViewport,
    handleWindowMouseMove,
    handleWindowMouseUp,
    handlers: {
      handleWheel,
      startPan,
      startDragNode,
      handleCanvasClick,
      handleDragStart,
      handleDrop,
      handleDragOver,
      handleConnectStart,
      handleConnectEnd,
    },
    actions: {
      deleteNode,
      updateNodeConfig,
      clearCanvas,
      loadActuators,
      loadRoutine,
      saveRoutine,
    },
  };
}
