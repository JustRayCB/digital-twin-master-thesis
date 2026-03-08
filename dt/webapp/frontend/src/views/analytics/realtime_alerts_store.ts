import { DEFAULT_PLANT_ID, fetchActiveAlerts } from "../../api";
import { realtimeClient } from "./realtime_client";

export type ActiveAlertSnapshot = Map<string, unknown>;

type Subscriber = (snapshot: ActiveAlertSnapshot) => void;

export function createRealtimeAlertsStore() {
  const activeAlerts: ActiveAlertSnapshot = new Map();
  const subscribers = new Set<Subscriber>();

  let started = false;

  function buildAlertKey(payload: unknown) {
    const alert = payload as any;
    const plantId = alert?.plant_id;
    const alertKey = alert?.alert_key;
    if (plantId && alertKey) {
      return `${plantId}:${alertKey}`;
    }
    const fallback = alert?.alert_id;
    if (fallback) {
      return String(fallback);
    }
    return "";
  }

  function upsertAlert(payload: unknown) {
    const alertId = buildAlertKey(payload);
    if (!alertId) {
      return;
    }
    activeAlerts.set(alertId, payload);
  }

  function notify() {
    const snapshot = new Map(activeAlerts);
    for (const subscriber of subscribers) {
      subscriber(snapshot);
    }
  }

  async function fetchActiveAlertsSnapshot() {
    const alerts = await fetchActiveAlerts(DEFAULT_PLANT_ID);
    for (const alert of alerts) {
      upsertAlert(alert);
    }
    notify();
  }

  function start() {
    if (started) {
      return;
    }
    started = true;
    realtimeClient.start();
    fetchActiveAlertsSnapshot().catch((error) => {
      console.error("Failed to load active alerts", error);
    });

    realtimeClient.subscribe("alerts_update", (payload) => {
      upsertAlert(payload);
      notify();
    });

    realtimeClient.subscribe("alerts_remove", (payload) => {
      const alertId = String(payload ?? "");
      if (!alertId) {
        return;
      }
      activeAlerts.delete(alertId);
      notify();
    });
  }

  function subscribe(subscriber: Subscriber) {
    subscribers.add(subscriber);
    subscriber(new Map(activeAlerts));
    return () => subscribers.delete(subscriber);
  }

  function getSnapshot() {
    return new Map(activeAlerts);
  }

  return {
    fetchActiveAlerts: fetchActiveAlertsSnapshot,
    start,
    subscribe,
    getSnapshot,
  };
}

export const realtimeAlerts = createRealtimeAlertsStore();
