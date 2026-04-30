import time
import uuid

from dt.communication.dataclasses import CameraSnapshot, RawSensorData
from dt.communication.messaging_service import KafkaService, MessagingService
from dt.communication.topics import Topics
from dt.image.extractors import (GreenRatioExtractor, ImageMetricExtractor,
                                 LeafCountExtractor, PlantHeightExtractor)
from dt.utils import Config, get_logger

logger = get_logger(__name__)


class ImageAnalysisService:
    """Analyze raw camera snapshots and publish derived metrics."""

    def __init__(self, messaging_service: MessagingService, green_threshold: float = 0.05) -> None:
        self.messaging_service = messaging_service
        self.logger = get_logger(__name__)

        # Register extractors
        self.extractors: list[ImageMetricExtractor] = [
            GreenRatioExtractor(threshold=green_threshold),
            LeafCountExtractor(),
            PlantHeightExtractor(plant_detection_method="exg"),
        ]

    def start(self) -> None:
        """Start consuming raw camera snapshots."""
        topics_to_subscribe = {extractor.source_topic.raw for extractor in self.extractors}

        for topic in topics_to_subscribe:
            self.messaging_service.subscribe(topic, self._on_snapshot)
            self.logger.info(f"Subscribed to {topic}")

    def shutdown(self) -> None:
        """Disconnect the messaging service."""
        self.logger.info("Shutting down image analysis service")
        self.messaging_service.disconnect()

    def _build_reading(
        self, snapshot: CameraSnapshot, value: float, target_topic: Topics, unit: str = ""
    ) -> RawSensorData:
        """Build a derived raw reading from an extracted metric."""
        self.logger.info(
            f"Building reading for topic={target_topic}, value={value}, unit={unit}, "
            f"correlation_id={snapshot.correlation_id}"
        )
        return RawSensorData(
            plant_id=snapshot.plant_id,
            sensor_id=snapshot.sensor_id,
            timestamp=snapshot.timestamp,
            value=value,
            unit=unit,
            topic=target_topic,
            correlation_id=snapshot.correlation_id,
        )

    def _on_snapshot(self, snapshot: CameraSnapshot) -> None:
        """Transform one snapshot into derived raw readings using extractors."""
        for extractor in self.extractors:
            if extractor.source_topic != snapshot.topic:
                continue

            try:
                value = extractor.extract(snapshot)

                # Determine unit based on topic (could also be part of the Extractor class)
                unit = ""
                if extractor.target_topic == Topics.GREEN_RATIO:
                    unit = "%"
                elif extractor.target_topic == Topics.LEAF_COUNT:
                    unit = "leaves"
                elif extractor.target_topic == Topics.PLANT_HEIGHT:
                    unit = "cm"

                reading = self._build_reading(snapshot, value, extractor.target_topic, unit)
                if not self.messaging_service.publish(extractor.target_topic.raw, reading):
                    self.logger.error(
                        f"Failed to publish {extractor.target_topic} reading for correlation_id="
                        f"{snapshot.correlation_id}"
                    )
            except Exception as exc:
                self.logger.error(
                    f"Failed to extract {extractor.target_topic} for correlation_id={snapshot.correlation_id}: "
                    f"{exc}"
                )


def run(green_threshold: float = 0.05) -> None:
    """Run the image analysis service as a long-lived process."""
    unique_id = f"image_analysis_{uuid.uuid4().hex[:8]}"
    messaging_service: MessagingService = KafkaService(
        host=Config.KAFKA_URL,
        client_id=unique_id,
        group_id="image_analysis_group",
    )
    if not messaging_service.connect():
        logger.error("Failed to connect to Kafka broker")
        raise ConnectionError("Failed to connect to Kafka broker")

    service = ImageAnalysisService(
        messaging_service=messaging_service,
        green_threshold=green_threshold,
    )
    service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping image analysis service (interrupt).")
    finally:
        service.shutdown()


if __name__ == "__main__":
    run()
