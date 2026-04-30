"""REST API Blueprint for the Webapp.

This module provides the API endpoints that the webapp frontend consumes.
It proxies requests to the database service.
"""

from flask import Blueprint, jsonify, request

from dt.communication.adapters import dump, load
from dt.communication.controller_client import ControllerClient
from dt.communication.dataclasses.controller import (ActionDispatch,
                                                     RoutineUpdate)
from dt.communication.dataclasses.queries import (ActiveAlertsQuery,
                                                   AlertHistoryQuery,
                                                   ForecastHistoryQuery,
                                                   HealthHistoryQuery,
                                                   ReadingsQuery,
                                                   RecommendationHistoryQuery)
from dt.communication.db_client import DatabaseApiClient
from dt.utils import get_logger

logger = get_logger(__name__)


def create_webapp_blueprint(
    db_client: DatabaseApiClient, controller_client: ControllerClient
) -> Blueprint:
    """Create the webapp API blueprint."""
    bp = Blueprint("api", __name__, url_prefix="/api")

    # ---------------------------------------------------------------------- #
    # Readings
    # ---------------------------------------------------------------------- #
    @bp.route("/db/readings", methods=["GET"])
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
            query = load("web", ReadingsQuery, request.args.to_dict())

            results = db_client.query_readings(query)

            # Serialize and convert s -> ms
            data = [dump("web", item) for item in results]

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
    @bp.route("/db/alerts/active", methods=["GET"])
    def get_active_alerts():
        """Get active alerts."""
        try:
            query = load("generic", ActiveAlertsQuery, request.args.to_dict())

            alerts = db_client.get_active_alerts(query)

            data = []
            for alert in alerts:
                data.append(dump("web", alert))

            return jsonify(data)

        except Exception as e:
            logger.error(f"Error fetching active alerts: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/db/alerts/history", methods=["GET"])
    def get_alert_history():
        """Get alert history."""
        try:
            query = load("generic", AlertHistoryQuery, request.args.to_dict())

            history = db_client.get_alert_history(query)

            data = []
            for event in history:
                data.append(dump("web", event))

            return jsonify(data)

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error fetching alert history: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/db/camera/snapshots/latest", methods=["GET"])
    def get_latest_camera_snapshot():
        """Get latest camera snapshot for a plant with browser-friendly timestamp."""
        plant_id = request.args.get("plant_id", default=1, type=int)
        try:
            snapshot = db_client.get_latest_camera_snapshot(plant_id)
            if snapshot is None:
                return jsonify({"error": "No camera snapshot found"}), 404

            payload = dump("web", snapshot)
            payload.pop("topic", None)
            return jsonify(payload), 200

        except Exception as e:
            logger.error(f"Error fetching latest camera snapshot: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # ---------------------------------------------------------------------- #
    # Metadata
    # ---------------------------------------------------------------------- #
    @bp.route("/db/sensors", methods=["GET"])
    def get_sensors():
        """List sensors."""
        try:
            sensors = db_client.list_sensors()
            return jsonify([dump("generic", s) for s in sensors])
        except Exception as e:
            logger.error(f"Error listing sensors: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/db/actuators", methods=["GET"])
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
    # Analytics
    # ---------------------------------------------------------------------- #
    @bp.route("/analytics/recommendations", methods=["GET"])
    def get_recommendation_history():
        """Get recommendation lifecycle history."""
        try:
            query = load("generic", RecommendationHistoryQuery, request.args.to_dict())
            recommendations = db_client.get_recommendation_history(query)
            return jsonify([dump("web", recommendation) for recommendation in recommendations])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error fetching recommendation history: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/db/health", methods=["GET"])
    def get_health_history():
        """Get plant health assessment history."""
        try:
            query = load("web", HealthHistoryQuery, request.args.to_dict())
            assessments = db_client.get_health_history(query)
            return jsonify([dump("web", assessment) for assessment in assessments])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error fetching health history: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @bp.route("/db/forecasts", methods=["GET"])
    def get_forecast_history():
        """Get forecast result history."""
        try:
            query = load("web", ForecastHistoryQuery, request.args.to_dict())
            forecasts = db_client.get_forecast_history(query)
            return jsonify([dump("web", forecast) for forecast in forecasts])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error fetching forecast history: {e}")
            return jsonify({"error": "Internal server error"}), 500

    # ---------------------------------------------------------------------- #
    # Controller
    # ---------------------------------------------------------------------- #
    @bp.route("/controller/mode", methods=["GET"])
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

    @bp.route("/controller/mode", methods=["PUT"])
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

    @bp.route("/controller/routines", methods=["GET"])
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

    @bp.route("/controller/routines", methods=["POST"])
    def create_routine():
        """Create routine."""
        data = request.json
        try:
            routine_create = load("generic", RoutineUpdate, data)
            new_id = controller_client.create_routine(routine_create)
            return jsonify({"id": new_id, "status": "created"}), 201
        except Exception as e:
            logger.error(f"Error creating routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/controller/routines/<int:routine_id>", methods=["PUT"])
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

    @bp.route("/controller/routines/<int:routine_id>", methods=["DELETE"])
    def delete_routine(routine_id):
        """Delete routine."""
        try:
            controller_client.delete_routine(routine_id)
            return jsonify({"status": "deleted"})
        except Exception as e:
            logger.error(f"Error deleting routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/controller/actions/dispatch", methods=["POST"])
    def dispatch_action():
        """Dispatch action."""
        data = request.json
        try:
            payload = load("generic", ActionDispatch, data)
            return jsonify(controller_client.dispatch_action(payload))
        except Exception as e:
            logger.error(f"Error dispatching action: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/controller/actions/history", methods=["GET"])
    def get_action_history():
        plant_id = request.args.get("plant_id", default=1, type=int)
        limit = request.args.get("limit", default=50, type=int)
        try:
            actions = controller_client.get_action_history(plant_id, limit)
            return jsonify([dump("web", a) for a in actions])
        except Exception as e:
            logger.error(f"Error getting action history: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/controller/policies", methods=["GET"])
    def get_policies():
        try:
            policies = controller_client.get_policies()
            return jsonify(dump("generic", policies))
        except Exception as e:
            logger.error(f"Error getting policies: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/controller/policies", methods=["PUT"])
    def set_policies():
        data = request.json
        try:
            from dt.communication.dataclasses.controller import \
                ActuatorConfigSet

            policies = load("generic", ActuatorConfigSet, data)
            controller_client.set_policies(policies)
            return jsonify({"status": "updated"})
        except Exception as e:
            logger.error(f"Error setting policies: {e}")
            return jsonify({"error": str(e)}), 500

    return bp
