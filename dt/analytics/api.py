"""Analytics API blueprint scaffold."""

from flask import Blueprint, jsonify


def create_analytics_blueprint() -> Blueprint:
    """Create analytics blueprint scaffold."""
    bp = Blueprint("analytics", __name__, url_prefix="/analytics")

    @bp.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"}), 200

    return bp
