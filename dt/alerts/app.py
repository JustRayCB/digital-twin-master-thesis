"""Alert engine application factory.

Provides create_app() entrypoint that bundles Flask blueprint, registry,
evaluator, publisher, and consumer thread.
"""

import uuid

from flask import Flask
from flask_cors import CORS

from dt.alerts.api import create_alert_blueprint
from dt.alerts.evaluator import RuleEvaluator
from dt.alerts.publisher import AlertPublisher
from dt.alerts.registry import AlertRegistry
from dt.alerts.rule_manager import build_alert_rule_manager
from dt.alerts.service import AlertEngineService
from dt.communication.dataclasses.queries import ActiveAlertsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService
from dt.utils import Config, get_logger

logger = get_logger(__name__)


def create_app(
    start_consumer: bool = True, config_path: str | None = None, definition_client=None
) -> Flask:
    """Create and configure the alert engine Flask application.

    This factory function wires together all alert engine components:
    - Loads alert rules from configuration
    - Instantiates registry, evaluator, publisher, and consumer service
    - Registers Flask blueprints for REST API
    - Optionally starts the Kafka consumer in the background

    Parameters
    ----------
    start_consumer : bool, optional
        Whether to start the Kafka consumer service, by default True.
        Set to False in tests to avoid background threads.
    config_path : str | None, optional
        Path to alert rules configuration file, by default None.
        If None, uses Config.ALERT_RULES_PATH.

    Returns
    -------
    Flask
        Configured Flask application instance.
    """
    app = Flask(__name__)
    CORS(app)

    # Load alert rules from configuration
    rules_path = config_path or Config.ALERT_RULES_PATH
    logger.info(f"Loading alert rules from {rules_path}")
    rule_manager = build_alert_rule_manager(rules_path)
    logger.info(f"Loaded {len(rule_manager)} alert rules")

    # Instantiate alert engine components
    registry = AlertRegistry()
    evaluator = RuleEvaluator(rule_manager.rules)

    # Create messaging service for publishing alerts
    # Use a unique client ID for the alert engine
    unique_id = f"alert_engine_{uuid.uuid4().hex[:8]}"
    messaging_service = KafkaService(
        host=Config.KAFKA_URL, client_id=unique_id, group_id="alert_engine_group"
    )

    # Connect to Kafka
    if not messaging_service.connect():
        logger.error("Failed to connect to Kafka broker")
        raise ConnectionError("Failed to connect to Kafka broker")

    # Create publisher with definition client
    definition_client = definition_client or DatabaseApiClient()
    publisher = AlertPublisher(messaging_service, definition_client)

    # Hydrate registry from persistent storage
    try:
        active_alerts = definition_client.get_active_alerts(ActiveAlertsQuery())
        registry.restore_state(active_alerts)
        logger.info(f"Restored {len(active_alerts)} active alerts from database")
    except Exception as e:
        logger.warning(f"Failed to restore active alerts from database: {e}")

    # Create alert engine service
    service = AlertEngineService(
        kafka_service=messaging_service,
        evaluator=evaluator,
        registry=registry,
        publisher=publisher,
    )

    # Store service components in app config for access by blueprints
    app.config["ALERT_REGISTRY"] = registry
    app.config["ALERT_PUBLISHER"] = publisher
    app.config["ALERT_RULE_MANAGER"] = rule_manager
    app.config["ALERT_SERVICE"] = service

    # Register Flask blueprints
    alerts_bp, rules_bp = create_alert_blueprint(registry, publisher, rule_manager)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)

    logger.info("Registered alert API blueprints")

    # Start Kafka consumer if requested
    if start_consumer:
        logger.info("Starting Kafka consumer service")
        service.start()
    else:
        logger.info("Kafka consumer service not started (start_consumer=False)")

    return app


def run(host: str = "0.0.0.0", port: int = 5003, debug: bool = False) -> None:
    """Run the alert engine Flask application.

    Convenience function that creates the app and starts the Flask development server.

    Parameters
    ----------
    host : str, optional
        The hostname to bind to, by default "0.0.0.0".
    port : int, optional
        The port to bind to, by default 5003.
    debug : bool, optional
        Whether to run in debug mode, by default False.
    """
    logger.info(f"Starting alert engine service on {host}:{port}")
    app = create_app(start_consumer=True)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run()
