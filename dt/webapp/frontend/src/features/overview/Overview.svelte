<script lang="ts">
  /**
   * @fileoverview Primary dashboard view.
   * Displays high-level plant health, current telemetry, quick actuator toggles, and routine status.
   */


  import PlantPixelArt from "./PlantPixelArt.svelte";
  import ClosedLoopSummaryPanel from "./ClosedLoopSummaryPanel.svelte";
  import RoutineCard from "./RoutineCard.svelte";
  import TelemetryCard from "./TelemetryCard.svelte";
  import { autoPilotEnabled, cameraSnapshotView, openRoutineBuilder, overviewViewMode } from "$shared/stores";
  import { PlantHealthState } from "$shared/types";
  import { onDestroy, onMount } from "svelte";
  import { writable } from "svelte/store";
  import {
    actuators,
    closedLoopStatus,
    deleteRoutine,
    destroy,
    editRoutine,
    initialize,
    latestPhoto,
    latestPhotoSrc,
    plantMetrics,
    routines,
    telemetry,
    toggleActuator,
    toggleRoutine,
    updateAutoPilotEnabled,
    vitality,
  } from "./overview.store";

  const healthState = writable<PlantHealthState>(PlantHealthState.HEALTHY);
  const currentTime = writable(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  let clockInterval: ReturnType<typeof setInterval> | null = null;

  $: healthState.set(mapPlantHealthState($vitality.status));
  $: photoAspectRatio =
    $overviewViewMode === "camera" && $latestPhoto?.width && $latestPhoto?.height
      ? `${$latestPhoto.width} / ${$latestPhoto.height}`
      : "1 / 1";

  function mapPlantHealthState(status: string): PlantHealthState {
    if (status === "Critical") {
      return PlantHealthState.COLD;
    }
    if (status === "Stressed") {
      return PlantHealthState.THIRSTY;
    }
    return PlantHealthState.HEALTHY;
  }

  async function handleAutoPilotChange(event: Event) {
    const enabled = (event.target as HTMLInputElement).checked;
    try {
      await updateAutoPilotEnabled(enabled);
    } catch (error) {
      autoPilotEnabled.set(!enabled);
      console.error("Failed to update AI auto-pilot mode", error);
    }
  }

  onMount(() => {
    void initialize(1);
    clockInterval = setInterval(() => {
      currentTime.set(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    }, 1000);
  });

  onDestroy(() => {
    if (clockInterval) {
      clearInterval(clockInterval);
      clockInterval = null;
    }
    destroy();
  });
</script>

<div class="flex flex-col h-full">
  <div class="flex flex-col md:flex-row justify-between items-end md:items-center gap-6 mb-12">
    <div class="relative">
      <div class="absolute -top-6 -left-4 text-cozy-blue opacity-50 -z-10">
        <span class="material-symbols-outlined text-6xl rotate-[-10deg]">wb_cloudy</span>
      </div>
      <h1 class="font-retro text-6xl text-ink">Basil Study </h1>
      <p class="text-gray-500 mt-2 font-sans font-medium tracking-wide border-l-4 border-cozy-lavender pl-3">
        Current Status: Cold & Dying
      </p>
    </div>

    <div class="flex bg-cozy-white p-1.5 border-2 border-ink rounded-xl shadow-hard-sm">
      <label class="cursor-pointer select-none">
        <input type="radio" name="view-mode" value="pixel" class="peer sr-only" bind:group={$overviewViewMode} />
        <div class="flex items-center gap-2 px-6 py-2 rounded-lg font-retro text-xl text-gray-400 peer-checked:bg-cozy-mint peer-checked:text-ink peer-checked:border-ink border-2 border-transparent transition-all">
          <span class="material-symbols-outlined text-lg">token</span>
          PIXEL
        </div>
      </label>
      <label class="cursor-pointer select-none">
        <input type="radio" name="view-mode" value="camera" class="peer sr-only" bind:group={$overviewViewMode} />
        <div class="flex items-center gap-2 px-6 py-2 rounded-lg font-retro text-xl text-gray-400 peer-checked:bg-cozy-mint peer-checked:text-ink peer-checked:border-ink border-2 border-transparent transition-all">
          <span class="material-symbols-outlined text-lg">photo_camera</span>
          PHOTO
        </div>
      </label>
    </div>
  </div>

  <div class="grid grid-cols-1 xl:grid-cols-[minmax(420px,1.2fr)_minmax(320px,0.8fr)] gap-8 xl:gap-10 flex-1">
    <div class="flex flex-col items-center justify-center relative min-h-[500px]">
      <div class="absolute w-full h-full border-4 border-dashed border-gray-200 rounded-3xl -z-10"></div>

      <div class="polaroid-container bg-white p-4 pb-16 shadow-hard-lg border-2 border-gray-100 max-w-2xl w-full relative">
        <div class="absolute -top-4 left-1/2 -translate-x-1/2 w-32 h-10 bg-yellow-100/80 border border-yellow-200/50 rotate-1 shadow-sm z-10 tape"></div>

        {#if $overviewViewMode === "camera"}
          <div class="absolute top-5 right-5 z-30 flex bg-cozy-white/90 p-1 border-2 border-ink rounded-lg shadow-hard-sm backdrop-blur-sm">
            <label class="cursor-pointer select-none">
              <input type="radio" name="camera-view" value="top" class="peer sr-only" bind:group={$cameraSnapshotView} />
              <div class="flex items-center gap-1 px-3 py-1 rounded-md font-retro text-lg text-gray-400 peer-checked:bg-cozy-lavender peer-checked:text-ink peer-checked:border-ink border-2 border-transparent transition-all">
                <span class="material-symbols-outlined text-base">grid_view</span>
                TOP
              </div>
            </label>
            <label class="cursor-pointer select-none">
              <input type="radio" name="camera-view" value="side" class="peer sr-only" bind:group={$cameraSnapshotView} />
              <div class="flex items-center gap-1 px-3 py-1 rounded-md font-retro text-lg text-gray-400 peer-checked:bg-cozy-peach peer-checked:text-ink peer-checked:border-ink border-2 border-transparent transition-all">
                <span class="material-symbols-outlined text-base">view_sidebar</span>
                SIDE
              </div>
            </label>
          </div>
        {/if}

        <div class="bg-gradient-to-br from-gray-100 to-gray-200 w-full border-2 border-ink relative overflow-hidden flex items-center justify-center group" style={`aspect-ratio: ${photoAspectRatio};`}>
          <div class="absolute inset-0 z-10 pointer-events-none opacity-5" style="background: repeating-linear-gradient(0deg, #000, #000 2px, transparent 2px, transparent 4px)"></div>
          {#if $overviewViewMode === "camera"}
            {#if $latestPhotoSrc}
              <img
                src={$latestPhotoSrc}
                alt="Latest plant snapshot"
                class="h-full w-full object-contain bg-gray-100"
              />
            {:else}
              <div class="flex h-full w-full items-center justify-center px-8 text-center font-retro text-2xl text-gray-400">
                Waiting for camera snapshot
              </div>
            {/if}
          {:else}
            <div class="w-[80%] h-[80%] pixel-art drop-shadow-xl group-hover:scale-105 transition-transform duration-500">
              <PlantPixelArt state={$healthState} />
            </div>
          {/if}

          <div class="absolute top-4 left-4 font-retro text-ink bg-white/80 px-2 py-1 border border-ink text-lg z-20 rounded shadow-sm">
            ● REC
          </div>
        </div>

      <div class="absolute bottom-4 left-6 right-6 flex justify-between items-end">
        <div class="font-handwriting text-ink text-2xl font-bold" style="transform: rotate(-1deg);">
          My Workspace Buddy
        </div>
        <span class="font-retro text-gray-400">{$currentTime}</span>
      </div>
    </div>

      <div class="mt-10 flex flex-wrap gap-6 justify-center">
        {#each $actuators as actuator (actuator.id)}
          <button
            on:click={() => toggleActuator(actuator.id)}
            class="group flex flex-col items-center gap-2"
          >
            <div
              class={[
                "size-14 rounded-2xl border-2 border-ink shadow-hard flex items-center justify-center text-ink group-active:translate-y-1 group-active:shadow-hard-sm transition-all",
                actuator.isOn ? "bg-cozy-mint" : "bg-white",
              ].join(" ")}
            >
              <span class="material-symbols-outlined text-2xl">
                {actuator.isOn ? "toggle_on" : "toggle_off"}
              </span>
            </div>
            <span class="font-retro text-lg text-ink font-bold tracking-wide">
              {actuator.name.toUpperCase()}
            </span>
            <span class="text-xs font-mono text-gray-500">
              {actuator.isOn ? "ON" : "OFF"}
            </span>
          </button>
        {/each}
      </div>
    </div>

    <div class="flex flex-col gap-6 justify-center">
      <div class="bg-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden group hover:translate-x-1 transition-transform">
        <div class="flex justify-between items-start mb-4 relative z-10">
          <div>
            <h3 class="font-retro text-2xl text-gray-500 uppercase tracking-widest">Vitality</h3>
            <div class="flex items-baseline gap-3 mt-1">
              <span class="text-5xl font-bold text-ink font-sans">{$vitality.score}</span>
              <span class={`text-xl font-retro px-2 rounded border ${$vitality.statusClass}`}>{$vitality.status}</span>
            </div>
            <p class="mt-2 max-w-sm font-sans text-sm font-semibold leading-snug text-gray-500">
              {$vitality.summary}
            </p>
          </div>
          <div class="size-12 rounded-full border-2 border-ink bg-pop-red flex items-center justify-center shadow-hard-sm">
            <span class="material-symbols-outlined text-white">favorite</span>
          </div>
        </div>
        <div class="w-full h-6 bg-gray-100 rounded-full border-2 border-ink overflow-hidden p-1">
          <div
            class={`h-full rounded-full border border-ink/20 relative ${$vitality.meterClass}`}
            style={`width: ${$vitality.meterWidth};`}
          >
            <div class="absolute inset-0" style="background-image: repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.5) 10px, rgba(255,255,255,0.5) 20px)"></div>
          </div>
        </div>
        <div class="mt-3 flex justify-between font-mono text-xs uppercase tracking-wide text-gray-500">
          <span>Confidence {$vitality.confidence}</span>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {#each Object.values($plantMetrics) as metric (metric.label)}
          <div class="bg-white border-2 border-ink rounded-xl shadow-hard-sm p-4 relative overflow-hidden">
            <div class={`absolute right-3 top-3 size-9 rounded-full border-2 border-ink ${metric.accentClass} flex items-center justify-center`}>
              <span class="material-symbols-outlined text-lg text-ink">{metric.icon}</span>
            </div>
            <p class="font-retro text-lg text-gray-500 uppercase tracking-widest pr-10">{metric.label}</p>
            <p class="mt-4 font-sans text-3xl font-black text-ink">{metric.value}</p>
          </div>
        {/each}
      </div>

      <div class="grid grid-cols-1 gap-5">
        <TelemetryCard
          title="TEMPERATURE"
          value={$telemetry.temperature.value}
          unit=""
          colorClass="bg-cozy-peach"
          iconName="thermostat"
          textColorClass="text-orange-400"
          subLabel1={$telemetry.temperature.label1}
          subLabel2={$telemetry.temperature.label2}
        />
        <TelemetryCard
          title="HUMIDITY"
          value={$telemetry.humidity.value}
          unit=""
          colorClass="bg-cozy-blue"
          iconName="humidity_percentage"
          textColorClass="text-blue-400"
          subLabel1={$telemetry.humidity.label1}
          subLabel2={$telemetry.humidity.label2}
        />
        <TelemetryCard
          title="MOISTURE"
          value={$telemetry.moisture.value}
          unit=""
          colorClass="bg-cozy-lavender"
          iconName="water_drop"
          textColorClass="text-purple-400"
          subLabel1={$telemetry.moisture.label1}
          subLabel2={$telemetry.moisture.label2}
          needsWater={$telemetry.moisture.needsWater}
        />
        <TelemetryCard
          title="LIGHT"
          value={$telemetry.light.value}
          unit=""
          colorClass="bg-cozy-yellow"
          iconName="wb_sunny"
          textColorClass="text-yellow-500"
          subLabel1={$telemetry.light.label1}
          subLabel2={$telemetry.light.label2}
        />
      </div>
    </div>
  </div>

  <ClosedLoopSummaryPanel summary={$closedLoopStatus} />

  <div class="mt-16 border-t-4 border-dashed border-gray-300 pt-8">
    <div class="flex justify-between items-center mb-8">
      <h3 class="font-retro text-4xl text-ink flex items-center gap-3">
        <span class="material-symbols-outlined text-3xl">smart_toy</span>
        ROUTINES
      </h3>
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-3 bg-cozy-white border-2 border-ink rounded-lg shadow-hard-sm px-4 py-2">
          <div class="bg-pop-red border border-ink p-1.5 rounded text-white flex">
            <span class="material-symbols-outlined text-lg">smart_toy</span>
          </div>
          <span class="font-retro text-lg font-bold leading-none mt-1 whitespace-nowrap">AI AUTO-PILOT</span>
          <div class="relative inline-block w-12 h-6 align-middle select-none transition duration-200 ease-in shrink-0 ml-2">
            <input
              type="checkbox"
              name="auto-pilot-toggle"
              id="auto-pilot-toggle"
              class="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 border-ink appearance-none cursor-pointer right-6 checked:right-0 checked:border-green-600 z-10"
              checked={$autoPilotEnabled}
              on:change={(event) => void handleAutoPilotChange(event)}
            />
            <label
              for="auto-pilot-toggle"
              class={[
                "toggle-label block overflow-hidden h-6 rounded-full border-2 border-ink cursor-pointer transition-colors",
                $autoPilotEnabled ? "bg-cozy-mint" : "bg-gray-300",
              ].join(" ")}
            ></label>
          </div>
        </div>

        <button
          on:click={() => openRoutineBuilder()}
          class="font-retro text-xl bg-cozy-white text-ink px-6 py-2 border-2 border-ink rounded-lg shadow-hard-sm hover:bg-gray-50 transition-colors"
        >
          + NEW RULE
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      {#each $routines as routine, index (routine.id)}
        <RoutineCard
          routine={routine}
          iconName={index === 0 ? "water_drop" : index === 1 ? "bedtime" : "warning"}
          iconBgClass={index === 0 ? "bg-cozy-blue/30" : index === 1 ? "bg-cozy-yellow/50" : "bg-pop-red/20"}
          iconColorClass={index === 2 ? "text-pop-red" : "text-ink"}
          onToggle={toggleRoutine}
          onEdit={editRoutine}
          onDelete={deleteRoutine}
        />
      {/each}
    </div>
  </div>
</div>
