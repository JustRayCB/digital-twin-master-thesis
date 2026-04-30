/**
 * @fileoverview Barrel export for realtime pub/sub capabilities.
 * Exports domain subscriptions, topics, and the underlying realtime client infrastructure.
 */

export { AlertSubscription } from "./alerts.subscription";
export { ActionSubscription } from "./actions.subscription";
export { AnalyticsSubscription } from "./analytics.subscription";
export { CameraSubscription } from "./camera.subscription";
export { ReadingSubscription } from "./readings.subscription";
export { realtimeClient } from "./realtime.client";
export type { RealtimeHandler } from "./realtime.client";
export {
  analyticsTopics,
  actionTopic,
  cameraSnapshotTopic,
  processedTopics,
  recommendationCompletedTopic,
  recommendationSubmittedTopic,
  type ProcessedTopicName,
} from "./topics";
export {
  analyticsSubscriptions,
  actionSubscriptions,
  alertSubscriptions,
  cameraSubscriptions,
  readingSubscriptions,
  statusSubscriptions,
} from "./subscriptions";
export { StatusSubscription } from "./status.subscription";
export { composeSubscriptionTokens, SubscriptionToken } from "./subscription.token";
