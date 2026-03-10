import time
import uuid

from dt.ai.image_metrics import compute_green_ratio
from dt.communication.dataclasses import CameraSnapshot, RawSensorData
from dt.communication.messaging_service import KafkaService, MessagingService
from dt.communication.topics import Topics
from dt.utils import Config, get_logger

logger = get_logger(__name__)


class ImageAnalysisService:
    """Analyze raw camera snapshots and publish derived green-ratio readings."""

    def __init__(self, messaging_service: MessagingService, green_threshold: float = 0.05) -> None:
        self.messaging_service = messaging_service
        self.green_threshold = green_threshold
        self.logger = get_logger(__name__)

    def start(self) -> None:
        """Start consuming raw camera snapshots."""
        self.messaging_service.subscribe(Topics.CAMERA_IMAGE.raw, self._on_snapshot)
        self.logger.info(f"Subscribed to {Topics.CAMERA_IMAGE.raw}")

    def shutdown(self) -> None:
        """Disconnect the messaging service."""
        self.logger.info("Shutting down image analysis service")
        self.messaging_service.disconnect()

    def build_green_ratio_reading(self, snapshot: CameraSnapshot) -> RawSensorData:
        """Build a derived raw reading from one camera snapshot."""
        ratio = compute_green_ratio(snapshot.image, threshold=self.green_threshold) * 100.0
        return RawSensorData(
            plant_id=snapshot.plant_id,
            sensor_id=snapshot.sensor_id,
            timestamp=snapshot.timestamp,
            value=ratio,
            unit="%",
            topic=Topics.GREEN_RATIO,
            correlation_id=snapshot.correlation_id,
        )

    def _on_snapshot(self, snapshot: CameraSnapshot) -> None:
        """Transform one snapshot into a derived raw green-ratio reading."""
        try:
            reading = self.build_green_ratio_reading(snapshot)
            if not self.messaging_service.publish(Topics.GREEN_RATIO.raw, reading):
                self.logger.error(
                    f"Failed to publish green ratio reading for correlation_id="
                    f"{snapshot.correlation_id}"
                )
        except Exception as exc:
            self.logger.error(
                f"Failed to analyze camera snapshot for correlation_id={snapshot.correlation_id}: "
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
