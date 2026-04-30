import type { ReadingQuery } from "$shared/types";

export type AnalyticsTimeView = "day" | "week" | "month";

const HISTORICAL_WINDOW_MS: Record<AnalyticsTimeView, number> = {
  day: 24 * 60 * 60 * 1000,
  week: 7 * 24 * 60 * 60 * 1000,
  month: 30 * 24 * 60 * 60 * 1000,
};

export function getHistoricalWindowMs(view: AnalyticsTimeView): number {
  return HISTORICAL_WINDOW_MS[view];
}

export function getTimeWindow(view: AnalyticsTimeView, now: number): { since: number; until: number } {
  return {
    since: now - getHistoricalWindowMs(view),
    until: now,
  };
}

export function buildReadingQuery(view: AnalyticsTimeView, now: number): ReadingQuery {
  const { since, until } = getTimeWindow(view, now);
  return {
    window: view === "day" ? "raw" : "1h",
    since,
    until,
  };
}
