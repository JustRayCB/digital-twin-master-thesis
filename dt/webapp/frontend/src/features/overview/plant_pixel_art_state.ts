/**
 * @fileoverview Visual transformation rules for the Plant Pixel Art component.
 * Maps plant health states to specific CSS colors, animations, and SVG rotations.
 */

import { PlantHealthState } from "$shared/types";

export function plantColorForState(state: PlantHealthState): string {
  switch (state) {
    case PlantHealthState.COLD:
      return "#5eead4";
    case PlantHealthState.HOT:
      return "#facc15";
    case PlantHealthState.THIRSTY:
      return "#65a30d";
    default:
      return "#4ade80";
  }
}

export function animationClassForState(state: PlantHealthState): string {
  switch (state) {
    case PlantHealthState.HOT:
      return "animate-wobble";
    default:
      return "";
  }
}

export function leafRotationForState(state: PlantHealthState): number {
  return state === PlantHealthState.THIRSTY ? 20 : 0;
}
