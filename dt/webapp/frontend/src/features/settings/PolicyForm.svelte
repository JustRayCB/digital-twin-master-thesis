<script lang="ts">
  import type { ActuatorConfig } from "$shared/types";
  import { updatePolicy } from "./settings.store";

  export let config: ActuatorConfig;
  export let path: string[];
  export let title: string = "";
  export let description: string = "";

  function handleChange(field: keyof ActuatorConfig, value: any) {
    updatePolicy([...path, field], value);
  }

  function toggleCommand(command: string) {
    const current = config.allowed_commands || [];
    const next = current.includes(command)
      ? current.filter((c) => c !== command)
      : [...current, command];
    handleChange("allowed_commands", next);
  }
</script>

<div class="bg-white/50 border-2 border-ink rounded-lg p-4 space-y-4">
  {#if title}
    <div class="border-b-2 border-ink pb-2">
      <h3 class="font-retro text-lg text-ink uppercase">{title}</h3>
      {#if description}
        <p class="text-xs text-gray-500 font-sans italic">{description}</p>
      {/if}
    </div>
  {/if}

  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="space-y-1">
      <label class="block font-retro text-xs text-ink uppercase" for="duration">Max Duration (s)</label>
      <input
        id="duration"
        type="number"
        value={config.max_duration_seconds}
        on:input={(e) => handleChange("max_duration_seconds", Number(e.currentTarget.value) || null)}
        class="w-full bg-desk border-2 border-ink rounded p-2 text-sm focus:ring-2 focus:ring-cozy-mint outline-none"
        placeholder="No limit"
      />
    </div>

    <div class="space-y-1">
      <label class="block font-retro text-xs text-ink uppercase" for="cooldown">Min Cooldown (s)</label>
      <input
        id="cooldown"
        type="number"
        value={config.min_cooldown_seconds}
        on:input={(e) => handleChange("min_cooldown_seconds", Number(e.currentTarget.value) || null)}
        class="w-full bg-desk border-2 border-ink rounded p-2 text-sm focus:ring-2 focus:ring-cozy-mint outline-none"
        placeholder="No cooldown"
      />
    </div>
  </div>

  <div class="flex items-center gap-3">
    <button
      on:click={() => handleChange("allow_overlap", !config.allow_overlap)}
      aria-label="Toggle allow overlapping actions"
      aria-pressed={config.allow_overlap}
      class={[
        "w-12 h-6 rounded-full border-2 border-ink relative transition-colors",
        config.allow_overlap ? "bg-cozy-mint" : "bg-pop-red/20"
      ].join(' ')}
    >
      <div
        class={[
          "absolute top-0.5 w-4 h-4 rounded-full border-2 border-ink bg-white transition-all",
          config.allow_overlap ? "left-6" : "left-0.5"
        ].join(' ')}
      ></div>
    </button>
    <span class="font-retro text-xs text-ink uppercase">Allow overlapping actions</span>
  </div>

  <div class="space-y-2">
    <span class="block font-retro text-xs text-ink uppercase">Allowed Commands</span>
    <div class="flex flex-wrap gap-2">
      {#each ["ON", "OFF"] as cmd}
        <button
          on:click={() => toggleCommand(cmd)}
          class={[
            "px-3 py-1 rounded border-2 border-ink font-retro text-xs transition-all",
            config.allowed_commands?.includes(cmd) 
              ? "bg-cozy-mint shadow-hard-sm translate-y-[-1px]" 
              : "bg-white opacity-50 grayscale"
          ].join(' ')}
        >
          {cmd}
        </button>
      {/each}
    </div>
  </div>
</div>
