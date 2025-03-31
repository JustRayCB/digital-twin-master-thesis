import sys

sys.dont_write_bytecode = True
import uuid
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO

from dt.communication import MQTTClient, MQTTTopics
from dt.utils import SensorData, get_logger
from dt.utils.dataclasses import DBTimestampQuery

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
logger = get_logger(__name__)
connection_status = False

# Simulated data for all components
dashboard_data = {
    # Plant Status Data
    "last_update": datetime.now().strftime("%H:%M"),
    "temperature": 23,
    "humidity": 45,
    "light": 780,
    "connection_status": "Connected",
    "health_status": "Good",
    "health_details": "Growing normally, soil drying",
    "alerts": [
        {"message": "Low soil moisture", "time": "14:20"},
        {"message": "Light levels optimal", "time": "13:45"},
    ],
    # Parameter Controls Data
    "control_mode": "Auto",
    "temp_setpoint": 23,
    "humidity_setpoint": 45,
    "soil_setpoint": 25,
    "soil_moisture": 25,
    # Real-time Monitoring Data
    "monitoring_period": "1h",
    "temp_history": [22, 22.5, 23, 23.2, 23.1, 23],
    "humidity_history": [44, 45, 46, 45, 45, 44],
    "soil_history": [26, 25, 25, 24, 24, 25],
    "light_history": [750, 760, 780, 790, 780, 780],
    # Quick Actions & Insights Data
    "recommendations": [
        "Water within next 8 hours",
        "Light levels optimal",
        "Temperature trending higher",
        "Soil pH stable",
    ],
}


# Function to get current date and time
def get_current_datetime():
    now = datetime.now()
    return now.strftime("%m/%d/%Y %H:%M:%S")


@app.route("/")
def dashboard():
    return render_template("dashboard.html", data=dashboard_data)


@app.route("/api/simulate", methods=["POST"])
def start_simulation():
    simulation_parameters = request.json
    logger.info(f"Starting simulation with parameters: {simulation_parameters}")

    temperature = simulation_parameters.get("temperature")
    humidity = simulation_parameters.get("humidity")
    soil_moisture = simulation_parameters.get("light")

    return {"status": "success"}


@app.route("/api/data/timestamp", methods=["POST"])
def get_sensor_data_from_timestamp():
    """API endpoint to get the data from the database from a specific timestamp to the current time.

    Returns
    -------
    JSON
        A JSON object with the data from the database.

    """
    # Get the start timestamp from the query parameters
    logger.info("Getting data from timestamp")
    request_data = request.get_json()
    if not DBTimestampQuery.validate_json(request_data):
        logger.error(f"Invalid JSON data to get data from timestamp {request_data}")
        return jsonify({"error": "Invalid JSON data"}), 400
    db_url = "http://localhost:5001/data/timestamp"
    response = requests.post(db_url, json=request_data)
    if response.status_code == 200:
        data = response.json()
        logger.info(f"Data from timestamp: {data}")
        return jsonify(data)
    else:
        logger.error(f"Error getting data from timestamp: {response.text}")
        return jsonify({"error": "Error getting data from timestamp"}), 500


# Handle client connection
@socketio.on("connect")
def connect():
    global connection_status
    logger.info(f"Client connected: {request.sid}")  # pyright: ignore[]
    socketio.emit("connection_status", {"connected": connection_status})


# Handle client disconnection
@socketio.on("disconnect")
def disconnect():
    logger.info(f"Client disconnected: {request.sid}")  # pyright: ignore[]


# Handle MQTT message from SensorManager and forward to web client via socketio
def forward_to_socketio(topic: MQTTTopics):
    def callback(payload: SensorData):
        value = payload.value
        time = payload.timestamp
        # TODO: Use only the topic inside the SensorData object. Currently, the topic is passed as an argument for debugging
        socketio_topic = topic.split("/")[-1]  # Get the last part of the topic (sensor's data)
        logger.info(f"Received message from MQTT: {value} at {time}")
        socketio.emit(socketio_topic, payload.shrink_data())

    return callback


def setup_mqtt_bridge():
    global connection_status
    # Generate a unique client ID to prevent conflicts
    unique_id = f"webapp_{uuid.uuid4().hex[:8]}"
    # mqtt_client = MQTTClient(hostname="192.168.129.7", id=unique_id)
    mqtt_client = MQTTClient(hostname="83.134.103.194", id=unique_id)
    connection_status = mqtt_client.connect()

    # Subscribe to topics
    mqtt_client.subscribe(MQTTTopics.SOIL_MOISTURE, forward_to_socketio(MQTTTopics.SOIL_MOISTURE))
    mqtt_client.subscribe(MQTTTopics.TEMPERATURE, forward_to_socketio(MQTTTopics.TEMPERATURE))
    mqtt_client.subscribe(MQTTTopics.HUMIDITY, forward_to_socketio(MQTTTopics.HUMIDITY))
    mqtt_client.subscribe(MQTTTopics.SOIL_MOISTURE, forward_to_socketio(MQTTTopics.LIGHT_INTENSITY))
    mqtt_client.subscribe(MQTTTopics.CAMERA_IMAGE, forward_to_socketio(MQTTTopics.CAMERA_IMAGE))

    # Return the client so it doesn't go out of scope
    return mqtt_client


if __name__ == "__main__":
    # TODO: Make queries to the database to get the latest data for the dashboard of data from a specific time to now

    # Only setup MQTT in the child process when using debug mode
    import os

    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    # Store the MQTT client to prevent it from being garbage collected
    mqtt_client = None

    if debug_mode and in_reloader:
        # Only setup in child process in debug mode
        mqtt_client = setup_mqtt_bridge()
    elif not debug_mode:
        # Setup normally in production mode
        mqtt_client = setup_mqtt_bridge()

    # Run the Flask app
    socketio.run(app, debug=debug_mode, host="127.0.0.1", port=5000)
