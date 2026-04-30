/**
 * @fileoverview Manages the lifecycle of realtime event subscriptions.
 * Provides a token-based mechanism for components to subscribe and safely clean up their listeners.
 */

import { SubscriptionToken } from "./subscription.token";

type RealtimeHandler = (payload: unknown) => void;
type RealtimeUnsubscribe = () => void;

/** Interface describing the minimal contract expected from the underlying realtime client. */
export type RealtimeClientLike = {
  start: () => void;
  subscribe: (eventName: string, handler: RealtimeHandler) => RealtimeUnsubscribe;
};

/** Tracks the high-level connection lifecycle. */
export type ConnectionState = {
  started: boolean;
  connected: boolean;
};

/**
 * Higher-level manager over the realtime client.
 * Issues `SubscriptionToken`s so callers can easily cleanup their event listeners on component unmount.
 */
export class RealtimeSubscriptionManager {
  private readonly subscriptions = new Map<SubscriptionToken, RealtimeUnsubscribe>();
  private readonly connectionState: ConnectionState = {
    started: false,
    connected: false,
  };
  private trackingToken: SubscriptionToken | null = null;

  public constructor(private readonly client: RealtimeClientLike) {}

  /**
   * Subscribes to a realtime topic. Auto-starts the client connection if it hasn't been started.
   * @param eventName - The topic to listen to.
   * @param handler - The message callback function.
   * @returns A token that can be used to manually cancel the subscription.
   */
  public subscribe(eventName: string, handler: RealtimeHandler): SubscriptionToken {
    this.ensureConnection();

    const unsubscribe = this.client.subscribe(eventName, handler);
    const token = new SubscriptionToken(() => this.unsubscribe(token));

    this.subscriptions.set(token, unsubscribe);
    return token;
  }

  /**
   * Cancels a previously established subscription.
   * @param token - The token returned by the `subscribe` method.
   */
  public unsubscribe(token: SubscriptionToken) {
    const unsubscribe = this.subscriptions.get(token);
    if (!unsubscribe) {
      return;
    }
    unsubscribe();
    this.subscriptions.delete(token);
  }

  /** Gets the current view of connection readiness. */
  public getConnectionState(): ConnectionState {
    return { ...this.connectionState };
  }

  /** Forcibly cancels all active subscriptions tracked by this manager. */
  public cleanupAll() {
    for (const [token, unsubscribe] of this.subscriptions.entries()) {
      unsubscribe();
      this.subscriptions.delete(token);
    }

    if (this.trackingToken) {
      this.trackingToken.cleanup();
      this.trackingToken = null;
    }

    this.connectionState.connected = false;
  }

  private ensureConnection() {
    if (this.connectionState.started) {
      return;
    }

    this.client.start();
    this.connectionState.started = true;

    // Track standard connection status heartbeat/events automatically.
    const unsubscribe = this.client.subscribe("connection_status", (payload) => {
      this.connectionState.connected = Boolean((payload as any)?.connected);
    });
    this.trackingToken = new SubscriptionToken(unsubscribe);
  }
}

export { SubscriptionToken };
