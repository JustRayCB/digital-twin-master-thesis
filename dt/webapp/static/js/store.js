export class DataType {
    static TEMPERATURE = new DataType("temperature");
    static HUMIDITY = new DataType("humidity");
    static SOIL_MOISTURE = new DataType("soil_moisture");
    static LIGHT = new DataType("light_intensity");
    static GROWTH = new DataType("growth");

    // Keep track of all values to iterate through them
    static ALL = [
        DataType.TEMPERATURE,
        DataType.HUMIDITY,
        DataType.SOIL_MOISTURE,
        DataType.LIGHT,
        DataType.GROWTH,
    ];

    constructor(name) {
        this.name = name;
    }

    toString() {
        return this.name;
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
        console.log("Initializing PlantDataStore");
        this.data = new Map();
        this.listeners = new Map();

        // Initialize data and listeners for each DataType
        DataType.ALL.forEach((dataType) => {
            this.data.set(dataType, { value: null, time: null });
            this.listeners.set(dataType, []);
        });

        this.socket = io.connect("http://localhost:5000");
        this.initSocketConnection();
    }

    /** Initialize connection with Socket to receive sensors data and update components */
    initSocketConnection() {
        DataType.ALL.forEach((dataType) => {
            const listeningField = `${dataType}`;
            this.socket.on(listeningField, (data) => {
                this.updateData(dataType, data);
            });
        });
    }

    /**
     * @param {DataType} dataType - The enum value representing the data type
     * @param {Object} data - Value of the data we just received
     */
    updateData(dataType, data) {
        console.log(`Received data: ${data} for datatype: ${dataType}`);
        this.data.set(dataType, { value: data.value, time: data.time });
        this.notifyListeners(dataType, data);
    }

    /**
     * @param {DataType} dataType - The enum value representing the data type
     * @param {Object} data - Value of the data we just received
     */
    notifyListeners(dataType, data) {
        const listeners = this.listeners.get(dataType);
        if (!listeners) return;

        for (const listenerCallback of listeners) {
            try {
                listenerCallback(data);
            } catch (error) {
                console.error(
                    `Error in listener callback for ${dataType}: `,
                    error,
                );
            }
        }
    }

    /**
     * @param {DataType} dataType - The enum value representing the data type
     * @param {function} callback - Function we need to call to notify the listener
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
     * @param {DataType} dataType - The enum value representing the data type
     * @returns {Object|null} The current data for the specified type
     */
    getData(dataType) {
        return this.data.get(dataType);
    }
}

// Export an instance
export const plantStore = new PlantDataStore();
