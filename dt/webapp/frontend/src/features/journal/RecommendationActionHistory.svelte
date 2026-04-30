<script lang="ts">
  import type { JournalActionHistoryItem, JournalRecommendationHistoryItem } from "./journal.types";

  import ActionHistoryList from "./ActionHistoryList.svelte";
  import RecommendationHistoryCard from "./RecommendationHistoryCard.svelte";

  export let recommendationHistory: JournalRecommendationHistoryItem[];
  export let actionHistory: JournalActionHistoryItem[];

  function getRelatedActions(correlationId: string): JournalActionHistoryItem[] {
    return actionHistory.filter((item) => item.correlation_id === correlationId);
  }
</script>

<div
  class="bg-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden h-full min-h-0 flex flex-col"
>
  <div class="absolute top-0 right-0 w-20 h-20 bg-cozy-blue/10 rounded-bl-full -z-0"></div>
  <h3 class="font-retro text-3xl text-ink flex items-center gap-3 mb-4">
    <span class="material-symbols-outlined text-3xl text-cozy-blue">hub</span>
    Closed-loop history
  </h3>

  <div class="flex flex-col gap-4 relative z-10 flex-1 min-h-0">
    <div class="bg-cozy-blue/10 border-2 border-cozy-blue rounded-lg p-4 flex flex-col flex-1 min-h-0">
      <h4 class="font-retro text-xl text-ink mb-3">Recommendations</h4>

      {#if recommendationHistory.length === 0}
        <p class="text-sm italic text-gray-600">No recommendations recorded</p>
      {:else}
        <div class="space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1 min-h-0">
          {#each recommendationHistory as item (item.correlation_id)}
            <RecommendationHistoryCard item={item} relatedActions={getRelatedActions(item.correlation_id)} />
          {/each}
        </div>
      {/if}
    </div>

    <ActionHistoryList {actionHistory} />
  </div>
</div>
