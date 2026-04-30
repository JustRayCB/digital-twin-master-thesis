/**
 * @fileoverview Transformation logic for presenting plant health assessments.
 */

import type { HealthAssessment, HealthState } from "$shared/types";

export type VitalitySnapshot = {
  score: string;
  confidence: string;
  status: string;
  summary: string;
  statusClass: string;
  meterWidth: string;
  meterClass: string;
};

const statePresentation: Record<HealthState | "waiting", Pick<VitalitySnapshot, "status" | "statusClass" | "meterClass">> = {
  waiting: {
    status: "Waiting",
    statusClass: "text-gray-500 bg-gray-100 border-gray-200",
    meterClass: "bg-gray-300",
  },
  healthy: {
    status: "Healthy",
    statusClass: "text-green-600 bg-green-100 border-green-200",
    meterClass: "bg-cozy-mint",
  },
  stressed: {
    status: "Stressed",
    statusClass: "text-yellow-700 bg-yellow-100 border-yellow-200",
    meterClass: "bg-cozy-yellow",
  },
  critical: {
    status: "Critical",
    statusClass: "text-pop-red bg-red-100 border-red-200",
    meterClass: "bg-pop-red",
  },
  unknown: {
    status: "Unknown",
    statusClass: "text-gray-500 bg-gray-100 border-gray-200",
    meterClass: "bg-gray-300",
  },
};

function formatRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return `${Math.round(Math.max(0, Math.min(value, 1)) * 100)}%`;
}

export function buildVitalitySnapshot(assessment: HealthAssessment | null): VitalitySnapshot {
  if (!assessment) {
    const presentation = statePresentation.waiting;
    return {
      score: "—",
      confidence: "—",
      status: presentation.status,
      summary: "Waiting for health assessment",
      statusClass: presentation.statusClass,
      meterWidth: "0%",
      meterClass: presentation.meterClass,
    };
  }

  const presentation = statePresentation[assessment.state] ?? statePresentation.unknown;
  const score = formatRatio(assessment.score);

  return {
    score,
    confidence: formatRatio(assessment.confidence),
    status: presentation.status,
    summary: assessment.summary || "No summary provided",
    statusClass: presentation.statusClass,
    meterWidth: score === "—" ? "0%" : score,
    meterClass: presentation.meterClass,
  };
}
