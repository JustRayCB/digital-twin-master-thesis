/**
 * @fileoverview Defines the standard messaging topics used for realtime event routing.
 * These map directly to the backend Kafka/Socket.IO event names.
 */

/** Constants for processed sensor telemetry topics. */
export const processedTopics = {
	temperature: "dt.sensors.processed.temperature",
	humidity: "dt.sensors.processed.humidity",
	soilMoisture: "dt.sensors.processed.soil_moisture",
	lightIntensity: "dt.sensors.processed.light_intensity",
	greenRatio: "dt.sensors.processed.green_ratio",
	plantHeight: "dt.sensors.processed.plant_height",
	leafCount: "dt.sensors.processed.leaf_count",
} as const;

/** Union type of all valid processed topic strings. */
export type ProcessedTopicName =
	(typeof processedTopics)[keyof typeof processedTopics];

/** Sub-selection of topics specifically used for charting analytics. */
export const analyticsTopics = [
	processedTopics.temperature,
	processedTopics.humidity,
	processedTopics.soilMoisture,
	processedTopics.lightIntensity,
	processedTopics.greenRatio,
	processedTopics.leafCount,
	processedTopics.plantHeight,
] as const;

/** Topics used for streaming new camera snapshots. */
export const cameraSnapshotTopics = {
	top: "dt.sensors.raw.camera_image_top",
	side: "dt.sensors.raw.camera_image_side",
} as const;

/** Topics used when querying persisted camera snapshots. */
export const cameraSnapshotDataTopics = {
	top: "dt.sensors.camera_image_top",
	side: "dt.sensors.camera_image_side",
} as const;

export type CameraSnapshotView = keyof typeof cameraSnapshotTopics;

export const recommendationSubmittedTopic = "recommendations_submitted";
export const recommendationCompletedTopic = "recommendations_completed";
export const healthAssessmentTopic = "dt.analytics.health";
export const forecastResultTopic = "dt.analytics.forecast";
export const actionTopic = "dt.actions";
