<script lang="ts">
  import { formatDisplayTime } from "$shared/utils/time";

  import type { JournalActionHistoryItem } from "./journal.types";

  export let actionHistory: JournalActionHistoryItem[];

  type DisplayActionHistoryItem = JournalActionHistoryItem & {
    completed_at?: number | null;
  };

  const statusRank: Record<string, number> = {
    running: 2,
    completed: 3,
    failed: 3,
    rejected: 3,
    skipped: 3,
  };

  function formatDuration(value?: number | null): string {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return "—";
    }

    if (Number.isInteger(value)) {
      return `${value}s`;
    }

    return `${value.toFixed(1).replace(/\.0$/, "")}s`;
  }

  function getLifecycleKey(action: JournalActionHistoryItem): string {
    return [
      action.plant_id,
      action.actuator_id,
      action.source,
      action.routine_id ?? "",
    ].join(":");
  }

  function getStatusRank(status?: string | null): number {
    return status ? statusRank[status.toLowerCase()] ?? 0 : 0;
  }

  function getActuatorLabel(action: JournalActionHistoryItem): string {
    return action.actuator_name?.trim() || `Actuator ${action.actuator_id}`;
  }

  function getSourceLabel(action: JournalActionHistoryItem): string {
    return action.source || "unknown";
  }

  function isSameAction(left: JournalActionHistoryItem, right: JournalActionHistoryItem): boolean {
    return left.execution_id === right.execution_id && left.action_id === right.action_id;
  }

  function mergeActionUpdate(
    current: DisplayActionHistoryItem,
    update: JournalActionHistoryItem,
  ): DisplayActionHistoryItem {
    const earliest = current.event_at <= update.event_at ? current : update;
    const latestEventAt = Math.max(current.completed_at ?? current.event_at, update.event_at);
    const finalStatus =
      getStatusRank(update.status) >= getStatusRank(current.status) ? update.status : current.status;

    return {
      ...earliest,
      ...(finalStatus === update.status ? update : current),
      event_at: earliest.event_at,
      duration: Math.max(current.duration ?? 0, update.duration ?? 0),
      status: finalStatus,
      error_message: update.error_message ?? current.error_message,
      completed_at: latestEventAt > earliest.event_at ? latestEventAt : current.completed_at,
    };
  }

  function collapseActionUpdates(history: JournalActionHistoryItem[]): DisplayActionHistoryItem[] {
    const collapsed: DisplayActionHistoryItem[] = [];
    const ordered = [...history].sort((left, right) => left.event_at - right.event_at);

    for (const action of ordered) {
      const existingIndex = collapsed.findIndex((current) => isSameAction(current, action));
      if (existingIndex >= 0) {
        collapsed[existingIndex] = mergeActionUpdate(collapsed[existingIndex], action);
        continue;
      }

      collapsed.push(action);
    }

    return collapsed;
  }

  function summarizeActionHistory(history: JournalActionHistoryItem[]): DisplayActionHistoryItem[] {
    const activeByKey = new Map<string, DisplayActionHistoryItem[]>();
    const summarized: DisplayActionHistoryItem[] = [];
    const ordered = collapseActionUpdates(history);

    for (const action of ordered) {
      const command = action.command.toUpperCase();
      const key = getLifecycleKey(action);

      if (command === "ON") {
        const active = activeByKey.get(key) ?? [];
        const existingIndex = active.findIndex((started) => isSameAction(started, action));
        if (existingIndex >= 0) {
          active[existingIndex] = mergeActionUpdate(active[existingIndex], action);
          activeByKey.set(key, active);
          continue;
        }

        active.push(action);
        activeByKey.set(key, active);
        continue;
      }

      if (command === "OFF") {
        const active = activeByKey.get(key) ?? [];
        const started = active.shift();
        if (active.length === 0) {
          activeByKey.delete(key);
        }

        if (started) {
          summarized.push({
            ...started,
            duration: Math.max(0, (action.event_at - started.event_at) / 1000),
            status: action.status ?? started.status,
            error_message: action.error_message ?? started.error_message,
            completed_at: action.completed_at ?? action.event_at,
          });
          continue;
        }
      }

      summarized.push(action);
    }

    for (const active of activeByKey.values()) {
      summarized.push(...active);
    }

    return summarized.sort((left, right) => right.event_at - left.event_at);
  }

  function isLifecycleAction(action: DisplayActionHistoryItem): boolean {
    return (
      action.command.toUpperCase() === "ON" &&
      action.duration > 0 &&
      typeof action.completed_at === "number" &&
      Number.isFinite(action.completed_at)
    );
  }

  $: displayActionHistory = summarizeActionHistory(actionHistory);
</script>

<div class="bg-cozy-peach/30 border-2 border-cozy-peach rounded-lg p-4 flex flex-col flex-1 min-h-0">
  <h4 class="font-retro text-xl text-ink mb-3">Action history</h4>

  {#if displayActionHistory.length === 0}
    <p class="text-sm italic text-gray-600">No actions recorded</p>
  {:else}
    <div class="space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1 min-h-0">
      {#each displayActionHistory as action, index (`${action.execution_id}-${action.event_at}-${action.action_id}-${action.status ?? "unknown"}-${index}`)}
        <div class="bg-white border-2 border-ink rounded-lg p-3">
          {#if isLifecycleAction(action)}
            <p class="font-retro text-lg text-ink">
              {getActuatorLabel(action)} was {action.command.toUpperCase()} for {formatDuration(action.duration)} at {formatDisplayTime(action.event_at)}
            </p>
            <p class="text-xs text-gray-600 font-sans">
              Plant {action.plant_id} • Source: {getSourceLabel(action)}{action.completed_at ? ` • ended ${formatDisplayTime(action.completed_at)}` : ''}
            </p>
          {:else}
            <p class="font-retro text-lg text-ink">{action.command}</p>
            <p class="text-xs text-gray-600 font-sans">
              Plant {action.plant_id} • {getActuatorLabel(action)} • {formatDisplayTime(action.event_at)}
            </p>
          {/if}
          <p class="text-xs text-ink font-sans mt-1">
            Status: {action.status ?? "unknown"}{action.duration > 0 ? ` • Duration: ${formatDuration(action.duration)}` : ''}
          </p>
          {#if action.error_message}
            <p class="text-xs text-red-700 font-sans mt-1">{action.error_message}</p>
          {/if}
          {#if !isLifecycleAction(action)}
            <p class="text-xs text-gray-600 font-sans mt-1">Source: {getSourceLabel(action)} • Time: {formatDisplayTime(action.event_at)}</p>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
