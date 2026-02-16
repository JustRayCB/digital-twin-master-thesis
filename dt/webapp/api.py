"""REST API Blueprint for the Webapp.

This module provides the API endpoints that the webapp frontend consumes.
It proxies requests to the database service, handling timestamp conversions
between the browser (milliseconds) and the backend (seconds).
"""

from flask import Blueprint, jsonify, request

from dt.communication.adapters import dump, load
from dt.communication.controller_client import ControllerClient
from dt.communication.dataclasses.controller import ActionDispatch, RoutineCreate, RoutineUpdate
from dt.communication.dataclasses.queries import ActiveAlertsQuery, AlertHistoryQuery, ReadingsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.utils import get_logger

logger = get_logger(__name__)

MS_IN_SECOND = 1000.0


def convert_timestamp_for_browser(item_dict: dict) -> dict:
    """Convert DB payload timestamps to JS-friendly shape.

    The database service returns timestamps in seconds:
    - Raw readings: `timestamp`
    - Aggregates: `bucket`

    The browser expects:
    - `time` in milliseconds
    """
    if "timestamp" in item_dict:
        item_dict["time"] = int(item_dict["timestamp"] * MS_IN_SECOND)
        del item_dict["timestamp"]
        return item_dict

    if "bucket" in item_dict:
        item_dict["time"] = int(item_dict["bucket"] * MS_IN_SECOND)
        del item_dict["bucket"]
        return item_dict

    return item_dict


def create_webapp_blueprint(
    db_client: DatabaseApiClient, controller_client: ControllerClient
) -> Blueprint:
    """Create the webapp API blueprint."""
    bp = Blueprint("api", __name__, url_prefix="/api")

    # ---------------------------------------------------------------------- #
    # Readings
    # ---------------------------------------------------------------------- #
    @bp.route("/readings", methods=["GET"])
    def get_readings():
        """Get processed readings or aggregates.

        Query params (JS friendly):
        - since: timestamp in ms
        - until: timestamp in ms
        - topic: str
        - sensor_id: int
        - plant_id: int
        - window: 'raw' or '1h'
        """
        try:
            query = load("generic", ReadingsQuery, request.args.to_dict())

            # Convert ms -> s
            query.since = float(query.since) / MS_IN_SECOND if query.since else None
            query.until = float(query.until) / MS_IN_SECOND if query.until else None

            results = db_client.query_readings(query)

            # Serialize and convert s -> ms
            data = [convert_timestamp_for_browser(dump("generic", item)) for item in results]

            return jsonify(data)

        except ValueError as e:
            logger.warning(f"Invalid query parameters: {e}")
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error fetching readings: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # ---------------------------------------------------------------------- #
    # Alerts
    # ---------------------------------------------------------------------- #
    @bp.route("/alerts/active", methods=["GET"])
    def get_active_alerts():
        """Get active alerts."""
        try:
            query = load("generic", ActiveAlertsQuery, request.args.to_dict())

            alerts = db_client.get_active_alerts(query)

            data = []
            for alert in alerts:
                alert_dict = dump("generic", alert)
                data.append(convert_timestamp_for_browser(alert_dict))

            return jsonify(data)

        except Exception as e:
            logger.error(f"Error fetching active alerts: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/alerts/history", methods=["GET"])
    def get_alert_history():
        """Get alert history."""
        try:
            query = load("generic", AlertHistoryQuery, request.args.to_dict())

            history = db_client.get_alert_history(query)

            data = []
            for event in history:
                event_dict = dump("generic", event)
                data.append(convert_timestamp_for_browser(event_dict))

            return jsonify(data)

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error fetching alert history: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # ---------------------------------------------------------------------- #
    # Metadata
    # ---------------------------------------------------------------------- #
    @bp.route("/sensors", methods=["GET"])
    def get_sensors():
        """List sensors."""
        try:
            sensors = db_client.list_sensors()
            return jsonify([dump("generic", s) for s in sensors])
        except Exception as e:
            logger.error(f"Error listing sensors: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/actuators", methods=["GET"])
    def get_actuators():
        """List actuators."""
        try:
            # We fetch actuators from DB service which has access to `actuators` table
            actuators = db_client.list_actuators()
            return jsonify(actuators)
        except Exception as e:
            logger.error(f"Error listing actuators: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # ---------------------------------------------------------------------- #
    # Controller
    # ---------------------------------------------------------------------- #
    @bp.route("/control/mode", methods=["GET"])
    def get_control_mode():
        """Get control mode."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400
        try:
            mode = controller_client.get_mode(plant_id)
            return jsonify(dump("generic", mode))
        except Exception as e:
            logger.error(f"Error getting control mode: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/control/mode", methods=["PUT"])
    def set_control_mode():
        """Set control mode."""
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400
        try:
            mode = controller_client.set_mode(
                data["plant_id"], data["ai_autopilot_enabled"], data["owner"]
            )
            return jsonify(dump("generic", mode))
        except Exception as e:
            logger.error(f"Error setting control mode: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines", methods=["GET"])
    def list_routines():
        """List routines."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400
        try:
            routines = controller_client.list_routines(plant_id)
            return jsonify([dump("generic", r) for r in routines])
        except Exception as e:
            logger.error(f"Error listing routines: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines", methods=["POST"])
    def create_routine():
        """Create routine."""
        data = request.json
        try:
            routine_create = load("generic", RoutineCreate, data)
            new_id = controller_client.create_routine(routine_create)
            return jsonify({"id": new_id, "status": "created"}), 201
        except Exception as e:
            logger.error(f"Error creating routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines/<int:routine_id>", methods=["PUT"])
    def update_routine(routine_id):
        """Update routine."""
        data = request.json
        try:
            routine_update = load("generic", RoutineUpdate, data)
            controller_client.update_routine(routine_id, routine_update)
            return jsonify({"status": "updated"})
        except Exception as e:
            logger.error(f"Error updating routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines/<int:routine_id>", methods=["DELETE"])
    def delete_routine(routine_id):
        """Delete routine."""
        try:
            controller_client.delete_routine(routine_id)
            return jsonify({"status": "deleted"})
        except Exception as e:
            logger.error(f"Error deleting routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/actions/dispatch", methods=["POST"])
    def dispatch_action():
        """Dispatch action."""
        data = request.json
        try:
            payload = load("generic", ActionDispatch, data)
            return jsonify(controller_client.dispatch_action(payload))
        except Exception as e:
            logger.error(f"Error dispatching action: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/actions/history", methods=["GET"])
    def get_action_history():
        """Get action history."""
        plant_id = request.args.get("plant_id", type=int)
        limit = request.args.get("limit", default=50, type=int)
        try:
            return jsonify(controller_client.get_action_history(plant_id, limit))
        except Exception as e:
            logger.error(f"Error getting action history: {e}")
            return jsonify({"error": str(e)}), 500

    return bp
