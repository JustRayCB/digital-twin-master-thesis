import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS

from dt.communication import MQTTClient, MQTTTopics
from dt.data.database.storage import Storage
from dt.utils import SensorData, SensorDataClass, get_logger
from dt.utils.dataclasses import DBTimestampQuery

app = Flask(__name__)
CORS(app)
logger = get_logger(__name__)
storage = Storage()


# Handle MQTT message from SensorManager and forward to web client via socketio
def forward_to_database(payload: SensorData):
    value = payload.value
    time = payload.timestamp
    logger.info(f"Received message from MQTT: {value} at {time}")
    storage.insert_data(payload)


def setup_mqtt_bridge():
    logger.info("Setting up MQTT bridge")
    unique_id = f"database_{uuid.uuid4().hex[:8]}"
    mqtt_client = MQTTClient(hostname="127.0.0.1", id=unique_id)
    if not mqtt_client.connect():
        logger.error("Failed to connect to MQTT broker")
        return

    # Subscribe to topics
    mqtt_client.subscribe(MQTTTopics.SOIL_MOISTURE, forward_to_database)
    mqtt_client.subscribe(MQTTTopics.TEMPERATURE, forward_to_database)
    mqtt_client.subscribe(MQTTTopics.HUMIDITY, forward_to_database)
    mqtt_client.subscribe(MQTTTopics.LIGHT_INTENSITY, forward_to_database)
    mqtt_client.subscribe(MQTTTopics.CAMERA_IMAGE, forward_to_database)

    # Return the client so it doesn't go out of scope
    return mqtt_client


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
    request_data = DBTimestampQuery.from_json(request_data)
    data: list[SensorData] = storage.get_data_from_timestamp(
        data_type=request_data.data_type,
        from_timestamp=request_data.from_timestamp,
        to_timestamp=request_data.to_timestamp,
    )
    shrank_data = [d.shrink_data() for d in data]
    logger.info(f"Lenght of data: {len(data)}")
    return jsonify(shrank_data)


@app.route("/data/id", methods=["GET"])
def get_sensor_data_from_id():
    """API endpoint to get the data from the database from a specific sensor id.

    Returns
    -------
    JSON
        A JSON object with the data from the database.

    """
    # Get the start timestamp from the query parameters
    logger.info("Getting data from sensor id")
    sensor_id: int = request.args.get("sensor_id", 1, type=int)
    limit: int = request.args.get("limit", 10, type=int)
    data: list[SensorData] = storage.get_data(sensor_id, limit)
    logger.info(f"Lenght of data: {len(data)}")
    return jsonify(data)


if __name__ == "__main__":
    # TODO: Test wether the app works with the MQTT bridge + the database
    import os

    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    mqtt_client = None

    if debug_mode and in_reloader:
        mqtt_client = setup_mqtt_bridge()
    elif not debug_mode:
        mqtt_client = setup_mqtt_bridge()

    app.run(host="127.0.0.1", port=5001, debug=debug_mode)
