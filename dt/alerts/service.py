"""Alert engine Kafka consumer service.

Subscribes to processed sensor topics and drives rule evaluation.
"""

from dt.alerts.engine.evaluator import RuleEvaluator
from dt.alerts.engine.publisher import AlertPublisher
from dt.alerts.state.models import AlertLifecycleEvent
from dt.alerts.state.registry import AlertRegistry
from dt.communication import MessagingService, Topics
from dt.communication.dataclasses import ProcessedSensorData
from dt.utils import get_logger


class AlertEngineService:
    """Kafka consumer service that evaluates alert rules against processed sensor data.

    Subscribes to all processed sensor topics, evaluates configured rules,
    and publishes alert lifecycle events to Kafka.

    Attributes
    ----------
    kafka_service : MessagingService
        Kafka service instance for consuming processed sensor data.
    evaluator : RuleEvaluator
        Rule evaluator for checking alert conditions.
    registry : AlertRegistry
        Alert registry for state management.
    publisher : AlertPublisher
        Alert publisher for Kafka events.
    logger : logging.Logger
        Logger instance.
    """

    def __init__(
        self,
        kafka_service: MessagingService,
        evaluator: RuleEvaluator,
        registry: AlertRegistry,
        publisher: AlertPublisher,
    ) -> None:
        """Initialize the alert engine service.

        Parameters
        ----------
        kafka_service : MessagingService
            Kafka service instance for consuming processed sensor data.
        evaluator : RuleEvaluator
            Rule evaluator for checking alert conditions.
        registry : AlertRegistry
            Alert registry for state management.
        publisher : AlertPublisher
            Alert publisher for Kafka events.
        """
        self.kafka_service = kafka_service
        self.evaluator = evaluator
        self.registry = registry
        self.publisher = publisher
        self.logger = get_logger(__name__)

    def start(self) -> None:
        """Start the alert engine service.

        Subscribes to all processed sensor topics and begins consuming messages.
        For each message, evaluates alert rules and publishes lifecycle events.
        """
        # Subscribe to all processed sensor topics
        sensor_topics = Topics.list_sensor_topics()

        for topic in sensor_topics:
            processed_topic = topic.processed
            self.kafka_service.subscribe(processed_topic, self._on_message)
            self.logger.info(f"Subscribed to {processed_topic}")

    def shutdown(self) -> None:
        """Shut down the alert engine service.

        Disconnects from Kafka and cleans up resources.
        """
        self.logger.info("Shutting down alert engine service")
        self.kafka_service.disconnect()

    def _on_message(self, payload: ProcessedSensorData) -> None:
        """Handle incoming processed sensor data.

        Evaluates alert rules against the payload and publishes lifecycle events
        for any triggered alerts.

        Parameters
        ----------
        payload : ProcessedSensorData
            The processed sensor data to evaluate.
        """
        # Evaluate rules against payload
        candidates = self.evaluator.evaluate(payload)

        # Process each candidate alert
        for candidate in candidates:
            # Register with registry using rule's persistence and cooldown settings
            event = self.registry.register(candidate)

            # Publish lifecycle events for CREATED and UPDATED
            if event in (AlertLifecycleEvent.CREATED, AlertLifecycleEvent.UPDATED):
                self.publisher.publish(event, candidate)
                self.logger.info(
                    f"Published {event.value} alert: {candidate.alert_id} "
                    f"(severity: {candidate.severity.value})"
                )
