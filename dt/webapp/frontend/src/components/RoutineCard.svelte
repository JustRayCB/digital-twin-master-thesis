<script lang="ts">
  import type { Routine } from "../types";

  export let routine: Routine;
  export let iconName: string;
  export let iconBgClass: string;
  export let iconColorClass: string = "text-ink";
  export let onToggle: (id: string) => void;
</script>

<div
  on:click={() => onToggle(routine.id)}
  class="bg-white border-2 border-ink rounded-xl p-4 flex gap-4 items-center shadow-sm hover:shadow-hard hover:-translate-y-1 transition-all cursor-pointer group"
>
  <div class={`size-12 ${iconBgClass} rounded-lg border-2 border-transparent group-hover:border-ink flex items-center justify-center transition-colors`}>
    <span class={`material-symbols-outlined ${iconColorClass}`}>{iconName}</span>
  </div>
  <div>
    <h4 class="font-retro text-2xl text-ink leading-none">{routine.name}</h4>
    <p class="text-gray-500 text-sm font-sans mt-1">{routine.condition}</p>
  </div>
  <div class="ml-auto">
    <div class={`w-10 h-6 rounded-full border-2 border-ink relative transition-colors ${routine.active ? "bg-green-400" : "bg-gray-200"}`}>
      <div class={`absolute top-1 bottom-1 w-4 bg-white rounded-full border border-ink transition-all ${routine.active ? "right-1" : "left-1"}`}></div>
    </div>
  </div>
</div>

