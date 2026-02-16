<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";

  import { processedTopics } from "./realtime_topics";
  import { createRealtimeMonitoringModel } from "./realtime_monitoring_model";

  const model = createRealtimeMonitoringModel();
  const dqHover = model.dqHover;
  const seriesVisibility = model.seriesVisibility;

  const series = [
    { key: "value", label: "processed" },
    { key: "raw_value", label: "raw" },
    { key: "calibrated_value", label: "calibrated" },
    { key: "normalized_value", label: "normalized" },
  ] as const;

  type SeriesKey = (typeof series)[number]["key"];

  let timeView: "day" | "week" | "month" = "day";

  let tempChart: HTMLElement | null = null;
  let humidityChart: HTMLElement | null = null;
  let moistureChart: HTMLElement | null = null;
  let lightChart: HTMLElement | null = null;

  $: model.setChartElement(processedTopics.temperature, tempChart as any);
  $: model.setChartElement(processedTopics.humidity, humidityChart as any);
  $: model.setChartElement(processedTopics.soilMoisture, moistureChart as any);
  $: model.setChartElement(processedTopics.lightIntensity, lightChart as any);

  onMount(async () => {
    await tick();
    await model.start(timeView);
  });
  onDestroy(() => model.stop());
</script>

<div class="flex flex-col h-full animate-in fade-in duration-500">
  <div class="flex flex-col md:flex-row justify-between items-end md:items-center gap-6 mb-8">
    <div class="relative">
      <h1 class="font-retro text-6xl text-ink">Sensor Trends</h1>
      <p class="text-gray-500 mt-2 font-sans font-medium tracking-wide border-l-4 border-cozy-lavender pl-3">
        Historical data for Monstera Study 03
      </p>
    </div>

    <div class="flex bg-cozy-white p-1.5 border-2 border-ink rounded-xl shadow-hard-sm">
      {#each ["day", "week", "month"] as view (view)}
        <label class="cursor-pointer select-none">
          <input
            type="radio"
            name="time-view"
            value={view}
            checked={timeView === view}
            on:change={() => {
              timeView = view as any;
              model.setTimeView(timeView);
            }}
            class="peer sr-only"
          />
          <div
            class={[
              "px-6 py-2 rounded-lg font-retro text-xl uppercase transition-all border-2 border-transparent",
              timeView === view
                ? view === "day"
                  ? "bg-cozy-peach text-ink border-ink"
                  : view === "week"
                    ? "bg-cozy-lavender text-ink border-ink"
                    : "bg-cozy-yellow text-ink border-ink"
                : "text-gray-400 hover:text-gray-600",
            ].join(" ")}
          >
            {view}
          </div>
        </label>
      {/each}
    </div>
  </div>

  <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6">
    <form class="flex flex-wrap gap-2 bg-cozy-white p-2 border-2 border-ink rounded-xl shadow-hard-sm">
      {#each series as s (s.key)}
        <label class="cursor-pointer select-none">
          <input
            type="checkbox"
            name="trace-toggle"
            value={s.key}
            checked={$seriesVisibility[s.key as SeriesKey]}
            on:change={(e) =>
              model.setSeriesVisible(
                s.key as SeriesKey,
                (e.currentTarget as HTMLInputElement).checked,
              )}
            class="peer sr-only"
          />
          <div
            class={[
              "px-4 py-1.5 rounded-lg font-retro text-lg uppercase transition-all border-2",
              $seriesVisibility[s.key as SeriesKey]
                ? "bg-desk text-ink border-ink"
                : "bg-white text-gray-400 border-transparent hover:text-gray-600",
            ].join(" ")}
          >
            {s.label}
          </div>
        </label>
      {/each}
    </form>

    <div class="bg-white border-2 border-ink shadow-hard-sm rounded-xl px-4 py-2 font-mono text-xs text-gray-600">
      <span class="font-bold">DQ (hover):</span> {$dqHover.dqScore ?? "—"}
      {#if $dqHover.flagsText}
        <span class="ml-2">{$dqHover.flagsText}</span>
      {/if}
    </div>
  </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-full flex-1">
      <div class="lg:col-span-8 flex flex-col gap-8">
        <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden">
          <div class="flex justify-between items-center mb-2">
          <div class="flex items-center gap-3">
            <div class="size-10 bg-cozy-peach border-2 border-ink rounded-lg flex items-center justify-center shadow-hard-sm">
              <span class="material-symbols-outlined text-ink">thermostat</span>
            </div>
            <div>
              <h3 class="font-retro text-2xl text-ink leading-none">Temperature</h3>
              <p class="text-xs font-sans text-gray-500 font-bold uppercase tracking-wider">Avg: 23.5°C</p>
            </div>
          </div>
          <button class="text-ink hover:text-gray-600">
            <span class="material-symbols-outlined">more_horiz</span>
          </button>
        </div>
        <div class="h-64 w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white">
          <div bind:this={tempChart} style="width: 100%; height: 100%;"></div>
        </div>
      </div>

      <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden">
        <div class="flex justify-between items-center mb-2">
          <div class="flex items-center gap-3">
            <div class="size-10 bg-cozy-blue border-2 border-ink rounded-lg flex items-center justify-center shadow-hard-sm">
              <span class="material-symbols-outlined text-ink">humidity_percentage</span>
            </div>
            <div>
              <h3 class="font-retro text-2xl text-ink leading-none">Humidity</h3>
              <p class="text-xs font-sans text-gray-500 font-bold uppercase tracking-wider">Avg: 46%</p>
            </div>
          </div>
          <button class="text-ink hover:text-gray-600">
            <span class="material-symbols-outlined">more_horiz</span>
          </button>
        </div>
        <div class="h-64 w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white">
          <div bind:this={humidityChart} style="width: 100%; height: 100%;"></div>
        </div>
      </div>

      <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden">
        <div class="flex justify-between items-center mb-2">
          <div class="flex items-center gap-3">
            <div class="size-10 bg-cozy-lavender border-2 border-ink rounded-lg flex items-center justify-center shadow-hard-sm">
              <span class="material-symbols-outlined text-ink">water_drop</span>
            </div>
            <div>
              <h3 class="font-retro text-2xl text-ink leading-none">Soil Moisture</h3>
              <p class="text-xs font-sans text-gray-500 font-bold uppercase tracking-wider">Avg: 45%</p>
            </div>
          </div>
          <button class="text-ink hover:text-gray-600">
            <span class="material-symbols-outlined">more_horiz</span>
          </button>
        </div>
        <div class="h-64 w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white">
          <div bind:this={moistureChart} style="width: 100%; height: 100%;"></div>
        </div>
      </div>
    </div>

    <div class="lg:col-span-4 flex flex-col gap-6">
      <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden">
        <div class="flex justify-between items-center mb-6">
          <div class="flex items-center gap-3">
            <div class="size-10 bg-cozy-yellow border-2 border-ink rounded-lg flex items-center justify-center shadow-hard-sm">
              <span class="material-symbols-outlined text-ink">light_mode</span>
            </div>
            <div>
              <h3 class="font-retro text-2xl text-ink leading-none">Light Exposure</h3>
              <p class="text-xs font-sans text-gray-500 font-bold uppercase tracking-wider">Total: 8h 12m</p>
            </div>
          </div>
        </div>
        <div class="h-40 w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white mb-2">
          <div bind:this={lightChart} style="width: 100%; height: 100%;"></div>
        </div>
      </div>

      <div class="bg-cozy-mint border-2 border-ink shadow-hard rounded-xl p-6 relative">
        <div class="absolute -right-2 -top-2 rotate-12 bg-white px-2 py-1 border-2 border-ink shadow-sm font-retro text-sm z-10">
          LIVE
        </div>
        <h3 class="font-retro text-2xl text-ink mb-4">Data Freshness</h3>
        <div class="flex items-center gap-4 mb-4">
          <div class="relative flex items-center justify-center size-16 bg-white rounded-full border-2 border-ink">
            <span class="material-symbols-outlined text-3xl text-pop-red">favorite</span>
          </div>
          <div>
            <div class="font-sans font-bold text-xl">Heartbeat</div>
            <div class="text-sm font-retro text-gray-600">Updated 2s ago</div>
          </div>
        </div>
        <div class="w-full bg-white/50 h-2 rounded-full overflow-hidden border border-ink/20">
          <div class="h-full bg-pop-red w-[98%]"></div>
        </div>
        <div class="mt-4 text-xs font-mono text-gray-600 leading-tight">
          Connection stability: 99.9%<br />
          Packets received: 14,203
        </div>
      </div>

      <div class="bg-desk border-2 border-ink border-dashed rounded-xl p-6 flex flex-col gap-4">
        <h3 class="font-retro text-2xl text-ink flex items-center gap-2">
          <span class="material-symbols-outlined">insights</span>
          AI Insights
        </h3>
        <div class="p-3 bg-white border border-ink rounded-lg shadow-sm">
          <p class="font-sans text-sm text-gray-600">
            <span class="text-pop-red font-bold">●</span> Temperature peaks at 2PM usually correspond with direct sunlight.
          </p>
        </div>
        <div class="p-3 bg-white border border-ink rounded-lg shadow-sm">
          <p class="font-sans text-sm text-gray-600">
            <span class="text-cozy-blue font-bold">●</span> Soil moisture depletion rate is stable. Next water cycle in approx 2 days.
          </p>
        </div>
      </div>
    </div>
  </div>

  <div class="mt-12 bg-white border-2 border-ink shadow-hard rounded-xl p-8 relative overflow-hidden">
    <div class="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-cozy-peach via-cozy-lavender to-cozy-yellow border-b-2 border-ink"></div>
    <div class="flex justify-between items-center mb-6 mt-2">
      <h3 class="font-retro text-3xl text-ink">Detailed Event Log</h3>
      <button class="flex items-center gap-2 px-4 py-1.5 bg-desk border-2 border-ink rounded-lg font-retro hover:bg-gray-100 transition-colors">
        <span class="material-symbols-outlined text-lg">download</span>
        EXPORT CSV
      </button>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-left font-sans">
        <thead class="bg-desk border-b-2 border-ink">
          <tr>
            <th class="py-3 px-4 font-retro text-xl font-normal text-gray-500">TIMESTAMP</th>
            <th class="py-3 px-4 font-retro text-xl font-normal text-gray-500">EVENT TYPE</th>
            <th class="py-3 px-4 font-retro text-xl font-normal text-gray-500">VALUE</th>
            <th class="py-3 px-4 font-retro text-xl font-normal text-gray-500">STATUS</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200 text-ink">
          <tr class="hover:bg-gray-50 transition-colors group text-ink">
            <td class="py-3 px-4 font-mono text-sm text-gray-600">Today, 12:45 PM</td>
            <td class="py-3 px-4 flex items-center gap-2">
              <span class="size-2 rounded-full bg-cozy-peach border border-ink"></span>
              Temperature Check
            </td>
            <td class="py-3 px-4 font-bold">24.5°C</td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-bold rounded border border-green-200">NORMAL</span>
            </td>
          </tr>
          <tr class="hover:bg-gray-50 transition-colors group text-ink">
            <td class="py-3 px-4 font-mono text-sm text-gray-600">Today, 12:30 PM</td>
            <td class="py-3 px-4 flex items-center gap-2">
              <span class="size-2 rounded-full bg-cozy-lavender border border-ink"></span>
              Moisture Scan
            </td>
            <td class="py-3 px-4 font-bold">42%</td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs font-bold rounded border border-yellow-200">LOW</span>
            </td>
          </tr>
          <tr class="hover:bg-gray-50 transition-colors group text-ink">
            <td class="py-3 px-4 font-mono text-sm text-gray-600">Today, 11:15 AM</td>
            <td class="py-3 px-4 flex items-center gap-2">
              <span class="size-2 rounded-full bg-cozy-yellow border border-ink"></span>
              Light Spike
            </td>
            <td class="py-3 px-4 font-bold">920lx</td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 bg-green-100 text-green-700 text-xs font-bold rounded border border-green-200">OPTIMAL</span>
            </td>
          </tr>
          <tr class="hover:bg-gray-50 transition-colors group text-ink">
            <td class="py-3 px-4 font-mono text-sm text-gray-600">Today, 09:00 AM</td>
            <td class="py-3 px-4 flex items-center gap-2">
              <span class="size-2 rounded-full bg-cozy-blue border border-ink"></span>
              Auto-Mist
            </td>
            <td class="py-3 px-4 font-bold">Executed</td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-bold rounded border border-blue-200">SYSTEM</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>
