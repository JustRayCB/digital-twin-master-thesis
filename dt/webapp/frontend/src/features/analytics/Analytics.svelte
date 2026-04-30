<script lang="ts">
    /**
     * @fileoverview Main Analytics view component.
     * Renders a dashboard of time-series charts for various telemetry topics, along with correlation analysis.
     */

    import { onDestroy, onMount, tick } from 'svelte'

    import { processedTopics, type ProcessedTopicName } from '$shared/realtime'
    import {
        analyticsStore,
        type AnalyticsSeriesKey,
        type AnalyticsTimeView,
        type CorrelationSummary,
    } from './analytics.store'

    /** Destructured store values for reactive UI updates */
    const { correlationMode, currentTimeView, errorState, loadingState, visibleSeries } = analyticsStore

    /** Available view modes for the analytics dashboard */
    const viewModes = ['trends', 'correlation'] as const
    /** Supported time ranges for data aggregation */
    const timeViews: AnalyticsTimeView[] = ['day', 'week', 'month']
    /** Telemetry series definitions with their display labels */
    const series: Array<{ key: AnalyticsSeriesKey; label: string }> = [
        { key: 'value', label: 'processed' },
        { key: 'raw_value', label: 'raw' },
        { key: 'calibrated_value', label: 'calibrated' },
        { key: 'normalized_value', label: 'normalized' },
        { key: 'forecast', label: 'forecast' },
    ]

    type CorrelationSensor = {
        id: string
        label: string
        topic: ProcessedTopicName
    }

    type CorrelationPair = {
        id: string
        label: string
        sensor1: ProcessedTopicName
        sensor2: ProcessedTopicName
    }

    const correlationSensors: CorrelationSensor[] = [
        { id: 'temperature', label: 'Temperature', topic: processedTopics.temperature },
        { id: 'humidity', label: 'Humidity', topic: processedTopics.humidity },
        { id: 'soil-moisture', label: 'Soil Moisture', topic: processedTopics.soilMoisture },
        { id: 'light-intensity', label: 'Light', topic: processedTopics.lightIntensity },
        { id: 'green-ratio', label: 'Green Ratio', topic: processedTopics.greenRatio },
        { id: 'leaf-count', label: 'Leaf Count', topic: processedTopics.leafCount },
        { id: 'plant-height', label: 'Plant Height', topic: processedTopics.plantHeight },
    ]

    function buildCorrelationPairs(sensors: CorrelationSensor[]): CorrelationPair[] {
        const pairs: CorrelationPair[] = []
        for (let first = 0; first < sensors.length; first += 1) {
            for (let second = first + 1; second < sensors.length; second += 1) {
                const sensor1 = sensors[first]
                const sensor2 = sensors[second]
                pairs.push({
                    id: `${sensor1.id}-${sensor2.id}`,
                    label: `${sensor1.label} ↔ ${sensor2.label}`,
                    sensor1: sensor1.topic,
                    sensor2: sensor2.topic,
                })
            }
        }
        return pairs
    }

    const correlationPairs = buildCorrelationPairs(correlationSensors)

    const correlationMethods = ['pearson', 'spearman'] as const

    let selectedCorrelationPairId = correlationPairs[0].id
    let selectedCorrelationMethod: (typeof correlationMethods)[number] = 'pearson'

    let temperatureChart: HTMLElement | null = null
    let humidityChart: HTMLElement | null = null
    let soilMoistureChart: HTMLElement | null = null
    let lightIntensityChart: HTMLElement | null = null
    let greenRatioChart: HTMLElement | null = null
    let leafCountChart: HTMLElement | null = null
    let plantHeightChart: HTMLElement | null = null
    let selectedCorrelationChart: HTMLElement | null = null
    let correlationMatrixChart: HTMLElement | null = null
    let correlationSummary: CorrelationSummary | null = null

    let mounted = false
    let wasCorrelationMode = false

    $: if ($correlationMode) {
        selectedCorrelationPairId
        selectedCorrelationMethod
        void updateCorrelationCharts()
    }

    $: if (mounted && $correlationMode) {
        wasCorrelationMode = true
    }

    $: if (mounted && wasCorrelationMode && !$correlationMode) {
        wasCorrelationMode = false
        void initializeTrendCharts()
    }

    function registerTrendCharts(): void {
        analyticsStore.initializeCharts({
            [processedTopics.temperature]: temperatureChart,
            [processedTopics.humidity]: humidityChart,
            [processedTopics.soilMoisture]: soilMoistureChart,
            [processedTopics.lightIntensity]: lightIntensityChart,
            [processedTopics.greenRatio]: greenRatioChart,
            [processedTopics.leafCount]: leafCountChart,
            [processedTopics.plantHeight]: plantHeightChart,
        })
    }

    async function initializeTrendCharts(): Promise<void> {
        await tick()
        registerTrendCharts()
    }

    function setViewMode(mode: (typeof viewModes)[number]): void {
        if (mode === 'correlation') {
            analyticsStore.enterCorrelationMode(['temperature', 'humidity'])
            return
        }

        analyticsStore.exitCorrelationMode()
    }

    async function setTimeView(view: AnalyticsTimeView): Promise<void> {
        await analyticsStore.setTimeView(view)
        if ($correlationMode) {
            await updateCorrelationCharts()
        }
    }


    function getSelectedCorrelationPair() {
        return (
            correlationPairs.find((pair) => pair.id === selectedCorrelationPairId) ??
            correlationPairs[0]
        )
    }

    function getTimeRangeLabel(view: AnalyticsTimeView): string {
        if (view === 'day') {
            return 'last 24 hours, raw readings'
        }
        if (view === 'week') {
            return 'last 7 days, hourly aggregates'
        }
        return 'last 30 days, hourly aggregates'
    }

    async function updateCorrelationCharts(): Promise<void> {
        await tick()

        if (
            !selectedCorrelationChart ||
            !correlationMatrixChart
        ) {
            return
        }

        const selectedPair = getSelectedCorrelationPair()

        correlationSummary = await analyticsStore.createScatterPlot(
            'selected-correlation',
            selectedCorrelationChart,
            selectedPair.sensor1,
            selectedPair.sensor2,
            selectedCorrelationMethod
        )
        await analyticsStore.createCorrelationMatrix(
            'correlation-matrix',
            correlationMatrixChart,
            [selectedPair.sensor1, selectedPair.sensor2],
            selectedCorrelationMethod
        )
    }

    onMount(() => {
        mounted = true
        registerTrendCharts()

        void analyticsStore.initialize()
    })

    onDestroy(() => {
        analyticsStore.destroy()
    })
</script>

<section class="flex flex-col h-full animate-in fade-in duration-500">
    <header class="flex flex-col gap-2 mb-5">
        <h1 class="font-retro text-6xl text-ink">Sensor Trends</h1>
        <p class="text-gray-500 mt-2 font-sans font-medium tracking-wide border-l-4 border-cozy-lavender pl-3">
            Historical data for Basil Study
        </p>
    </header>

    <div class="bg-cozy-white p-4 border-2 border-ink rounded-xl shadow-hard-sm mb-5">
        <div class="grid grid-cols-1 xl:grid-cols-[auto_1fr] gap-4">
            <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Analysis</div>
            <div class="flex flex-wrap gap-2" role="group" aria-label="View mode controls">
                {#each viewModes as mode (mode)}
                    <label class="cursor-pointer select-none">
                        <input
                            type="radio"
                            name="view-mode"
                            value={mode}
                            checked={mode === 'correlation' ? $correlationMode : !$correlationMode}
                            on:change={() => {
                                setViewMode(mode)
                            }}
                            class="peer sr-only"
                        />
                        <span class="block px-4 py-1.5 rounded-lg font-retro text-lg uppercase transition-all border-2 border-transparent peer-checked:bg-desk peer-checked:text-ink peer-checked:border-ink text-gray-400 hover:text-gray-600">{mode}</span>
                    </label>
                {/each}
            </div>

            <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Time range</div>
            <div class="flex flex-wrap gap-2" role="group" aria-label="Time view controls">
                {#each timeViews as view (view)}
                    <label class="cursor-pointer select-none">
                        <input
                            type="radio"
                            name="time-view"
                            value={view}
                            checked={$currentTimeView === view}
                            on:change={() => {
                                void setTimeView(view)
                            }}
                            class="peer sr-only"
                        />
                        <span class="block px-4 py-1.5 rounded-lg font-retro text-lg uppercase transition-all border-2 border-transparent peer-checked:bg-cozy-peach peer-checked:text-ink peer-checked:border-ink text-gray-400 hover:text-gray-600">{view}</span>
                    </label>
                {/each}
            </div>

            <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Data layer</div>
            <div class="flex flex-wrap gap-2" role="group" aria-label="Series visibility controls">
                {#each series as item (item.key)}
                    <label class="cursor-pointer select-none">
                        <input
                            type="checkbox"
                            name="series-toggle"
                            value={item.key}
                            checked={$visibleSeries[item.key]}
                            on:change={(event) =>
                                analyticsStore.toggleSeriesVisibility(
                                    item.key,
                                    (event.currentTarget as HTMLInputElement).checked
                                )}
                            class="peer sr-only"
                        />
                        <span class="block px-4 py-1.5 rounded-lg font-retro text-lg uppercase transition-all border-2 peer-checked:bg-desk peer-checked:text-ink peer-checked:border-ink bg-white text-gray-400 border-transparent hover:text-gray-600">{item.label}</span>
                    </label>
                {/each}
            </div>

            {#if $correlationMode}
                <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Pair</div>
                <div class="flex items-center gap-3">
                    <select
                        class="bg-white border-2 border-ink rounded-lg px-3 py-2 font-retro text-base"
                        bind:value={selectedCorrelationPairId}
                    >
                        {#each correlationPairs as pair (pair.id)}
                            <option value={pair.id}>{pair.label}</option>
                        {/each}
                    </select>
                </div>

                <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Method</div>
                <div class="flex items-center gap-3">
                    <select
                        class="bg-white border-2 border-ink rounded-lg px-3 py-2 font-retro text-base uppercase"
                        bind:value={selectedCorrelationMethod}
                    >
                        {#each correlationMethods as method (method)}
                            <option value={method}>{method}</option>
                        {/each}
                    </select>
                </div>
            {/if}
        </div>
    </div>

    {#if $errorState}
        <div
            class="mb-5 rounded-xl border-2 border-ink bg-cozy-peach px-4 py-3 shadow-hard-sm"
            role="alert"
        >
            <p class="font-retro text-lg uppercase text-ink">
                {$loadingState === 'partial'
                    ? 'Historical data refresh failed. Showing cached data and live updates.'
                    : 'Historical data failed to load. Live updates may still continue.'}
            </p>
            <p class="mt-2 font-sans text-sm text-gray-700">{$errorState.message}</p>
        </div>
    {/if}

    {#if $correlationMode}
        <div class="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative min-h-[760px]">
                <div class="mb-4 flex flex-col gap-1">
                    <h2 class="font-retro text-3xl text-ink">Selected Pair</h2>
                    <p class="font-sans text-sm text-gray-600">{getSelectedCorrelationPair().label} over {getTimeRangeLabel($currentTimeView)}</p>
                </div>
                <div class="min-h-[640px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white">
                    <div bind:this={selectedCorrelationChart} style="width: 100%; height: 640px; min-height: 640px;"></div>
                </div>
            </div>
            <aside class="bg-desk border-2 border-ink shadow-hard rounded-xl p-6 min-h-[460px]">
                <h2 class="font-retro text-3xl text-ink">Correlation Readout</h2>
                {#if correlationSummary}
                    <div class="mt-5 space-y-4 font-sans text-sm text-gray-700">
                        <div>
                            <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Relationship</div>
                            <p class="mt-1 text-2xl font-retro text-ink">
                                {correlationSummary.strength} {correlationSummary.direction}
                            </p>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div class="rounded-lg border-2 border-ink bg-white p-3">
                                <div class="text-xs font-bold uppercase tracking-wider text-gray-500">r</div>
                                <div class="mt-1 font-retro text-3xl text-ink">{correlationSummary.coefficient.toFixed(3)}</div>
                            </div>
                            <div class="rounded-lg border-2 border-ink bg-white p-3">
                                <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Matched samples</div>
                                <div class="mt-1 font-retro text-3xl text-ink">{correlationSummary.sampleCount}</div>
                            </div>
                        </div>
                        <p>
                            {correlationSummary.method === 'spearman' ? 'Spearman ranks the readings first, so it focuses on monotonic movement rather than exact linear scaling.' : 'Pearson uses the plotted values directly, so it measures linear movement between the two sensors.'}
                        </p>
                        <p>
                            Data basis: {getTimeRangeLabel($currentTimeView)}. The matrix uses the same method and time range for every pair.
                        </p>
                        <p>
                            Matched samples are pairs of values recorded at the same timestamp; readings without a timestamp match are not plotted or used for r.
                        </p>
                    </div>
                {:else}
                    <p class="mt-5 font-sans text-sm text-gray-600">Choose a pair to render correlation details.</p>
                {/if}
            </aside>
            <div class="xl:col-span-2 bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[520px]">
                <div class="mb-4 flex flex-col gap-1">
                    <h2 class="font-retro text-3xl text-ink">All Pair Matrix</h2>
                    <p class="font-sans text-sm text-gray-600">Every sensor pair using {selectedCorrelationMethod} correlation over {getTimeRangeLabel($currentTimeView)}.</p>
                </div>
                <div class="h-full min-h-[460px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={correlationMatrixChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
        </div>
    {:else}
        <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px]">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={temperatureChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px]">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={humidityChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px]">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={lightIntensityChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px]">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={soilMoistureChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px]">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={greenRatioChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px]">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={leafCountChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
            <div class="bg-cozy-white border-2 border-ink shadow-hard rounded-xl p-6 relative overflow-hidden min-h-[420px] lg:col-span-2">
                <div class="h-full min-h-[360px] w-full chart-grid border-2 border-ink/10 rounded-lg relative bg-white overflow-hidden">
                    <div bind:this={plantHeightChart} style="width: 100%; height: 100%;"></div>
                </div>
            </div>
        </div>
    {/if}
</section>
