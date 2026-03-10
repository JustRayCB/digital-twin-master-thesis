import type { ProcessedReadingPayload } from "./realtime_types";
import { processedTopics, type ProcessedTopicName } from "./realtime_topics";
import { realtimeClient } from "./realtime_client";

const SERIES = [
  { key: "value", label: "processed" },
  { key: "raw_value", label: "raw" },
  { key: "calibrated_value", label: "calibrated" },
  { key: "normalized_value", label: "normalized" },
] as const;

export type SeriesKey = (typeof SERIES)[number]["key"];

export type SeriesPoint = {
  x: string;
  y: number | null;
  customdata: [number | null, string];
};

export type TopicSnapshot = Record<SeriesKey, SeriesPoint[]>;

function formatFlags(flags: unknown) {
  if (!flags || typeof flags !== "object") {
    return "";
  }
  const entries = Object.entries(flags as Record<string, unknown>);
  const violations = entries
    .filter(([key, value]) => key !== "valid_data_point" && value === true)
    .map(([key]) => key);
  return violations.length ? `flags: ${violations.join(", ")}` : "";
}

function getSeriesValue(reading: ProcessedReadingPayload, key: SeriesKey) {
  const value = Number((reading as any)?.[key]);
  return Number.isFinite(value) ? value : null;
}

function emptySnapshot(): TopicSnapshot {
  return {
    value: [],
    raw_value: [],
    calibrated_value: [],
    normalized_value: [],
  };
}

type Subscriber = (topic: ProcessedTopicName, payload: ProcessedReadingPayload) => void;

function appendWithLimit<T>(items: T[], item: T, maxPoints: number) {
  items.push(item);
  if (items.length > maxPoints) {
    items.splice(0, items.length - maxPoints);
  }
}

type SeriesPointRecord = Partial<Record<SeriesKey, SeriesPoint>>;

function mergeSnapshots(
  existing: TopicSnapshot,
  readings: ProcessedReadingPayload[],
  maxPoints: number,
): TopicSnapshot {
  const pointsByTime = new Map<string, SeriesPointRecord>();

  for (const series of SERIES) {
    for (const point of existing[series.key]) {
      const entry = pointsByTime.get(point.x) ?? {};
      if (!entry[series.key]) {
        entry[series.key] = point;
      }
      pointsByTime.set(point.x, entry);
    }
  }

  for (const payload of readings) {
    const x = new Date(Number(payload.time)).toISOString();
    const existingEntry = pointsByTime.get(x);
    if (existingEntry) {
      continue;
    }
    const flagsText = formatFlags(payload.flags);
    const customdata: [number | null, string] = [payload.dq_score ?? null, flagsText];
    const entry: SeriesPointRecord = {};
    for (const series of SERIES) {
      const y = getSeriesValue(payload, series.key);
      entry[series.key] = { x, y, customdata };
    }
    pointsByTime.set(x, entry);
  }

  const sortedTimes = Array.from(pointsByTime.keys()).sort(
    (a, b) => Number(new Date(a)) - Number(new Date(b)),
  );
  const cappedTimes = sortedTimes.slice(-maxPoints);

  const snapshot = emptySnapshot();
  for (const time of cappedTimes) {
    const entry = pointsByTime.get(time) ?? {};
    for (const series of SERIES) {
      const point =
        entry[series.key] ?? { x: time, y: null, customdata: [null, ""] };
      snapshot[series.key].push(point);
    }
  }

  return snapshot;
}

export function createRealtimeReadingsStore(maxPoints = 600) {
  const snapshots = new Map<ProcessedTopicName, TopicSnapshot>();
  const subscribers = new Set<Subscriber>();

  let started = false;

  function getSnapshot(topic: ProcessedTopicName): TopicSnapshot {
    const existing = snapshots.get(topic);
    if (existing) {
      return existing;
    }
    const fresh = emptySnapshot();
    snapshots.set(topic, fresh);
    return fresh;
  }

  function notify(topic: ProcessedTopicName, payload: ProcessedReadingPayload) {
    for (const subscriber of subscribers) {
      subscriber(topic, payload);
    }
  }

  function onReading(topic: ProcessedTopicName, payload: ProcessedReadingPayload) {
    const snapshot = getSnapshot(topic);
    const x = new Date(Number(payload.time)).toISOString();
    const flagsText = formatFlags(payload.flags);
    const customdata: [number | null, string] = [payload.dq_score ?? null, flagsText];

    for (const series of SERIES) {
      const y = getSeriesValue(payload, series.key);
      appendWithLimit(snapshot[series.key], { x, y, customdata }, maxPoints);
    }

    notify(topic, payload);
  }

  function start() {
    if (started) {
      return;
    }
    started = true;
    realtimeClient.start();

    for (const topic of Object.values(processedTopics)) {
      realtimeClient.subscribe(topic, (payload) =>
        onReading(topic, payload as ProcessedReadingPayload),
      );
    }
  }

  function subscribe(subscriber: Subscriber) {
    subscribers.add(subscriber);
    return () => subscribers.delete(subscriber);
  }

  function hydrate(topic: ProcessedTopicName, readings: ProcessedReadingPayload[]) {
    const existing = getSnapshot(topic);
    snapshots.set(topic, mergeSnapshots(existing, readings, maxPoints));
  }

  return {
    start,
    subscribe,
    getSnapshot,
    hydrate,
  };
}

export const realtimeReadings = createRealtimeReadingsStore();
