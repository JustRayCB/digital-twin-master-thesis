import { DataType, plantStore } from '../store.js'

export function initPlantStatus() {
    const update_time = document.getElementById('update-time')
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
        const date = new Date(data.time * 1000)
        const hours = date.getHours().toString().padStart(2, '0')
        const minutes = date.getMinutes().toString().padStart(2, '0')
        const formatted_time = `${hours}:${minutes}`
        update_time.textContent = formatted_time
    })

    plantStore.subscribe('connection_status', (data) => {
        console.log('Connection status updated')
        updateConnectionStatus(data.connected)
    })
}

function updateConnectionStatus(isConnected) {
    const statusText = document.getElementById('connection-status')
    const statusIndicator = document.getElementById('status-indicator')

    if (isConnected) {
        statusText.textContent = 'Connected'
        statusIndicator.className = 'status-indicator connected'
    } else {
        statusText.textContent = 'Disconnected'
        statusIndicator.className = 'status-indicator disconnected'

        // Optionally add an alert when disconnection occurs
        // addAlert('Lost connection to plant monitoring system')
    }
}
