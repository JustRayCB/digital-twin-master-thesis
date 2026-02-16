<script lang="ts">
  import Header from "./components/Header.svelte";
  import Analytics from "./views/analytics/Analytics.svelte";
  import Journal from "./views/journal/Journal.svelte";
  import LogicBuilder from "./views/logic_builder/LogicBuilder.svelte";
  import Overview from "./views/overview/Overview.svelte";
  import { currentView, navigate } from "./app_state";
  import type { ViewState } from "./types";

  export let apiBase = "/api";

  function handleNavigate(view: ViewState) {
    navigate(view);
  }
</script>

{#if $currentView === "LOGIC_BUILDER"}
  <LogicBuilder onBack={() => navigate("OVERVIEW")} />
{:else}
  <div class="font-sans bg-desk text-ink min-h-screen flex flex-col overflow-x-hidden selection:bg-cozy-lavender selection:text-ink">
    <Header currentView={$currentView} onNavigate={handleNavigate} />

    <main class="flex-1 p-6 md:p-8 lg:px-12 gap-8 max-w-[1400px] mx-auto w-full">
      {#if $currentView === "OVERVIEW"}
        <Overview />
      {:else if $currentView === "ANALYTICS"}
        <Analytics />
      {:else if $currentView === "JOURNAL"}
        <Journal />
      {:else}
        <div class="bg-white border-2 border-ink shadow-hard rounded-xl p-6">
          <h2 class="font-retro text-3xl">Coming soon</h2>
          <p class="text-gray-500 mt-2">View: {$currentView}</p>
          <p class="text-gray-500 mt-2">API base: {apiBase}</p>
        </div>
      {/if}
    </main>
  </div>
{/if}
