export type VitalitySnapshot = {
  value: string;
  status: string;
  statusClass: string;
  meterWidth: string;
  meterClass: string;
};

function clampRatio(value: number) {
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

export function buildVitalitySnapshot(greenRatio: number | null): VitalitySnapshot {
  if (!Number.isFinite(greenRatio)) {
    return {
      value: "—",
      status: "Waiting",
      statusClass: "text-gray-500 bg-gray-100 border-gray-200",
      meterWidth: "0%",
      meterClass: "bg-gray-300",
    };
  }

  const ratio = clampRatio(Number(greenRatio));
  const percentage = Math.round(ratio * 100);

  if (percentage >= 80) {
    return {
      value: `${percentage}%`,
      status: "Excellent",
      statusClass: "text-green-600 bg-green-100 border-green-200",
      meterWidth: `${percentage}%`,
      meterClass: "bg-cozy-mint",
    };
  }

  if (percentage >= 60) {
    return {
      value: `${percentage}%`,
      status: "Good",
      statusClass: "text-lime-700 bg-lime-100 border-lime-200",
      meterWidth: `${percentage}%`,
      meterClass: "bg-cozy-mint",
    };
  }

  if (percentage >= 40) {
    return {
      value: `${percentage}%`,
      status: "Fair",
      statusClass: "text-yellow-700 bg-yellow-100 border-yellow-200",
      meterWidth: `${percentage}%`,
      meterClass: "bg-cozy-yellow",
    };
  }

  return {
    value: `${percentage}%`,
    status: "Low",
    statusClass: "text-pop-red bg-red-100 border-red-200",
    meterWidth: `${percentage}%`,
    meterClass: "bg-pop-red",
  };
}
