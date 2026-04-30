<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    loadingState,
    errorState,
    policies,
    isDirty,
    loadPolicies,
    savePolicies,
    resetDraft,
    destroy,
  } from "./settings.store";
  import PolicyForm from "./PolicyForm.svelte";

  onMount(() => {
    loadPolicies();
  });

  onDestroy(() => {
    destroy();
  });

  let activeTab: "defaults" | "actuators" | "plants" = "defaults";
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-4">
      <h1 class="font-retro text-5xl text-ink uppercase tracking-tighter">
        Settings
      </h1>
      {#if $isDirty}
        <span
          class="bg-pop-red text-white font-retro text-xs px-2 py-1 rounded animate-pulse"
          >UNSAVED CHANGES</span
        >
      {/if}
    </div>

    <div class="flex gap-4">
      {#if $isDirty}
        <button
          on:click={resetDraft}
          class="font-retro text-xl bg-white text-ink px-6 py-3 border-2 border-ink rounded-lg shadow-hard-sm hover:translate-y-[-2px] transition-all"
        >
          RESET
        </button>
      {/if}
      <button
        on:click={savePolicies}
        disabled={!$isDirty ||
          $loadingState === "saving" ||
          $loadingState === "loading"}
        class="font-retro text-xl bg-cozy-mint text-ink px-8 py-3 border-2 border-ink rounded-lg shadow-hard-sm hover:translate-y-[-2px] hover:shadow-hard active:translate-y-[2px] active:shadow-none transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {$loadingState === "saving" ? "SAVING..." : "SAVE CHANGES"}
      </button>
    </div>
  </div>

  <div
    class="grid grid-cols-1 xl:grid-cols-[260px_minmax(0,1fr)] gap-5"
  >
    <aside class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl overflow-hidden h-fit">
      <div class="p-3 border-b-2 border-ink bg-white/50 text-xs font-bold uppercase tracking-wider text-gray-500">
        Settings sections
      </div>
      <div class="flex flex-col">
        <button
          on:click={() => (activeTab = "defaults")}
          class={[
            "text-left px-4 py-3 font-retro text-xl border-b-2 border-ink transition-colors",
            activeTab === "defaults" ? "bg-cozy-mint" : "hover:bg-cozy-mint/10",
          ].join(" ")}
        >
          GLOBAL DEFAULTS
        </button>
        <button
          on:click={() => (activeTab = "actuators")}
          class={[
            "text-left px-4 py-3 font-retro text-xl border-b-2 border-ink transition-colors",
            activeTab === "actuators" ? "bg-cozy-mint" : "hover:bg-cozy-mint/10",
          ].join(" ")}
        >
          ACTUATORS
        </button>
        <button
          on:click={() => (activeTab = "plants")}
          class={[
            "text-left px-4 py-3 font-retro text-xl transition-colors",
            activeTab === "plants" ? "bg-cozy-mint" : "hover:bg-cozy-mint/10",
          ].join(" ")}
        >
          PLANTS
        </button>
      </div>
    </aside>

    <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl overflow-hidden">
      <div class="p-8">
        {#if $loadingState === "loading"}
          <div class="flex flex-col items-center justify-center py-24 gap-4">
            <span
              class="material-symbols-outlined animate-spin text-6xl text-cozy-mint"
              >autorenew</span
            >
            <span class="font-retro text-xl text-ink">FETCHING POLICIES...</span>
          </div>
        {:else}
          {#if $errorState}
            <div
              class="bg-pop-red/10 border-2 border-pop-red text-pop-red p-4 rounded-lg mb-6 font-sans font-bold flex items-start gap-3"
            >
              <span class="material-symbols-outlined mt-0.5">error</span>
              <span>{$errorState.message}</span>
            </div>
          {/if}

          {#if $policies}
            {#if activeTab === "defaults"}
              <div class="max-w-2xl">
                <PolicyForm
                  title="Global Default Policy"
                  description="These constraints apply to all actuators unless overridden specifically."
                  config={$policies.defaults}
                  path={["defaults"]}
                />
              </div>
            {:else if activeTab === "actuators"}
              <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {#each Object.entries($policies.actuators) as [id, config]}
                  <PolicyForm
                    title={`Actuator: ${id}`}
                    {config}
                    path={["actuators", id]}
                  />
                {/each}
                {#if Object.keys($policies.actuators).length === 0}
                  <div
                    class="col-span-2 py-12 text-center text-gray-500 font-retro uppercase"
                  >
                    No actuator overrides defined
                  </div>
                {/if}
              </div>
            {:else if activeTab === "plants"}
              <div class="space-y-8">
                {#each Object.entries($policies.plants) as [plantId, plantConfig]}
                  <div class="border-2 border-ink rounded-xl p-6 bg-white/30">
                    <h3 class="font-retro text-2xl text-ink mb-4">
                      PLANT ID: {plantId}
                    </h3>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {#each Object.entries(plantConfig.actuators) as [actId, config]}
                        <PolicyForm
                          title={`Override: ${actId}`}
                          {config}
                          path={["plants", plantId, "actuators", actId]}
                        />
                      {/each}
                    </div>
                  </div>
                {/each}
                {#if Object.keys($policies.plants).length === 0}
                  <div
                    class="py-12 text-center text-gray-500 font-retro uppercase"
                  >
                    No plant-specific overrides defined
                  </div>
                {/if}
              </div>
            {/if}
          {/if}
        {/if}
      </div>
    </div>
  </div>
</div>
