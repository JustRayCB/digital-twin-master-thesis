/**
 * @fileoverview Transformation and validation logic for the Logic Builder graph.
 * Handles compiling the visual representation into the payload expected by the backend engine,
 * validating the user's logic before submission, and inflating a saved payload back into a visual diagram.
 */
import type { Actuator } from "$shared/types";
import { actionConfigFromGraphAction, buildActionPayload } from "./node.transforms";

import type {
  GraphNode,
  GraphUiNode,
  LogicBuilderGraph,
  NodeConfig,
  NodeData,
  NodeType,
  RoutineGraphPayload,
  ValidationError,
} from "./types";

function normalizeActuatorName(name: string): string {
  return name.trim().toLowerCase();
}

function actionKeyForLabel(label: string): string {
  return normalizeActuatorName(label);
}

function actionLookupKeysForLabel(label: string): string[] {
  const normalized = actionKeyForLabel(label);
  if (normalized === "pump") return ["pump", "water pump"];
  if (normalized === "grow light" || normalized === "timed light" || normalized === "light") {
    return [normalized, "light", "lights", "lamp"];
  }
  if (normalized === "ptc heater") return ["ptc heater", "heater", "heating"];
  return [normalized];
}

function actuatorIdForLabel(label: string, actuatorLookup: Record<string, number>): number | undefined {
  for (const key of actionLookupKeysForLabel(label)) {
    const actuatorId = actuatorLookup[key];
    if (actuatorId !== undefined) {
      return actuatorId;
    }
  }
  return undefined;
}

function topicForNodeLabel(label: string): string {
  const normalized = label.trim().toLowerCase();
  if (normalized === "temperature") return "dt.sensors.temperature";
  if (normalized === "humidity") return "dt.sensors.humidity";
  if (normalized === "light level") return "dt.sensors.light";
  return "dt.sensors.soil_moisture";
}

function triggerNodeDisplay(topic: string): { label: string; icon: string; bgClass: string; unit: string } {
  if (topic === "dt.sensors.temperature") {
    return { label: "Temperature", icon: "thermostat", bgClass: "bg-cozy-peach", unit: "°C" };
  }
  if (topic === "dt.sensors.humidity") {
    return { label: "Humidity", icon: "humidity_percentage", bgClass: "bg-cozy-blue", unit: "%" };
  }
  if (topic === "dt.sensors.light") {
    return { label: "Light Level", icon: "wb_sunny", bgClass: "bg-cozy-yellow", unit: "lux" };
  }
  return { label: "Moisture Level", icon: "water_drop", bgClass: "bg-cozy-lavender", unit: "%" };
}

function unitForTriggerLabel(label: string): string {
  return triggerNodeDisplay(topicForNodeLabel(label)).unit;
}

function actionNodeDisplay(label: string): { icon: string; bgClass: string } {
  const normalized = label.trim().toLowerCase();
  if (normalized === "fan") return { icon: "air", bgClass: "bg-cozy-blue" };
  if (normalized === "grow light" || normalized === "light" || normalized === "lamp") return { icon: "lightbulb", bgClass: "bg-cozy-yellow" };
  if (normalized === "timed light") return { icon: "timer", bgClass: "bg-cozy-yellow" };
  if (normalized === "ptc heater" || normalized === "heater") return { icon: "local_fire_department", bgClass: "bg-cozy-peach" };
  return { icon: "shower", bgClass: "bg-cozy-mint" };
}

function buildActuatorLookup(actuators: Actuator[]): Record<string, number> {
  const lookup: Record<string, number> = {};
  for (const actuator of actuators) {
    lookup[normalizeActuatorName(actuator.name)] = actuator.id;
  }
  return lookup;
}

function toEditorNode(
  node: GraphNode,
  index: number,
  graphUi: Record<string, GraphUiNode>,
  actuators: Actuator[],
): NodeData | null {
  const ui = graphUi[node.id];
  const x = Number(ui?.x ?? (node.kind === "trigger" ? 150 : 520));
  const y = Number(ui?.y ?? (120 + index * 120));
  const uiLabel = typeof ui?.label === "string" ? ui.label : undefined;

  if (node.kind === "trigger") {
    const trigger = node.trigger;
    if (trigger.type === "time") return { id: node.id, type: "TRIGGER", x, y, label: uiLabel ?? "Time of Day", config: { triggerKind: "time", time: trigger.time ?? "08:00" }, icon: "schedule", bgClass: "bg-cozy-yellow", inputs: false, outputs: true };
    if (trigger.type === "date") return { id: node.id, type: "TRIGGER", x, y, label: uiLabel ?? "Specific Date", config: { triggerKind: "date", date: trigger.date ?? "2026-02-14" }, icon: "event", bgClass: "bg-cozy-blue", inputs: false, outputs: true };
    if (trigger.type === "interval") return { id: node.id, type: "TRIGGER", x, y, label: uiLabel ?? "Every N Days", config: { triggerKind: "interval", everyDays: trigger.every_days ?? 2, at: trigger.at ?? "19:00" }, icon: "repeat", bgClass: "bg-cozy-peach", inputs: false, outputs: true };
    const display = triggerNodeDisplay(trigger.topic ?? "");
    return { id: node.id, type: "TRIGGER", x, y, label: uiLabel ?? display.label, config: { triggerKind: "sensor", operator: trigger.op ?? "<", value: trigger.value ?? 50, unit: display.unit }, icon: display.icon, bgClass: display.bgClass, inputs: false, outputs: true };
  }

  const actuatorId = Number(node.action.actuator_id);
  if (!Number.isFinite(actuatorId)) return null;
  const actuator = actuators.find((item) => item.id === actuatorId);
  const label = uiLabel ?? actuator?.name ?? `Actuator ${actuatorId}`;
  const display = actionNodeDisplay(label);
  return { id: node.id, type: "ACTION", x, y, label, config: actionConfigFromGraphAction(label, node.action), icon: display.icon, bgClass: display.bgClass, inputs: true, outputs: false };
}

export function defaultNodeConfig(type: NodeType, name: string): NodeConfig {
  if (type === "TRIGGER") {
    if (name === "Time of Day") return { triggerKind: "time", time: "08:00" };
    if (name === "Specific Date") return { triggerKind: "date", date: "2026-02-14" };
    if (name === "Every N Days") return { triggerKind: "interval", everyDays: 2, at: "19:00" };
    return { triggerKind: "sensor", operator: "<", value: 40, unit: unitForTriggerLabel(name) };
  }
  return { duration: 5, unit: "s" };
}

export function buildGraphPayload(graph: LogicBuilderGraph, actuators: Actuator[], name: string, plantId: number): RoutineGraphPayload {
  const actuatorLookup = buildActuatorLookup(actuators);
  const ui: Record<string, { x: number; y: number; label: string }> = {};
  const nodes = graph.nodes.map((node) => {
    ui[node.id] = { x: node.x, y: node.y, label: node.label };
    if (node.type === "TRIGGER") {
      const triggerKind = node.config.triggerKind ?? "sensor";
      if (triggerKind === "time") return { id: node.id, kind: "trigger" as const, trigger: { type: "time" as const, time: node.config.time } };
      if (triggerKind === "date") return { id: node.id, kind: "trigger" as const, trigger: { type: "date" as const, date: node.config.date } };
      if (triggerKind === "interval") return { id: node.id, kind: "trigger" as const, trigger: { type: "interval" as const, every_days: node.config.everyDays === undefined ? undefined : Number(node.config.everyDays), at: node.config.at } };
      return { id: node.id, kind: "trigger" as const, trigger: { type: "sensor" as const, topic: topicForNodeLabel(node.label), op: node.config.operator, value: node.config.value === undefined ? undefined : Number(node.config.value) } };
    }
    return { id: node.id, kind: "action" as const, action: buildActionPayload(node.label, node.config, actuatorIdForLabel(node.label, actuatorLookup)) };
  });
  return { nodes, edges: graph.edges.map((edge) => ({ source: edge.source, target: edge.target })), name, plant_id: plantId, ui };
}

export function deserializeGraphPayload(payload: unknown, actuators: Actuator[]): LogicBuilderGraph {
  const graph = (payload ?? {}) as Partial<RoutineGraphPayload>;
  const nodes = Array.isArray(graph.nodes)
    ? graph.nodes.map((node, index) => toEditorNode(node, index, graph.ui ?? {}, actuators)).filter((node): node is NodeData => node !== null)
    : [];
  const edges = Array.isArray(graph.edges)
    ? graph.edges.map((edge, index) => ({ id: `e${index + 1}`, source: edge.source, target: edge.target }))
    : [];
  return { nodes, edges };
}

export function getValidationErrors(routineName: string, graph: LogicBuilderGraph, actuators: Actuator[]): ValidationError[] {
  const errors: ValidationError[] = [];
  if (!routineName.trim()) {
    errors.push({ code: "empty_routine_name", message: "Routine name is required" });
  }
  const actuatorLookup = buildActuatorLookup(actuators);
  for (const node of graph.nodes) {
    if (node.type !== "ACTION") continue;
    if (actuatorIdForLabel(node.label, actuatorLookup) === undefined) {
      errors.push({ code: "missing_action_actuator", nodeId: node.id, message: `Action node actuator_id is missing for '${node.label}'` });
    }
  }
  return errors;
}

export type { LogicBuilderGraph } from "./types";
