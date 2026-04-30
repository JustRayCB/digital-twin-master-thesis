<script lang="ts">
  /**
   * @fileoverview Primary navigation header component.
   * Displays the brand, main view switcher, and a global realtime connection status indicator.
   */


  import { onDestroy, onMount } from "svelte";

  import { readingSubscriptions, statusSubscriptions } from "$shared/realtime";
  import type { SubscriptionToken } from "$shared/realtime/subscription.token";
  import { applyConnectionStatusPayload, connectionStatus, setLastUpdate } from "$shared/stores";
  import type { ViewState } from "$shared/types";
  import { navItems } from "./header_state";

    /** The currently active view, used to highlight the corresponding navigation button. */
  export let currentView: ViewState;
    /** Callback triggered when a navigation button is clicked. */
  export let onNavigate: (view: ViewState) => void;

  let connectionLabel = "Disconnected";
  let lastUpdateLabel = "—";
  let statusSubscription: SubscriptionToken | null = null;
  let readingsSubscription: SubscriptionToken | null = null;

  // Reactive statements to update the connection status and last update time labels whenever the underlying store values change.
  $: connectionLabel = $connectionStatus.connected ? "Connected" : "Disconnected";
  $: lastUpdateLabel = formatLastUpdate(Number($connectionStatus.lastUpdate));

  function formatLastUpdate(value: number) {
    if (!Number.isFinite(value)) {
      return "—";
    }
    return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  onMount(() => {
    // Subscribe to realtime connection status updates and processed readings to keep the header connection indicators up to date.
    statusSubscription = statusSubscriptions.subscribeToConnectionStatus((payload) => {
      applyConnectionStatusPayload(payload);
    });

    // Subscribe to processed readings to update the "Last update" timestamp whenever new data is received.
    readingsSubscription = readingSubscriptions.subscribeToProcessedReadings((payload) => {
      const timestamp = Number((payload as any)?.time);
      if (!Number.isFinite(timestamp)) {
        return;
      }
      setLastUpdate(timestamp);
    });
  });

  onDestroy(() => {
    if (statusSubscription) {
      statusSubscription.cleanup();
      statusSubscription = null;
    }
    if (readingsSubscription) {
      readingsSubscription.cleanup();
      readingsSubscription = null;
    }
  });
</script>

<header class="bg-cozy-white border-b-4 border-ink px-6 py-4 sticky top-0 z-50">
  <div class="w-full grid grid-cols-[1fr_auto_1fr] items-center gap-4">
    <div class="flex items-center gap-4 justify-self-start">
      <div class="size-12 bg-cozy-mint border-2 border-ink flex items-center justify-center shadow-hard-sm rounded-lg">
        <span class="material-symbols-outlined text-ink text-3xl">potted_plant</span>
      </div>
      <div class="flex flex-col">
        <h2 class="font-retro text-4xl text-ink leading-none tracking-wide">DIGITAL TWIN</h2>
        <div class="flex items-center gap-2 mt-1">
          <span
            class={[
              "size-3 rounded-full animate-pulse border border-ink",
              connectionLabel === "Connected" ? "bg-green-500" : "bg-pop-red",
            ].join(" ")}
          ></span>
          <span class="text-xs uppercase tracking-widest text-gray-500 font-bold">{connectionLabel}</span>
        </div>
      </div>
    </div>

    <div class="hidden md:flex justify-self-center px-8">
      <nav class="flex items-center gap-4">
        {#each navItems as view}
          <button
            on:click={() => onNavigate(view)}
            class={[
              "px-6 py-2 rounded-full font-retro text-xl tracking-wider transition-all border-2",
              currentView === view
                ? "bg-ink text-cozy-white border-transparent shadow-hard-sm hover:-translate-y-1"
                : "bg-cozy-white text-ink border-ink hover:bg-gray-50 hover:-translate-y-1",
            ].join(" ")}
          >
            {view}
          </button>
        {/each}
      </nav>
    </div>

    <div class="flex items-center gap-4 justify-self-end">
      <div class="hidden sm:flex items-center gap-2 px-3 py-1 bg-cozy-blue/30 border-2 border-ink rounded-lg font-retro text-lg">
        <span class="material-symbols-outlined text-sm">schedule</span>
        <span>Last update: {lastUpdateLabel}</span>
      </div>
      <button
        class="size-12 flex items-center justify-center bg-cozy-yellow border-2 border-ink rounded-full hover:bg-yellow-200 transition-colors shadow-hard-sm active:translate-y-0.5 active:shadow-none"
      >
        <span class="material-symbols-outlined">notifications</span>
      </button>
      <div
        class="size-12 border-2 border-ink rounded-full bg-cover bg-center shadow-hard-sm overflow-hidden"
        style='background-image: url("https://cdn-icons-png.flaticon.com/512/3135/3135715.png");'
      ></div>
    </div>
  </div>
</header>
