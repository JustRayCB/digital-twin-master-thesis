/**
 * @fileoverview Manages the global state of the realtime WebSocket connection.
 * Used by components to react to connection loss or recovery.
 */

import { writable } from "svelte/store";

type ConnectionStatusSubscriber = () => void;

/** Represents the current state of the backend connection. */
export interface ConnectionStatus {
  connected: boolean;
  lastUpdate: number | null;
}

/** Interface for services that can write updates to the connection status. */
export interface ConnectionStatusWriter {
  applyConnectionStatusPayload(payload: unknown, lastUpdate?: number): void;
}

const DEFAULT_CONNECTION_STATUS: ConnectionStatus = {
  connected: false,
  lastUpdate: null,
};

/** Global store for realtime connection status. */
export const connectionStatus = writable<ConnectionStatus>({ ...DEFAULT_CONNECTION_STATUS });

/**
 * Processes a payload from the realtime client to update connection state.
 * @param payload - The payload received from the realtime service.
 * @param lastUpdate - Timestamp of when the update occurred (defaults to now).
 */
export function applyConnectionStatusPayload(payload: unknown, lastUpdate: number = Date.now()) {
  if (!payload || typeof payload !== "object") {
    return;
  }

  connectionStatus.set({
    connected: Boolean((payload as { connected?: unknown }).connected),
    lastUpdate,
  });
}

/**
 * Updates the last known update timestamp without changing connection state.
 * @param timestamp - The new last update time.
 */
export function setLastUpdate(timestamp: number) {
  connectionStatus.update((current) => ({
    ...current,
    lastUpdate: timestamp,
  }));
}

/** Resets the connection status to its initial default state. */
export function resetConnectionStatus() {
  connectionStatus.set({ ...DEFAULT_CONNECTION_STATUS });
}

