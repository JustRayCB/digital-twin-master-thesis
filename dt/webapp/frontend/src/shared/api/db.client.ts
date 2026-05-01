import type {
  ForecastHistoryQuery,
  ForecastResult,
  HealthAssessment,
  HealthHistoryQuery,
  ActiveAlert,
  AggregatedReading,
  Actuator,
  AlertHistory,
  CameraSnapshot,
  CameraSnapshotQuery,
  Reading,
  ReadingQuery,
  Sensor,
} from "$shared/types";
import { HttpClient } from "./http.client";

type RawReadingQuery = Omit<ReadingQuery, "window">;
type AggregatedReadingQuery = Omit<ReadingQuery, "window">;

export class DbClient {
  public constructor(private readonly http: HttpClient) {}

  public async fetchRawReadings(query: RawReadingQuery = {}): Promise<Reading[]> {
    const readings = await this.http.get<Reading[]>("/api/db/readings", {
      window: "raw",
      sensor_id: query.sensorId,
      plant_id: query.plantId,
      topic: query.topic,
      since: query.since,
      until: query.until,
    });

    return readings.map(normalizeReadingTopic);
  }

  public async fetchAggregatedReadings(query: AggregatedReadingQuery = {}): Promise<AggregatedReading[]> {
    const readings = await this.http.get<AggregatedReading[]>("/api/db/readings", {
      window: "1h",
      sensor_id: query.sensorId,
      plant_id: query.plantId,
      topic: query.topic,
      since: query.since,
      until: query.until,
    });

    return readings.map(normalizeReadingTopic);
  }

  public fetchActiveAlerts(plantId?: number): Promise<ActiveAlert[]> {
    return this.http.get<ActiveAlert[]>("/api/db/alerts/active", {
      plant_id: plantId,
    });
  }

  public fetchAlertHistory(plantId?: number, limit?: number): Promise<AlertHistory[]> {
    return this.http.get<AlertHistory[]>("/api/db/alerts/history", {
      plant_id: plantId,
      limit,
    });
  }

  public async acknowledgeAlert(alertKey: string, actor: string): Promise<void> {
    await this.http.post<unknown>(`/api/db/alerts/${alertKey}/acknowledge`, { actor });
  }

  public async clearAlert(alertKey: string): Promise<void> {
    await this.http.post<unknown>(`/api/db/alerts/${alertKey}/clear`, {});
  }

  public fetchLatestSnapshot(plantId?: number, topic?: string): Promise<CameraSnapshot | null> {
    return this.http.getOrNullOnNotFound<CameraSnapshot>("/api/db/camera/snapshots/latest", {
      plant_id: plantId,
      topic,
    });
  }

  public fetchSnapshotHistory(query: CameraSnapshotQuery): Promise<CameraSnapshot[]> {
    return this.http.get<CameraSnapshot[]>("/api/db/camera/snapshots", {
      plant_id: query.plantId,
      since: query.since,
      until: query.until,
    });
  }

  public fetchSensors(plantId?: number): Promise<Sensor[]> {
    return this.http.get<Sensor[]>("/api/db/sensors", {
      plant_id: plantId,
    });
  }

  public fetchActuators(plantId?: number): Promise<Actuator[]> {
    return this.http.get<Actuator[]>("/api/db/actuators", {
      plant_id: plantId,
    });
  }

  public fetchHealthHistory(query: HealthHistoryQuery): Promise<HealthAssessment[]> {
    return this.http.get<HealthAssessment[]>("/api/db/health", {
      plant_id: query.plantId,
      since: query.since,
      until: query.until,
      limit: query.limit,
      correlation_id: query.correlationId,
    });
  }

  public fetchForecastHistory(query: ForecastHistoryQuery): Promise<ForecastResult[]> {
    return this.http.get<ForecastResult[]>("/api/db/forecasts", {
      plant_id: query.plantId,
      metric: query.metric,
      horizon_seconds: query.horizonSeconds,
      since: query.since,
      until: query.until,
      limit: query.limit,
      correlation_id: query.correlationId,
    });
  }

}

function normalizeReadingTopic<T extends { topic?: string | null }>(reading: T): T {
  if (!reading.topic || reading.topic.includes(".processed.")) {
    return reading;
  }

  const parts = reading.topic.split(".");
  const topicName = parts[parts.length - 1];
  if (!topicName) {
    return reading;
  }

  return {
    ...reading,
    topic: `dt.sensors.processed.${topicName}`,
  };
}
