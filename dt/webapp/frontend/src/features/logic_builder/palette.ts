/**
 * @fileoverview Defines the available node types that can be dragged onto the canvas.
 * Organizes them into Triggers (inputs) and Actions (outputs).
 */

import type { NodeType } from "./types";

/** Configuration for an item displayed in the drag-and-drop sidebar. */
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

/** Pre-defined list of available trigger nodes (sensors, timers). */
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

/** Pre-defined list of available action nodes (hardware actuators). */
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
    name: "Timed Light",
    desc: "Action",
    icon: "timer",
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
