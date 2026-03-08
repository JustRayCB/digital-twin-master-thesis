<script lang="ts">
  import type { Routine } from "../types";

  export let routine: Routine;
  export let iconName: string;
  export let iconBgClass: string;
  export let iconColorClass: string = "text-ink";
  export let onToggle: (id: number) => void;
  export let onEdit: (id: number) => void;
  export let onDelete: (id: number) => void;

  function handleCardKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onEdit(routine.id);
    }
  }
</script>

<div
  on:click={() => onEdit(routine.id)}
  on:keydown={handleCardKeyDown}
  role="button"
  tabindex="0"
  class="bg-white border-2 border-ink rounded-xl p-4 flex flex-col gap-4 shadow-sm hover:shadow-hard hover:-translate-y-1 transition-all group cursor-pointer"
>
  <div class="flex gap-4 items-center">
    <div class={`size-12 ${iconBgClass} rounded-lg border-2 border-transparent group-hover:border-ink flex items-center justify-center transition-colors`}>
      <span class={`material-symbols-outlined ${iconColorClass}`}>{iconName}</span>
    </div>
    <div>
      <h4 class="font-retro text-2xl text-ink leading-none">{routine.name}</h4>
      <p class="text-gray-500 text-sm font-sans mt-1">{routine.condition}</p>
    </div>
    <button
      on:click|stopPropagation={() => onToggle(routine.id)}
      class="ml-auto focus:outline-none"
      aria-label="Toggle routine"
      title={routine.active ? "Disable routine" : "Enable routine"}
    >
      <div class={`w-10 h-6 rounded-full border-2 border-ink relative transition-colors ${routine.active ? "bg-green-400" : "bg-gray-200"}`}>
        <div class={`absolute top-1 bottom-1 w-4 bg-white rounded-full border border-ink transition-all ${routine.active ? "right-1" : "left-1"}`}></div>
      </div>
    </button>
  </div>
  <div class="flex justify-end">
    <button
      on:click|stopPropagation={() => onDelete(routine.id)}
      class="size-9 border-2 border-ink rounded-md bg-white hover:bg-gray-50 transition-colors flex items-center justify-center"
      aria-label="Delete routine"
      title="Delete routine"
    >
      <span class="material-symbols-outlined text-base text-ink">delete</span>
    </button>
  </div>
</div>
