"""Main Flask application for the web dashboard.

This application serves the main dashboard for the digital twin project.
It has the following key responsibilities:

1.  Web Interface: Renders the main `dashboard.html` template, which
    provides the user interface for monitoring and controlling the digital
    twin.

2.  Real-time Updates: Sets up a Flask-SocketIO server to push real-time
    sensor data to connected web clients.

3.  Messaging Bridge: Initializes a Kafka client that subscribes to
    processed sensor data topics. When a message is received, it is
    broadcast to the appropriate SocketIO room, allowing for live updates
    on the dashboard.

4.  API Endpoints: Provides API endpoints for the frontend to fetch
    historical data from the database service.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO

import dt.webapp.consumer as consumer
from dt.communication.controller_client import ControllerClient
from dt.communication.db_client import DatabaseApiClient
from dt.utils import get_logger
from dt.webapp.api import create_webapp_blueprint
from dt.webapp.ui import create_ui_blueprint, default_ui_dir

# Global SocketIO instance (initialized in create_app)
socketio = SocketIO(cors_allowed_origins="*")
logger = get_logger(__name__)


# Simulated data for initial render (to be replaced by real data fetching)
dashboard_data = {
    # Plant Status Data
    "last_update": datetime.now().strftime("%H:%M"),
    "temperature": 23,
    "humidity": 45,
    "light": 780,
    "connection_status": "Connected",
    "health_status": "Good",
    "health_details": "Growing normally, soil drying",
    "alerts": [],
    # Parameter Controls Data
    "control_mode": "Auto",
    "temp_setpoint": 23,
    "humidity_setpoint": 45,
    "soil_setpoint": 25,
    "soil_moisture": 25,
    # Real-time Monitoring Data (placeholders)
    "monitoring_period": "24h",
    "temp_history": [],
    "humidity_history": [],
    "soil_history": [],
    "light_history": [],
    # Quick Actions & Insights Data
    "recommendations": [
        "Water within next 8 hours",
        "Light levels optimal",
        "Temperature trending higher",
        "Soil pH stable",
    ],
}


def create_app(
    start_consumer: bool = True,
    db_client: Optional[DatabaseApiClient] = None,
    controller_client: Optional[ControllerClient] = None,
    ui_dir: Optional[Path] = None,
) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    start_consumer : bool, optional
        Whether to start the Kafka consumer background thread, by default True.
    db_client : DatabaseApiClient | None, optional
        Dependency injection for the database client. If None, a new one is created.
    controller_client : ControllerClient | None, optional
        Dependency injection for the controller client. If None, a new one is created.
    ui_dir : Path | None, optional
        Directory containing a built UI (expects `index.html` plus assets). If None,
        defaults to `dt/webapp/static/ui`.

    Returns
    -------
    Flask
        The configured Flask application.
    """
    app = Flask(__name__)
    CORS(app)

    # Initialize SocketIO with this app
    socketio.init_app(app)

    # Dependency Injection
    if db_client is None:
        db_client = DatabaseApiClient()

    if controller_client is None:
        controller_client = ControllerClient()

    # Register API Blueprint
    api_bp = create_webapp_blueprint(db_client, controller_client)
    app.register_blueprint(api_bp)

    # Register UI Blueprint
    resolved_ui_dir = default_ui_dir() if ui_dir is None else ui_dir
    app.register_blueprint(create_ui_blueprint(resolved_ui_dir))

    # Routes
    @app.route("/")
    def dashboard():
        return render_template("dashboard.html", data=dashboard_data)

    # Kafka / Real-time Setup
    if start_consumer:
        # We attach the client to the app to keep it alive
        app.msg_client = consumer.setup_bridge(db_client, socketio)  # type: ignore

    return app


# Handle client connection
@socketio.on("connect")
def connect():
    """Handle a new client connection to the SocketIO server.

    This function is called when a new client establishes a connection. It
    logs the connection and emits the current connection status to the
    client.
    """
    logger.info("Client connected")
    socketio.emit("connection_status", {"connected": consumer.connection_status})
    with consumer.latest_by_topic_lock:
        cached = list(consumer.latest_by_topic.items())
    for topic, payload in cached:
        socketio.emit(topic, payload)
    with consumer.active_alerts_lock:
        cached_alerts = list(consumer.active_alerts_by_key.values())
    for payload in cached_alerts:
        socketio.emit("alerts_update", payload)


@socketio.on("disconnect")
def disconnect():
    """Handle a client disconnection from the SocketIO server.

    This function is called when a client disconnects. It logs the
    disconnection event.
    """
    logger.info("Client disconnected")


if __name__ == "__main__":
    import argparse
    import os

    # Ensure the setup runs only once, not in the reloader process
    in_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    debug_mode = True

    parser = argparse.ArgumentParser(
        description="Run the Digital Twin dashboard webapp.",
        epilog="Example: python -m dt.webapp.app --demo --demo-interval 0.5",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Emit synthetic readings/alerts via Socket.IO (no Kafka required).",
    )
    parser.add_argument(
        "--demo-interval",
        type=float,
        default=1.0,
        help="Seconds between demo emissions (default: 1.0).",
    )
    args = parser.parse_args()

    start_consumer = not args.demo
    app = create_app(start_consumer=(start_consumer and (not debug_mode or in_reloader)))

    if args.demo and (not debug_mode or in_reloader):
        from dt.webapp.demo import DemoConfig, start_demo_emitter

        start_demo_emitter(
            socketio,
            DemoConfig(plant_id=1, interval_seconds=args.demo_interval),
        )

    socketio.run(app, debug=debug_mode, host=args.host, port=args.port)
