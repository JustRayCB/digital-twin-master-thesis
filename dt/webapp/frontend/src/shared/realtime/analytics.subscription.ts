import { RealtimeClient } from "./realtime.client";
import { composeSubscriptionTokens, SubscriptionToken } from "./subscription.token";
import {
  forecastResultTopic,
  healthAssessmentTopic,
  recommendationCompletedTopic,
  recommendationSubmittedTopic,
} from "./topics";

type RecommendationSubmittedHandler = (payload: unknown) => void;
type RecommendationCompletedHandler = (payload: unknown) => void;
type HealthAssessmentHandler = (payload: unknown) => void;
type ForecastResultHandler = (payload: unknown) => void;
type RecommendationLifecycleEvent =
  | { type: "submitted"; payload: unknown }
  | { type: "completed"; payload: unknown };
type RecommendationLifecycleHandler = (event: RecommendationLifecycleEvent) => void;

export class AnalyticsSubscription {
  public constructor(private readonly client: RealtimeClient) {}

  public subscribeToRecommendationSubmitted(handler: RecommendationSubmittedHandler): SubscriptionToken {
    return this.client.subscribe(recommendationSubmittedTopic, handler);
  }

  public subscribeToRecommendationCompleted(handler: RecommendationCompletedHandler): SubscriptionToken {
    return this.client.subscribe(recommendationCompletedTopic, handler);
  }

  public subscribeToHealthAssessments(handler: HealthAssessmentHandler): SubscriptionToken {
    return this.client.subscribe(healthAssessmentTopic, handler);
  }

  public subscribeToForecastResults(handler: ForecastResultHandler): SubscriptionToken {
    return this.client.subscribe(forecastResultTopic, handler);
  }

  public subscribeToRecommendationLifecycle(
    handler: RecommendationLifecycleHandler,
  ): SubscriptionToken {
    const submittedToken = this.subscribeToRecommendationSubmitted((payload) => {
      handler({ type: "submitted", payload });
    });
    const completedToken = this.subscribeToRecommendationCompleted((payload) => {
      handler({ type: "completed", payload });
    });

    return composeSubscriptionTokens([submittedToken, completedToken]);
  }
}

export type {
  RecommendationCompletedHandler,
  ForecastResultHandler,
  HealthAssessmentHandler,
  RecommendationLifecycleEvent,
  RecommendationLifecycleHandler,
  RecommendationSubmittedHandler,
};
