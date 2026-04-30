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

ESP32_CAMERA_FRAME_DIMENSIONS = {
    "96X96": (96, 96),
    "QQVGA": (160, 120),
    "QCIF": (176, 144),
    "HQVGA": (240, 176),
    "240X240": (240, 240),
    "QVGA": (320, 240),
    "CIF": (400, 296),
    "HVGA": (480, 320),
    "VGA": (640, 480),
    "SVGA": (800, 600),
    "XGA": (1024, 768),
    "HD": (1280, 720),
    "SXGA": (1280, 1024),
    "UXGA": (1600, 1200),
}


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
        return Topics.CAMERA_IMAGE_TOP

    @abstractmethod
    def _capture_jpeg(self) -> bytes | None:
        """Capture a JPEG image and return it as bytes."""
        raise NotImplementedError

    @override
    def read(self, current_time: float) -> CameraSnapshot | None:
        try:
            self.last_read_time = current_time
            image_bytes = self._capture_jpeg()
        except Exception as exc:
            self.logger.error(f"Failed to read {self.name}: {exc}")
            return None

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
        framesize: str = "VGA",
        quality: int = 70,
        timeout: float | tuple[float, float] = 10,
    ) -> None:
        normalized_framesize = framesize.strip().upper()
        dimensions = ESP32_CAMERA_FRAME_DIMENSIONS.get(normalized_framesize)
        if dimensions is None:
            raise ValueError(f"Unsupported ESP32 camera framesize: {normalized_framesize}")

        super().__init__(name, read_interval, pin, *dimensions)
        self.snapshot_url = snapshot_url
        self.framesize = normalized_framesize
        self.quality = quality
        self.timeout = timeout

    @override
    def _capture_jpeg(self) -> bytes | None:
        params: dict[str, str | int] = {}
        params["framesize"] = self.framesize
        params["quality"] = self.quality

        response = requests.get(self.snapshot_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    @property
    @override
    def topic(self) -> Topics:
        return Topics.CAMERA_IMAGE_SIDE
