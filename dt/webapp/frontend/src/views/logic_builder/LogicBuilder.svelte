<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { get } from "svelte/store";

  import { navigate, routineDraft } from "../../app_state";
  import NodeContent from "./NodeContent.svelte";
  import {
    createLogicBuilderModel,
    getConnectorPos,
    logicActionPalette,
    renderPath,
    triggerPalette,
  } from "./logic_builder_model";

  export let onBack: () => void = () => navigate("OVERVIEW");

  const model = createLogicBuilderModel();
  const { nodes, edges, viewport, connectingSourceId, mousePos, routineName, routineId } = model;

  let canvasElement: HTMLDivElement | null = null;

  onMount(() => {
    window.addEventListener("mousemove", model.handleWindowMouseMove);
    window.addEventListener("mouseup", model.handleWindowMouseUp);
    model.actions.loadActuators().finally(() => {
      model.actions.loadRoutine(get(routineDraft));
    });
  });

  onDestroy(() => {
    window.removeEventListener("mousemove", model.handleWindowMouseMove);
    window.removeEventListener("mouseup", model.handleWindowMouseUp);
  });

  function zoomIn() {
    model.updateViewport((current) => ({ ...current, zoom: Math.min(current.zoom + 0.1, 2) }));
  }

  function zoomOut() {
    model.updateViewport((current) => ({ ...current, zoom: Math.max(current.zoom - 0.1, 0.5) }));
  }

  function resetView() {
    model.setViewportValue({ x: 0, y: 0, zoom: 1 });
  }

  async function saveRoutine() {
    try {
      await model.actions.saveRoutine();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to save routine";
      alert(message);
    }
  }

  $: model.setCanvasElement(canvasElement);
</script>

<div class="flex flex-col h-screen bg-desk text-ink font-sans selection:bg-cozy-lavender selection:text-ink overflow-hidden">
  <header class="bg-cozy-white border-b-4 border-ink px-6 py-4 sticky top-0 z-50 shadow-sm">
    <div class="max-w-[1600px] mx-auto flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-6">
        <button on:click={onBack} class="flex items-center gap-3 group hover:bg-gray-50 rounded-lg pr-4 -ml-2 p-2 transition-colors">
          <div class="size-10 bg-white border-2 border-ink flex items-center justify-center shadow-hard-sm rounded-lg group-hover:-translate-x-1 transition-transform">
            <span class="material-symbols-outlined text-ink text-2xl">arrow_back</span>
          </div>
          <span class="font-retro text-xl tracking-wider text-ink/70 group-hover:text-ink">BACK TO OVERVIEW</span>
        </button>
        <div class="h-8 w-0.5 bg-ink/20 hidden sm:block"></div>
        <div class="flex flex-col">
          <div class="flex items-center gap-3">
            <h2 class="font-retro text-3xl text-ink leading-none tracking-wide">NEW RULE EDITOR</h2>
            <span class="px-2 py-0.5 bg-cozy-yellow border border-ink text-[10px] font-bold uppercase tracking-widest rounded-full">
              {$routineId ? "Saved" : "Unsaved"}
            </span>
          </div>
          <div class="flex items-center gap-2 mt-1">
            <span class="text-xs uppercase tracking-widest text-gray-500 font-bold">Editing:</span>
            <input
              class="bg-transparent border-b border-ink/30 text-xs uppercase tracking-widest text-gray-700 font-bold focus:outline-none focus:border-ink"
              value={$routineName}
              on:input={(e) => routineName.set((e.target as HTMLInputElement).value)}
            />
          </div>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <button
          on:click={model.actions.clearCanvas}
          class="px-5 py-2 bg-white text-ink border-2 border-ink rounded-lg font-retro text-xl tracking-wide shadow-hard-sm hover:translate-y-0.5 hover:shadow-none transition-all flex items-center gap-2 opacity-60 hover:opacity-100"
        >
          <span class="material-symbols-outlined text-lg">delete</span>
          CLEAR
        </button>
        <button on:click={saveRoutine} class="px-6 py-2 bg-cozy-mint text-ink border-2 border-ink rounded-lg font-retro text-xl tracking-wide shadow-hard-sm hover:-translate-y-1 hover:shadow-hard transition-all flex items-center gap-2">
          <span class="material-symbols-outlined text-lg">save</span>
          SAVE RULE
        </button>
      </div>
    </div>
  </header>

  <main class="flex-1 flex overflow-hidden max-w-[1600px] mx-auto w-full min-h-0">
    <aside class="w-80 bg-cozy-white border-r-4 border-ink p-6 overflow-y-auto z-20 flex flex-col gap-6 shadow-[4px_0_0_0_rgba(0,0,0,0.05)] shrink-0">
      <div>
        <h3 class="font-retro text-2xl text-ink border-b-2 border-ink pb-2 mb-4 flex items-center gap-2 text-ink/80">
          <span class="material-symbols-outlined">sensors</span>
          TRIGGERS
        </h3>
        <div class="flex flex-col gap-3">
          {#each triggerPalette as item (item.name)}
            <div
              draggable="true"
              on:dragstart={(e) => model.handlers.handleDragStart(e, item.type, item.name, item.bg, item.icon, item.inputs, item.outputs)}
              class={`${item.bg} border-2 border-ink rounded-lg p-3 shadow-hard-sm hover:translate-x-1 cursor-grab active:cursor-grabbing transition-transform group`}
            >
              <div class="flex items-center gap-3">
                <div class="size-8 bg-white border border-ink rounded flex items-center justify-center pointer-events-none">
                  <span class="material-symbols-outlined text-sm">{item.icon}</span>
                </div>
                <div class="pointer-events-none">
                  <div class="font-bold font-retro text-lg leading-none">{item.name}</div>
                  <div class="text-xs font-sans opacity-70 mt-0.5">{item.desc}</div>
                </div>
                <span class="material-symbols-outlined ml-auto opacity-0 group-hover:opacity-50 pointer-events-none">drag_indicator</span>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <div>
        <h3 class="font-retro text-2xl text-ink border-b-2 border-ink pb-2 mb-4 flex items-center gap-2 text-ink/80">
          <span class="material-symbols-outlined">bolt</span>
          LOGIC & ACTIONS
        </h3>
        <div class="flex flex-col gap-3">
          {#each logicActionPalette as item (item.name)}
            <div
              draggable="true"
              on:dragstart={(e) => model.handlers.handleDragStart(e, item.type, item.name, item.bg, item.icon, item.inputs, item.outputs)}
              class={`${item.bg} border-2 border-ink rounded-lg p-3 shadow-hard-sm hover:translate-x-1 cursor-grab active:cursor-grabbing transition-transform group`}
            >
              <div class="flex items-center gap-3 pointer-events-none">
                <div class={`size-8 ${item.iconBg || "bg-white"} border border-ink rounded flex items-center justify-center`}>
                  <span class="material-symbols-outlined text-sm">{item.icon}</span>
                </div>
                <div>
                  <div class="font-bold font-retro text-lg leading-none">
                    {item.name}
                  </div>
                  <div class="text-xs font-sans opacity-70 mt-0.5">{item.desc}</div>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    </aside>

    <section
      class="flex-1 relative bg-desk overflow-hidden cursor-crosshair active:cursor-grabbing"
      on:mousedown={model.handlers.startPan}
      on:wheel={model.handlers.handleWheel}
      on:drop={model.handlers.handleDrop}
      on:dragover={model.handlers.handleDragOver}
      on:click={model.handlers.handleCanvasClick}
    >
      <div class="absolute inset-0 bg-grid-pattern bg-grid-sm opacity-20 pointer-events-none"></div>

      <div class="absolute top-6 left-6 right-6 flex justify-between items-start pointer-events-none z-30">
        <div class="bg-white border-2 border-ink rounded-lg shadow-hard-sm pointer-events-auto flex">
          <button on:click={zoomIn} class="px-3 py-2 hover:bg-gray-100 transition-colors border-r-2 border-ink flex items-center" title="Zoom In">
            <span class="material-symbols-outlined">add</span>
          </button>
          <button on:click={zoomOut} class="px-3 py-2 hover:bg-gray-100 transition-colors border-r-2 border-ink flex items-center" title="Zoom Out">
            <span class="material-symbols-outlined">remove</span>
          </button>
          <button on:click={resetView} class="px-3 py-2 hover:bg-gray-100 transition-colors flex items-center" title="Reset View">
            <span class="material-symbols-outlined">fit_screen</span>
          </button>
        </div>

        <button class="bg-pop-red text-white border-2 border-ink px-8 py-3 rounded-lg shadow-hard pointer-events-auto font-retro text-2xl tracking-wide hover:-translate-y-1 hover:shadow-hard-lg transition-all flex items-center gap-3 group">
          <span class="material-symbols-outlined text-3xl group-hover:animate-pulse">play_circle</span>
          TEST LOGIC
        </button>
      </div>

      <div
        bind:this={canvasElement}
        class="absolute inset-0 origin-top-left transition-transform duration-75 ease-out"
        style:transform={`translate(${$viewport.x}px, ${$viewport.y}px) scale(${$viewport.zoom})`}
      >
        <svg class="absolute top-0 left-0 overflow-visible pointer-events-none z-0" style="width: 1px; height: 1px;">
          {#each $edges as edge (edge.id)}
            {@const source = $nodes.find((n) => n.id === edge.source)}
            {@const target = $nodes.find((n) => n.id === edge.target)}
            {#if source && target}
              {@const start = getConnectorPos(source, "output")}
              {@const end = getConnectorPos(target, "input")}
              <path
                d={renderPath(start.x, start.y, end.x, end.y)}
                fill="none"
                stroke="#1c1917"
                stroke-width="3"
                marker-end="url(#arrowhead)"
              />
            {/if}
          {/each}

          {#if $connectingSourceId}
            {@const source = $nodes.find((n) => n.id === $connectingSourceId)}
            {#if source}
              {@const start = getConnectorPos(source, "output")}
              <path
                d={renderPath(start.x, start.y, $mousePos.x, $mousePos.y)}
                fill="none"
                stroke="#1c1917"
                stroke-width="3"
                stroke-dasharray="5,5"
                class="animate-pulse"
              />
            {/if}
          {/if}

          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#1c1917" />
            </marker>
          </defs>
        </svg>

        {#each $nodes as node (node.id)}
          <div
            class={`absolute ${node.bgClass} border-2 border-ink rounded-xl shadow-hard-lg z-10 group flex flex-col`}
            style={`left: ${node.x}px; top: ${node.y}px; width: 256px; cursor: grab;`}
          >
            <div
              on:mousedown={(e) => model.handlers.startDragNode(e, node.id)}
              class="bg-white/50 border-b-2 border-ink px-3 py-2 flex justify-between items-center rounded-t-xl cursor-grab active:cursor-grabbing"
            >
              <div class="flex items-center gap-2 pointer-events-none">
                <span class="material-symbols-outlined text-sm">{node.icon}</span>
                <span class="font-retro font-bold text-lg">{node.label}</span>
              </div>
              <span
                on:click={(e) => {
                  e.stopPropagation();
                  model.actions.deleteNode(node.id);
                }}
                class="material-symbols-outlined text-ink/50 text-sm cursor-pointer hover:text-red-500 hover:scale-110 transition-transform"
              >
                close
              </span>
            </div>

            <div class="p-3 bg-white m-1 rounded-lg border border-ink/10 flex-1 flex flex-col justify-center">
              <NodeContent node={node} updateNodeConfig={model.actions.updateNodeConfig} />
            </div>

            {#if node.inputs}
              <div
                class="card-connector left hover:scale-125 transition-transform"
                title="Input"
                on:click={(e) => model.handlers.handleConnectEnd(e, node.id)}
              ></div>
            {/if}
            {#if node.outputs}
              <div
                class={[
                  "card-connector right hover:scale-125 transition-transform",
                  $connectingSourceId === node.id ? "bg-pop-red" : "",
                ].join(" ")}
                title="Output"
                on:click={(e) => model.handlers.handleConnectStart(e, node.id)}
              ></div>
            {/if}
          </div>
        {/each}
      </div>

      {#if $nodes.length === 0}
        <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div class="bg-white/80 border-2 border-ink p-6 rounded-xl text-center shadow-hard backdrop-blur-sm">
            <span class="material-symbols-outlined text-4xl text-gray-400 mb-2">drag_indicator</span>
            <p class="font-retro text-2xl text-ink">Drag nodes from the sidebar</p>
            <p class="font-sans text-gray-500">to start building your logic flow</p>
          </div>
        </div>
      {/if}
    </section>
  </main>
</div>
