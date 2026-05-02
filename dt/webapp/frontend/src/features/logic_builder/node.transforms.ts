/**
 * @fileoverview Utility functions for calculating node visual attributes and converting action payloads.
 */
import type { NodeConfig, NodeData } from "./types";

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

type GraphAction = {
  command?: string;
  duration?: number;
};

export function isGrowLightLabel(label: string): boolean {
  return label.trim().toLowerCase() === "grow light";
}

export function isTimedLightLabel(label: string): boolean {
  return label.trim().toLowerCase() === "timed light";
}

export function defaultActionConfig(label: string): NodeConfig {
  if (isGrowLightLabel(label)) {
    return { actionState: true };
  }
  if (isTimedLightLabel(label)) {
    return { duration: 10, unit: "s" };
  }
  return { duration: 10, unit: "s" };
}

export function actionConfigFromGraphAction(label: string, action: GraphAction): NodeConfig {
  if (isGrowLightLabel(label)) {
    return { actionState: action.command !== "OFF" };
  }
  return { duration: Number(action.duration ?? 0), unit: "s" };
}

export function buildActionPayload(label: string, config: NodeConfig, actuatorId: number | undefined) {
  if (isGrowLightLabel(label)) {
    return {
      actuator_id: actuatorId,
      command: config.actionState === false ? "OFF" : "ON",
      duration: 0,
    };
  }

  return {
    actuator_id: actuatorId,
    command: "ON",
    duration: Number(config.duration ?? 0),
  };
}
