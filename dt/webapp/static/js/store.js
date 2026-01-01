/**
 * @class
 * @classdesc An enumeration-like class for data types used in the application.
 * This provides a centralized and consistent way to refer to different types of sensor data and system events.
 */
export class DataType {
	static TEMPERATURE = new DataType("temperature");
	static HUMIDITY = new DataType("humidity");
	static SOIL_MOISTURE = new DataType("soil_moisture");
	static LIGHT = new DataType("light_intensity");
	static TIME = new DataType("time"); // Used only to update the latest time in the UI.
	static ALERTS = new DataType("alerts");
	static HEALTH_STATUS = new DataType("health_status");

	/**
	 * @type {DataType[]}
	 * @description A list of all sensor-related data types, used for iteration.
	 */
	static SENSORS = [
		DataType.TEMPERATURE,
		DataType.HUMIDITY,
		DataType.SOIL_MOISTURE,
		DataType.LIGHT,
	];

	/**
	 * @param {string} name - The name of the data type.
	 */
	constructor(name) {
		this.name = name;
	}

	/**
	 * @returns {string} The string representation of the data type's name.
	 */
	toString() {
		return this.name;
	}
}

/**
 * @class PlantDataStore
 * @classdesc Centralized data store for the application. It manages real-time and historical data,
 * communicates with the backend via Socket.IO, and notifies subscribed components of data changes.
 */
class PlantDataStore {
	constructor() {
		// Initialize maps using DataType objects as keys
		console.log("Initializing PlantDataStore");
		/** @type {Map<DataType, Array<Object>>} */
		this.realtimeData = new Map();
		/** @type {Map<DataType, Array<Object>>} */
		this.historicalData = new Map();
		/** @type {Map<DataType|string, Array<function>>} */
		this.listeners = new Map();

		// Initialize data and listeners for each Sensor DataType
		DataType.SENSORS.forEach((dataType) => {
			this.realtimeData.set(dataType, []);
			this.historicalData.set(dataType, []);
			this.listeners.set(dataType, []);
		});

		// Initialize listeners for non-sensor data types
		this.listeners.set(DataType.TIME, []);
		this.listeners.set("connection_status", []);

		this.listeners.set(DataType.ALERTS, []);
		this.alerts = [];

		this.listeners.set(DataType.HEALTH_STATUS, []);
		this.healthStatus = {
			status: "Healthy",
			details: "No issues detected",
		};

		this.connectionStatus = false;

		this.socket = io.connect("http://localhost:5000");
		this.initSocketConnection();
	}

	/**
	 * Returns the processed Kafka topic string used for Socket.IO events and history queries.
	 * @param {DataType} dataType
	 * @returns {string}
	 */
	topicForDataType(dataType) {
		return `dt.sensors.processed.${dataType}`;
	}

	/**
	 * Normalize a reading payload into a single internal shape (timestamps are ms).
	 * @param {Object} payload
	 * @returns {Object}
	 */
	normalizeReading(payload) {
		const time = Number(payload?.time);
		return {
			plant_id: payload?.plant_id,
			sensor_id: payload?.sensor_id,
			time: Number.isFinite(time) ? time : null,
			unit: payload?.unit,
			value: payload?.value ?? null,
			raw_value: payload?.raw_value ?? null,
			calibrated_value: payload?.calibrated_value ?? null,
			normalized_value: payload?.normalized_value ?? null,
			dq_score: payload?.dq_score ?? null,
			imputed: payload?.imputed ?? null,
			flags: payload?.flags ?? null,
			// Traceability metadata available for drill-down views and debugging.
			correlation_id: payload?.correlation_id ?? null,
			calibration_profile_id: payload?.calibration_profile_id ?? null,
			normalization_profile_id: payload?.normalization_profile_id ?? null,
		};
	}

	/**
	 * Initializes the Socket.IO connection and sets up event listeners for real-time data updates.
	 * This includes listeners for sensor data, connection status, alerts, and health status.
	 */
	initSocketConnection() {
		DataType.SENSORS.forEach((dataType) => {
			const listeningField = this.topicForDataType(dataType);
			this.socket.on(listeningField, (data) => {
				this.updateData(dataType, data);
			});
		});

		this.socket.on("connection_status", (status) => {
			console.log(`Received connection status: ${status.connected}`);
			this.connectionStatus = status.connected;
			this.notifyListeners("connection_status", {
				connected: this.connectionStatus,
			});
		});

		this.socket.on("alerts_update", (alert) => {
			console.log(`Received alerts: ${alert}`);
			// Replace existing alert with the same alert_id (multi-plant safe)
			this.alerts = this.alerts.filter(
				(existing) => existing.alert_id !== alert.alert_id,
			);
			this.alerts.unshift(alert); // Add the new alert to the beginning of the list

			// Keep only the last 5 alerts
			if (this.alerts.length > 5) {
				this.alerts.pop();
			}
			this.notifyListeners(DataType.ALERTS, this.alerts);
		});

		this.socket.on("alerts_remove", (alertId) => {
			console.log(`Removing alert with id: ${alertId}`);
			this.alerts = this.alerts.filter((alert) => alert.alert_id !== alertId);
			this.notifyListeners(DataType.ALERTS, this.alerts);
		});

		this.socket.on("health_status", (healthStatus) => {
			console.log(`Received health status: ${healthStatus.status}`);
			this.healthStatus = healthStatus;
			this.notifyListeners(DataType.HEALTH_STATUS, this.healthStatus);
		});
	}

	/**
	 * Updates the real-time data for a given data type and notifies listeners.
	 * @param {DataType} dataType - The enum value representing the data type.
	 * @param {Object} data - The new data point received from the backend (e.g., { value: 23, time: 167... }).
	 */
	updateData(dataType, data) {
		console.log(`Received data: ${data} for datatype: ${dataType}`);
		const reading = this.normalizeReading(data);
		this.realtimeData.get(dataType).push(reading); // Add the new data to the realtime data

		this.notifyListeners(dataType, reading);

		// Send the time to update the latest time in the UI
		this.notifyListeners(DataType.TIME, { time: reading.time });
	}

	/**
	 * Fetches historical data for all sensor types within a given time range.
	 * @param {number} timeRangeStart - The start of the time range as a Unix timestamp (in milliseconds).
	 * @param {number} timeRangeEnd - The end of the time range as a Unix timestamp (in milliseconds).
	 */
	async fetchHistoricalData(timeRangeStart, timeRangeEnd) {
		console.log(
			`Fetching historical data from ${timeRangeStart} to ${timeRangeEnd}`,
		);

		const fetchPromises = DataType.SENSORS.map((dataType) => {
			const queryParams = new URLSearchParams({
				topic: this.topicForDataType(dataType),
				since: String(timeRangeStart),
				until: String(timeRangeEnd),
				window: "raw",
			});
			console.log(
				`Sending data to fetch historical data: ${queryParams.toString()}`,
			);
			return fetch(`/api/readings?${queryParams.toString()}`, { method: "GET" })
				.then((response) => response.json())
				.then((data) => {
					const readings = Array.isArray(data)
						? data
								.map((item) => this.normalizeReading(item))
								.filter((item) => item.time !== null)
								.sort((a, b) => a.time - b.time)
						: [];
					this.historicalData.set(dataType, readings);
					console.log(`Fetched historical data for ${dataType}:`, data);
				});
		});

		await Promise.all(fetchPromises);

		console.log("All historical data fetched successfully");
		this.mergeHistoricalAndRealTimeData();
	}

	/**
	 * Merges the fetched historical data with the new real-time data that has arrived since
	 * the historical fetch began. Notifies listeners with the complete, merged data set.
	 */
	mergeHistoricalAndRealTimeData() {
		DataType.SENSORS.forEach((dataType) => {
			const historicalData = this.historicalData.get(dataType);
			const realtimeData = this.realtimeData.get(dataType);

			if (historicalData.length === 0) {
				console.error(`No historical data found for ${dataType}`);
				return;
			}

			// Filter real-time data to only include entries
			// that are not already in historical data (newest data)
			const lastHistoricalTimestamp =
				historicalData[historicalData.length - 1].time;

			const newRealtimeData = realtimeData.filter((data) => {
				return data.time > lastHistoricalTimestamp;
			});

			// Merge historical and real-time data
			const mergedData = [...historicalData, ...newRealtimeData];

			this.notifyListeners(dataType, { type: "historical", data: mergedData });
		});
	}

	/**
	 * Notifies all registered listeners for a specific data type.
	 * @param {DataType|string} dataType - The data type for which to notify listeners.
	 * @param {Object} data - The data to pass to the listener callbacks.
	 */
	notifyListeners(dataType, data) {
		const listeners = this.listeners.get(dataType);
		if (!listeners) return;

		for (const listenerCallback of listeners) {
			try {
				listenerCallback(data);
			} catch (error) {
				console.error(`Error in listener callback for ${dataType}: `, error);
			}
		}
	}

	/**
	 * Subscribes a callback function to a specific data type.
	 * @param {DataType|string} dataType - The data type to subscribe to.
	 * @param {function} callback - The callback function to execute when new data is available.
	 */
	subscribe(dataType, callback) {
		if (!this.listeners.has(dataType)) {
			console.error(`Invalid data type: ${dataType}`);
			return;
		}

		const listeners = this.listeners.get(dataType);
		listeners.push(callback);
	}

	/**
	 * Retrieves the current real-time data for a specified data type.
	 * @param {DataType} dataType - The enum value representing the data type.
	 * @returns {Array<Object>|undefined} The current real-time data for the specified type.
	 */
	getData(dataType) {
		return this.realtimeData.get(dataType);
	}
}

// Export a singleton instance of the data store.
export const plantStore = new PlantDataStore();
