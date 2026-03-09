export const processedTopics = {
	temperature: "dt.sensors.processed.temperature",
	humidity: "dt.sensors.processed.humidity",
	soilMoisture: "dt.sensors.processed.soil_moisture",
	lightIntensity: "dt.sensors.processed.light_intensity",
} as const;

export type ProcessedTopicName =
	(typeof processedTopics)[keyof typeof processedTopics];

export const cameraSnapshotTopic = "dt.sensors.raw.camera_image";
