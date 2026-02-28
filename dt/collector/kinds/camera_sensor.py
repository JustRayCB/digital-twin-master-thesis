import time
from base64 import b64encode
from io import BytesIO

from picamera2 import Picamera2
from typing_extensions import override

from dt.collector.kinds.base_sensor import Pin, Sensor
from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics
from dt.utils.ids import new_correlation_id


class CameraSensor(Sensor):
    def __init__(self, name: str, read_interval: int, pin: Pin = -1) -> None:
        super().__init__(name, read_interval, pin)
        self._mime_type = "image/jpeg"
        self._width = 640
        self._height = 480

    @property
    @override
    def unit(self) -> str:
        return self._mime_type

    @property
    @override
    def topic(self) -> Topics:
        return Topics.CAMERA_IMAGE

    def _capture_jpeg(self, width: int, height: int) -> bytes:

        camera = Picamera2()
        configuration = camera.create_still_configuration(main={"size": (width, height)})
        camera.configure(configuration)
        camera.start()
        stream = BytesIO()
        try:
            camera.capture_file(stream, format="jpeg")
        finally:
            camera.stop()
        return stream.getvalue()

    @override
    def read(self) -> CameraSnapshot | None:
        current_time = time.time()
        try:
            image_bytes = self._capture_jpeg(self._width, self._height)
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
            width=self._width,
            height=self._height,
        )

    @override
    def read_sensor(self) -> float | None:
        return None
