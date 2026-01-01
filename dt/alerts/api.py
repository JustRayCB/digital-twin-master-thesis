"""Alert service REST API.

Flask blueprint providing endpoints for alert submission, acknowledgment,
clearing, and listing active alerts.
"""

from __future__ import annotations

import time
from typing import Any

import cattrs.errors
from flask import Blueprint, jsonify, request

from dt.alerts.registry import AlertRegistry
from dt.alerts.rule_manager import AlertRuleManager
from dt.alerts.rules import SeverityLevel
from dt.communication.adapters import dump
from dt.communication.dataclasses.alerts.alert_record import (
    AlertDefinition,
    AlertHistoryEvent,
    AlertStatus,
    ExternalAlertEvent,
)
from dt.communication.dataclasses.alerts.alert_type import AlertType


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
        """Submit a new external alert.

        Expects JSON payload with alert submission data:
        - alert_key: Unique identifier for this alert
        - plant_id: Plant identifier
        - severity: Severity level (info, warning, error, critical)
        - message: Human-readable alert message
        - correlation_id: Correlation ID for tracing
        - metadata: Additional context (dict)
        - persistence_count: Optional, defaults to 1
        - cooldown_seconds: Optional, defaults to 300

        Returns
        -------
        flask.Response
            202 with alert_key on success, 400 on validation error.
        """
        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400

        if data is None:
            return jsonify({"error": "Invalid JSON"}), 400

        try:
            # Extract persistence and cooldown settings (with defaults)
            persistence_count = int(data.pop("persistence_count", 1))
            cooldown_seconds = int(data.pop("cooldown_seconds", 300))

            if persistence_count < 1 or cooldown_seconds < 0:
                return jsonify({"error": "Invalid persistence_count or cooldown_seconds"}), 400

            required = ["alert_key", "plant_id", "severity", "message", "correlation_id"]
            for field in required:
                if field not in data or data[field] in (None, ""):
                    return jsonify({"error": f"Missing required field: {field}"}), 400

            try:
                severity = SeverityLevel(data["severity"])
            except ValueError:
                return jsonify({"error": f"Invalid severity: {data['severity']}"}), 400

            alert_key = str(data["alert_key"])
            plant_id = int(data["plant_id"])

            alert_event = ExternalAlertEvent(
                alert_key=alert_key,
                plant_id=plant_id,
                timestamp=time.time(),
                status=AlertStatus.ACTIVE,
                severity=severity,
                message=data["message"],
                correlation_id=data["correlation_id"],
                metadata=data.get("metadata", {}),
            )

            definition = AlertDefinition(
                alert_key=alert_key,
                plant_id=plant_id,
                sensor_id=data.get("sensor_id"),
                source=str(data.get("source", "external")),
                rule_id=None,
                rule_name=None,
                kind=AlertType.EXTERNAL,
                persistence_count=persistence_count,
                cooldown_seconds=cooldown_seconds,
            )

            status = registry.register(
                alert_event, definition.persistence_count, definition.cooldown_seconds
            )
            alert_event.status = status

            # Publish lifecycle events for explicit state changes
            # Broadcast only when active
            if status == AlertStatus.ACTIVE:
                publisher.publish(definition, alert_event)

            return (
                jsonify({"alert_key": alert_event.alert_key, "status": alert_event.status.value}),
                202,
            )

        except (ValueError, KeyError, cattrs.errors.ClassValidationError) as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    @bp.route("/<alert_key>/acknowledge", methods=["POST"])
    def acknowledge_alert(alert_key: str):
        """Acknowledge an alert.

        Expects JSON payload with 'actor' field.

        Parameters
        ----------
        alert_key : str
            The alert key to acknowledge.

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

            # Get alert state from registry
            alert_state = registry.get_alert_state(alert_key)
            if alert_state is None:
                return jsonify({"error": f"Alert '{alert_key}' not found"}), 404

            # Update registry
            registry.acknowledge(alert_key, actor)

            # Create minimal alert event for publishing
            alert_event = AlertHistoryEvent(
                alert_key=alert_key,
                plant_id=alert_state.plant_id,
                timestamp=time.time(),
                status=AlertStatus.ACKNOWLEDGED,
                severity=alert_state.severity,
                message=alert_state.message,
                correlation_id=alert_state.correlation_id,
                acknowledged_by=actor,
            )

            definition = AlertDefinition(
                alert_key=alert_key,
                plant_id=alert_state.plant_id,
                sensor_id=None,
                source=alert_state.source,
                rule_id=alert_state.rule_id,
                rule_name=alert_state.rule_id,
                kind=AlertType.EXTERNAL if alert_state.rule_id is None else AlertType.SENSOR,
                persistence_count=1,
                cooldown_seconds=300,
            )

            publisher.publish(definition, alert_event)

            return jsonify({"status": "acknowledged", "alert_key": alert_key}), 200

        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    @bp.route("/<alert_key>/clear", methods=["POST"])
    def clear_alert(alert_key: str):
        """Clear an alert.

        Parameters
        ----------
        alert_key : str
            The alert key to clear.

        Returns
        -------
        flask.Response
            200 on success, 404 if alert not found.
        """
        try:
            # Get alert state from registry
            alert_state = registry.get_alert_state(alert_key)
            if alert_state is None:
                return jsonify({"error": f"Alert '{alert_key}' not found"}), 404

            # Update registry
            success = registry.clear(alert_key)
            if not success:
                return jsonify({"error": f"Alert '{alert_key}' not found"}), 404

            # Create minimal alert event for publishing
            alert_event = AlertHistoryEvent(
                alert_key=alert_key,
                plant_id=alert_state.plant_id,
                timestamp=time.time(),
                status=AlertStatus.CLEARED,
                severity=alert_state.severity,
                message=alert_state.message,
                correlation_id=alert_state.correlation_id,
                acknowledged_by=alert_state.acknowledged_by,
            )

            definition = AlertDefinition(
                alert_key=alert_key,
                plant_id=alert_state.plant_id,
                sensor_id=None,
                source=alert_state.source,
                rule_id=alert_state.rule_id,
                rule_name=alert_state.rule_id,
                kind=AlertType.EXTERNAL if alert_state.rule_id is None else AlertType.SENSOR,
                persistence_count=1,
                cooldown_seconds=300,
            )

            publisher.publish(definition, alert_event)

            return jsonify({"status": "cleared", "alert_key": alert_key}), 200

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
            rule_dicts = [dump("generic", rule) for rule in rules]

            return jsonify(rule_dicts), 200

        except Exception as e:
            return jsonify({"error": f"Internal error: {str(e)}"}), 500

    return bp, rules_bp
