import type {
  ActiveAlert,
  ActionDispatchPayload,
  Actuator,
  CameraSnapshot,
  Reading,
  ReadingQuery,
  RoutineRecord,
  RoutineUpdatePayload,
} from "./types";

export const DEFAULT_PLANT_ID = 1;

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function buildQuery(params: QueryParams) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    search.set(key, String(value));
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchReadings(query: ReadingQuery = {}): Promise<Reading[]> {
  const params = {
    window: query.window ?? "raw",
    sensor_id: query.sensorId,
    plant_id: query.plantId,
    topic: query.topic,
    since: query.since,
    until: query.until,
  };
  const search = buildQuery(params);
  return requestJson(`/api/readings${search}`);
}

export function fetchActiveAlerts(plantId?: number): Promise<ActiveAlert[]> {
  const search = buildQuery({ plant_id: plantId });
  return requestJson(`/api/alerts/active${search}`);
}

export function fetchRoutines(plantId: number = DEFAULT_PLANT_ID): Promise<RoutineRecord[]> {
  const search = buildQuery({ plant_id: plantId });
  return requestJson(`/api/routines${search}`);
}

export function updateRoutine(routineId: number, payload: RoutineUpdatePayload): Promise<{ status: string }> {
  return requestJson(`/api/routines/${routineId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteRoutine(routineId: number): Promise<{ status: string }> {
  return requestJson(`/api/routines/${routineId}`, {
    method: "DELETE",
  });
}

export function dispatchAction(payload: ActionDispatchPayload): Promise<unknown> {
  return requestJson(`/api/actions/dispatch`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchActuators(): Promise<Actuator[]> {
  return requestJson(`/api/actuators`);
}

export async function fetchLatestCameraSnapshot(
  plantId: number = DEFAULT_PLANT_ID,
): Promise<CameraSnapshot | null> {
  const search = buildQuery({ plant_id: plantId });
  const response = await fetch(`/api/camera/snapshots/latest${search}`);

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return (await response.json()) as CameraSnapshot;
}
