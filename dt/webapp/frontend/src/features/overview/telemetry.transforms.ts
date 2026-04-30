/**
 * @fileoverview Logic for formatting and contextualizing raw telemetry readings.
 * Translates numeric values into human-readable strings and contextual labels (e.g., "Normal", "Needs Water").
 */

import { processedTopics } from "$shared/realtime/topics";

type TelemetrySeriesPoint = {
  x: string;
  y: number | null;
  customdata: [number | null, string];
};

export type TopicSnapshot = {
  value: TelemetrySeriesPoint[];
  raw_value: TelemetrySeriesPoint[];
  calibrated_value: TelemetrySeriesPoint[];
  normalized_value: TelemetrySeriesPoint[];
};

/** Formatted representation of the latest telemetry states for the UI. */
export type TelemetrySnapshot = {
  temperature: { value: string; label1: string; label2: string };
  humidity: { value: string; label1: string; label2: string };
  moisture: { value: string; label1: string; label2: string; needsWater: boolean };
  light: { value: string; label1: string; label2: string };
};

export function createEmptyTelemetrySnapshot(): TelemetrySnapshot {
  return {
    temperature: { value: "—", label1: "Room Ambient", label2: "Normal Range" },
    humidity: { value: "—", label1: "Air Sensor", label2: "Stable" },
    moisture: { value: "—", label1: "Soil Sensor A", label2: "Getting Dry", needsWater: false },
    light: { value: "—", label1: "Window Sensor", label2: "Optimal" },
  };
}

function formatTelemetryValue(value: number | null, unit: string, digits = 0) {
  if (!Number.isFinite(value)) {
    return "—";
  }
  return `${Number(value).toFixed(digits)}${unit}`;
}

function extractLatestValue(snapshot: TopicSnapshot, key: "value"): number | null {
  const series = snapshot?.[key];
  if (!Array.isArray(series) || series.length === 0) {
    return null;
  }
  const latest = series[series.length - 1];
  const value = Number(latest?.y);
  return Number.isFinite(value) ? value : null;
}

function temperatureLabel(value: number | null) {
  if (value === null) {
    return "—";
  }
  if (value < 18) {
    return "Cold";
  }
  if (value <= 26) {
    return "Normal";
  }
  return "Warm";
}

function humidityLabel(value: number | null) {
  if (value === null) {
    return "—";
  }
  if (value < 35) {
    return "Dry Air";
  }
  if (value <= 55) {
    return "Comfort";
  }
  return "Humid";
}

function moistureLabel(value: number | null) {
  if (value === null) {
    return "—";
  }
  if (value < 30) {
    return "Needs Water";
  }
  if (value <= 60) {
    return "Stable";
  }
  return "Wet Soil";
}

function lightLabel(value: number | null) {
  if (value === null) {
    return "—";
  }
  if (value < 400) {
    return "Low Light";
  }
  if (value <= 1000) {
    return "Good";
  }
  return "Bright";
}

/**
 * Merges a newly received realtime snapshot into the existing telemetry UI state.
 */
export function updateTelemetryFromTopicSnapshot(
  current: TelemetrySnapshot,
  topic: string,
  snapshot: TopicSnapshot,
): TelemetrySnapshot {
  if (topic === processedTopics.temperature) {
    const value = extractLatestValue(snapshot, "value");
    return {
      ...current,
      temperature: {
        ...current.temperature,
        value: formatTelemetryValue(value, "°C", 1),
        label2: temperatureLabel(value),
      },
    };
  }

  if (topic === processedTopics.humidity) {
    const value = extractLatestValue(snapshot, "value");
    return {
      ...current,
      humidity: {
        ...current.humidity,
        value: formatTelemetryValue(value, "%", 0),
        label2: humidityLabel(value),
      },
    };
  }

  if (topic === processedTopics.soilMoisture) {
    const value = extractLatestValue(snapshot, "value");
    const label2 = moistureLabel(value);
    return {
      ...current,
      moisture: {
        ...current.moisture,
        value: formatTelemetryValue(value, "%", 0),
        label2,
        needsWater: label2 === "Needs Water",
      },
    };
  }

  if (topic === processedTopics.lightIntensity) {
    const value = extractLatestValue(snapshot, "value");
    return {
      ...current,
      light: {
        ...current.light,
        value: formatTelemetryValue(value, "lx", 0),
        label2: lightLabel(value),
      },
    };
  }

  return current;
}
