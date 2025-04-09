import { DataType, plantStore } from '../store.js'

/**  Subscribe all the element to the store to update content when data is received */
export function initPlantStatus() {
    // Update time element
    const update_time = document.getElementById('update-time')

    // Sensor data elements
    const stats_temperature = document.getElementById('temperature')
    const stats_humidity = document.getElementById('humidity')
    const stats_light = document.getElementById('light')

    plantStore.subscribe(DataType.TEMPERATURE, (data) => {
        // Round the temperature value to the nearest first decimal
        const temperature_value = data.value.toFixed(1)
        stats_temperature.textContent = `${temperature_value}°C`
    })

    plantStore.subscribe(DataType.HUMIDITY, (data) => {
        // Round the humidity value to the nearest integer
        const humidity_value = Math.round(data.value)
        stats_humidity.textContent = `${humidity_value}%`
    })

    plantStore.subscribe(DataType.LIGHT, (data) => {
        // Round the light value to the nearest integer
        const light_value = Math.round(data.value)
        stats_light.textContent = `${light_value}lx`
    })

    plantStore.subscribe(DataType.TIME, (data) => {
        // Transform the timestamp to a human-readable format
        console.log(data.time)
        const date = new Date(data.time)
        const hours = date.getHours().toString().padStart(2, '0')
        const minutes = date.getMinutes().toString().padStart(2, '0')
        const formatted_time = `${hours}:${minutes}`
        update_time.textContent = formatted_time
    })

    plantStore.subscribe('connection_status', (data) => {
        console.log('Connection status updated')
        updateConnectionStatus(data.connected)
    })

    plantStore.subscribe(DataType.ALERTS, (data) => {
        console.log('Alerts updated')
        updateAlerts(data)
    })

    plantStore.subscribe(DataType.HEALTH_STATUS, (data) => {
        console.log('Health status updated')
        updateHealthStatus(data)
    })
}

/**
 * Updates the connection status. It will display a green indicator if connected, red otherwise
 * @param {Boolean} isConnected - Wether the connection is established or not
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
 * Updates the alerts list with the new updated one
 * @param {Obj} alerts - The list of alerts to display and alert is typically { id: string, message: string, time: number }
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
 * Updates the health status elements with the new health data
 * @param {Obj} healthData - The health status data { status: string, details: string }
 */
function updateHealthStatus(healthData) {
    // Health status elements
    const healthStatus = document.getElementById('health-status')
    const healthDetails = document.getElementById('health-details')

    healthStatus.textContent = healthData.status
    healthDetails.textContent = healthData.details
}
