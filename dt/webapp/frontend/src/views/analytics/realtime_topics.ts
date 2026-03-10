export const processedTopics = {
	temperature: "dt.sensors.processed.temperature",
	humidity: "dt.sensors.processed.humidity",
	soilMoisture: "dt.sensors.processed.soil_moisture",
	lightIntensity: "dt.sensors.processed.light_intensity",
	greenRatio: "dt.sensors.processed.green_ratio",
} as const;

export type ProcessedTopicName =
	(typeof processedTopics)[keyof typeof processedTopics];

export const analyticsTopics = [
	processedTopics.temperature,
	processedTopics.humidity,
	processedTopics.soilMoisture,
	processedTopics.lightIntensity,
] as const;

export const cameraSnapshotTopic = "dt.sensors.raw.camera_image";
