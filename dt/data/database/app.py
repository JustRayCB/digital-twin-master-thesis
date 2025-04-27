import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS

from dt.communication import MessagingService, Topics
from dt.communication.messaging_service import KafkaService
from dt.data.database import InfluxDBStorage, SQLStorage, Storage
from dt.utils import Config, SensorData, SensorDataClass, get_logger
from dt.utils.dataclasses import DBIdQuery, DBTimestampQuery

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
def forward_to_database(payload: SensorData):
    value = payload.value
    time = payload.timestamp
    logger.info(f"Received message from Broker: {value} at {time}")
    storage.insert_data(payload)


def setup_bridge():
    logger.info("Setting up bridge")
    unique_id = f"database_{uuid.uuid4().hex[:8]}"
    client: MessagingService = KafkaService(host=Config.KAFKA_URL, client_id=unique_id)
    if not client.connect():
        logger.error("Failed to connect to Messaging Service's broker")
        return

    # Subscribe to topics
    client.subscribe(Topics.SOIL_MOISTURE.processed, forward_to_database)
    client.subscribe(Topics.TEMPERATURE.processed, forward_to_database)
    client.subscribe(Topics.HUMIDITY.processed, forward_to_database)
    client.subscribe(Topics.LIGHT_INTENSITY.processed, forward_to_database)
    client.subscribe(Topics.CAMERA_IMAGE.processed, forward_to_database)

    # Return the client so it doesn't go out of scope
    return client


@app.route("/bind_sensor", methods=["POST"])
def bind_sensor():
    """API endpoint to bind a sensor to the database.

    Returns
    -------
    JSON
        A JSON object with the status of the binding operation.

    """
    logger.info("Binding sensor to the database")

    sensor_data = request.get_json()
    if not SensorDataClass.validate_json(sensor_data):
        logger.error(f"Invalid JSON data to bind sensor {sensor_data}")
        return jsonify({"error": "Invalid JSON data"}), 400
    sensor = SensorDataClass.from_json(sensor_data)

    storage.bind_sensors(sensor)
    logger.info(f"Sensor bound successfully: {sensor}")
    return jsonify({"status": "Sensor bound successfully", "sensor_id": sensor.sensor_id}), 200


@app.route("/data/timestamp", methods=["POST"])
def get_data_by_timeframe():
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
    request_data = DBTimestampQuery.from_json(request_data)

    data: list[SensorData] = storage.get_data_by_timeframe(
        data_type=request_data.data_type,
        from_timestamp=request_data.from_timestamp,
        to_timestamp=request_data.to_timestamp,
    )
    shrank_data = [d.shrink_data() for d in data]
    logger.info(f"Lenght of data: {len(data)}")
    return jsonify(shrank_data)


@app.route("/data/id", methods=["POST"])
def get_sensor_data_from_id():
    """API endpoint to get the data from the database from a specific sensor id.

    Returns
    -------
    JSON
        A JSON object with the data from the database.

    """
    # Get the start timestamp from the query parameters
    logger.info("Getting data from sensor id")

    request_data = request.get_json()
    if not DBIdQuery.validate_json(request_data):
        logger.error(f"Invalid JSON data to get data from id {request_data}")
        return jsonify({"error": "Invalid JSON data"}), 400
    request_data = DBIdQuery.from_json(request_data)

    data: list[SensorData] = storage.get_data(
        sensor_id=request_data.sensor_id, limit=request_data.limit
    )

    logger.info(f"Lenght of data: {len(data)}")
    return jsonify(data)


if __name__ == "__main__":
    # TODO: Test wether the app works with the MQTT bridge + the database
    import os

    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    msg_client = None

    if debug_mode and in_reloader:
        msg_client = setup_bridge()
    elif not debug_mode:
        msg_client = setup_bridge()

    app.run(host="0.0.0.0", port=5001, debug=debug_mode)
