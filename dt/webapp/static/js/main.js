import { initRealTimeMonitoring } from './components/realtime_monitoring.js'
import { initPlantStatus } from './components/plant_status.js'
import { initiParameterControls } from './components/parameter_controls.js'

document.addEventListener('DOMContentLoaded', () => {
    console.log('Hello')
    initializeComponents()
})

function initializeComponents() {
    initRealTimeMonitoring()
    initPlantStatus()
    initiParameterControls()
}
