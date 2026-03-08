/**
 * @file Manages the parameter controls component of the dashboard.
 * This includes handling user interactions with sliders for temperature, humidity, and soil moisture,
 * as well as the simulation control button.
 */

/**
 * Initializes the event listeners for the parameter controls component.
 * This function sets up listeners for the input sliders to update their
 * corresponding value displays in real-time. It also sets up the event listener
 * for the "Simulate" button to send the current control parameters to the backend.
 */ 
export function initiParameterControls() {
    const tempSlider = document.getElementById('temp-slider')
    const humiditySlider = document.getElementById('humidity-slider')
    const moistureSlider = document.getElementById('moisture-slider')

    // Event that modify the value of the text when the slider is moved
    tempSlider.addEventListener('input', () => {
        document.getElementById('current-temp').innerText = tempSlider.value
    })

    // Update the displayed value when the humidity slider is moved.
    humiditySlider.addEventListener('input', () => {
        document.getElementById('current-humidity').innerText = humiditySlider.value
    })

    // Update the displayed value when the moisture slider is moved.
    moistureSlider.addEventListener('input', () => {
        document.getElementById('current-moisture').innerText = moistureSlider.value
    })

    // Handle the click event for the "Simulate" button.
    document.getElementById('simulate-button').addEventListener('click', function () {
        // Collect all parameter values
        const simulationParams = {
            temperature: tempSlider.value,
            humidity: humiditySlider.value,
            soilMoisture: moistureSlider.value,
        }

        // Send the simulation parameters to the backend API.
        fetch('/api/simulate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(simulationParams),
        })
            .then((response) => response.json())
            .then((data) => {
                console.log('Simulation started:', data)
                // TODO: Trigger any UI updates needed after simulation starts.
            })
            .catch((error) => {
                console.error('Error starting simulation:', error)
            })
    })
}
