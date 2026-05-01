import { cameraSnapshotTopics, type CameraSnapshotView } from "./topics";
import { RealtimeClient } from "./realtime.client";
import { SubscriptionToken } from "./subscription.token";

type SnapshotHandler = (view: CameraSnapshotView, payload: unknown) => void;
type LatestSnapshotHandler = (payload: unknown) => void;

export class CameraSubscription {
  public constructor(private readonly client: RealtimeClient) {}

  public subscribeToSnapshots(handler: SnapshotHandler): SubscriptionToken {
    const tokens = Object.entries(cameraSnapshotTopics).map(([view, topic]) =>
      this.client.subscribe(topic, (payload) => handler(view as CameraSnapshotView, payload)),
    );

    return {
      cleanup: () => {
        for (const token of tokens) {
          token.cleanup();
        }
      },
    };
  }
}

export type { SnapshotHandler, LatestSnapshotHandler };
