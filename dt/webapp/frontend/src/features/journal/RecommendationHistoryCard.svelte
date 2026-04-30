<script lang="ts">
  import { formatDisplayTime } from "$shared/utils/time";

  import type { JournalActionHistoryItem, JournalRecommendationHistoryItem } from "./journal.types";

  export let item: JournalRecommendationHistoryItem;
  export let relatedActions: JournalActionHistoryItem[];

  function formatConfidence(value: number): string {
    if (!Number.isFinite(value)) {
      return "—";
    }

    return `${Math.round(value * 100)}%`;
  }

  function formatDuration(value?: number | null): string {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return "—";
    }

    return `${value}s`;
  }

  function summarizeControllerStatus(recommendation: JournalRecommendationHistoryItem): string {
    if (recommendation.action_results.length === 0) {
      return "Pending controller result";
    }

    return recommendation.action_results.map((result) => result.status).join(", ");
  }
</script>

<div class="bg-white border-2 border-ink rounded-lg p-3">
  <div class="flex items-start justify-between gap-3">
    <div>
      <p class="font-retro text-lg text-ink">{item.reason || "Recommendation"}</p>
      <p class="text-xs font-sans text-gray-600">
        Plant {item.plant_id} • {formatDisplayTime(item.time)}
      </p>
    </div>
    <span class="px-2 py-1 border border-ink rounded text-xs font-retro bg-cozy-mint/50">
      {formatConfidence(item.confidence)}
    </span>
  </div>

  <p class="text-xs font-mono text-gray-600 mt-2 break-all">correlation_id: {item.correlation_id}</p>
  <p class="text-xs text-ink font-sans mt-1">Status: {summarizeControllerStatus(item)}</p>

  <details class="mt-2">
    <summary class="px-2 py-1 border border-ink rounded text-xs font-retro bg-white hover:bg-gray-50 transition-colors cursor-pointer inline-block">
      Show details
    </summary>
    <div class="mt-2 p-2 border border-gray-300 rounded bg-gray-50/70 space-y-2">
      {#if item.model_metadata}
        <div>
          <p class="font-retro text-xs text-gray-500 uppercase">Model metadata</p>
          <p class="text-xs text-gray-600 font-sans">
            {item.model_metadata.model_name} • {item.model_metadata.model_version}
          </p>
        </div>
      {/if}

      <div>
        <p class="font-retro text-sm text-gray-600">Proposed actions</p>
        {#if item.actions.length === 0}
          <p class="text-xs italic text-gray-500">No actions proposed</p>
        {:else}
          <div class="mt-1 space-y-1">
            {#each item.actions as action, actionIndex (`${item.correlation_id}-action-${actionIndex}`)}
              <p class="text-xs text-ink font-sans">
                {action.capability} • {action.command} • {formatDuration(action.duration_seconds)}
              </p>
            {/each}
          </div>
        {/if}
      </div>

      <div>
        <p class="font-retro text-sm text-gray-600">Controller results</p>
        {#if item.action_results.length === 0}
          <p class="text-xs italic text-gray-500">Pending controller result</p>
        {:else}
          <div class="mt-1 space-y-1">
            {#each item.action_results as result, resultIndex (`${item.correlation_id}-result-${resultIndex}`)}
              <p class="text-xs text-ink font-sans">
                Action #{result.action_index + 1} • {result.status}
              </p>
            {/each}
          </div>
        {/if}
      </div>

      <div>
        <p class="font-retro text-sm text-gray-600">Related actions</p>
        {#if relatedActions.length === 0}
          <p class="text-xs italic text-gray-500">No related action recorded for this recommendation</p>
        {:else}
          <div class="mt-1 space-y-1">
            {#each relatedActions as related (`${related.execution_id}-${related.event_at}`)}
              <p class="text-xs text-ink font-sans">
                {formatDisplayTime(related.event_at)} • {related.command} • {related.status ?? "unknown"}
              </p>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </details>
</div>
