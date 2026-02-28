"""Database service REST API.

Flask blueprint providing endpoints for sensor registration, data querying,
actuator listing, and alert history management.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import SensorDescriptor
from dt.communication.dataclasses.controller import ActionCommand, ControlMode, RoutineUpdate
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

    @bp.route("/camera/snapshots/latest", methods=["GET"])
    def get_latest_camera_snapshot():
        """Return the latest camera snapshot for a plant."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        snapshot = storage.get_latest_camera_snapshot(plant_id=plant_id)
        if snapshot is None:
            return jsonify({"error": "No camera snapshot found"}), 404

        return jsonify(dump("generic", snapshot)), 200

    @bp.route("/actuators", methods=["GET"])
    def list_actuators():
        """Return all registered actuators."""
        logger.info("Listing actuators")
        actuators = storage.list_actuators()
        logger.info(f"Found {len(actuators)} actuators")
        return jsonify(actuators)

    @bp.route("/plants", methods=["GET"])
    def list_plants():
        """Return all registered plants."""
        logger.info("Listing plants")
        plants = storage.list_plants()
        logger.info(f"Found {len(plants)} plants")
        return jsonify(plants)

    @bp.route("/bind_actuator", methods=["POST"])
    def bind_actuator():
        """Register an actuator and return its assigned ID."""
        logger.info("Binding actuator to the database")

        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        if payload is None:
            return jsonify({"error": "Missing JSON payload"}), 400

        try:
            plant_id = int(payload["plant_id"])
            name = str(payload["name"])
            pin = int(payload["pin"])
            relay_channel = int(payload["relay_channel"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.error(f"Invalid actuator payload: {exc}")
            return jsonify({"error": "Invalid actuator payload"}), 400

        actuator_id = storage.register_actuator(plant_id, name, pin, relay_channel)
        return jsonify({"status": "Actuator bound successfully", "actuator_id": actuator_id}), 200

    @bp.route("/actions/log", methods=["POST"])
    def log_action_execution():
        """Upsert an action execution status record."""
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        if payload is None:
            return jsonify({"error": "Missing JSON payload"}), 400

        try:
            action = load("generic", ActionCommand, payload["action"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.error(f"Invalid action logging payload: {exc}")
            return jsonify({"error": "Invalid action logging payload"}), 400

        if action.status is None:
            return jsonify({"error": "Invalid action logging payload"}), 400

        storage.log_action_execution(action=action)
        return jsonify({"status": "ok"}), 200

    # ---------------------------------------------------------------------- #
    # Controller data
    # ---------------------------------------------------------------------- #
    @bp.route("/controller/mode", methods=["GET"])
    def get_controller_mode():
        """Get controller mode for a plant."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        mode = storage.get_mode(plant_id)
        return jsonify(dump("generic", mode))

    @bp.route("/controller/mode", methods=["PUT"])
    def set_controller_mode():
        """Set controller mode for a plant."""
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        if payload is None:
            return jsonify({"error": "Missing JSON payload"}), 400

        try:
            mode = load("generic", ControlMode, payload)
        except Exception as exc:
            logger.error(f"Invalid controller mode payload: {exc}")
            return jsonify({"error": "Invalid controller mode payload"}), 400

        storage.set_mode(mode)
        return jsonify({"status": "ok"}), 200

    @bp.route("/controller/routines", methods=["GET"])
    def list_controller_routines():
        """List routines for a plant."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        routines = storage.get_routines(plant_id)
        return jsonify([dump("generic", routine) for routine in routines])

    @bp.route("/controller/routines", methods=["POST"])
    def create_controller_routine():
        """Create a new routine."""
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        if payload is None:
            return jsonify({"error": "Missing JSON payload"}), 400

        try:
            routine = load("generic", RoutineUpdate, payload)
        except (TypeError, ValueError) as exc:
            logger.error(f"Invalid routine payload: {exc}")
            return jsonify({"error": "Invalid routine payload"}), 400

        if routine.plant_id is None or routine.name is None or routine.graph is None:
            return jsonify({"error": "plant_id, name, and graph are required"}), 400
        if routine.compiled_rules is None:
            return jsonify({"error": "compiled_rules is required"}), 400

        routine_id = storage.create_routine(routine)
        return jsonify({"id": routine_id, "status": "created"}), 201

    @bp.route("/controller/routines/<int:routine_id>", methods=["PUT"])
    def update_controller_routine(routine_id: int):
        """Update a routine."""
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        if payload is None:
            return jsonify({"error": "Missing JSON payload"}), 400

        try:
            updates = load("generic", RoutineUpdate, payload)
        except Exception as exc:
            logger.error(f"Invalid routine update payload: {exc}")
            return jsonify({"error": "Invalid routine update payload"}), 400

        storage.update_routine(routine_id, updates)
        return jsonify({"status": "updated"}), 200

    @bp.route("/controller/routines/<int:routine_id>", methods=["DELETE"])
    def delete_controller_routine(routine_id: int):
        """Delete a routine."""
        storage.delete_routine(routine_id)
        return jsonify({"status": "deleted"}), 200

    @bp.route("/controller/actions/history", methods=["GET"])
    def get_controller_action_history():
        """Get action execution history."""
        plant_id = request.args.get("plant_id", type=int)
        limit = request.args.get("limit", default=50, type=int)

        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        history = storage.get_action_history(plant_id, limit)
        return jsonify([dump("generic", item) for item in history])

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
