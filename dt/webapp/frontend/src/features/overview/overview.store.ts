/**
 * @fileoverview Main state management for the Overview dashboard feature.
 * Coordinates fetching initial state from the API and merging in realtime updates from Socket.IO.
 */
import { derived, get, writable } from "svelte/store";

import { analyticsClient, controllerClient, dbClient } from "$shared/api";
import {
  buildProcessedReadingCacheKey,
  mergeProcessedReadingIntoCache,
  normalizeProcessedReadings,
} from "$shared/readings/processed_readings";
import { analyticsSubscriptions, cameraSubscriptions, readingSubscriptions } from "$shared/realtime";
import { processedTopics } from "$shared/realtime/topics";
import { openRoutineBuilder } from "$shared/stores/app.store";
import type {
  ActionDispatchPayload,
  ActionHistoryRecord,
  ActionResult,
  Actuator,
  CameraSnapshot,
  ControlMode,
  HealthAssessment,
  Reading,
  Recommendation,
  Routine,
  RoutineUpdatePayload,
} from "$shared/types";
import { formatChartTime } from "$shared/utils/time";
import {
  createEmptyPlantMetricsSnapshot,
  updatePlantMetricsFromReading,
  type PlantMetricsSnapshot,
} from "./plant_metrics";
import { mapRoutine } from "./overview.transforms";
import {
  createEmptyTelemetrySnapshot,
  updateTelemetryFromTopicSnapshot,
  type TelemetrySnapshot,
  type TopicSnapshot,
} from "./telemetry.transforms";
import { buildVitalitySnapshot, type VitalitySnapshot } from "./vitality";

type LoadingState = "idle" | "loading" | "loaded" | "error" | "partial";

type ErrorState = {
  message: string;
  cause: Error;
};

export type ActuatorControl = {
  id: number;
  name: string;
  isOn: boolean;
};

export type ClosedLoopStatusValue =
  | "idle"
  | "pending"
  | "accepted"
  | "advisory_only"
  | "rejected"
  | "failed"
  | "partial";

export type ClosedLoopStatusSummary = {
  status: ClosedLoopStatusValue;
  recommendation: Recommendation | null;
  actionResults: ActionResult[];
  latestRelatedAction: ActionHistoryRecord | null;
  correlationId: string | null;
  time: number | null;
};

let currentPlantId = 1;
let readingSubscriptionToken: { cleanup: () => void } | null = null;
let cameraSubscriptionToken: { cleanup: () => void } | null = null;
let recommendationLifecycleSubscriptionToken: { cleanup: () => void } | null = null;
let healthAssessmentSubscriptionToken: { cleanup: () => void } | null = null;
let receivedRealtimeSnapshot = false;
let actuatorStateById: Record<number, boolean> = {};
let latestSubmittedRecommendation: Recommendation | null = null;
let latestCompletedRecommendation: Recommendation | null = null;
let actionHistoryCache: ActionHistoryRecord[] = [];
let telemetryReadingCache: Reading[] = [];
const telemetryReadingCounts = new Map<string, number>();

let routinesOperationState: LoadingState = "idle";
let routinesOperationError: ErrorState | null = null;
let actuatorsOperationState: LoadingState = "idle";
let actuatorsOperationError: ErrorState | null = null;

const routinesData = writable<Routine[]>([]);
const actuatorsData = writable<ActuatorControl[]>([]);
const telemetryData = writable<TelemetrySnapshot>(createEmptyTelemetrySnapshot());
const vitalityData = writable<VitalitySnapshot>(buildVitalitySnapshot(null));
const plantMetricsData = writable<PlantMetricsSnapshot>(createEmptyPlantMetricsSnapshot());
const latestPhotoSrcData = writable<string | null>(null);
const controlModeData = writable<ControlMode | null>(null);
const closedLoopStatusData = writable<ClosedLoopStatusSummary>({
  status: "idle",
  recommendation: null,
  actionResults: [],
  latestRelatedAction: null,
  correlationId: null,
  time: null,
});
const loadingStateData = writable<LoadingState>("idle");
const errorStateData = writable<ErrorState | null>(null);

export const routines = derived(routinesData, ($routines) => $routines);
export const actuators = derived(actuatorsData, ($actuators) => $actuators);
export const telemetry = derived(telemetryData, ($telemetry) => $telemetry);
export const vitality = derived(vitalityData, ($vitality) => $vitality);
export const plantMetrics = derived(plantMetricsData, ($plantMetrics) => $plantMetrics);
export const latestPhotoSrc = derived(latestPhotoSrcData, ($latestPhotoSrc) => $latestPhotoSrc);
export const controlMode = derived(controlModeData, ($controlMode) => $controlMode);
export const closedLoopStatus = derived(closedLoopStatusData, ($closedLoopStatus) => $closedLoopStatus);
export const loadingState = derived(loadingStateData, ($loadingState) => $loadingState);
export const errorState = derived(errorStateData, ($errorState) => $errorState);

function getRecommendationTime(recommendation: Recommendation | null): number {
  if (!recommendation || !Number.isFinite(recommendation.time)) {
    return 0;
  }

  return recommendation.time;
}

function getLatestRecommendation(recommendations: Recommendation[]): Recommendation | null {
  if (recommendations.length === 0) {
    return null;
  }

  return recommendations.reduce((latest, candidate) =>
    getRecommendationTime(candidate) >= getRecommendationTime(latest) ? candidate : latest,
  );
}

function getLatestCompletedRecommendation(recommendations: Recommendation[]): Recommendation | null {
  const completed = recommendations.filter(
    (recommendation) =>
      Array.isArray(recommendation.action_results) && recommendation.action_results.length > 0,
  );

  return getLatestRecommendation(completed);
}

function normalizeRecommendation(payload: unknown): Recommendation | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Partial<Recommendation> & Record<string, unknown>;
  if (typeof record.correlation_id !== "string") {
    return null;
  }

  return {
    time: Number(record.time),
    plant_id: Number(record.plant_id),
    correlation_id: record.correlation_id,
    reason: typeof record.reason === "string" ? record.reason : "",
    confidence: Number(record.confidence),
    model_metadata: record.model_metadata as Recommendation["model_metadata"],
    actions: Array.isArray(record.actions) ? (record.actions as Recommendation["actions"]) : [],
    action_results: Array.isArray(record.action_results)
      ? (record.action_results as Recommendation["action_results"])
      : [],
  };
}

function normalizeHealthAssessment(payload: unknown): HealthAssessment | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Partial<HealthAssessment> & Record<string, unknown>;
  if (typeof record.state !== "string") {
    return null;
  }

  return {
    plant_id: Number(record.plant_id),
    timestamp: Number(record.timestamp),
    correlation_id: typeof record.correlation_id === "string" ? record.correlation_id : "",
    state: record.state as HealthAssessment["state"],
    score: typeof record.score === "number" && Number.isFinite(record.score) ? record.score : null,
    confidence:
      typeof record.confidence === "number" && Number.isFinite(record.confidence)
        ? record.confidence
        : null,
    summary: typeof record.summary === "string" ? record.summary : "",
  };
}

function resolveFinalStatus(actionResults: ActionResult[]): ClosedLoopStatusValue {
  if (actionResults.length === 0) {
    return "pending";
  }

  const firstStatus = actionResults[0].status;
  const hasMixedStatus = actionResults.some((result) => result.status !== firstStatus);
  return hasMixedStatus ? "partial" : firstStatus;
}

function findLatestRelatedAction(correlationId: string | null): ActionHistoryRecord | null {
  if (!correlationId) {
    return null;
  }

  const related = actionHistoryCache.filter((entry) => entry.correlation_id === correlationId);
  if (related.length === 0) {
    return null;
  }

  return related.reduce((latest, candidate) =>
    candidate.event_at >= latest.event_at ? candidate : latest,
  );
}

function refreshClosedLoopStatus(): void {
  const submitted = latestSubmittedRecommendation;
  const completed = latestCompletedRecommendation;

  if (!submitted && !completed) {
    closedLoopStatusData.set({
      status: "idle",
      recommendation: null,
      actionResults: [],
      latestRelatedAction: null,
      correlationId: null,
      time: null,
    });
    return;
  }

  const hasPendingRecommendation =
    !!submitted && (!completed || getRecommendationTime(submitted) > getRecommendationTime(completed));

  if (hasPendingRecommendation && submitted) {
    closedLoopStatusData.set({
      status: "pending",
      recommendation: submitted,
      actionResults: [],
      latestRelatedAction: findLatestRelatedAction(submitted.correlation_id),
      correlationId: submitted.correlation_id,
      time: submitted.time,
    });
    return;
  }

  if (completed) {
    closedLoopStatusData.set({
      status: resolveFinalStatus(completed.action_results),
      recommendation: completed,
      actionResults: completed.action_results,
      latestRelatedAction: findLatestRelatedAction(completed.correlation_id),
      correlationId: completed.correlation_id,
      time: completed.time,
    });
  }
}

function toErrorState(error: unknown): ErrorState {
  if (error instanceof Error) {
    return {
      message: error.message,
      cause: error,
    };
  }

  return {
    message: String(error),
    cause: new Error(String(error)),
  };
}

function combineLoadingStates(states: LoadingState[]): LoadingState {
  if (states.some((state) => state === "loading")) {
    return "loading";
  }
  if (states.some((state) => state === "error")) {
    return "error";
  }
  if (states.some((state) => state === "partial")) {
    return "partial";
  }
  if (states.every((state) => state === "loaded")) {
    return "loaded";
  }
  return "idle";
}

function combineErrors(errors: Array<ErrorState | null>): ErrorState | null {
  for (const error of errors) {
    if (error) {
      return error;
    }
  }
  return null;
}

function refreshOperationState(): void {
  loadingStateData.set(combineLoadingStates([routinesOperationState, actuatorsOperationState]));
  errorStateData.set(combineErrors([routinesOperationError, actuatorsOperationError]));
}

function setRoutinesOperationState(state: LoadingState, error: ErrorState | null = null): void {
  routinesOperationState = state;
  routinesOperationError = error;
  refreshOperationState();
}

function setActuatorsOperationState(state: LoadingState, error: ErrorState | null = null): void {
  actuatorsOperationState = state;
  actuatorsOperationError = error;
  refreshOperationState();
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

function mapActuator(actuator: Actuator, isOn: boolean): ActuatorControl {
  return {
    id: actuator.id,
    name: actuator.name,
    isOn,
  };
}

function extractPhotoSource(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Record<string, unknown>;
  const mimeType = record.mime_type;
  const image = record.image;
  if (typeof mimeType !== "string" || typeof image !== "string" || image.length === 0) {
    return null;
  }

  return `data:${mimeType};base64,${image}`;
}

function extractLatestValue(snapshot: TopicSnapshot, key: "value"): number | null {
  const series = snapshot[key];
  if (!Array.isArray(series) || series.length === 0) {
    return null;
  }
  const latest = series[series.length - 1];
  const value = Number(latest?.y);
  return Number.isFinite(value) ? value : null;
}

function getReadingTopic(reading: Reading): string | null {
  const topic = reading.topic;
  return typeof topic === "string" && topic.length > 0 ? topic : null;
}

const overviewReadingTopics = [
  processedTopics.temperature,
  processedTopics.humidity,
  processedTopics.soilMoisture,
  processedTopics.lightIntensity,
  processedTopics.greenRatio,
  processedTopics.leafCount,
  processedTopics.plantHeight,
];

function latestReading(readings: Reading[]): Reading | null {
  if (readings.length === 0) {
    return null;
  }

  return readings.reduce((latest, candidate) =>
    candidate.time >= latest.time ? candidate : latest,
  );
}

function getLatestCachedReading(topic: string): Reading | null {
  return latestReading(
    telemetryReadingCache.filter((reading) => getReadingTopic(reading) === topic),
  );
}

function clearTelemetryReadingsForTopic(topic: string): void {
  telemetryReadingCache = telemetryReadingCache.filter(
    (reading) => getReadingTopic(reading) !== topic,
  );

  for (const key of telemetryReadingCounts.keys()) {
    if (key.startsWith(`${topic}:`)) {
      telemetryReadingCounts.delete(key);
    }
  }
}

function pruneTelemetryReadingsForTopic(topic: string): void {
  const latest = getLatestCachedReading(topic);
  if (!latest) {
    return;
  }

  const retainedKeys = new Set<string>();
  telemetryReadingCache = telemetryReadingCache.filter((reading) => {
    if (getReadingTopic(reading) !== topic) {
      return true;
    }

    if (reading.time !== latest.time) {
      return false;
    }

    const key = buildProcessedReadingCacheKey(reading);
    if (key) {
      retainedKeys.add(key);
    }
    return true;
  });

  for (const key of telemetryReadingCounts.keys()) {
    if (key.startsWith(`${topic}:`) && !retainedKeys.has(key)) {
      telemetryReadingCounts.delete(key);
    }
  }
}

function cacheLatestReadingsForTopic(
  topic: string,
  readings: Reading[],
  counts: Map<string, number>,
): Reading | null {
  const topicReadings = readings.filter((reading) => getReadingTopic(reading) === topic);
  const latest = latestReading(topicReadings);
  const currentLatest = getLatestCachedReading(topic);

  if (!latest || (currentLatest && latest.time <= currentLatest.time)) {
    return currentLatest;
  }

  clearTelemetryReadingsForTopic(topic);
  const latestReadings = topicReadings.filter((reading) => reading.time === latest.time);
  telemetryReadingCache = [...telemetryReadingCache, ...latestReadings];

  for (const reading of latestReadings) {
    const key = buildProcessedReadingCacheKey(reading);
    if (key) {
      telemetryReadingCounts.set(key, counts.get(key) ?? 1);
    }
  }

  return latestReading(latestReadings);
}

function mergeTelemetryReading(reading: Reading): Reading | null {
  const topic = getReadingTopic(reading);
  if (!topic) {
    return null;
  }

  telemetryReadingCache = mergeProcessedReadingIntoCache(
    telemetryReadingCache,
    telemetryReadingCounts,
    reading,
  );
  pruneTelemetryReadingsForTopic(topic);
  return getLatestCachedReading(topic);
}

function buildSnapshotFromReadingPayload(payload: unknown): TopicSnapshot {
  const value = Number((payload as { value?: unknown })?.value);
  const time = Number((payload as { time?: unknown })?.time);
  const timestamp = Number.isFinite(time) ? time : Date.now();
  const point = {
    x: formatChartTime(timestamp),
    y: Number.isFinite(value) ? value : null,
    customdata: [null, ""] as [number | null, string],
  };

  return {
    value: [point],
    raw_value: [],
    calibrated_value: [],
    normalized_value: [],
  };
}

function applyReadingToCards(reading: Reading): void {
  const topic = getReadingTopic(reading);
  if (!topic) {
    return;
  }

  const snapshot = buildSnapshotFromReadingPayload(reading);
  const value = extractLatestValue(snapshot, "value");
  plantMetricsData.update((current) => updatePlantMetricsFromReading(current, topic, value));

  telemetryData.update((current) =>
    updateTelemetryFromTopicSnapshot(current, topic, snapshot),
  );
}

function mapSnapshotToSrc(snapshot: CameraSnapshot): string {
  return `data:${snapshot.mime_type};base64,${snapshot.image}`;
}

function updateActuatorState(actuatorId: number, isOn: boolean): void {
  actuatorStateById = { ...actuatorStateById, [actuatorId]: isOn };

  actuatorsData.update((current) =>
    current.map((actuator) =>
      actuator.id === actuatorId ? { ...actuator, isOn } : actuator,
    ),
  );
}

function startRealtimeSubscriptions(): void {
  if (!readingSubscriptionToken) {
    readingSubscriptionToken = readingSubscriptions.subscribeToProcessedReadings((payload) => {
      const reading = mergeTelemetryReading(payload as Reading);
      if (!reading) {
        return;
      }

      applyReadingToCards(reading);
    });
  }

  if (!cameraSubscriptionToken) {
    cameraSubscriptionToken = cameraSubscriptions.subscribeToSnapshots((payload) => {
      const src = extractPhotoSource(payload);
      if (!src) {
        return;
      }

      receivedRealtimeSnapshot = true;
      latestPhotoSrcData.set(src);
    });
  }

  if (!recommendationLifecycleSubscriptionToken) {
    recommendationLifecycleSubscriptionToken = analyticsSubscriptions.subscribeToRecommendationLifecycle(
      (event) => {
        const recommendation = normalizeRecommendation(event.payload);
        if (!recommendation) {
          return;
        }

        if (event.type === "submitted") {
          if (getRecommendationTime(recommendation) >= getRecommendationTime(latestSubmittedRecommendation)) {
            latestSubmittedRecommendation = recommendation;
          }
          refreshClosedLoopStatus();
          return;
        }

        if (getRecommendationTime(recommendation) >= getRecommendationTime(latestCompletedRecommendation)) {
          latestCompletedRecommendation = recommendation;
        }
        refreshClosedLoopStatus();
        void loadActionHistoryForClosedLoop();
      },
    );
  }

  if (!healthAssessmentSubscriptionToken) {
    healthAssessmentSubscriptionToken = analyticsSubscriptions.subscribeToHealthAssessments((payload) => {
      const assessment = normalizeHealthAssessment(payload);
      if (!assessment || assessment.plant_id !== currentPlantId) {
        return;
      }

      vitalityData.set(buildVitalitySnapshot(assessment));
    });
  }
}

async function loadActionHistoryForClosedLoop(): Promise<void> {
  actionHistoryCache = await controllerClient.fetchActionHistory(currentPlantId, 50);
  refreshClosedLoopStatus();
}

async function loadClosedLoopStatus(): Promise<void> {
  const recommendationHistory = await analyticsClient.fetchRecommendationHistory(currentPlantId);
  latestSubmittedRecommendation = getLatestRecommendation(recommendationHistory);
  latestCompletedRecommendation = getLatestCompletedRecommendation(recommendationHistory);

  await loadActionHistoryForClosedLoop();
}

async function loadHealthAssessment(): Promise<void> {
  const healthHistory = await dbClient.fetchHealthHistory({ plantId: currentPlantId, limit: 1 });
  const [latest] = healthHistory;
  vitalityData.set(buildVitalitySnapshot(latest ?? null));
}

async function loadLatestReadings(): Promise<void> {
  const until = Date.now();
  const since = until - 24 * 60 * 60 * 1000;

  const readingsByTopic = await Promise.all(
    overviewReadingTopics.map(async (topic) => {
      const readings = await dbClient.fetchRawReadings({
        plantId: currentPlantId,
        topic,
        since,
        until,
      });
      const latest = latestReading(readings);
      const normalizedCache = normalizeProcessedReadings(
        latest ? readings.filter((reading) => reading.time === latest.time) : [],
      );
      return [topic, normalizedCache] as const;
    }),
  );

  const latestByTopic = readingsByTopic.map(([topic, normalizedCache]) =>
    [
      topic,
      cacheLatestReadingsForTopic(topic, normalizedCache.readings, normalizedCache.counts),
    ] as const,
  );

  telemetryData.update((current) => {
    let next = current;
    for (const [topic, reading] of latestByTopic) {
      if (!reading) {
        continue;
      }
      next = updateTelemetryFromTopicSnapshot(next, topic, buildSnapshotFromReadingPayload(reading));
    }
    return next;
  });

  plantMetricsData.update((current) => {
    let next = current;
    for (const [topic, reading] of latestByTopic) {
      next = updatePlantMetricsFromReading(next, topic, reading?.value ?? null);
    }
    return next;
  });
}

async function refreshRoutines(): Promise<void> {
  setRoutinesOperationState("loading");

  try {
    const data = await controllerClient.fetchRoutines(currentPlantId);
    routinesData.set(data.map(mapRoutine));
    setRoutinesOperationState("loaded");
  } catch (error) {
    const operationError = toErrorState(error);
    const hasCachedRoutines = get(routinesData).length > 0;
    setRoutinesOperationState(hasCachedRoutines ? "partial" : "error", operationError);
    throw error;
  }
}

async function refreshActuators(): Promise<void> {
  setActuatorsOperationState("loading");

  try {
    const data = await dbClient.fetchActuators(currentPlantId);
    const mapped = data
      .filter((actuator) => actuator.plant_id === currentPlantId)
      .sort((left, right) => left.name.localeCompare(right.name))
      .map((actuator) => {
        const stateFromMemory = actuatorStateById[actuator.id];
        const stateFromStatus = actuatorStatusToOn(actuator.status);
        const isOn = stateFromMemory ?? stateFromStatus ?? false;
        return mapActuator(actuator, isOn);
      });

    actuatorStateById = mapped.reduce<Record<number, boolean>>((map, actuator) => {
      map[actuator.id] = actuator.isOn;
      return map;
    }, { ...actuatorStateById });

    actuatorsData.set(mapped);
    setActuatorsOperationState("loaded");
  } catch (error) {
    const operationError = toErrorState(error);
    const hasCachedActuators = get(actuatorsData).length > 0;
    setActuatorsOperationState(hasCachedActuators ? "partial" : "error", operationError);
    throw error;
  }
}

async function loadControlMode(): Promise<void> {
  const mode = await controllerClient.fetchControlMode(currentPlantId);
  controlModeData.set(mode);
}

async function loadLatestSnapshotFallback(): Promise<void> {
  if (receivedRealtimeSnapshot || get(latestPhotoSrcData)) {
    return;
  }

  const snapshot = await dbClient.fetchLatestSnapshot(currentPlantId);
  if (!snapshot || receivedRealtimeSnapshot) {
    return;
  }

  latestPhotoSrcData.set(mapSnapshotToSrc(snapshot));
}

/**
 * Initializes the overview state by fetching hardware configuration and establishing realtime subscriptions.
 * @param plantId - The specific plant to monitor (defaults to 1).
 */
export async function initialize(plantId = 1): Promise<void> {
  currentPlantId = plantId;
  startRealtimeSubscriptions();

  await Promise.all([
    refreshRoutines(),
    refreshActuators(),
    loadControlMode(),
    loadLatestSnapshotFallback(),
    loadClosedLoopStatus(),
    loadHealthAssessment(),
    loadLatestReadings(),
  ]);
}

/**
 * Cleans up realtime subscriptions and resets the overview state to avoid memory leaks on view changes.
 */
export function destroy(): void {
  readingSubscriptionToken?.cleanup();
  readingSubscriptionToken = null;

  cameraSubscriptionToken?.cleanup();
  cameraSubscriptionToken = null;

  recommendationLifecycleSubscriptionToken?.cleanup();
  recommendationLifecycleSubscriptionToken = null;

  healthAssessmentSubscriptionToken?.cleanup();
  healthAssessmentSubscriptionToken = null;

  routinesOperationState = "idle";
  routinesOperationError = null;
  actuatorsOperationState = "idle";
  actuatorsOperationError = null;
  refreshOperationState();
}

export function reset(): void {
  destroy();

  receivedRealtimeSnapshot = false;
  actuatorStateById = {};
  latestSubmittedRecommendation = null;
  latestCompletedRecommendation = null;
  actionHistoryCache = [];
  telemetryReadingCache = [];
  telemetryReadingCounts.clear();

  routinesData.set([]);
  actuatorsData.set([]);
  telemetryData.set(createEmptyTelemetrySnapshot());
  vitalityData.set(buildVitalitySnapshot(null));
  plantMetricsData.set(createEmptyPlantMetricsSnapshot());
  latestPhotoSrcData.set(null);
  controlModeData.set(null);
  closedLoopStatusData.set({
    status: "idle",
    recommendation: null,
    actionResults: [],
    latestRelatedAction: null,
    correlationId: null,
    time: null,
  });

  routinesOperationState = "idle";
  routinesOperationError = null;
  actuatorsOperationState = "idle";
  actuatorsOperationError = null;
  refreshOperationState();
}

export async function createRoutine(payload: RoutineUpdatePayload): Promise<number> {
  const response = await controllerClient.createRoutine(payload);
  await refreshRoutines();
  return response.id;
}

export async function updateRoutine(id: number, payload: RoutineUpdatePayload): Promise<void> {
  await controllerClient.updateRoutine(id, payload);
  await refreshRoutines();
}

export async function toggleRoutine(id: number): Promise<void> {
  const routine = get(routinesData).find((item) => item.id === id);
  if (!routine) {
    return;
  }

  try {
    await updateRoutine(id, { enabled: !routine.active });
  } catch (error) {
    console.error("Failed to toggle routine", error);
  }
}

export async function deleteRoutine(id: number): Promise<void> {
  await controllerClient.deleteRoutine(id);
  await refreshRoutines();
}

export function editRoutine(id: number): void {
  const routine = get(routinesData).find((item) => item.id === id);
  if (!routine) {
    return;
  }

  openRoutineBuilder({
    id: routine.id,
    plant_id: routine.plant_id ?? currentPlantId,
    name: routine.name,
    enabled: routine.active,
    graph: routine.graph,
  });
}

export async function dispatchAction(payload: ActionDispatchPayload): Promise<void> {
  await controllerClient.dispatchAction(payload);
  updateActuatorState(payload.actuator_id, payload.command === "ON");
}

export async function toggleActuator(id: number): Promise<void> {
  const actuator = get(actuatorsData).find((item) => item.id === id);
  if (!actuator) {
    return;
  }

  try {
    await dispatchAction({
      plant_id: currentPlantId,
      actuator_id: id,
      command: actuator.isOn ? "OFF" : "ON",
      source: "manual",
    });
  } catch (error) {
    console.error("Failed to dispatch actuator command", error);
  }
}

export function getActionHistory(limit?: number): Promise<ActionHistoryRecord[]> {
  return controllerClient.fetchActionHistory(currentPlantId, limit);
}
