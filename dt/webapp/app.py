"""Main Flask application for the web dashboard.

This application serves the main dashboard for the digital twin project.
It has the following key responsibilities:

1.  Web Interface: Renders the main `dashboard.html` template, which
    provides the user interface for monitoring and controlling the digital
    twin.

2.  Real-time Updates: Sets up a Flask-SocketIO server to push real-time
    sensor data to connected web clients.

3.  Messaging Bridge: Initializes a Kafka client that subscribes to
    processed sensor data topics. When a message is received, it is
    broadcast to the appropriate SocketIO room, allowing for live updates
    on the dashboard.

4.  API Endpoints: Provides API endpoints for the frontend to fetch
    historical data from the database service.
"""

import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_socketio import SocketIO

from dt.communication import (DatabaseApiClient, KafkaService,
                              MessagingService, Topics)
from dt.communication.dataclasses import DBTimestampQuery, RawSensorData
from dt.utils import Config, get_logger

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


@app.route("/")
def dashboard():
    """Render the main dashboard page.

    This route serves the dashboard.html template, passing in the
    dashboard_data dictionary to populate the initial state of the UI.

    Returns
    -------
    str
        The rendered HTML for the dashboard page.
    """
    return render_template("dashboard.html", data=dashboard_data)


@app.route("/api/simulate", methods=["POST"])
def start_simulation():
    """API endpoint to start a simulation.

    .. warning::
        This is a placeholder endpoint and is not yet implemented.

    Returns
    -------
    dict
        A JSON response indicating the status of the operation.
    """
    simulation_parameters = request.json
    logger.info(f"Starting simulation with parameters: {simulation_parameters}")

    temperature = simulation_parameters.get("temperature")  # noqa: F841
    humidity = simulation_parameters.get("humidity")  # noqa: F841
    soil_moisture = simulation_parameters.get("light")  # noqa: F841

    return {"status": "success"}


@app.route("/api/data/timestamp", methods=["POST"])
def get_data_by_timeframe():
    """API endpoint to get historical data within a specific time range.

    This endpoint acts as a proxy to the database service. It receives a
    `DBTimestampQuery` from the client, converts the JavaScript timestamps
    to Python format, and then calls the database service to retrieve the
    data.

    Returns
    -------
    flask.Response
        A JSON response containing the requested historical data, or an
        error message.
    """

    request_data = request.get_json()
    if not DBTimestampQuery.validate_json(request_data):
        logger.error(f"Invalid JSON data to get data from timestamp {request_data}")
        return jsonify({"error": "Invalid JSON data"}), 400
    # Convert the JSON data to a DBTimestampQuery object
    query: DBTimestampQuery = DBTimestampQuery.from_json(request_data)
    query.js_to_py_timestamp()  # Convert the timestamp from JavaScript format to Python format

    db_client = DatabaseApiClient()
    data = db_client.get_data_by_timeframe(query)

    logger.info(f"Getting data by timefreame for {query}")

    return jsonify(data)


# Handle client connection
@socketio.on("connect")
def connect():
    """Handle a new client connection to the SocketIO server.

    This function is called when a new client establishes a connection. It
    logs the connection and emits the current connection status to the
    client.
    """
    global connection_status
    logger.info(f"Client connected: {request.sid}")  # pyright: ignore[]
    socketio.emit("connection_status", {"connected": connection_status})


# Handle client disconnection
@socketio.on("disconnect")
def disconnect():
    """Handle a client disconnection from the SocketIO server.

    This function is called when a client disconnects. It logs the
    disconnection event.
    """
    logger.info(f"Client disconnected: {request.sid}")  # pyright: ignore[]


# Handle message from SensorManager and forward to web client via socketio
def forward_to_socketio(topic: Topics):
    """Create a callback function to forward Kafka messages to SocketIO.

    This factory function returns a callback that can be used with the Kafka
    consumer. The returned callback takes a RawSensorData payload, converts
    its timestamp to JavaScript format, and emits it to the appropriate
    SocketIO room (determined by the topic's short name).

    Parameters
    ----------
    topic : Topics
        The topic for which the callback is being created.

    Returns
    -------
    Callable[[SensorData], None]
        The callback function.
    """

    def callback(payload: RawSensorData):
        socketio_topic = topic.short_name
        logger.info(f"Received message from broker: {payload.value} at {payload.timestamp}")
        payload.py_to_js_timestamp()
        socketio.emit(socketio_topic, payload.shrink_data())

    return callback


def setup_bridge() -> MessagingService:
    """Set up the messaging bridge from Kafka to SocketIO.

    This function initializes a Kafka client, connects to the broker, and
    subscribes to all processed sensor data topics. For each topic, it sets
    up a callback using `forward_to_socketio` to relay the messages to the
    web clients.

    Returns
    -------
    MessagingService
        The initialized and connected messaging service client.
    """
    global connection_status
    # Generate a unique client ID to prevent conflicts
    unique_id = f"webapp_{uuid.uuid4().hex[:8]}"
    msg_client: MessagingService = KafkaService(
        host=Config.KAFKA_URL, client_id=unique_id, group_id="webapp_consumer_group"
    )
    if not msg_client.connect():
        logger.error("Failed to connect to Messaging Service's broker")
        raise ConnectionError("Failed to connect to messaging broker")
    connection_status = True

    for topic in Topics.list_sensor_topics():
        msg_client.subscribe(topic.processed, forward_to_socketio(topic))
    # Return the client so it doesn't go out of scope
    return msg_client


if __name__ == "__main__":
    import os

    # Ensure the setup runs only once, not in the reloader process
    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    # Store the Messaging Service's client to prevent it from being garbage collected
    msg_client = None

    if debug_mode and in_reloader:
        # Only setup in child process in debug mode
        msg_client = setup_bridge()
    elif not debug_mode:
        # Setup normally in production mode
        msg_client = setup_bridge()

    # Run the Flask app
    socketio.run(app, debug=debug_mode, host="127.0.0.1", port=5000)
