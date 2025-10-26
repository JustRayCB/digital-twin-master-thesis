"""Flask application for the database service.

This application serves as the main entry point for the database service.
It performs two primary functions:

1.  Messaging Bridge: It sets up a Kafka client that subscribes to various
    sensor data topics. When a message is received, it is forwarded to the
    configured storage backend (e.g., InfluxDB) for persistence.

2.  REST API: It exposes a set of HTTP endpoints for interacting with the
    database. This includes endpoints for binding new sensors and querying
    historical sensor data by time range or sensor ID.
"""

import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS

from dt.communication import MessagingService, Topics
from dt.communication.dataclasses import (
    DBIdQuery,
    DBTimestampQuery,
    RawSensorData,
    SensorDescriptor,
)
from dt.communication.messaging_service import KafkaService
from dt.data.database import InfluxDBStorage, Storage
from dt.utils import Config, get_logger

app = Flask(__name__)
CORS(app)
logger = get_logger(__name__)
storage: Storage = InfluxDBStorage(
    url=Config.INFLUX_URL,
    token=Config.INFLUX_TOKEN,
    org=Config.INFLUX_ORG,
    bucket=Config.INFLUX_BUCKET,
)


# Handle Messaging Service's message from SensorManager and forward to web client via socketio
def forward_to_database(payload: RawSensorData):
    """Callback function for the messaging service.

    This function is called by the Kafka consumer whenever a message is
    received on a subscribed sensor topic. It takes the SensorData payload
    and inserts it into the storage backend.

    Parameters
    ----------
    payload : SensorData
        The sensor data received from the messaging service.
    """
    logger.info(f"Received message from Broker: {payload.value} at {payload.timestamp}")
    storage.insert_data(payload)


def setup_bridge():
    """Set up the messaging bridge to the database.

    This function initializes a Kafka client, connects to the broker, and
    subscribes to all processed sensor data topics. The `forward_to_database`
    function is used as the callback to handle incoming messages.

    Returns
    -------
    MessagingService
        The initialized and connected messaging service client. This is
        returned to prevent it from being garbage-collected, which would
        close the connection.
    """
    logger.info("Setting up messaging bridge")
    unique_id = f"database_{uuid.uuid4().hex[:8]}"
    client: MessagingService = KafkaService(
        host=Config.KAFKA_URL, client_id=unique_id, group_id="database_consumer_group"
    )
    if not client.connect():
        logger.error("Failed to connect to Messaging Service's broker")
        raise ConnectionError("Failed to connect to messaging broker")

    # Subscribe to all processed sensor topics
    for topic in Topics.list_sensor_topics():
        client.subscribe(topic.processed, forward_to_database)

    # Return the client so it doesn't go out of scope
    return client


@app.route("/bind_sensor", methods=["POST"])
def bind_sensor():
    """API endpoint to bind a sensor to the database.

    This endpoint expects a JSON payload representing a SensorDescriptor.
    It validates the payload and, if valid, registers the sensor with the
    storage backend.

    Returns
    -------
    flask.Response
        A JSON response indicating the status of the operation and the
        assigned `sensor_id`, or an error message.

    """
    logger.info("Binding sensor to the database")

    sensor_data = request.get_json()
    if not SensorDescriptor.validate_json(sensor_data):
        logger.error(f"Invalid JSON data to bind sensor {sensor_data}")

        return jsonify({"error": "Invalid JSON data"}), 400
    sensor = SensorDescriptor.from_json(sensor_data)

    storage.bind_sensors(sensor)
    logger.info(f"Sensor bound successfully: {sensor}")
    return jsonify({"status": "Sensor bound successfully", "sensor_id": sensor.sensor_id}), 200


@app.route("/sensors", methods=["GET"])
def list_sensors():
    """Return all registered sensors."""

    logger.info("Listing registered sensors")
    descriptors = storage.list_sensors()
    return jsonify([descriptor.to_dict() for descriptor in descriptors])


@app.route("/data/timestamp", methods=["POST"])
def get_data_by_timeframe():
    """API endpoint to get data within a specific time range.

    This endpoint expects a JSON payload representing a `DBTimestampQuery`.
    It queries the storage backend for data of a specific type within the
    given time range and returns the data.

    Returns
    -------
    flask.Response
        A JSON response containing a list of data points, where each point
        is a dictionary with "value" and "time" keys.
    """
    logger.info("Getting data from timestamp")

    request_data = request.get_json()
    if not DBTimestampQuery.validate_json(request_data):
        logger.error(f"Invalid JSON data to get data from timestamp {request_data}")
        return jsonify({"error": "Invalid JSON data"}), 400
    query = DBTimestampQuery.from_json(request_data)

    data: list[RawSensorData] = storage.get_data_by_timeframe(
        data_type=query.data_type,
        since=query.since,
        until=query.until,
    )
    shrank_data = [d.shrink_data() for d in data]
    logger.info(f"Found {len(data)} data points")
    return jsonify(shrank_data)


@app.route("/data/id", methods=["POST"])
def get_sensor_data_from_id():
    """API endpoint to get recent data for a specific sensor ID.

    This endpoint expects a JSON payload representing a DBIdQuery. It
    fetches a limited number of the most recent data points for the given
    sensor ID.

    Returns
    -------
    flask.Response
        A JSON response containing a list of `SensorData` objects.
    """
    logger.info("Getting data from sensor id")

    request_data = request.get_json()
    if not DBIdQuery.validate_json(request_data):
        logger.error(f"Invalid JSON data to get data from id {request_data}")
        return jsonify({"error": "Invalid JSON data"}), 400
    query = DBIdQuery.from_json(request_data)

    data: list[RawSensorData] = storage.get_data(sensor_id=query.sensor_id, limit=query.limit)

    logger.info(f"Found {len(data)} data points")
    return jsonify(data)


if __name__ == "__main__":
    import os

    # Ensure the setup runs only once, not in the reloader process
    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    msg_client = None

    if debug_mode and in_reloader:
        msg_client = setup_bridge()
    elif not debug_mode:
        msg_client = setup_bridge()

    app.run(host="0.0.0.0", port=5001, debug=debug_mode)
