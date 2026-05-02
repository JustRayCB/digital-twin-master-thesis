/**
 * @fileoverview Data models for the Logic Builder (visual node editor).
 * Contains both UI-specific state models and the serializable payloads expected by the backend logic compiler.
 */

/** Broad classification of a node's role in a routine. */
export type NodeType = "TRIGGER" | "ACTION";

/** Highly flexible bag of configuration properties entered by the user for a specific node. */
export interface NodeConfig {
  operator?: string;
  value?: string | number;
  unit?: string;
  time?: string;
  date?: string;
  everyDays?: number;
  at?: string;
  triggerKind?: "sensor" | "time" | "date" | "interval";
  actionState?: boolean;
  duration?: number;
  message?: string;
}

/** Represents a node on the visual canvas. */
export interface NodeData {
  id: string;
  type: NodeType;
  x: number;
  y: number;
  label: string;
  config: NodeConfig;
  icon: string;
  bgClass: string;
  inputs: boolean;
  outputs: boolean;
}

/** Represents a visual connection between two nodes. */
export interface Edge {
  id: string;
  source: string;
  target: string;
}

/** State of the infinite-canvas camera. */
export interface Viewport {
  x: number;
  y: number;
  zoom: number;
}

/** Complete state of a visual routine diagram. */
export interface LogicBuilderGraph {
  nodes: NodeData[];
  edges: Edge[];
}

export interface ValidationError {
  code: string;
  nodeId?: string;
  message: string;
}

/** Backend representation: Visual metadata (coordinates) saved alongside the logic. */
export interface GraphUiNode {
  x?: number;
  y?: number;
  label?: string;
}

/** Backend representation: A condition that initiates a routine. */
export type GraphTrigger =
  | { type: "sensor"; topic?: string; op?: string; value?: number }
  | { type: "time"; time?: string }
  | { type: "date"; date?: string }
  | { type: "interval"; every_days?: number; at?: string };

/** Backend representation: An operation to perform when a trigger fires. */
export type GraphAction = {
  actuator_id?: number;
  command?: string;
  duration?: number;
};

/** Backend representation: A compiled logic node. */
export type GraphNode =
  | { id: string; kind: "trigger"; trigger: GraphTrigger }
  | { id: string; kind: "action"; action: GraphAction };

/** The final payload sent to the API to save a configured routine. */
export interface RoutineGraphPayload {
  nodes: GraphNode[];
  edges: Array<{ source: string; target: string }>;
  name: string;
  plant_id: number;
  ui?: Record<string, GraphUiNode>;
}
