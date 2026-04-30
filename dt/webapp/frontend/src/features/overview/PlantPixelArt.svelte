<script lang="ts">
  /**
   * @fileoverview SVG-based pixel art representation of the plant.
   * Dynamically alters colors and animations based on the current health state.
   */


  import { PlantHealthState } from "$shared/types";
  import {
    animationClassForState,
    leafRotationForState,
    plantColorForState,
  } from "./plant_pixel_art_state";

  export let state: PlantHealthState;
</script>

<div class={`relative w-full h-full flex items-end justify-center ${animationClassForState(state)}`}>
  <svg viewBox="0 0 100 100" class="w-full h-full drop-shadow-md" preserveAspectRatio="xMidYMid meet">
    <g id="pot">
      <rect x="35" y="70" width="30" height="20" fill="#a8a29e" stroke="#1c1917" stroke-width="2" />
      <rect x="32" y="65" width="36" height="5" fill="#d6d3d1" stroke="#1c1917" stroke-width="2" />
      <rect x="36" y="66" width="28" height="3" fill={state === PlantHealthState.THIRSTY ? "#78350f" : "#44403c"} />
      {#if state === PlantHealthState.THIRSTY}
        <path d="M40 67 L45 68 M50 67 L55 68" stroke="#1c1917" stroke-width="0.5" />
      {/if}
    </g>

    <g id="plant" transform={`translate(0, ${state === PlantHealthState.THIRSTY ? 5 : 0})`}>
      <rect x="48" y="45" width="4" height="20" fill={plantColorForState(state)} stroke="#1c1917" stroke-width="1" />

      <g transform={`rotate(${-leafRotationForState(state)}, 48, 55)`}>
        <rect x="25" y="40" width="23" height="15" rx="2" fill={plantColorForState(state)} stroke="#1c1917" stroke-width="1" />
        <rect x="30" y="47" width="15" height="1" fill="#1c1917" opacity="0.2" />
      </g>

      <g transform={`rotate(${leafRotationForState(state)}, 52, 50)`}>
        <rect x="52" y="30" width="23" height="15" rx="2" fill={plantColorForState(state)} stroke="#1c1917" stroke-width="1" />
        <rect x="55" y="37" width="15" height="1" fill="#1c1917" opacity="0.2" />
      </g>

      <g transform={`rotate(${leafRotationForState(state) / 2}, 50, 45)`}>
        <rect x="40" y="15" width="20" height="30" rx="2" fill={plantColorForState(state)} stroke="#1c1917" stroke-width="1" />
        <rect x="50" y="20" width="1" height="20" fill="#1c1917" opacity="0.2" />
      </g>
    </g>

    {#if state === PlantHealthState.COLD}
      <g id="frost">
        <rect x="20" y="20" width="4" height="4" fill="#bae6fd" class="animate-pulse" />
        <rect x="80" y="30" width="4" height="4" fill="#bae6fd" class="animate-pulse" style="animation-delay: 0.5s;" />
        <rect x="30" y="60" width="3" height="3" fill="#bae6fd" class="animate-pulse" style="animation-delay: 1s;" />
      </g>
    {/if}

    {#if state === PlantHealthState.HOT}
      <g id="sweat">
        <path d="M65 25 Q70 20 75 25 T65 25" fill="#3b82f6" stroke="#1c1917" stroke-width="0.5" class="animate-bounce" />
        <path d="M30 35 Q35 30 40 35 T30 35" fill="#3b82f6" stroke="#1c1917" stroke-width="0.5" class="animate-bounce" style="animation-delay: 0.2s;" />
      </g>
    {/if}
  </svg>
</div>
