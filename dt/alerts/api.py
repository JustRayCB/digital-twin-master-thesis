"""Alert service REST API.

Flask blueprint providing endpoints for alert submission, acknowledgment,
clearing, and listing active alerts.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from dt.alerts.config.manager import AlertRuleManager
from dt.alerts.state.models import AlertLifecycleEvent
from dt.alerts.state.registry import AlertRegistry
from dt.communication.dataclasses.alerts import CandidateAlert


def create_alert_blueprint(
    registry: AlertRegistry, publisher: Any, rule_manager: AlertRuleManager
) -> tuple[Blueprint, Blueprint]:
    """Create Flask blueprints for alert service API.

    Parameters
    ----------
    registry : AlertRegistry
        Alert registry instance for state management.
    publisher : Any
        Alert publisher instance for Kafka events.
    rule_manager : AlertRuleManager
        Alert rule manager instance.

    Returns
    -------
    tuple[Blueprint, Blueprint]
        Tuple of (alerts_blueprint, rules_blueprint).
    """
    bp = Blueprint("alerts", __name__, url_prefix="/alerts")
    rules_bp = Blueprint("alert_rules", __name__)

    @bp.route("/submit", methods=["POST"])
    def submit_alert():
        """Submit a new alert.

        Expects JSON payload with alert submission data.

        Returns
        -------
        flask.Response
            202 with alert_id on success, 400 on validation error.
        """
        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        if data is None:
            return jsonify({"error": "Invalid JSON"}), 400

        try:
            candidate = CandidateAlert.from_submission_dict(data)

            # Register with registry
            event = registry.register(candidate)

            # Publish lifecycle events for explicit state changes
            # Broadcast CREATED and UPDATED so downstream consumers see repeated violations
            if event in (AlertLifecycleEvent.CREATED, AlertLifecycleEvent.UPDATED):
                publisher.publish(event, candidate)

            return jsonify({"alert_id": candidate.alert_id, "event": event.value}), 202

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    @bp.route("/<alert_id>/acknowledge", methods=["POST"])
    def acknowledge_alert(alert_id: str):
        """Acknowledge an alert.

        Expects JSON payload with 'actor' field.

        Parameters
        ----------
        alert_id : str
            The alert ID to acknowledge.

        Returns
        -------
        flask.Response
            200 on success, 400 on missing actor, 404 if alert not found.
        """
        try:
            data = request.get_json()
            if data is None or "actor" not in data:
                return jsonify({"error": "Missing required field: actor"}), 400

            actor = data["actor"]
            success = registry.acknowledge(alert_id, actor)

            if not success:
                return jsonify({"error": f"Alert '{alert_id}' not found"}), 404

            # Publish acknowledgment event with actor information
            publisher.publish(AlertLifecycleEvent.ACKNOWLEDGED, alert_id, actor=actor)

            return jsonify({"status": "acknowledged", "alert_id": alert_id}), 200

        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    @bp.route("/<alert_id>/clear", methods=["POST"])
    def clear_alert(alert_id: str):
        """Clear an alert.

        Parameters
        ----------
        alert_id : str
            The alert ID to clear.

        Returns
        -------
        flask.Response
            200 on success, 404 if alert not found.
        """
        try:
            success = registry.clear(alert_id)

            if not success:
                return jsonify({"error": f"Alert '{alert_id}' not found"}), 404

            # Publish clear event (actor could be added in future)
            publisher.publish(AlertLifecycleEvent.CLEARED, alert_id, actor=None)

            return jsonify({"status": "cleared", "alert_id": alert_id}), 200

        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    @bp.route("/active", methods=["GET"])
    def list_active_alerts():
        """List all active alerts.

        Returns
        -------
        flask.Response
            200 with list of active alert states.
        """
        try:
            alerts = registry.get_active_alerts()

            # Serialize alert states to dictionaries
            alert_dicts = [alert.to_dict() for alert in alerts]

            return jsonify(alert_dicts), 200

        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    # Add endpoint to list configured rules on separate blueprint
    @rules_bp.route("/alert-rules", methods=["GET"])
    def list_alert_rules():
        """List all configured alert rules.

        Returns
        -------
        flask.Response
            200 with list of alert rule configurations.
        """
        try:
            rules = rule_manager.rules

            # Serialize rules to dictionaries
            rule_dicts = [rule.to_dict() for rule in rules]

            return jsonify(rule_dicts), 200

        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    return bp, rules_bp
