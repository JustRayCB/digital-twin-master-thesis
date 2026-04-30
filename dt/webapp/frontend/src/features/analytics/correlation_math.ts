export interface SensorData {
  values: number[];
  timestamps: number[];
  dqScores: number[];
}

export interface AlignedData {
  x: number[];
  y: number[];
  dq1: number[];
  dq2: number[];
}

export type CorrelationMethod = "pearson" | "spearman";

/**
 * Calculates the Pearson correlation coefficient between two numeric arrays.
 *
 * Returns `0` when arrays are empty, have different lengths, or one series has
 * zero variance.
 */
export function calculatePearsonCorrelation(x: number[], y: number[]): number {
  if (x.length !== y.length || x.length === 0) {
    return 0;
  }

  const n = x.length;
  const meanX = x.reduce((a, b) => a + b, 0) / n;
  const meanY = y.reduce((a, b) => a + b, 0) / n;

  let numerator = 0;
  let denomX = 0;
  let denomY = 0;

  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX;
    const dy = y[i] - meanY;
    numerator += dx * dy;
    denomX += dx * dx;
    denomY += dy * dy;
  }

  if (denomX === 0 || denomY === 0) {
    return 0;
  }

  return numerator / Math.sqrt(denomX * denomY);
}

function rankValues(values: number[]): number[] {
  const sorted = values
    .map((value, index) => ({ value, index }))
    .sort((left, right) => left.value - right.value);
  const ranks = new Array<number>(values.length);

  let index = 0;
  while (index < sorted.length) {
    let tieEnd = index;
    while (tieEnd + 1 < sorted.length && sorted[tieEnd + 1].value === sorted[index].value) {
      tieEnd += 1;
    }

    const averageRank = (index + tieEnd + 2) / 2;
    for (let tieIndex = index; tieIndex <= tieEnd; tieIndex += 1) {
      ranks[sorted[tieIndex].index] = averageRank;
    }
    index = tieEnd + 1;
  }

  return ranks;
}

export function calculateSpearmanCorrelation(x: number[], y: number[]): number {
  if (x.length !== y.length || x.length === 0) {
    return 0;
  }

  return calculatePearsonCorrelation(rankValues(x), rankValues(y));
}

export function calculateCorrelation(
  x: number[],
  y: number[],
  method: CorrelationMethod = "pearson",
): number {
  if (method === "spearman") {
    return calculateSpearmanCorrelation(x, y);
  }

  return calculatePearsonCorrelation(x, y);
}

/**
 * Aligns two sensor series by timestamp and returns only matching points.
 *
 * The output order follows `sensor1.timestamps`. When `sensor2` contains
 * duplicate timestamps, the last value is used.
 */
export function alignSensorData(sensor1: SensorData, sensor2: SensorData): AlignedData {
  const x: number[] = [];
  const y: number[] = [];
  const dq1: number[] = [];
  const dq2: number[] = [];

  const timeMap = new Map<number, { value: number; dq: number }>();
  sensor2.timestamps.forEach((t, i) => {
    timeMap.set(t, { value: sensor2.values[i], dq: sensor2.dqScores[i] });
  });

  sensor1.timestamps.forEach((t, i) => {
    const match = timeMap.get(t);
    if (match) {
      x.push(sensor1.values[i]);
      y.push(match.value);
      dq1.push(sensor1.dqScores[i]);
      dq2.push(match.dq);
    }
  });

  return { x, y, dq1, dq2 };
}
