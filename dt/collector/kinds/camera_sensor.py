import time
from abc import abstractmethod
from base64 import b64encode
from contextlib import suppress
from io import BytesIO

import requests
from typing_extensions import override

from dt.collector.kinds.base_sensor import Pin, Sensor
from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics
from dt.utils.ids import new_correlation_id


class CameraSensor(Sensor):
    def __init__(
        self,
        name: str,
        read_interval: int,
        pin: Pin = -1,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        super().__init__(name, read_interval, pin)
        self.width = width
        self.height = height
        self._mime_type = "image/jpeg"

    @property
    @override
    def unit(self) -> str:
        return self._mime_type

    @property
    @override
    def topic(self) -> Topics:
        return Topics.CAMERA_IMAGE

    @abstractmethod
    def _capture_jpeg(self) -> bytes | None:
        """Capture a JPEG image and return it as bytes."""
        raise NotImplementedError

    @override
    def read(self) -> CameraSnapshot | None:
        current_time = time.time()
        try:
            image_bytes = self._capture_jpeg()
        except Exception as exc:
            self.logger.error(f"Failed to read {self.name}: {exc}")
            return None

        self.last_read_time = current_time
        if not image_bytes:
            self.logger.error(f"Failed to read {self.name}: no image returned")
            return None

        self.last_data = float(len(image_bytes))
        image_b64 = b64encode(image_bytes).decode("ascii")

        return CameraSnapshot(
            plant_id=self.plant_id,
            sensor_id=self.sensor_id,
            timestamp=current_time,
            topic=self.topic,
            correlation_id=new_correlation_id(),
            mime_type=self._mime_type,
            image=image_b64,
            width=self.width,
            height=self.height,
        )

    @override
    def read_sensor(self) -> float | None:
        return None


class RPICameraSensor(CameraSensor):
    """Raspberry Pi Camera Sensor."""

    def __init__(
        self,
        name: str,
        read_interval: int,
        pin: Pin = -1,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        super().__init__(name, read_interval, pin, width, height)

    @override
    def _capture_jpeg(self) -> bytes | None:
        from picamera2 import Picamera2

        camera = Picamera2()
        configuration = camera.create_still_configuration(main={"size": (self.width, self.height)})
        camera.configure(configuration)
        stream = BytesIO()
        try:
            camera.start()
            camera.capture_file(stream, format="jpeg")
        finally:
            with suppress(Exception):
                camera.stop()
            with suppress(Exception):
                camera.close()
        return stream.getvalue()


class ESP32CameraSensor(CameraSensor):
    """ESP32-CAM Sensor fetching snapshots via HTTP GET."""

    def __init__(
        self,
        name: str,
        read_interval: int,
        snapshot_url: str,
        pin: Pin = -1,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        super().__init__(name, read_interval, pin, width, height)
        self.snapshot_url = snapshot_url

    @override
    def _capture_jpeg(self) -> bytes | None:
        # Add a timeout so the thread doesn't hang if the ESP32 is offline
        response = requests.get(self.snapshot_url, timeout=10)
        response.raise_for_status()
        return response.content
