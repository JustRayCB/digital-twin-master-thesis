"""Analytics application factory."""

import uuid

from flask import Flask
from flask_cors import CORS

from dt.analytics.alerts.evaluator import RuleEvaluator
from dt.analytics.alerts.api import create_alert_blueprint
from dt.analytics.alerts.publisher import AlertPublisher
from dt.analytics.alerts.registry import AlertRegistry
from dt.analytics.alerts.rule_manager import build_alert_rule_manager
from dt.analytics.alerts.service import AlertEngineService
from dt.analytics.api import create_analytics_blueprint
from dt.analytics.models.classification import PlantHealthBaselineModel
from dt.analytics.features.extractor import FeatureExtractor
from dt.analytics.policies.engine import RecommendationPolicyEngine
from dt.analytics.publisher import AnalyticsPublisher
from dt.analytics.service import AnalyticsService
from dt.communication.dataclasses.queries import ActiveAlertsQuery
from dt.communication.db_client import DatabaseApiClient
from dt.communication.messaging_service import KafkaService
from dt.utils import Config, get_logger

logger = get_logger(__name__)


def create_app(
    start_consumer: bool = True, config_path: str | None = None, definition_client=None
) -> Flask:
    """Create and configure the analytics Flask application."""
    app = Flask(__name__)
    CORS(app)

    rules_path = config_path or Config.ALERT_RULES_PATH
    logger.info(f"Loading alert rules from {rules_path}")
    rule_manager = build_alert_rule_manager(rules_path)
    logger.info(f"Loaded {len(rule_manager)} alert rules")

    registry = AlertRegistry()
    evaluator = RuleEvaluator(rule_manager.rules)

    unique_id = f"analytics_service_{uuid.uuid4().hex[:8]}"
    messaging_service = KafkaService(
        host=Config.KAFKA_URL,
        client_id=unique_id,
        group_id="analytics_service_group",
    )

    if not messaging_service.connect():
        logger.error("Failed to connect to Kafka broker")
        raise ConnectionError("Failed to connect to Kafka broker")

    definition_client = definition_client or DatabaseApiClient()
    alert_publisher = AlertPublisher(messaging_service, definition_client)

    try:
        active_alerts = definition_client.get_active_alerts(ActiveAlertsQuery())
        registry.restore_state(active_alerts)
        logger.info(f"Restored {len(active_alerts)} active alerts from database")
    except Exception as exc:
        logger.warning(f"Failed to restore active alerts from database: {exc}")

    alert_service = AlertEngineService(
        kafka_service=messaging_service,
        evaluator=evaluator,
        registry=registry,
        publisher=alert_publisher,
    )
    feature_extractor = FeatureExtractor()
    publisher = AnalyticsPublisher(messaging_service)
    health_model = PlantHealthBaselineModel()
    recommendation_engine = RecommendationPolicyEngine()
    service = AnalyticsService(
        kafka_service=messaging_service,
        alert_service=alert_service,
        feature_extractor=feature_extractor,
        publisher=publisher,
        db_client=definition_client,
        health_model=health_model,
        recommendation_engine=recommendation_engine,
    )

    app.config["ALERT_REGISTRY"] = registry
    app.config["ALERT_PUBLISHER"] = alert_publisher
    app.config["ALERT_RULE_MANAGER"] = rule_manager
    app.config["ALERT_SERVICE"] = alert_service
    app.config["ANALYTICS_PUBLISHER"] = publisher
    app.config["ANALYTICS_SERVICE"] = service
    app.config["FEATURE_EXTRACTOR"] = feature_extractor
    app.config["HEALTH_MODEL"] = health_model
    app.config["RECOMMENDATION_ENGINE"] = recommendation_engine

    alerts_bp, rules_bp = create_alert_blueprint(registry, alert_publisher, rule_manager)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(create_analytics_blueprint())

    if start_consumer:
        service.start()

    return app


def run(host: str = "0.0.0.0", port: int = 5003, debug: bool = False) -> None:
    logger.info(f"Starting analytics service on {host}:{port}")
    app = create_app(start_consumer=True)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run()
