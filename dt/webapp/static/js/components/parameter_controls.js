export function initiParameterControls() {
    const tempSlider = document.getElementById('temp-slider')
    const humiditySlider = document.getElementById('humidity-slider')
    const moistureSlider = document.getElementById('moisture-slider')

    // Event that modify the value of the text when the slider is moved
    tempSlider.addEventListener('input', () => {
        document.getElementById('current-temp').innerText = tempSlider.value
    })

    humiditySlider.addEventListener('input', () => {
        document.getElementById('current-humidity').innerText = humiditySlider.value
    })

    moistureSlider.addEventListener('input', () => {
        document.getElementById('current-moisture').innerText = moistureSlider.value
    })

    document.getElementById('simulate-button').addEventListener('click', function () {
        // Collect all parameter values
        const simulationParams = {
            temperature: tempSlider.value,
            humidity: humiditySlider.value,
            soilMoisture: moistureSlider.value,
        }

        // Send the data to backend
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
                // Trigger any UI updates needed
            })
            .catch((error) => {
                console.error('Error starting simulation:', error)
            })
    })
}
