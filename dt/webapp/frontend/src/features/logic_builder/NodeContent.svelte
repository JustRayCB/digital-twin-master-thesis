<script lang="ts">
  /**
   * @fileoverview Dynamic form renderer for individual logic nodes.
   * Renders the appropriate input fields based on the node's type (Trigger vs Action) and specific configuration.
   */


  import { isGrowLightLabel } from "./node.transforms";
  import type { NodeData } from "./types";

  export let node: NodeData;
  export let updateNodeConfig: (id: string, updates: Record<string, unknown>) => void;

  function stopProp(event: MouseEvent | TouchEvent) {
    event.stopPropagation();
  }
</script>

{#if node.type === "TRIGGER"}
  <div class="flex flex-col gap-3" on:mousedown={stopProp}>
    {#if (node.config.triggerKind || "sensor") === "sensor"}
      <div class="flex items-center gap-2">
        <select
          class="bg-desk border border-ink rounded px-1 py-1 text-sm font-bold font-mono focus:outline-none"
          value={node.config.operator}
          on:change={(e) => updateNodeConfig(node.id, { operator: (e.target as HTMLSelectElement).value })}
        >
          <option value="<">&lt;</option>
          <option value=">">&gt;</option>
          <option value="=">=</option>
          <option value="!=">!=</option>
        </select>
        <input
          type="number"
          class="bg-desk border border-ink rounded px-2 py-1 text-sm font-retro w-20 focus:outline-none"
          value={node.config.value}
          on:change={(e) => updateNodeConfig(node.id, { value: (e.target as HTMLInputElement).value })}
        />
        <span class="font-retro text-ink/60">{node.config.unit}</span>
      </div>
    {/if}

    {#if node.config.triggerKind === "time"}
      <input
        type="time"
        class="bg-desk border border-ink rounded px-2 py-1 text-sm font-retro w-28 focus:outline-none"
        value={node.config.time || "08:00"}
        on:change={(e) => updateNodeConfig(node.id, { time: (e.target as HTMLInputElement).value })}
      />
    {/if}

    {#if node.config.triggerKind === "date"}
      <input
        type="date"
        class="bg-desk border border-ink rounded px-2 py-1 text-sm font-retro w-40 focus:outline-none"
        value={node.config.date || "2026-02-14"}
        on:change={(e) => updateNodeConfig(node.id, { date: (e.target as HTMLInputElement).value })}
      />
    {/if}

    {#if node.config.triggerKind === "interval"}
      <div class="flex items-center gap-2">
        <input
          type="number"
          class="bg-desk border border-ink rounded px-2 py-1 text-sm font-retro w-16 focus:outline-none"
          value={node.config.everyDays || 2}
          min="1"
          on:change={(e) => updateNodeConfig(node.id, { everyDays: Number((e.target as HTMLInputElement).value) })}
        />
        <span class="font-retro text-sm">days</span>
        <input
          type="time"
          class="bg-desk border border-ink rounded px-2 py-1 text-sm font-retro w-28 focus:outline-none"
          value={node.config.at || "19:00"}
          on:change={(e) => updateNodeConfig(node.id, { at: (e.target as HTMLInputElement).value })}
        />
      </div>
    {/if}
  </div>
{:else if node.type === "ACTION"}
  {#if isGrowLightLabel(node.label)}
    <div class="flex flex-col gap-2" on:mousedown={stopProp}>
      <div class="flex items-center justify-between bg-desk border border-ink rounded p-2">
        <span class="font-retro text-sm">STATE:</span>
        <button
          class={[
            "px-3 py-0.5 border border-ink rounded font-bold text-xs",
            node.config.actionState ? "bg-green-400 text-ink" : "bg-gray-200 text-gray-500",
          ].join(" ")}
          on:click={() => updateNodeConfig(node.id, { actionState: !node.config.actionState })}
        >
          {node.config.actionState ? "ON" : "OFF"}
        </button>
      </div>

    </div>
  {:else}
    <div class="flex items-center gap-2" on:mousedown={stopProp}>
      <span class="font-retro text-xs text-gray-500 uppercase">Run For:</span>
      <input
        type="number"
        class="bg-desk border border-ink rounded px-2 py-1 text-sm font-retro w-16 focus:outline-none"
        value={node.config.duration}
        on:change={(e) => updateNodeConfig(node.id, { duration: Number((e.target as HTMLInputElement).value) })}
      />
      <span class="font-retro text-sm">sec</span>
    </div>
  {/if}
{/if}
