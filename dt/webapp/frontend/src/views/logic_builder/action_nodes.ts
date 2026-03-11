import type { NodeConfig } from "./types";

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

export function buildActionPayload(label: string, config: NodeConfig, actuatorId: number) {
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
