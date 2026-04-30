/**
 * @fileoverview State and logic store for the Journal (Logbook) feature.
 * The Journal feature allows users to keep track of manual actions (like watering, pruning),
 * and automatically tracks critical system alerts. This store manages both the list of active alerts
 * and the history of journal entries.
 *
 * It interfaces with the REST API to fetch initial alerts and uses realtime subscriptions to stay
 * in sync with the backend. It also manages the state of the "Add Entry" form.
 */
import { derived, get, writable } from "svelte/store";

import { analyticsClient, controllerClient, dbClient } from "$shared/api";
import { actionSubscriptions, alertSubscriptions, analyticsSubscriptions } from "$shared/realtime";
import type { ActiveAlert, Actuator } from "$shared/types";
import type {
  JournalActionHistoryItem,
  JournalAlertItem,
  JournalEntry,
  JournalRecommendationHistoryItem,
} from "./journal.types";

export const journalIcons = [
  { value: "water_drop", label: "Water" },
  { value: "content_cut", label: "Pruning" },
  { value: "nutrition", label: "Fertilizer" },
  { value: "photo_camera", label: "Photo" },
  { value: "settings", label: "System" },
  { value: "edit_note", label: "Note" },
] as const;

export const journalColors = [
  { value: "bg-cozy-blue", label: "Blue" },
  { value: "bg-cozy-peach", label: "Peach" },
  { value: "bg-cozy-yellow", label: "Yellow" },
  { value: "bg-cozy-lavender", label: "Lavender" },
  { value: "bg-gray-200", label: "Gray" },
] as const;

export type JournalIconValue = (typeof journalIcons)[number]["value"];
export type JournalColorValue = (typeof journalColors)[number]["value"];

let alertLifecycleToken: { cleanup: () => void } | null = null;
let recommendationLifecycleToken: { cleanup: () => void } | null = null;
let actionToken: { cleanup: () => void } | null = null;
let actuatorMetadata: Actuator[] = [];
let activePlantId: number | null = null;

const alertsData = writable<JournalAlertItem[]>([]);
const entriesData = writable<JournalEntry[]>([]);
const recommendationHistoryData = writable<JournalRecommendationHistoryItem[]>([]);
const actionHistoryData = writable<JournalActionHistoryItem[]>([]);
const loadingStateData = writable<"idle" | "loading" | "loaded" | "error">("idle");

export const alerts = derived(alertsData, ($alerts) => $alerts);
export const entries = derived(entriesData, ($entries) => $entries);
export const recommendationHistory = derived(
  recommendationHistoryData,
  ($recommendationHistory) => $recommendationHistory,
);
export const actionHistory = derived(actionHistoryData, ($actionHistory) => $actionHistory);
export const loadingState = derived(loadingStateData, ($loadingState) => $loadingState);
export const isLoading = derived(loadingStateData, ($loadingState) => $loadingState === "loading");
export const entryTitle = writable("");
export const entryText = writable("");
export const entryTags = writable("");
export const entryIcon = writable<JournalIconValue>("edit_note");
export const entryColor = writable<JournalColorValue>("bg-gray-200");
export const tankLevelPercent = writable(35);
export const tankLiters = writable(3.5);
export const tankRefilledLabel = writable("2d Ago");
export const tankEmptyInLabel = writable("4 Days");

function inferAlertKind(payload: ActiveAlert): "water" | "temp" {
  const alertKey = String(payload.alert_key ?? "").toLowerCase();
  const message = String(payload.message ?? "").toLowerCase();
  const text = `${alertKey} ${message}`;

  if (text.includes("moisture") || text.includes("water") || text.includes("pump")) {
    return "water";
  }

  return "temp";
}

function toJournalAlertItem(alert: ActiveAlert): JournalAlertItem {
  const id = String(alert.alert_key ?? "").trim() || String(alert.alert_id ?? "").trim() || "alert";
  const message = String(alert.message ?? "").trim();
  const severity = typeof alert.severity === "string" ? alert.severity : null;
  const status = typeof alert.status === "string" ? alert.status : null;

  return {
    id,
    title: message || id,
    desc: [severity, status].filter(Boolean).join(" • "),
    kind: inferAlertKind(alert),
    severity,
    status,
  };
}

function upsertAlert(alert: JournalAlertItem): void {
  alertsData.update((current) => {
    const index = current.findIndex((item) => item.id === alert.id);
    if (index < 0) {
      return [alert, ...current];
    }

    const next = [...current];
    next[index] = alert;
    return next;
  });
}

function clearEntryForm(): void {
  entryTitle.set("");
  entryText.set("");
  entryTags.set("");
  entryIcon.set("edit_note");
  entryColor.set("bg-gray-200");
}

function formatDayLabel(value: Date): string {
  const now = new Date();
  const isToday =
    now.getFullYear() === value.getFullYear() &&
    now.getMonth() === value.getMonth() &&
    now.getDate() === value.getDate();

  if (isToday) {
    return "Today";
  }

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday =
    yesterday.getFullYear() === value.getFullYear() &&
    yesterday.getMonth() === value.getMonth() &&
    yesterday.getDate() === value.getDate();

  if (isYesterday) {
    return "Yesterday";
  }

  return value.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function sortRecommendationHistory(
  history: JournalRecommendationHistoryItem[],
): JournalRecommendationHistoryItem[] {
  return [...history].sort((left, right) => right.time - left.time);
}

function sortActionHistory(history: JournalActionHistoryItem[]): JournalActionHistoryItem[] {
  return [...history].sort((left, right) => right.event_at - left.event_at);
}

function normalizeActionHistoryItem(payload: unknown): JournalActionHistoryItem | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Partial<JournalActionHistoryItem> & { time?: number | null };
  const eventAt = Number(record.event_at ?? record.time);
  if (!Number.isFinite(eventAt)) {
    return null;
  }

  return {
    plant_id: Number(record.plant_id),
    execution_id: String(record.execution_id),
    action_id: String(record.action_id),
    actuator_id: Number(record.actuator_id),
    actuator_name: record.actuator_name ?? null,
    event_at: eventAt,
    duration: Number(record.duration ?? 0),
    command: String(record.command),
    reason: String(record.reason ?? ""),
    correlation_id: String(record.correlation_id),
    source: String(record.source ?? "unknown"),
    routine_id: record.routine_id ?? null,
    status: record.status ?? null,
    error_message: record.error_message ?? null,
  };
}

function attachActuatorNames(
  history: JournalActionHistoryItem[],
  actuators: Actuator[],
): JournalActionHistoryItem[] {
  const namesById = new Map(actuators.map((actuator) => [actuator.id, actuator.name]));

  return history.map((item) => ({
    ...item,
    actuator_name: namesById.get(item.actuator_id) ?? item.actuator_name ?? null,
  }));
}

function mergeActionHistory(
  current: JournalActionHistoryItem[],
  incoming: JournalActionHistoryItem[],
): JournalActionHistoryItem[] {
  const next = [...current];

  for (const item of incoming) {
    const index = next.findIndex(
      (existing) =>
        existing.execution_id === item.execution_id &&
        existing.action_id === item.action_id &&
        existing.status === item.status,
    );

    if (index < 0) {
      next.push(item);
      continue;
    }

    next[index] = item;
  }

  return sortActionHistory(next);
}

function upsertActionHistoryItem(item: JournalActionHistoryItem): void {
  actionHistoryData.update((current) => {
    return mergeActionHistory(current, [item]);
  });
}

function upsertRecommendationHistoryItem(item: JournalRecommendationHistoryItem): void {
  recommendationHistoryData.update((current) => {
    const index = current.findIndex((existing) => existing.correlation_id === item.correlation_id);
    if (index < 0) {
      return sortRecommendationHistory([item, ...current]);
    }

    const next = [...current];
    next[index] = item;
    return sortRecommendationHistory(next);
  });
}

function normalizeRecommendationHistoryItem(payload: unknown): JournalRecommendationHistoryItem | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Partial<JournalRecommendationHistoryItem>;
  if (typeof record.correlation_id !== "string") {
    return null;
  }

  return {
    time: Number(record.time),
    plant_id: Number(record.plant_id),
    correlation_id: record.correlation_id,
    reason: typeof record.reason === "string" ? record.reason : "",
    confidence: Number(record.confidence),
    model_metadata: record.model_metadata ?? null,
    actions: Array.isArray(record.actions) ? record.actions : [],
    action_results: Array.isArray(record.action_results) ? record.action_results : [],
  };
}

/**
 * Initializes the journal feature by fetching currently active alerts from the backend
 * and establishing a realtime subscription to listen for new alerts or alert resolutions.
 *
 * @param plantId - Optional identifier to filter alerts for a specific plant.
 */
export async function initialize(plantId?: number): Promise<void> {
  loadingStateData.set("loading");

  try {
    const resolvedPlantId = plantId ?? 1;
    if (activePlantId !== null && activePlantId !== resolvedPlantId) {
      actionHistoryData.set([]);
    }
    activePlantId = resolvedPlantId;

    if (!actionToken) {
      actionToken = actionSubscriptions.subscribeToActions((payload) => {
        const action = normalizeActionHistoryItem(payload);
        if (!action || action.plant_id !== activePlantId) {
          return;
        }

        upsertActionHistoryItem(attachActuatorNames([action], actuatorMetadata)[0]);
      });
    }

    const [activeAlerts, recommendationHistory, actionHistory, actuators] = await Promise.all([
      dbClient.fetchActiveAlerts(plantId),
      analyticsClient.fetchRecommendationHistory(resolvedPlantId),
      controllerClient.fetchActionHistory(resolvedPlantId),
      dbClient.fetchActuators(resolvedPlantId),
    ]);

    actuatorMetadata = actuators;

    alertsData.set(activeAlerts.map(toJournalAlertItem));
    recommendationHistoryData.set(sortRecommendationHistory(recommendationHistory));
    const normalizedActionHistory = actionHistory
      .map(normalizeActionHistoryItem)
      .filter((item): item is JournalActionHistoryItem => item !== null);
    const fetchedActionHistory = attachActuatorNames(normalizedActionHistory, actuators);
    actionHistoryData.update((current) =>
      mergeActionHistory(attachActuatorNames(current, actuators), fetchedActionHistory),
    );

    if (!alertLifecycleToken) {
      alertLifecycleToken = alertSubscriptions.subscribeToAlertLifecycle((event) => {
        if (event.type === "updated") {
          upsertAlert(toJournalAlertItem(event.payload as ActiveAlert));
          return;
        }

        const alertKey = String(event.payload ?? "");
        alertsData.update((current) => current.filter((alert) => alert.id !== alertKey));
      });
    }

    if (!recommendationLifecycleToken) {
      recommendationLifecycleToken = analyticsSubscriptions.subscribeToRecommendationLifecycle((event) => {
        const recommendation = normalizeRecommendationHistoryItem(event.payload);
        if (!recommendation) {
          return;
        }

        upsertRecommendationHistoryItem(recommendation);
      });
    }

    loadingStateData.set("loaded");
  } catch (error) {
    loadingStateData.set("error");
    throw error;
  }
}

/**
 * Marks an active alert as "acknowledged" by a user.
 * This updates the local UI optimistically and sends a request to the backend.
 *
 * @param alertKey - The unique identifier of the alert to acknowledge.
 * @param actor - The name or ID of the user acknowledging the alert.
 */
export async function acknowledgeAlert(alertKey: string, actor: string): Promise<void> {
  alertsData.update((current) =>
    current.map((alert) =>
      alert.id === alertKey
        ? {
            ...alert,
            desc: [alert.severity, "acknowledged"].filter(Boolean).join(" • "),
            status: "acknowledged",
          }
        : alert,
    ),
  );

  await dbClient.acknowledgeAlert(alertKey, actor);
}

/**
 * Clears an alert, indicating the underlying issue has been resolved.
 * This removes the alert from the local UI and informs the backend.
 *
 * @param alertKey - The unique identifier of the alert to clear.
 */
export async function clearAlert(alertKey: string): Promise<void> {
  await dbClient.clearAlert(alertKey);
  alertsData.update((current) => current.filter((alert) => alert.id !== alertKey));
}

/**
 * Reads the current state of the "Add Entry" form stores, creates a new `JournalEntry` object,
 * and adds it to the beginning of the entry history.
 *
 * Note: Currently this only updates local state and does not persist to a backend.
 *
 * @returns The generated unique ID of the new entry, or an empty string if validation failed.
 */
export function addEntry(): string {
  const title = get(entryTitle).trim() || "Journal Entry";
  const text = get(entryText).trim();
  if (!text) {
    return "";
  }

  const now = new Date();
  const id = `${now.valueOf()}-${Math.random().toString(36).slice(2, 8)}`;
  const tags = get(entryTags)
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

  entriesData.update((current) => [
    {
      id,
      title,
      text,
      tags,
      icon: get(entryIcon),
      iconColor: get(entryColor),
      dayLabel: formatDayLabel(now),
      timeLabel: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      createdAt: now.valueOf(),
    },
    ...current,
  ]);

  clearEntryForm();
  return id;
}

/**
 * Simulates refilling the water tank.
 * Updates the related store values to show a full tank.
 */
export function refillTank(): void {
  tankLevelPercent.set(100);
  tankLiters.set(10);
  tankRefilledLabel.set("Just now");
  tankEmptyInLabel.set("—");
}

/**
 * Tears down the journal feature state.
 * Cleans up realtime subscriptions and resets all stores to their initial values
 * to prevent memory leaks when navigating away from the Journal view.
 */
export function destroy(): void {
  alertLifecycleToken?.cleanup();
  alertLifecycleToken = null;
  recommendationLifecycleToken?.cleanup();
  recommendationLifecycleToken = null;
  actionToken?.cleanup();
  actionToken = null;
  alertsData.set([]);
  entriesData.set([]);
  recommendationHistoryData.set([]);
  actionHistoryData.set([]);
  actuatorMetadata = [];
  activePlantId = null;
  loadingStateData.set("idle");
  clearEntryForm();
  tankLevelPercent.set(35);
  tankLiters.set(3.5);
  tankRefilledLabel.set("2d Ago");
  tankEmptyInLabel.set("4 Days");
}
