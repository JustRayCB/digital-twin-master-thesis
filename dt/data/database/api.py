"""Database service REST API.

Flask blueprint providing endpoints for sensor registration, data querying,
actuator listing, and alert history management.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import SensorDescriptor
from dt.communication.dataclasses.alerts.alert_record import AlertDefinition
from dt.communication.dataclasses.queries import ActiveAlertsQuery, AlertHistoryQuery, ReadingsQuery
from dt.data.database.storage import Storage
from dt.utils import get_logger

logger = get_logger(__name__)


def create_database_blueprint(storage: Storage) -> Blueprint:
    """Create a Flask blueprint for the database service API.

    Parameters
    ----------
    storage : Storage
        The storage backend instance used for data persistence and retrieval.

    Returns
    -------
    Blueprint
        A configured Flask blueprint with all database service routes.
    """
    bp = Blueprint("database", __name__)

    @bp.route("/bind_sensor", methods=["POST"])
    def bind_sensor():
        """API endpoint to bind a sensor to the database."""
        logger.info("Binding sensor to the database")

        try:
            sensor_data = request.get_json(force=True)
            if sensor_data is None:
                return jsonify({"error": "Missing JSON payload"}), 400

            sensor = load("generic", SensorDescriptor, sensor_data)
        except Exception as e:
            logger.error(f"Invalid sensor data: {e}")
            return jsonify({"error": "Invalid sensor data format"}), 400

        sensor_id = storage.register_sensor(sensor)
        logger.info(f"Sensor bound successfully with ID: {sensor_id}")
        return jsonify({"status": "Sensor bound successfully", "sensor_id": sensor_id}), 200

    @bp.route("/sensors", methods=["GET"])
    def list_sensors():
        """Return all registered sensors with relational metadata."""
        logger.info("Listing registered sensors")
        descriptors = storage.list_sensors()
        return jsonify([dump("generic", descriptor) for descriptor in descriptors])

    @bp.route("/readings", methods=["GET"])
    def get_readings():
        """Query sensor readings with optional aggregation."""
        logger.info("Getting readings")

        try:
            query_params = load("generic", ReadingsQuery, request.args.to_dict())
        except Exception as e:
            logger.error(f"Invalid query parameters: {e}")
            return jsonify({"error": str(e)}), 400

        if query_params.window == "raw":
            data = storage.query_readings(query_params)
            result = [dump("generic", reading) for reading in data]
        else:  # window == "1h"
            data = storage.query_aggregates(query_params)
            result = [dump("generic", aggregate) for aggregate in data]

        logger.info(f"Found {len(result)} readings")
        return jsonify(result)

    @bp.route("/actuators", methods=["GET"])
    def list_actuators():
        """Return all registered actuators."""
        logger.info("Listing actuators")
        actuators = storage.list_actuators()
        logger.info(f"Found {len(actuators)} actuators")
        return jsonify(actuators)

    @bp.route("/alerts/definitions", methods=["POST"])
    def ensure_alert_definition():
        """Ensure an alert definition exists (idempotent upsert)."""
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        if payload is None:
            return jsonify({"error": "Invalid JSON"}), 400

        try:
            definition = load("generic", AlertDefinition, payload)
        except Exception as exc:
            logger.error(f"Invalid alert definition payload: {exc}")
            return jsonify({"error": "Invalid alert definition"}), 400

        storage.save_alert_definition(definition)
        return jsonify({"status": "ok"}), 200

    @bp.route("/alerts/history", methods=["GET"])
    def get_alert_history():
        """Retrieve alert event history."""
        logger.info("Getting alert history")

        try:
            query = load("generic", AlertHistoryQuery, request.args.to_dict())
        except Exception as e:
            logger.error(f"Invalid query parameters: {e}")
            return jsonify({"error": str(e)}), 400

        events = storage.get_alert_history(query)
        result = [dump("generic", event) for event in events]

        logger.info(f"Retrieved {len(result)} alert events")
        return jsonify(result)

    @bp.route("/alerts/active", methods=["GET"])
    def get_active_alerts():
        """Retrieve currently active alerts."""
        logger.info("Getting active alerts from storage")

        try:
            query = load("generic", ActiveAlertsQuery, request.args.to_dict())
        except Exception as e:
            logger.error(f"Invalid query parameters: {e}")
            return jsonify({"error": str(e)}), 400

        events = storage.get_active_alerts(query)
        result = [dump("generic", event) for event in events]

        logger.info(f"Retrieved {len(result)} active alerts")
        return jsonify(result)

    return bp
