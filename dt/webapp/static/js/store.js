export class DataType {
    static TEMPERATURE = new DataType('temperature')
    static HUMIDITY = new DataType('humidity')
    static SOIL_MOISTURE = new DataType('soil_moisture')
    static LIGHT = new DataType('light_intensity')
    static GROWTH = new DataType('growth')
    static TIME = new DataType('time') // Will not be present in ALL as we only use it to update the latest time in the UI
    static ALERTS = new DataType('alerts')
    static HEALTH_STATUS = new DataType('health_status')

    // Keep track of all values to iterate through them
    static SENSORS = [
        DataType.TEMPERATURE,
        DataType.HUMIDITY,
        DataType.SOIL_MOISTURE,
        DataType.LIGHT,
        DataType.GROWTH,
    ]

    constructor(name) {
        this.name = name
    }

    toString() {
        return this.name
    }
}

/**
 * @class
 * @classdesc Centralize data store for the application that will receive data from the backend
 *              then send notification to listener to update the correct components
 */
class PlantDataStore {
    constructor() {
        // Initialize maps using DataType objects as keys
        console.log('Initializing PlantDataStore')
        this.realtimeData = new Map()
        this.historicalData = new Map()
        this.listeners = new Map()

        // Initialize data and listeners for each DataType
        DataType.SENSORS.forEach((dataType) => {
            this.realtimeData.set(dataType, [])
            this.historicalData.set(dataType, [])
            this.listeners.set(dataType, [])
        })

        this.listeners.set(DataType.TIME, [])
        this.listeners.set('connection_status', [])

        this.listeners.set(DataType.ALERTS, [])
        this.alerts = []

        this.listeners.set(DataType.HEALTH_STATUS, [])
        this.healthStatus = {
            status: 'Healthy',
            details: 'No issues detected',
        }

        this.connectionStatus = false

        this.socket = io.connect('http://localhost:5000')
        this.initSocketConnection()
    }

    /** Initialize connection with Socket to receive sensors data and update components */
    initSocketConnection() {
        DataType.SENSORS.forEach((dataType) => {
            const listeningField = `${dataType}`
            this.socket.on(listeningField, (data) => {
                this.updateData(dataType, data)
            })
        })

        this.socket.on('connection_status', (status) => {
            console.log(`Received connection status: ${status.connected}`)
            this.connectionStatus = status.connected
            this.notifyListeners('connection_status', { connected: this.connectionStatus })
        })

        this.socket.on('alerts_update', (alert) => {
            console.log(`Received alerts: ${alert}`)
            this.alerts.unshift(alert) // Add the new alert to the beginning of the list

            // Keep only the last 5 alerts
            if (this.alerts.length > 5) {
                this.alerts.pop()
            }
            this.notifyListeners(DataType.ALERTS, this.alerts)
        })

        this.socket.on('alerts_remove', (alertId) => {
            console.log(`Removing alert with id: ${alertId}`)
            this.alerts = this.alerts.filter((alert) => alert.id !== alertId)
            this.notifyListeners(DataType.ALERTS, this.alerts)
        })

        this.socket.on('health_status', (healthStatus) => {
            console.log(`Received health status: ${healthStatus.status}`)
            this.healthStatus = healthStatus
            this.notifyListeners(DataType.HEALTH_STATUS, this.healthStatus)
        })
    }

    /**
     * @param {DataType} dataType - The enum value representing the data type
     * @param {Object} data - Value of the data we just received
     */
    updateData(dataType, data) {
        console.log(`Received data: ${data} for datatype: ${dataType}`)
        this.realtimeData.get(dataType).push(data) // Add the new data to the realtime data

        this.notifyListeners(dataType, data)

        // Send the time to update the latest time in the UI
        this.notifyListeners(DataType.TIME, { time: data.time })
    }

    async fetchHistoricalData(timeRangeStart, timeRangeEnd) {
        console.log(`Fetching historical data from ${timeRangeStart} to ${timeRangeEnd}`)

        const fetchPromises = DataType.SENSORS.map((dataType) => {
            const toSendData = {
                data_type: dataType.toString(),
                from_timestamp: timeRangeStart,
                to_timestamp: timeRangeEnd,
            }
            console.log(`Sending data to fetch historical data: ${JSON.stringify(toSendData)}`)
            return fetch(`/api/data/timestamp`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(toSendData),
            })
                .then((response) => response.json())
                .then((data) => {
                    this.historicalData.set(dataType, data)
                    console.log(`Fetched historical data for ${dataType}:`, data)
                })
        })

        await Promise.all(fetchPromises)

        console.log('All historical data fetched successfully')
        this.mergeHistoricalAndRealTimeData()
    }

    mergeHistoricalAndRealTimeData() {
        DataType.SENSORS.forEach((dataType) => {
            const historicalData = this.historicalData.get(dataType)
            const realtimeData = this.realtimeData.get(dataType)

            if (!historicalData || !realtimeData) {
                console.error(`No data found for ${dataType}`)
                return
            }

            // Filter real-time data to only include entries
            // that are not already in historical data (newest data)
            const lastHistoricalTimestamp = historicalData[historicalData.length - 1].time

            const newRealtimeData = realtimeData.filter((data) => {
                return data.time > lastHistoricalTimestamp
            })

            // Merge historical and real-time data
            const mergedData = [...historicalData, ...newRealtimeData]

            this.notifyListeners(dataType, { type: 'historical', data: mergedData })
        })
    }

    /**
     * @param {DataType} dataType - The enum value representing the data type
     * @param {Object} data - Value of the data we just received
     */
    notifyListeners(dataType, data) {
        const listeners = this.listeners.get(dataType)
        if (!listeners) return

        for (const listenerCallback of listeners) {
            try {
                listenerCallback(data)
            } catch (error) {
                console.error(`Error in listener callback for ${dataType}: `, error)
            }
        }
    }

    /**
     * @param {DataType|string} dataType - The enum value representing the data type
     * @param {function} callback - Function we need to call to notify the listener
     */
    subscribe(dataType, callback) {
        if (!this.listeners.has(dataType)) {
            console.error(`Invalid data type: ${dataType}`)
            return
        }

        const listeners = this.listeners.get(dataType)
        listeners.push(callback)
    }

    /**
     * @param {DataType} dataType - The enum value representing the data type
     * @returns {Object|null} The current data for the specified type
     */
    getData(dataType) {
        return this.realtimeData.get(dataType)
    }
}

// Export an instance
export const plantStore = new PlantDataStore()
