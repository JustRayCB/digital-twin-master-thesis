import { cameraSnapshotTopic } from "./topics";
import { RealtimeClient } from "./realtime.client";
import { SubscriptionToken } from "./subscription.token";

type SnapshotHandler = (payload: unknown) => void;
type LatestSnapshotHandler = (payload: unknown) => void;

export class CameraSubscription {
  public constructor(private readonly client: RealtimeClient) {}

  public subscribeToSnapshots(handler: SnapshotHandler): SubscriptionToken {
    return this.client.subscribe(cameraSnapshotTopic, handler);
  }
}

export type { SnapshotHandler, LatestSnapshotHandler };
