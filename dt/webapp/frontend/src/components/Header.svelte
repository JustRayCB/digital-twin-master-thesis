<script lang="ts">
  import { onDestroy, onMount } from "svelte";

  import type { ViewState } from "../types";
  import { navItems } from "./header_state";
  import { realtimeReadings } from "../views/analytics/realtime_readings_store";
  import { realtimeStatus } from "../views/analytics/realtime_status_store";

  export let currentView: ViewState;
  export let onNavigate: (view: ViewState) => void;

  let connectionStatus = "Disconnected";
  let lastUpdate = "—";
  let unsubscribeStatus: (() => void) | null = null;
  let unsubscribeReadings: (() => void) | null = null;

  function formatLastUpdate(value: number) {
    if (!Number.isFinite(value)) {
      return "—";
    }
    return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  onMount(() => {
    realtimeStatus.start();
    realtimeReadings.start();

    unsubscribeStatus = realtimeStatus.subscribe((snapshot) => {
      connectionStatus = snapshot.connected ? "Connected" : "Disconnected";
    });
    unsubscribeReadings = realtimeReadings.subscribe((_topic, payload) => {
      lastUpdate = formatLastUpdate(Number(payload.time));
    });
  });

  onDestroy(() => {
    if (unsubscribeStatus) {
      unsubscribeStatus();
      unsubscribeStatus = null;
    }
    if (unsubscribeReadings) {
      unsubscribeReadings();
      unsubscribeReadings = null;
    }
  });
</script>

<header class="bg-cozy-white border-b-4 border-ink px-6 py-4 sticky top-0 z-50">
  <div class="max-w-[1400px] mx-auto flex items-center justify-between">
    <div class="flex items-center gap-4">
      <div class="size-12 bg-cozy-mint border-2 border-ink flex items-center justify-center shadow-hard-sm rounded-lg">
        <span class="material-symbols-outlined text-ink text-3xl">potted_plant</span>
      </div>
      <div class="flex flex-col">
        <h2 class="font-retro text-4xl text-ink leading-none tracking-wide">DIGITAL TWIN</h2>
        <div class="flex items-center gap-2 mt-1">
          <span
            class={[
              "size-3 rounded-full animate-pulse border border-ink",
              connectionStatus === "Connected" ? "bg-green-500" : "bg-pop-red",
            ].join(" ")}
          ></span>
          <span class="text-xs uppercase tracking-widest text-gray-500 font-bold">{connectionStatus}</span>
        </div>
      </div>
    </div>

    <div class="hidden md:flex flex-1 justify-center px-8">
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

    <div class="flex items-center gap-4">
      <div class="hidden sm:flex items-center gap-2 px-3 py-1 bg-cozy-blue/30 border-2 border-ink rounded-lg font-retro text-lg">
        <span class="material-symbols-outlined text-sm">schedule</span>
        <span>Last update: {lastUpdate}</span>
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
