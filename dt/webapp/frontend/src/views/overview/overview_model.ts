import { get, writable } from "svelte/store";

import {
  DEFAULT_PLANT_ID,
  deleteRoutine as deleteRoutineRequest,
  dispatchAction,
  fetchActuators,
  fetchLatestCameraSnapshot,
  fetchRoutines,
  updateRoutine,
} from "../../api";
import { openRoutineBuilder } from "../../app_state";
import type { Actuator, CameraSnapshot, RoutineRecord } from "../../types";
import { PlantHealthState, type Routine } from "../../types";
import { cameraSnapshotTopic, processedTopics } from "../analytics/realtime_topics";
import { realtimeClient } from "../analytics/realtime_client";
import { realtimeReadings } from "../analytics/realtime_readings_store";

type ActuatorControl = {
  id: number;
  name: string;
  isOn: boolean;
};

type TelemetrySnapshot = {
  temperature: { value: string; label1: string; label2: string };
  humidity: { value: string; label1: string; label2: string };
  moisture: { value: string; label1: string; label2: string; needsWater: boolean };
  light: { value: string; label1: string; label2: string };
};

const actuatorStateById = writable<Record<number, boolean>>({});

function formatTelemetryValue(value: number | null, unit: string, digits = 0) {
  if (!Number.isFinite(value)) {
    return "—";
  }
  return `${Number(value).toFixed(digits)}${unit}`;
}

function extractLatestValue(snapshot: any, key: string): number | null {
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

function formatCurrentTime(value: Date) {
  return value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatLastUpdate(value: number) {
  if (!Number.isFinite(value)) {
    return "—";
  }
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatRoutineCondition(routine: RoutineRecord) {
  return routine.enabled ? "Enabled" : "Disabled";
}

function mapRoutine(routine: RoutineRecord): Routine {
  return {
    id: routine.id,
    name: routine.name,
    condition: formatRoutineCondition(routine),
    active: routine.enabled,
    graph: routine.graph,
    plant_id: routine.plant_id,
  };
}

function mapActuator(actuator: Actuator, isOn: boolean): ActuatorControl {
  return {
    id: actuator.id,
    name: actuator.name,
    isOn,
  };
}

function actuatorStatusToOn(status: string | null | undefined): boolean | null {
  if (typeof status !== "string") {
    return null;
  }
  const normalized = status.toLowerCase();
  if (normalized === "on") {
    return true;
  }
  if (normalized === "off") {
    return false;
  }
  return null;
}

function mergeActuatorStateMap(
  current: Record<number, boolean>,
  controls: ActuatorControl[],
): Record<number, boolean> {
  const merged = { ...current };
  for (const control of controls) {
    merged[control.id] = control.isOn;
  }
  return merged;
}

function buildPhotoSource(mimeType: string, image: string) {
  return `data:${mimeType};base64,${image}`;
}

function extractPhotoSource(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const mimeType = record.mime_type;
  const image = record.image;
  if (typeof mimeType !== "string") {
    return null;
  }
  if (typeof image !== "string" || !image) {
    return null;
  }
  return buildPhotoSource(mimeType, image);
}

export function createOverviewModel() {
  const healthState = writable<PlantHealthState>(PlantHealthState.HEALTHY);
  const routines = writable<Routine[]>([]);
  const actuators = writable<ActuatorControl[]>([]);
  const latestPhotoSrc = writable<string | null>(null);
  const connectionStatus = writable("Disconnected");
  const lastUpdate = writable("—");
  const currentTime = writable(formatCurrentTime(new Date()));
  const telemetry = writable<TelemetrySnapshot>({
    temperature: { value: "—", label1: "Room Ambient", label2: "Normal Range" },
    humidity: { value: "—", label1: "Air Sensor", label2: "Stable" },
    moisture: { value: "—", label1: "Soil Sensor A", label2: "Getting Dry", needsWater: false },
    light: { value: "—", label1: "Window Sensor", label2: "Optimal" },
  });

  let unsubscribeStatus: (() => void) | null = null;
  let unsubscribeReadings: (() => void) | null = null;
  let unsubscribeCamera: (() => void) | null = null;
  let clockInterval: ReturnType<typeof setInterval> | null = null;
  let receivedRealtimeSnapshot = false;

  async function loadRoutines() {
    const data = await fetchRoutines(DEFAULT_PLANT_ID);
    routines.set(data.map(mapRoutine));
  }

  async function loadActuators() {
    const data = await fetchActuators();
    const filtered = data.filter((actuator) => actuator.plant_id === DEFAULT_PLANT_ID);
    const sorted = filtered.sort((a, b) => a.name.localeCompare(b.name));
    const currentState = get(actuatorStateById);
    const next = sorted.map((actuator) => {
      const persistedState = currentState[actuator.id];
      const statusState = actuatorStatusToOn(actuator.status);
      const isOn = statusState ?? persistedState ?? false;
      return mapActuator(actuator, isOn);
    });
    actuators.set(next);
    actuatorStateById.set(mergeActuatorStateMap(currentState, next));
  }

  async function toggleRoutine(id: number) {
    const current = get(routines);
    const target = current.find((routine) => routine.id === id);
    if (!target) {
      return;
    }
    const nextActive = !target.active;
    const updated = current.map((routine) =>
      routine.id === id ? { ...routine, active: nextActive, condition: nextActive ? "Enabled" : "Disabled" } : routine,
    );
    routines.set(updated);
    try {
      await updateRoutine(id, { enabled: nextActive });
    } catch (error) {
      console.error("Failed to toggle routine", error);
      routines.set(current);
    }
  }

  function editRoutine(id: number) {
    const target = get(routines).find((routine) => routine.id === id);
    if (!target) {
      return;
    }
    openRoutineBuilder({
      id: target.id,
      plant_id: target.plant_id ?? DEFAULT_PLANT_ID,
      name: target.name,
      enabled: target.active,
      graph: target.graph,
    });
  }

  async function deleteRoutine(id: number) {
    const current = get(routines);
    const updated = current.filter((routine) => routine.id !== id);
    routines.set(updated);
    try {
      await deleteRoutineRequest(id);
    } catch (error) {
      console.error("Failed to delete routine", error);
      routines.set(current);
    }
  }

  async function toggleActuator(id: number) {
    const current = get(actuators);
    const target = current.find((actuator) => actuator.id === id);
    if (!target) {
      return;
    }
    const nextState = !target.isOn;
    const updated = current.map((actuator) =>
      actuator.id === id ? { ...actuator, isOn: nextState } : actuator,
    );
    actuators.set(updated);
    actuatorStateById.set(mergeActuatorStateMap(get(actuatorStateById), updated));
    try {
      await dispatchAction({
        plant_id: DEFAULT_PLANT_ID,
        actuator_id: id,
        command: nextState ? "ON" : "OFF",
        source: "manual",
      });
    } catch (error) {
      console.error("Failed to dispatch actuator command", error);
      actuators.set(current);
      actuatorStateById.set(mergeActuatorStateMap(get(actuatorStateById), current));
    }
  }

  function setHealthState(state: PlantHealthState) {
    healthState.set(state);
  }

  async function start() {
    realtimeReadings.start();

    if (!unsubscribeCamera) {
      unsubscribeCamera = realtimeClient.subscribe(cameraSnapshotTopic, (payload) => {
        const src = extractPhotoSource(payload);
        if (!src) {
          return;
        }
        receivedRealtimeSnapshot = true;
        latestPhotoSrc.set(src);
      });
    }

    if (!clockInterval) {
      currentTime.set(formatCurrentTime(new Date()));
      clockInterval = setInterval(() => {
        currentTime.set(formatCurrentTime(new Date()));
      }, 1000);
    }

    unsubscribeReadings = realtimeReadings.subscribe((topic, payload) => {
      lastUpdate.set(formatLastUpdate(Number(payload.time)));
      const snapshot = realtimeReadings.getSnapshot(topic);
      telemetry.update((current) => {
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
      });
    });

    const loadLatestSnapshot = async () => {
      if (receivedRealtimeSnapshot) {
        return;
      }
      try {
        const snapshot = await fetchLatestCameraSnapshot(DEFAULT_PLANT_ID);
        if (!snapshot || receivedRealtimeSnapshot) {
          return;
        }
        latestPhotoSrc.set(buildPhotoSource(snapshot.mime_type, snapshot.image));
      } catch (error) {
        console.error("Failed to load latest camera snapshot", error);
      }
    };

    await Promise.all([loadRoutines(), loadActuators(), loadLatestSnapshot()]);
  }

  function stop() {
    if (unsubscribeStatus) {
      unsubscribeStatus();
      unsubscribeStatus = null;
    }
    if (unsubscribeReadings) {
      unsubscribeReadings();
      unsubscribeReadings = null;
    }
    if (unsubscribeCamera) {
      unsubscribeCamera();
      unsubscribeCamera = null;
    }
    receivedRealtimeSnapshot = false;
    if (clockInterval) {
      clearInterval(clockInterval);
      clockInterval = null;
    }
  }

  return {
    healthState,
    routines,
    actuators,
    latestPhotoSrc,
    connectionStatus,
    lastUpdate,
    currentTime,
    telemetry,
    toggleRoutine,
    editRoutine,
    deleteRoutine,
    toggleActuator,
    setHealthState,
    start,
    stop,
  };
}
