import type { AggregatedReading, Reading } from "$shared/types";

export type SensorData = {
  values: number[];
  timestamps: number[];
  dqScores: number[];
};

function toFiniteDqScore(value: number | null | undefined): number {
  if (value == null) {
    return 1;
  }

  const dqScore = Number(value);
  return Number.isFinite(dqScore) ? dqScore : 1;
}

export function getReadingTopic(reading: Reading): string | null {
  const topic = (reading as { topic?: unknown }).topic;
  if (typeof topic !== "string") {
    return null;
  }

  return topic;
}

export function filterReadingsByTopic(readings: Reading[], topic: string): Reading[] {
  const withTopic = readings.filter((reading) => getReadingTopic(reading) === topic);
  if (withTopic.length > 0) {
    return withTopic;
  }

  return readings.filter((reading) => getReadingTopic(reading) === null);
}

export function mapAggregatedReadings(readings: AggregatedReading[]): SensorData {
  const values: number[] = [];
  const timestamps: number[] = [];
  const dqScores: number[] = [];

  for (const reading of readings) {
    const value = Number(reading.mean_value);
    const timestamp = Number(reading.time);
    const dqScore = toFiniteDqScore(reading.avg_dq_score);

    if (Number.isFinite(value) && Number.isFinite(timestamp)) {
      values.push(value);
      timestamps.push(timestamp);
      dqScores.push(dqScore);
    }
  }

  return { values, timestamps, dqScores };
}

export function mapRawReadings(readings: Reading[]): SensorData {
  const values: number[] = [];
  const timestamps: number[] = [];
  const dqScores: number[] = [];

  for (const reading of readings) {
    const value = Number(reading.value);
    const timestamp = Number(reading.time);
    const dqScore = toFiniteDqScore(reading.dq_score);

    if (Number.isFinite(value) && Number.isFinite(timestamp)) {
      values.push(value);
      timestamps.push(timestamp);
      dqScores.push(dqScore);
    }
  }

  return { values, timestamps, dqScores };
}

export function filterSensorDataByTimeRange(
  data: SensorData,
  since: number,
  until: number,
): SensorData {
  const values: number[] = [];
  const timestamps: number[] = [];
  const dqScores: number[] = [];

  for (let index = 0; index < data.timestamps.length; index += 1) {
    const timestamp = data.timestamps[index];
    if (timestamp < since || timestamp > until) {
      continue;
    }

    values.push(data.values[index]);
    timestamps.push(timestamp);
    dqScores.push(data.dqScores[index]);
  }

  return { values, timestamps, dqScores };
}
