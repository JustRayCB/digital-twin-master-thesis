import { RealtimeClient } from "./realtime.client";
import { SubscriptionToken } from "./subscription.token";

type StatusHandler = (payload: unknown) => void;
type HealthHandler = (payload: unknown) => void;

export class StatusSubscription {
	public constructor(private readonly client: RealtimeClient) {}

	public subscribeToConnectionStatus(
		handler: StatusHandler,
	): SubscriptionToken {
		return this.client.subscribe("connection_status", handler);
	}
}

export type { StatusHandler, HealthHandler };
