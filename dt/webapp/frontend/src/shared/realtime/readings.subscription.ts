/**
 * @fileoverview Domain-specific subscription wrapper for sensor readings.
 * Ensures that all incoming reading payloads are augmented with the topic name they arrived on.
 */

import { processedTopics } from "./topics";
import { RealtimeClient } from "./realtime.client";
import { composeSubscriptionTokens, SubscriptionToken } from "./subscription.token";

type ReadingHandler = (payload: unknown) => void;

/** Helper for hooking up realtime reading handlers. */
export class ReadingSubscription {
  public constructor(private readonly client: RealtimeClient) {}

  /**
   * Subscribes a handler to all known processed reading topics.
   * @param handler - The callback function to execute.
   * @returns A token for unsubscribing from all wrapped topics simultaneously.
   */
  public subscribeToProcessedReadings(handler: ReadingHandler): SubscriptionToken {
    return this.subscribeToAllSensors(handler);
  }

  /**
   * Subscribes a handler to a specific sensor topic.
   * @param topic - The exact topic name to subscribe to.
   * @param handler - The callback function.
   */
  public subscribeToSensorTopic(topic: string, handler: ReadingHandler): SubscriptionToken {
    return this.client.subscribe(topic, (payload) => {
      handler(this.withTopic(payload, topic));
    });
  }

  /**
   * Internal helper to map an array of topics into an array of subscription tokens, bundled together.
   */
  public subscribeToAllSensors(
    handler: ReadingHandler,
    topics: readonly string[] = Object.values(processedTopics),
  ): SubscriptionToken {
    const tokens = topics.map((topic) =>
      this.subscribeToSensorTopic(topic, handler)
    );
    // Bundle all individual topic subscriptions into a single token for easier management. 
    // This allows the caller to unsubscribe from all related topics with one action, rather than needing to track multiple tokens.
    return composeSubscriptionTokens(tokens);
  }

  /** Normalizes the payload shape to always include the origin topic. */
  private withTopic(payload: unknown, topic: string): unknown {
    if (payload && typeof payload === "object") {
      return { ...(payload as Record<string, unknown>), topic };
    }
    return { topic, payload };
  }
}
