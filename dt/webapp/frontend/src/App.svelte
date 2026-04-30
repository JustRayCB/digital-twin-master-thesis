<script lang="ts">
  /**
   * @fileoverview Root application component.
   * Manages global layout and top-level routing between main application views (Overview, Analytics, Journal, Logic Builder).
   */

  import Header from "$shared/components/Header.svelte";
  import Analytics from "$features/analytics/Analytics.svelte";
  import Journal from "$features/journal/Journal.svelte";
  import LogicBuilder from "$features/logic_builder/LogicBuilder.svelte";
  import Overview from "$features/overview/Overview.svelte";
  import Settings from "$features/settings/Settings.svelte";
  import { currentView, navigate } from "$shared/stores";
  import type { ViewState } from "$shared/types";

  /**
   * Base URL for API requests. Usually passed in from the entry point.
   */
  export let apiBase = "/api";

  /**
   * Handles top-level navigation events emitted by the Header component.
   * @param view - The target view state to navigate to.
   */
  function handleNavigate(view: ViewState) {
    navigate(view);
  }
</script>

{#if $currentView === "LOGIC_BUILDER"}
  <LogicBuilder onBack={() => navigate("OVERVIEW")} />
{:else}
  <div
    class="dashboard-shell font-sans bg-desk text-ink min-h-screen flex flex-col overflow-x-hidden selection:bg-cozy-lavender selection:text-ink"
  >
    <Header currentView={$currentView} onNavigate={handleNavigate} />

    <main class="dashboard-page w-full">
      {#if $currentView === "OVERVIEW"}
        <Overview />
      {:else if $currentView === "ANALYTICS"}
        <Analytics />
      {:else if $currentView === "JOURNAL"}
        <Journal />
      {:else if $currentView === "SETTINGS"}
        <Settings {apiBase} />
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
