import { initRealTimeMonitoring } from "./components/realtime_monitoring.js";

document.addEventListener("DOMContentLoaded", () => {
    console.log("Hello");
    initializeComponents();
});

function initializeComponents() {
    initRealTimeMonitoring();
}
