import { processedTopics } from "$shared/realtime";

export type PlantMetricSnapshot = {
  value: string;
  label: string;
  icon: string;
  accentClass: string;
};

export type PlantMetricsSnapshot = {
  greenRatio: PlantMetricSnapshot;
  leafCount: PlantMetricSnapshot;
  plantHeight: PlantMetricSnapshot;
};

export function createEmptyPlantMetricsSnapshot(): PlantMetricsSnapshot {
  return {
    greenRatio: {
      value: "—",
      label: "Green ratio",
      icon: "grass",
      accentClass: "bg-cozy-mint",
    },
    leafCount: {
      value: "—",
      label: "Leaf count",
      icon: "eco",
      accentClass: "bg-cozy-yellow",
    },
    plantHeight: {
      value: "—",
      label: "Plant height",
      icon: "height",
      accentClass: "bg-cozy-blue",
    },
  };
}

export function updatePlantMetricsFromReading(
  current: PlantMetricsSnapshot,
  topic: string,
  value: number | null,
): PlantMetricsSnapshot {
  if (value === null || !Number.isFinite(value)) {
    return current;
  }

  if (topic === processedTopics.greenRatio) {
    return {
      ...current,
      greenRatio: { ...current.greenRatio, value: `${Math.round(value)}%` },
    };
  }

  if (topic === processedTopics.leafCount) {
    return {
      ...current,
      leafCount: { ...current.leafCount, value: `${Math.round(value)} leaves` },
    };
  }

  if (topic === processedTopics.plantHeight) {
    return {
      ...current,
      plantHeight: { ...current.plantHeight, value: `${value.toFixed(1)} cm` },
    };
  }

  return current;
}
