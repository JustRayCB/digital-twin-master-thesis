export type NodeType = "TRIGGER" | "ACTION";

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

export interface Edge {
  id: string;
  source: string;
  target: string;
}

export interface Viewport {
  x: number;
  y: number;
  zoom: number;
}
