<script lang="ts">
  import { onDestroy, onMount } from "svelte";

  import { createJournalModel, journalColors, journalIcons } from "./journal_model";

  const model = createJournalModel();
  const alerts = model.alerts;
  const logs = model.logs;
  const entryTitle = model.entryTitle;
  const entryText = model.entryText;
  const entryTags = model.entryTags;
  const entryIcon = model.entryIcon;
  const entryColor = model.entryColor;
  const tankLevelPercent = model.tankLevelPercent;
  const tankLiters = model.tankLiters;
  const tankRefilledLabel = model.tankRefilledLabel;
  const tankEmptyInLabel = model.tankEmptyInLabel;

  onMount(() => model.start());
  onDestroy(() => model.stop());
</script>

<div class="flex flex-col animate-in fade-in duration-500 w-full">
  <div class="flex flex-col md:flex-row justify-between items-end md:items-center gap-6 mb-8">
    <div class="relative">
      <div class="absolute -top-6 -left-4 text-cozy-blue opacity-50 -z-10">
        <span class="material-symbols-outlined text-6xl rotate-[-10deg]">wb_cloudy</span>
      </div>
      <h1 class="font-retro text-6xl text-ink">Alerts & Journal</h1>
      <p class="text-gray-500 mt-2 font-sans font-medium tracking-wide border-l-4 border-pop-red pl-3">
        Attention Needed: {$alerts.length} Active Alerts
      </p>
    </div>

    <div class="flex bg-cozy-white p-1.5 border-2 border-ink rounded-xl shadow-hard-sm">
      <button class="flex items-center gap-2 px-6 py-2 rounded-lg font-retro text-xl bg-cozy-peach text-ink border-2 border-ink shadow-sm hover:translate-x-0.5 hover:translate-y-0.5 hover:shadow-none transition-all">
        <span class="material-symbols-outlined text-lg">history</span>
        EXPORT LOGS
      </button>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 lg:h-[700px] w-full">
    <div class="lg:col-span-5 flex flex-col gap-6 h-full min-h-0">
      <div class="bg-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden flex flex-col flex-1 min-h-0">
        <div class="absolute top-0 right-0 w-24 h-24 bg-pop-red/10 rounded-bl-full -z-0"></div>
        <div class="flex-shrink-0 mb-4 relative z-10">
          <h3 class="font-retro text-3xl text-ink flex items-center gap-3">
            <span class="material-symbols-outlined text-3xl text-pop-red animate-bounce">warning</span>
            Active Crises
          </h3>
        </div>

        {#if $alerts.length === 0}
          <div class="p-4 text-center font-sans text-gray-500 italic">No active alerts. Good job!</div>
        {:else}
          <div class="flex flex-col gap-3 relative z-10 overflow-y-auto pr-2 -mr-2 pb-2 custom-scrollbar flex-1 min-h-0">
            {#each $alerts as alert (alert.id)}
              <div class={`${alert.kind === "water" ? "bg-pop-red/10 border-pop-red" : "bg-cozy-yellow/30 border-cozy-yellow"} border-2 rounded-lg p-3 flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between shrink-0`}>
                <div class="flex gap-3 items-center">
                  <div class={`size-8 ${alert.kind === "water" ? "bg-pop-red text-white" : "bg-cozy-yellow text-ink"} border-2 border-ink rounded flex items-center justify-center shrink-0`}>
                    <span class="material-symbols-outlined text-sm">{alert.kind === "water" ? "water_drop" : "thermostat"}</span>
                  </div>
                  <div>
                    <div class="font-retro text-lg text-ink leading-none">{alert.title}</div>
                    <div class="text-xs font-sans text-gray-600 mt-1">{alert.desc}</div>
                  </div>
                </div>
                <button
                  on:click={() => model.dismissAlert(alert.id)}
                  class="px-3 py-1 rounded border-2 border-ink bg-white font-retro text-sm hover:bg-gray-50 transition-colors shrink-0"
                >
                  DISMISS
                </button>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="bg-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-retro text-3xl text-ink flex items-center gap-3">
            <span class="material-symbols-outlined text-3xl text-cozy-blue">water</span>
            Water Tank Status
          </h3>
          <div class="flex items-center gap-2">
            <button
              on:click={() => model.refillTank()}
              class="px-3 py-1 rounded border-2 border-ink bg-cozy-mint font-retro text-sm hover:bg-green-100 transition-colors"
            >
              REFILL
            </button>
          </div>
        </div>

        <div class="flex gap-4 items-stretch">
          <div class="w-28 bg-white border-2 border-ink rounded-xl overflow-hidden flex flex-col justify-end relative shadow-inner shrink-0">
            <div class="absolute inset-0 fluid-container z-0 pointer-events-none"></div>
            <div class="wave bg-blue-400 relative z-10 w-full" style="height: 35%;">
              <div class="absolute top-0 w-full h-2 bg-blue-500 opacity-50"></div>
              <div class="absolute bottom-2 left-2 size-2 bg-white/50 rounded-full animate-[ping_3s_infinite]"></div>
            </div>
            <div class="absolute right-0 top-0 bottom-0 w-4 border-l-2 border-ink bg-gray-50 flex flex-col justify-between py-2 items-center z-20">
              <span class="w-2 h-0.5 bg-ink"></span>
              <span class="w-2 h-0.5 bg-ink"></span>
              <span class="w-2 h-0.5 bg-ink"></span>
            </div>
          </div>

          <div class="flex-1 flex flex-col gap-3 min-w-0">
            <div class="bg-white border-2 border-ink rounded-lg p-3 shadow-sm">
              <div class="flex justify-between items-baseline">
                <span class="font-retro text-lg text-gray-500">Level</span>
                <span class="font-sans font-bold text-2xl text-ink">{Number($tankLiters).toFixed(1)}L</span>
              </div>
              <div class="w-full bg-gray-200 h-2.5 border border-ink rounded-full mt-2 overflow-hidden">
                <div class="bg-blue-400 h-full border-r border-ink" style={`width: ${$tankLevelPercent}%;`}></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="bg-white border-2 border-ink rounded-lg p-2 text-center">
                <span class="block font-retro text-gray-500 text-xs uppercase">Refilled</span>
                <span class="block font-bold text-ink text-sm">{$tankRefilledLabel}</span>
              </div>
              <div class="bg-white border-2 border-ink rounded-lg p-2 text-center">
                <span class="block font-retro text-gray-500 text-xs uppercase">Empty In</span>
                <span class="block font-bold text-ink text-pop-red text-sm">{$tankEmptyInLabel}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="lg:col-span-7 flex flex-col h-full min-h-0">
      <div class="bg-desk border-4 border-dashed border-ink/20 rounded-3xl p-6 h-full relative flex flex-col min-h-0">
        <div class="absolute -top-5 left-8 w-40 h-12 bg-cozy-lavender/40 border border-cozy-lavender rotate-[-2deg] shadow-sm z-10 tape flex items-center justify-center">
          <span class="font-handwriting font-bold text-ink text-xl font-retro">MANUAL LOGS</span>
        </div>

        <div
          class="bg-white border-2 border-ink shadow-hard-lg rounded-xl flex-1 overflow-hidden flex flex-col relative min-h-0"
          style="background-image: repeating-linear-gradient(transparent, transparent 31px, #e5e7eb 31px, #e5e7eb 32px); background-attachment: local;"
        >
          <div class="absolute left-16 top-0 bottom-0 w-0.5 bg-red-200/80 z-0 h-full"></div>

          <div class="p-6 pt-10 flex-1 overflow-y-auto z-10 custom-scrollbar min-h-0">
            <div class="space-y-6">
              {#each $logs as log (log.id)}
                <div class="flex gap-6 items-start group">
                  <div class="w-24 pt-1 text-right font-retro text-gray-500 text-lg">
                    {log.dayLabel}<br /><span class="text-xs">{log.timeLabel}</span>
                  </div>
                  <div class="flex-1 bg-cozy-white border-2 border-ink rounded-lg p-4 shadow-sm group-hover:shadow-md transition-shadow relative">
                    <div class={`absolute -left-3 top-4 size-6 ${log.iconColor} border-2 border-ink rounded-full flex items-center justify-center z-20`}>
                      <span class="material-symbols-outlined text-xs">{log.icon}</span>
                    </div>
                    <h4 class="font-bold text-ink text-xl font-retro">{log.title}</h4>
                    <p class="text-gray-600 font-sans text-sm mt-1">{log.desc}</p>
                    {#if log.tags}
                      <div class="flex gap-2 mt-3">
                        {#each log.tags as tag (tag)}
                          <span class="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-xs font-mono">{tag}</span>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          </div>

          <div class="p-4 bg-gray-50 border-t-2 border-ink z-20 shrink-0">
            <div class="grid grid-cols-1 md:grid-cols-12 gap-3">
              <div class="md:col-span-4">
                <label for="journal-entry-title" class="block text-xs font-bold uppercase tracking-wider text-gray-500 font-sans mb-1">Entry title</label>
                <input
                  id="journal-entry-title"
                  class="w-full bg-white border-2 border-ink rounded-lg px-4 py-2 font-retro text-lg focus:outline-none focus:ring-2 focus:ring-cozy-lavender placeholder:text-gray-400"
                  placeholder="Entry title"
                  type="text"
                  bind:value={$entryTitle}
                />
              </div>

              <div class="md:col-span-3">
                <label for="journal-entry-tags" class="block text-xs font-bold uppercase tracking-wider text-gray-500 font-sans mb-1">Tags</label>
                <input
                  id="journal-entry-tags"
                  class="w-full bg-white border-2 border-ink rounded-lg px-4 py-2 font-retro text-lg focus:outline-none focus:ring-2 focus:ring-cozy-lavender placeholder:text-gray-400"
                  placeholder="Tags (comma separated)"
                  type="text"
                  bind:value={$entryTags}
                />
              </div>

              <div class="md:col-span-2">
                <label for="journal-entry-icon" class="block text-xs font-bold uppercase tracking-wider text-gray-500 font-sans mb-1">Icon</label>
                <select
                  id="journal-entry-icon"
                  class="w-full bg-white border-2 border-ink rounded-lg px-3 py-2 font-retro text-lg focus:outline-none focus:ring-2 focus:ring-cozy-lavender"
                  bind:value={$entryIcon}
                >
                  {#each journalIcons as icon (icon.value)}
                    <option value={icon.value}>{icon.label}</option>
                  {/each}
                </select>
              </div>

              <div class="md:col-span-2">
                <label for="journal-entry-color" class="block text-xs font-bold uppercase tracking-wider text-gray-500 font-sans mb-1">Color</label>
                <select
                  id="journal-entry-color"
                  class="w-full bg-white border-2 border-ink rounded-lg px-3 py-2 font-retro text-lg focus:outline-none focus:ring-2 focus:ring-cozy-lavender"
                  bind:value={$entryColor}
                >
                  {#each journalColors as color (color.value)}
                    <option value={color.value}>{color.label}</option>
                  {/each}
                </select>
              </div>

              <div class="md:col-span-12 flex gap-3">
                <div class="size-10 bg-white border-2 border-ink rounded-lg flex items-center justify-center text-gray-400 hover:text-ink cursor-pointer transition-colors shrink-0">
                  <span class="material-symbols-outlined">add_a_photo</span>
                </div>
                <input
                  class="flex-1 bg-white border-2 border-ink rounded-lg px-4 font-retro text-lg focus:outline-none focus:ring-2 focus:ring-cozy-lavender placeholder:text-gray-400 min-w-0"
                  placeholder="Write a new journal entry..."
                  type="text"
                  bind:value={$entryText}
                  on:keydown={(e) => e.key === "Enter" && model.addEntry()}
                />
                <button
                  on:click={() => model.addEntry()}
                  class="bg-ink text-white px-6 py-2 rounded-lg font-retro text-xl border-2 border-transparent hover:bg-gray-800 transition-colors shrink-0"
                >
                  SAVE
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
