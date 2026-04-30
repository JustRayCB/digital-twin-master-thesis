<script lang="ts">
  /**
   * @fileoverview Reusable UI component for displaying a single telemetry metric block.
   */


  export let title: string;
  export let value: string | number;
  export let unit: string | undefined = undefined;
  export let subLabel1: string;
  export let subLabel2: string;
  export let iconName: string;
  export let colorClass: string;
  export let textColorClass: string = "text-ink";
  export let needsWater: boolean | undefined = undefined;
</script>

<div class={`${colorClass} border-2 border-ink shadow-hard rounded-xl p-5 hover:translate-x-1 transition-transform cursor-default`}>
  <div class="flex justify-between items-center mb-1">
    <div class="flex items-center gap-2">
      <div class="size-8 bg-white border border-ink rounded-lg flex items-center justify-center">
        <span class={`material-symbols-outlined ${textColorClass} text-lg`}>{iconName}</span>
      </div>
      <span class="font-retro text-xl text-ink/70 uppercase">{title}</span>
    </div>
    {#if needsWater}
      <span class="bg-white/50 px-2 py-0.5 rounded border border-ink/20 text-xs font-bold text-ink">NEEDS WATER</span>
    {:else}
      <div class="flex gap-1">
        {#if title === "LIGHT"}
          <span class="size-2 rounded-full bg-ink"></span>
          <span class="size-2 rounded-full bg-ink"></span>
          <span class="size-2 rounded-full bg-ink"></span>
          <span class="size-2 rounded-full bg-ink/30"></span>
        {:else}
          <span class="material-symbols-outlined text-ink opacity-20 text-4xl">
            {iconName === "thermostat" ? "sunny" : iconName === "wb_sunny" ? "wb_sunny" : ""}
          </span>
        {/if}
      </div>
    {/if}
  </div>
  <div class="flex items-end justify-between mt-2">
    <div class="font-sans text-5xl font-bold text-ink">
      {value}
      {#if unit}
        <span class="text-2xl ml-1 font-normal opacity-60">{unit}</span>
      {/if}
    </div>
    <div class="text-right">
      <div class="text-xs font-bold uppercase tracking-wider opacity-60">{subLabel1}</div>
      <div class="font-retro text-lg">{subLabel2}</div>
    </div>
  </div>
</div>
