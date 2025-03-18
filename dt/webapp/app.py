import random
import time
from datetime import datetime
from random import uniform
from threading import Lock

import plotly
import plotly.express as px
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO

from dt.communication import MQTTClient, MQTTTopics
from dt.utils.logger import get_logger

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
logger = get_logger(__name__)

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

# Global variables
thread = None
thread_lock = Lock()
last_value = None  # To keep track of last emitted value


# Function to get current date and time
def get_current_datetime():
    now = datetime.now()
    return now.strftime("%m/%d/%Y %H:%M:%S")


# Function to generate random values and send them to the client
def background_thread():
    print("Starting background thread for random value generation")
    # Start with an initial value
    current_value = round(uniform(16.0, 26.0), 2)
    while True:
        # Generate a random change between -1.0 and 1.0
        change = round(uniform(-1.0, 1.0), 2)
        # Update the current value within the range 16.0 - 26.0
        current_value = max(16.0, min(26.0, current_value + change))
        # Get the current time
        current_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
        print(f"Generated value: {current_value}  at {current_time}")

        # Send the data to the client via WebSocket
        socketio.emit(
            "update_soil_moisture",
            {"soil_moisture": current_value, "time": current_time},
        )

        # Sleep for 1 second before generating the next value
        time.sleep(1)


@app.route("/")
def dashboard():
    return render_template("dashboard.html", data=dashboard_data)


# Handle client connection
@socketio.on("connect")
def connect():
    logger.info(f"Client connected: {request.sid}")  # pyright: ignore[]


# Handle client disconnection
@socketio.on("disconnect")
def disconnect():
    logger.info(f"Client disconnected: {request.sid}")  # pyright: ignore[]


# Handle MQTT message from SensorManager and forward to web client via socketio


def forward_to_socketio(topic):
    def callback(payload):
        value = payload["value"]
        time = payload["timestamp"]
        socketio_topic = topic.split("/")[-1]  # Get the last part of the topic (sensor's data)
        logger.info(f"Received message from MQTT: {value} at {time}")
        # socketio.emit(socketio_topic, {"value": value, "time": time})
        # print(f"Received message from MQTT: {value} at {time}")

    return callback


def setup_mqtt_bridge():
    mqtt_client = MQTTClient(id="webapp")
    mqtt_client.connect()

    mqtt_client.subscribe(MQTTTopics.SOIL_MOISTURE, forward_to_socketio(MQTTTopics.SOIL_MOISTURE))
    mqtt_client.subscribe(MQTTTopics.TEMPERATURE, forward_to_socketio(MQTTTopics.TEMPERATURE))
    mqtt_client.subscribe(MQTTTopics.HUMIDITY, forward_to_socketio(MQTTTopics.HUMIDITY))
    mqtt_client.subscribe(
        MQTTTopics.LIGHT_INTENSITY, forward_to_socketio(MQTTTopics.LIGHT_INTENSITY)
    )
    mqtt_client.subscribe(MQTTTopics.CAMERA_IMAGE, forward_to_socketio(MQTTTopics.CAMERA_IMAGE))


if __name__ == "__main__":
    # app.run(debug=True)
    setup_mqtt_bridge()
    socketio.run(app, debug=True, host="127.0.0.1", port=5000)
