import { get, writable } from "svelte/store";

import { realtimeAlerts } from "../analytics/realtime_alerts_store";

export type AlertItem = {
  id: string;
  title: string;
  desc: string;
  kind: "water" | "temp";
};

export type LogEntry = {
  id: string;
  dayLabel: string;
  timeLabel: string;
  title: string;
  desc: string;
  icon: string;
  iconColor: string;
  tags?: string[];
};

export const journalIcons = [
  { value: "water_drop", label: "Water" },
  { value: "content_cut", label: "Pruning" },
  { value: "nutrition", label: "Fertilizer" },
  { value: "photo_camera", label: "Photo" },
  { value: "settings", label: "System" },
  { value: "edit_note", label: "Note" },
] as const;

export const journalColors = [
  { value: "bg-cozy-blue", label: "Blue" },
  { value: "bg-cozy-peach", label: "Peach" },
  { value: "bg-cozy-yellow", label: "Yellow" },
  { value: "bg-cozy-lavender", label: "Lavender" },
  { value: "bg-gray-200", label: "Gray" },
] as const;

function buildAlertTitle(payload: unknown) {
  const message = String((payload as any)?.message ?? "").trim();
  if (message) {
    return message;
  }
  const alertKey = String((payload as any)?.alert_key ?? "").trim();
  return alertKey || "Alert";
}

function buildAlertDescription(payload: unknown) {
  const severity = String((payload as any)?.severity ?? "").trim();
  const status = String((payload as any)?.status ?? "").trim();
  const parts = [severity, status].filter(Boolean);
  return parts.length ? parts.join(" • ") : "";
}

function inferAlertKind(payload: unknown): "water" | "temp" {
  const alertKey = String((payload as any)?.alert_key ?? "").toLowerCase();
  const message = String((payload as any)?.message ?? "").toLowerCase();
  const text = `${alertKey} ${message}`;
  if (text.includes("moisture") || text.includes("water") || text.includes("pump")) {
    return "water";
  }
  return "temp";
}

export function createJournalModel() {
  const alerts = writable<AlertItem[]>([]);
  const dismissedAlertIds = writable<Set<string>>(new Set());

  const tankCapacityLiters = 10.0;
  const tankLevelPercent = writable(35);
  const tankLiters = writable(3.5);
  const tankRefilledLabel = writable("2d Ago");
  const tankEmptyInLabel = writable("4 Days");

  const logs = writable<LogEntry[]>([
    {
      id: "1",
      dayLabel: "Today",
      timeLabel: "10:42 AM",
      title: "Manual Mist",
      desc: "Humidity was reading low on sensor A, gave a quick spritz to the upper leaves.",
      icon: "water_drop",
      iconColor: "bg-cozy-blue",
    },
    {
      id: "2",
      dayLabel: "Yesterday",
      timeLabel: "04:15 PM",
      title: "Pruning Session",
      desc: "Removed two yellowing leaves near the base. Plant looks much tidier. Checked for pests - all clear.",
      icon: "content_cut",
      iconColor: "bg-cozy-peach",
      tags: ["#maintenance", "#health-check"],
    },
    {
      id: "3",
      dayLabel: "Oct 24",
      timeLabel: "09:00 AM",
      title: "Fertilizer Added",
      desc: "Added 5ml of liquid fertilizer to the water tank. Regular monthly feeding schedule.",
      icon: "nutrition",
      iconColor: "bg-cozy-yellow",
    },
  ]);

  const entryTitle = writable("");
  const entryText = writable("");
  const entryTags = writable("");
  const entryIcon = writable<(typeof journalIcons)[number]["value"]>("edit_note");
  const entryColor = writable<(typeof journalColors)[number]["value"]>("bg-gray-200");

  let unsubscribeAlerts: (() => void) | null = null;

  function start() {
    realtimeAlerts.start();
    unsubscribeAlerts = realtimeAlerts.subscribe((snapshot) => {
      const nextAlerts: AlertItem[] = [];
      for (const [id, payload] of snapshot.entries()) {
        nextAlerts.push({
          id,
          title: buildAlertTitle(payload),
          desc: buildAlertDescription(payload),
          kind: inferAlertKind(payload),
        });
      }

      const dismissed = get(dismissedAlertIds);
      alerts.set(nextAlerts.filter((a) => !dismissed.has(a.id)));
    });
  }

  function stop() {
    if (unsubscribeAlerts) {
      unsubscribeAlerts();
      unsubscribeAlerts = null;
    }
  }

  function dismissAlert(id: string) {
    dismissedAlertIds.update((current) => {
      const next = new Set(current);
      next.add(id);
      return next;
    });
    alerts.update((current) => current.filter((a) => a.id !== id));
  }

  function addEntry() {
    const text = get(entryText).trim();
    if (!text) {
      return;
    }
    const title = get(entryTitle).trim() || "Journal Entry";
    const tagsInput = get(entryTags).trim();
    const tags = tagsInput
      ? tagsInput
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      : undefined;
    const icon = get(entryIcon);
    const iconColor = get(entryColor);
    const now = new Date();
    const timeLabel = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    logs.update((current) => [
      {
        id: String(Date.now()),
        dayLabel: "Today",
        timeLabel,
        title,
        desc: text,
        icon,
        iconColor,
        tags,
      },
      ...current,
    ]);
    entryTitle.set("");
    entryText.set("");
    entryTags.set("");
  }

  function refillTank() {
    tankLevelPercent.set(100);
    tankLiters.set(tankCapacityLiters);
    tankRefilledLabel.set("Just now");
    tankEmptyInLabel.set("—");
  }

  return {
    alerts,
    logs,
    entryTitle,
    entryText,
    entryTags,
    entryIcon,
    entryColor,
    tankLevelPercent,
    tankLiters,
    tankRefilledLabel,
    tankEmptyInLabel,
    start,
    stop,
    dismissAlert,
    addEntry,
    refillTank,
  };
}
