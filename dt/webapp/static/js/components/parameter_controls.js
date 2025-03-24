export function initiParameterControls() {
    document.getElementById('temp-slider').addEventListener('input', () => {
        document.getElementById('current-temp').innerText =
            document.getElementById('temp-slider').value
    })

    document.getElementById('humidity-slider').addEventListener('input', () => {
        document.getElementById('current-humidity').innerText =
            document.getElementById('humidity-slider').value
    })

    document.getElementById('moisture-slider').addEventListener('input', () => {
        document.getElementById('current-moisture').innerText =
            document.getElementById('moisture-slider').value
    })
}
