"""REST API Blueprint for the Webapp.

This module provides the API endpoints that the webapp frontend consumes.
It proxies requests to the database service, handling timestamp conversions
between the browser (milliseconds) and the backend (seconds).
"""

from flask import Blueprint, jsonify, request

from dt.communication.adapters import dump, load
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


def create_webapp_blueprint(db_client: DatabaseApiClient) -> Blueprint:
    """Create the webapp API blueprint."""
    bp = Blueprint("api", __name__, url_prefix="/api")

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

    @bp.route("/sensors", methods=["GET"])
    def get_sensors():
        """List sensors."""
        try:
            sensors = db_client.list_sensors()
            return jsonify([dump("generic", s) for s in sensors])
        except Exception as e:
            logger.error(f"Error listing sensors: {e}")
            return jsonify({"error": "Internal server error"}), 500

    return bp
