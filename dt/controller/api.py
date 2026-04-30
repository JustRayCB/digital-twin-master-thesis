"""Controller Service API.

Exposes endpoints for managing controller mode, routines, and actions.
"""

from flask import Blueprint, jsonify, request

from dt.communication.adapters import dump, load
from dt.communication.dataclasses.controller import (ActionDispatch,
                                                     ActuatorConfigSet,
                                                     ControlMode,
                                                     RoutineUpdate)
from dt.controller.service import ControllerService
from dt.utils import get_logger

logger = get_logger(__name__)


def create_controller_blueprint(service: ControllerService) -> Blueprint:
    """Create the controller blueprint."""
    bp = Blueprint("controller", __name__, url_prefix="/controller")

    # ---------------------------------------------------------------------- #
    # Mode
    # ---------------------------------------------------------------------- #
    @bp.route("/mode", methods=["GET"])
    def get_mode():
        """Get controller mode for a plant."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        try:
            mode = service.get_mode(plant_id)
            return jsonify(dump("generic", mode))
        except Exception as e:
            logger.error(f"Error fetching mode: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/mode", methods=["PUT"])
    def set_mode():
        """Set controller mode for a plant."""
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        try:
            payload = load("generic", ControlMode, data)
        except Exception as exc:
            return jsonify({"error": f"Invalid payload: {exc}"}), 400

        try:
            mode = service.set_mode(payload)
            return jsonify({"status": "updated", "mode": dump("generic", mode)})
        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            return jsonify({"error": str(e)}), 500

    # ---------------------------------------------------------------------- #
    # Routines
    # ---------------------------------------------------------------------- #
    @bp.route("/routines", methods=["GET"])
    def list_routines():
        """List routines for a plant."""
        plant_id = request.args.get("plant_id", type=int)
        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        try:
            routines = service.list_routines(plant_id)
            return jsonify([dump("generic", routine) for routine in routines])
        except Exception as e:
            logger.error(f"Error listing routines: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines", methods=["POST"])
    def create_routine():
        """Create a new routine."""
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        try:
            routine = load("generic", RoutineUpdate, data)
            routine_id = service.create_routine(routine)

            return jsonify({"id": routine_id, "status": "created"}), 201
        except ValueError as e:
            return jsonify({"error": f"Invalid routine graph: {e}"}), 400
        except Exception as e:
            logger.error(f"Error creating routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines/<int:routine_id>", methods=["PUT"])
    def update_routine(routine_id):
        """Update a routine."""
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        try:
            routine_update = load("generic", RoutineUpdate, data)
            service.update_routine(routine_id, routine_update)

            return jsonify({"status": "updated"})
        except ValueError as e:
            return jsonify({"error": f"Invalid routine graph: {e}"}), 400
        except Exception as e:
            logger.error(f"Error updating routine: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/routines/<int:routine_id>", methods=["DELETE"])
    def delete_routine(routine_id):
        """Delete a routine."""
        plant_id = request.args.get("plant_id", type=int)  # Hint for refresh

        try:
            service.delete_routine(routine_id, plant_id)
            return jsonify({"status": "deleted"})
        except Exception as e:
            logger.error(f"Error deleting routine: {e}")
            return jsonify({"error": str(e)}), 500

    # ---------------------------------------------------------------------- #
    # Actions
    # ---------------------------------------------------------------------- #
    @bp.route("/actions/dispatch", methods=["POST"])
    def dispatch_action():
        """Dispatch a manual or AI action."""
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        try:
            payload = load("generic", ActionDispatch, data)
        except Exception as exc:
            return jsonify({"error": f"Invalid payload: {exc}"}), 400

        try:
            result = service.dispatch_action(payload)
            return jsonify(result)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Error dispatching action: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/actions/history", methods=["GET"])
    def get_action_history():
        """Get action execution history."""
        plant_id = request.args.get("plant_id", type=int)
        limit = request.args.get("limit", default=50, type=int)

        if not plant_id:
            return jsonify({"error": "plant_id is required"}), 400

        try:
            history = service.get_action_history(plant_id, limit)
            return jsonify([dump("generic", item) for item in history])
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return jsonify({"error": str(e)}), 500

    # ---------------------------------------------------------------------- #
    # Policies
    # ---------------------------------------------------------------------- #
    @bp.route("/policies", methods=["GET"])
    def get_policies():
        """Get actuator policies."""
        try:
            policies = service.get_policies()
            return jsonify(dump("generic", policies))
        except Exception as e:
            logger.error(f"Error getting policies: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route("/policies", methods=["PUT"])
    def set_policies():
        """Set actuator policies."""
        data = request.json
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        try:
            policies = load("generic", ActuatorConfigSet, data)
        except Exception as exc:
            return jsonify({"error": f"Invalid payload: {exc}"}), 400

        try:
            service.set_policies(policies)
            return jsonify({"status": "updated"})
        except Exception as e:
            logger.error(f"Error setting policies: {e}")
            return jsonify({"error": str(e)}), 500

    return bp
