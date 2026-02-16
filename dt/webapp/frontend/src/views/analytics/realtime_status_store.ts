import { realtimeClient } from "./realtime_client";

export type ConnectionStatusSnapshot = { connected: boolean };

type Subscriber = (snapshot: ConnectionStatusSnapshot) => void;

export function createRealtimeStatusStore() {
  let latest: ConnectionStatusSnapshot = { connected: false };
  const subscribers = new Set<Subscriber>();

  let started = false;

  function notify() {
    for (const subscriber of subscribers) {
      subscriber(latest);
    }
  }

  function start() {
    if (started) {
      return;
    }
    started = true;
    realtimeClient.start();

    realtimeClient.subscribe("connection_status", (payload) => {
      const connected = Boolean((payload as any)?.connected);
      latest = { connected };
      notify();
    });
  }

  function subscribe(subscriber: Subscriber) {
    subscribers.add(subscriber);
    subscriber(latest);
    return () => subscribers.delete(subscriber);
  }

  function getSnapshot() {
    return latest;
  }

  return {
    start,
    subscribe,
    getSnapshot,
  };
}

export const realtimeStatus = createRealtimeStatusStore();

