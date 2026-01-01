/**
 * @file Manages the "Plant Status" component of the dashboard.
 * This includes updating real-time sensor readings, connection status, alerts, and health status.
 */
import { DataType, plantStore } from '../store.js'


/**
 * Initializes the plant status component by subscribing to the central data store (`plantStore`).
 * It sets up listeners for temperature, humidity, light, time, connection status, alerts,
 * and health status. When new data is received for any of these, it calls the appropriate
 * function to update the UI.
 */
export function initPlantStatus() {
    // Update time element
    const update_time = document.getElementById('update-time')

    // Sensor data elements
    const stats_temperature = document.getElementById('temperature')
    const stats_humidity = document.getElementById('humidity')
    const stats_light = document.getElementById('light')

    // Subscribe to temperature updates
    plantStore.subscribe(DataType.TEMPERATURE, (data) => {
        const value = Number(data?.value)
        if (Number.isFinite(value)) {
            // Round the temperature value to the nearest first decimal
            const temperature_value = value.toFixed(1)
            stats_temperature.textContent = `${temperature_value}°C`
        } else {
            stats_temperature.textContent = '—'
        }
    })

    // Subscribe to humidity updates
    plantStore.subscribe(DataType.HUMIDITY, (data) => {
        const value = Number(data?.value)
        if (Number.isFinite(value)) {
            // Round the humidity value to the nearest integer
            const humidity_value = Math.round(value)
            stats_humidity.textContent = `${humidity_value}%`
        } else {
            stats_humidity.textContent = '—'
        }
    })

    // Subscribe to light intensity updates
    plantStore.subscribe(DataType.LIGHT, (data) => {
        const value = Number(data?.value)
        if (Number.isFinite(value)) {
            // Round the light value to the nearest integer
            const light_value = Math.round(value)
            stats_light.textContent = `${light_value}lx`
        } else {
            stats_light.textContent = '—'
        }
    })

    // Subscribe to time updates to show the last update time
    plantStore.subscribe(DataType.TIME, (data) => {
        // Transform the timestamp to a human-readable format
        console.log(data.time)
        const date = new Date(data.time)
        const hours = date.getHours().toString().padStart(2, '0')
        const minutes = date.getMinutes().toString().padStart(2, '0')
        const formatted_time = `${hours}:${minutes}`
        update_time.textContent = formatted_time
    })

    // Subscribe to connection status updates
    plantStore.subscribe('connection_status', (data) => {
        console.log('Connection status updated')
        updateConnectionStatus(data.connected)
    })

    // Subscribe to alert updates
    plantStore.subscribe(DataType.ALERTS, (data) => {
        console.log('Alerts updated')
        updateAlerts(data)
    })

    // Subscribe to health status updates
    plantStore.subscribe(DataType.HEALTH_STATUS, (data) => {
        console.log('Health status updated')
        updateHealthStatus(data)
    })
}


/**
 * Updates the UI to reflect the current connection status to the backend.
 * It changes the color of a status indicator and updates the accompanying text.
 * @param {boolean} isConnected - Whether the application is connected to the backend.
 */
function updateConnectionStatus(isConnected) {
    const statusText = document.getElementById('connection-status')
    const statusIndicator = document.getElementById('status-indicator')

    if (isConnected) {
        statusText.textContent = 'Connected'
        statusIndicator.className = 'status-indicator connected'
    } else {
        statusText.textContent = 'Disconnected'
        statusIndicator.className = 'status-indicator disconnected'
    }
}

/**
 * Updates the alerts list in the UI.
 * It clears the existing list and populates it with the new alerts provided. It also updates the alert count badge.
 * @param {Array<Object>} alerts - An array of alert objects to display. Each object should have `message` and `time` properties.
 */
function updateAlerts(alerts) {
    const alertsList = document.getElementById('alerts-list')
    const alertsCount = document.getElementById('alert-count')

    alertsCount.textContent = alerts.length

    // Clear the current alerts list
    alertsList.innerHTML = ''

    // Populate the alerts list with the new alerts
    alerts.forEach((alert) => {
        const alertItem = document.createElement('li')
        const time = new Date(alert.time)
        const fromattedTime = `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}`
        alertItem.textContent = `${alert.message} - ${fromattedTime}`
        alertsList.appendChild(alertItem)
    })
}


/**
 * Updates the health status and details displayed in the UI.
 * @param {Object} healthData - An object containing the health status data.
 * @param {string} healthData.status - The current health status (e.g., "Good", "Warning").
 * @param {string} healthData.details - A more detailed description of the health status.
 */
function updateHealthStatus(healthData) {
    // Health status elements
    const healthStatus = document.getElementById('health-status')
    const healthDetails = document.getElementById('health-details')

    healthStatus.textContent = healthData.status
    healthDetails.textContent = healthData.details
}
