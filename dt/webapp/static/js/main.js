import { initRealTimeCharts } from './components/realtime_monitoring.js'

document.addEventListener('DOMContentLoaded', () => {
    console.log('Hello')

    initRealTimeCharts()
    // const plantStatus = new PlantStatusComponent('plant-status', '/api/component/plant-status')
    // plantStatus.init()

    // const paramControls = new ParameterControlsComponent(
    //     'parameter-controls',
    //     '/api/component/parameter-controls'
    // )
    // paramControls.init()
})
