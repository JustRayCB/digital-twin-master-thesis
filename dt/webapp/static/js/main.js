/**
 * @file Main entry point for the web application's JavaScript.
 * This script initializes all the major UI components after the DOM has fully loaded.
 */ 
import { initRealTimeMonitoring } from './components/realtime_monitoring.js'
import { initPlantStatus } from './components/plant_status.js'
import { initiParameterControls } from './components/parameter_controls.js'

document.addEventListener('DOMContentLoaded', () => {
    console.log('Hello')
    initializeComponents()
})

/**
 * Initializes all the main components of the dashboard.
 * This function calls the initialization logic for the real-time monitoring charts,
 * the plant status display, and the parameter controls.
 */
function initializeComponents() {
    initRealTimeMonitoring()
    initPlantStatus()
    initiParameterControls()
}
