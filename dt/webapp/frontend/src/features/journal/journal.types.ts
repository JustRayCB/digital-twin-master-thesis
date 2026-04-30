import type { ActionHistoryRecord, Recommendation } from "$shared/types";

/**
 * @fileoverview Domain data types specific to the Journal/Logbook feature.
 */

/** Represents a critical system alert currently requiring attention in the journal sidebar. */
export interface JournalAlertItem {
  id: string;
  title: string;
  desc: string;
  kind: "water" | "temp";
  severity: string | null;
  status: string | null;
}

/** Represents an entry in the historical timeline (e.g. past actions, resolved alerts, observations). */
export interface JournalEntry {
  id: string;
  title: string;
  text: string;
  tags: string[];
  icon: string;
  iconColor: string;
  dayLabel: string;
  timeLabel: string;
  createdAt: number;
}

/** Represents one recommendation lifecycle record shown in the Closed-loop history section. */
export type JournalRecommendationHistoryItem = Recommendation;

/** Represents one controller action history record shown in the Closed-loop history section. */
export type JournalActionHistoryItem = ActionHistoryRecord;
