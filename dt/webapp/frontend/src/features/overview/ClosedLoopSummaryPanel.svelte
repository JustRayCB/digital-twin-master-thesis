<script lang="ts">
  import type { ClosedLoopStatusSummary } from "./overview.store";
  import {formatChartTime} from "$shared/utils/time";

  let { summary }: { summary: ClosedLoopStatusSummary } = $props();

  const statusLabels: Record<string, string> = {
    idle: "Idle",
    pending: "Pending",
    accepted: "Accepted",
    advisory_only: "Advisory only",
    rejected: "Rejected",
    failed: "Failed",
    partial: "Partial",
  };


  function formatDuration(value: number | null | undefined): string {
    if (!Number.isFinite(value)) {
      return "";
    }

    return ` · ${value}s`;
  }
</script>

<div class="mt-12 bg-white border-2 border-ink shadow-hard rounded-xl p-6">
  <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
    <div>
      <h3 class="font-retro text-2xl text-ink uppercase tracking-wider">Automation summary</h3>
      <p class="text-gray-600 text-sm mt-1">Latest recommendation and controller outcome.</p>
    </div>

    <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border-2 border-ink bg-cozy-white shadow-hard-sm self-start">
      <span class="font-retro text-xs text-gray-500 uppercase tracking-wide">Current status</span>
      <span class="font-retro text-sm text-ink uppercase tracking-wide">
        {statusLabels[summary.status] ?? summary.status}
      </span>
    </div>
  </div>

  <div class="space-y-5 text-sm">
    <div class="pb-4 border-b border-dashed border-gray-300">
      <p class="font-retro text-gray-500 uppercase tracking-wide mb-2">Recommendation</p>
      {#if summary.recommendation}
        <p class="text-ink font-medium">{summary.recommendation.reason}</p>
        <div class="mt-2 flex flex-wrap gap-2">
          {#each summary.recommendation.actions as action}
            <span class="px-2 py-1 rounded border border-ink bg-gray-50 text-xs font-mono">
              {action.capability}: {action.command}{formatDuration(action.duration_seconds)}
            </span>
          {/each}
        </div>
        <p class="mt-2 text-gray-600">Confidence: {summary.recommendation.confidence.toFixed(2)}</p>
      {:else}
        <p class="text-gray-600">No recommendation yet.</p>
      {/if}
    </div>

    <div class="pb-4 border-b border-dashed border-gray-300">
      <p class="font-retro text-gray-500 uppercase tracking-wide mb-2">Current status</p>
      {#if summary.status === "idle"}
        <p class="text-gray-600">No controller result yet.</p>
      {:else if summary.actionResults.length === 0}
        <p class="text-gray-600">
          {summary.status === "pending"
            ? "Recommendation pending controller result."
            : "No controller result yet."}
        </p>
      {:else}
        <ul class="space-y-1 text-gray-700">
          {#each summary.actionResults as result}
            <li class="font-mono text-xs">Action {result.action_index + 1}: {result.status}</li>
          {/each}
        </ul>
      {/if}
    </div>

    <div class="pb-4 border-b border-dashed border-gray-300">
      <p class="font-retro text-gray-500 uppercase tracking-wide mb-2">Latest action</p>
      {#if summary.status === "idle"}
        <p class="text-gray-600">No recommendation yet.</p>
      {:else if summary.status === "pending"}
        <p class="text-gray-600">Recommendation pending controller result.</p>
      {:else if !summary.latestRelatedAction}
        <p class="text-gray-600">No hardware action recorded.</p>
      {:else}
        <p class="text-gray-700 font-mono text-xs">
          {summary.latestRelatedAction.command} · {summary.latestRelatedAction.status ?? "unknown"}
        </p>
      {/if}
    </div>

    <div>
      <p class="font-retro text-gray-500 uppercase tracking-wide mb-2">Updated</p>
      <p class="text-gray-700">{summary.time !== null ? formatChartTime(summary.time) : '-'}</p>
    </div>
  </div>
</div>
