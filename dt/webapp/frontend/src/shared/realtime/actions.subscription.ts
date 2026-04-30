import { RealtimeClient } from "./realtime.client";
import { SubscriptionToken } from "./subscription.token";
import { actionTopic } from "./topics";

type ActionHandler = (payload: unknown) => void;

export class ActionSubscription {
  public constructor(private readonly client: RealtimeClient) {}

  public subscribeToActions(handler: ActionHandler): SubscriptionToken {
    return this.client.subscribe(actionTopic, handler);
  }
}

export type { ActionHandler };
