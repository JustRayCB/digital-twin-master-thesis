import { RealtimeClient } from "./realtime.client";
import { composeSubscriptionTokens, SubscriptionToken } from "./subscription.token";

// Type definitions for alert event handlers and lifecycle events.
type AlertHandler = (payload: unknown) => void;
type AlertRemovalHandler = (payload: unknown) => void;
// Represents the lifecycle events for alerts, including updates and removals. 
// It encapsulates the type of event and its associated payload, 
type AlertLifecycleEvent =
  | { type: "updated"; payload: unknown }
  | { type: "removed"; payload: unknown };
type LifecycleHandler = (event: AlertLifecycleEvent) => void;

export class AlertSubscription {
  public constructor(private readonly client: RealtimeClient) {}

  public subscribeToAlertUpdates(handler: AlertHandler): SubscriptionToken {
    return this.client.subscribe("alerts_update", handler);
  }

  public subscribeToAlertRemovals(handler: AlertRemovalHandler): SubscriptionToken {
    return this.client.subscribe("alerts_remove", handler);
  }

  /** Subscribes to both alert updates and removals, invoking the provided handler for each event. */
  public subscribeToAlertLifecycle(handler: LifecycleHandler): SubscriptionToken {
    const updateToken = this.subscribeToAlertUpdates((payload) => {
      handler({ type: "updated", payload });
    });
    const removalToken = this.subscribeToAlertRemovals((payload) => {
      handler({ type: "removed", payload });
    });

    return composeSubscriptionTokens([updateToken, removalToken]);
  }
}

export type { AlertHandler, AlertRemovalHandler, AlertLifecycleEvent, LifecycleHandler };
