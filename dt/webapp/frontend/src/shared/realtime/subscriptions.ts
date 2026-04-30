/**
 * @fileoverview Singletons for domain-specific realtime subscriptions.
 * Pre-wires the specific topic handlers with the global subscription manager.
 */

import { realtimeClient } from "./realtime.client";
import { ActionSubscription } from "./actions.subscription";
import { AnalyticsSubscription } from "./analytics.subscription";
import { AlertSubscription } from "./alerts.subscription";
import { CameraSubscription } from "./camera.subscription";
import { ReadingSubscription } from "./readings.subscription";
import { StatusSubscription } from "./status.subscription";

/** Domain-specific helper for subscribing to telemetry reading events. */
export const readingSubscriptions = new ReadingSubscription(realtimeClient);

/** Domain-specific helper for subscribing to active alert events. */
export const alertSubscriptions = new AlertSubscription(realtimeClient);

/** Domain-specific helper for subscribing to incoming camera snapshot events. */
export const cameraSubscriptions = new CameraSubscription(realtimeClient);

/** Domain-specific helper for recommendation lifecycle events. */
export const analyticsSubscriptions = new AnalyticsSubscription(realtimeClient);

/** Domain-specific helper for controller action status events. */
export const actionSubscriptions = new ActionSubscription(realtimeClient);

/** Domain-specific helper for subscribing to backend connection heartbeat/status events. */
export const statusSubscriptions = new StatusSubscription(realtimeClient);
