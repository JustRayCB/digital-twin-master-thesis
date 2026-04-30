import base64

import cv2
import numpy as np
import pytest

from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics
from dt.image.extractors.green_ratio import GreenRatioExtractor
from dt.image.extractors.leaf_count import LeafCountExtractor
from dt.image.extractors.plant_height import PlantHeightExtractor
from dt.image.image_analysis_service import ImageAnalysisService


def _encode_jpeg_base64(pixels: list[list[tuple[int, int, int]]]) -> str:
    rgb_image = np.array(pixels, dtype=np.uint8)
    bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(".jpg", bgr_image)
    if not ok:
        raise RuntimeError("Failed to encode test JPEG")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def test_compute_green_ratio_returns_high_ratio_for_green_image() -> None:
    """Green-heavy images should produce a high green ratio with normalized ExG."""
    image_b64 = _encode_jpeg_base64([[(0, 255, 0)] * 12 for _ in range(12)])

    extractor = GreenRatioExtractor(threshold=0.05)
    ratio = extractor.compute_green_ratio(image_b64)

    assert ratio == pytest.approx(1.0, abs=0.01)


def test_compute_green_ratio_returns_low_ratio_for_red_image() -> None:
    """Non-green images should produce a low green ratio with normalized ExG."""
    image_b64 = _encode_jpeg_base64([[(255, 0, 0)] * 12 for _ in range(12)])

    extractor = GreenRatioExtractor(threshold=0.05)
    ratio = extractor.compute_green_ratio(image_b64)

    assert ratio == pytest.approx(0.0, abs=0.01)


def test_compute_green_ratio_returns_expected_ratio_for_mixed_image() -> None:
    """Mixed images should return the expected green-pixel fraction with normalized ExG."""
    pixels = []
    for _ in range(16):
        pixels.append([(0, 255, 0)] * 8 + [(255, 0, 0)] * 8)
    image_b64 = _encode_jpeg_base64(pixels)

    extractor = GreenRatioExtractor(threshold=0.05)
    ratio = extractor.compute_green_ratio(image_b64)

    assert ratio == pytest.approx(0.5, abs=0.1)


def test_decode_base64_image_rejects_invalid_base64() -> None:
    """Invalid base64 payloads should raise a clear exception."""
    extractor = GreenRatioExtractor()
    with pytest.raises(ValueError, match="Invalid base64 image payload"):
        extractor.decode_base64_image("not-base64")


def test_decode_base64_image_returns_rgb_numpy_array() -> None:
    """Decoded images should be exposed as RGB numpy arrays for metric computation."""
    image_b64 = _encode_jpeg_base64([[(12, 34, 56)] * 6 for _ in range(6)])

    extractor = GreenRatioExtractor()
    decoded = extractor.decode_base64_image(image_b64)

    assert isinstance(decoded, np.ndarray)
    assert decoded.shape == (6, 6, 3)
    assert decoded.dtype == np.uint8


def test_decode_base64_image_rejects_invalid_image_bytes() -> None:
    """Non-image bytes should raise a clear exception."""
    invalid_bytes = base64.b64encode(b"definitely-not-a-jpeg").decode("ascii")

    extractor = GreenRatioExtractor()
    with pytest.raises(ValueError, match="Invalid image payload"):
        extractor.decode_base64_image(invalid_bytes)


def _build_snapshot(topic: Topics = Topics.CAMERA_IMAGE_TOP) -> CameraSnapshot:
    return CameraSnapshot(
        plant_id=1,
        sensor_id=2,
        timestamp=123.0,
        topic=topic,
        correlation_id="corr-123",
        mime_type="image/jpeg",
        image=_encode_jpeg_base64([[(0, 255, 0)] * 8 for _ in range(8)]),
        width=8,
        height=8,
    )


def test_leaf_count_extractor_raises_when_model_unavailable() -> None:
    extractor = LeafCountExtractor()
    extractor.model = None

    with pytest.raises(RuntimeError, match="Leaf count model is unavailable"):
        extractor.extract(_build_snapshot(Topics.CAMERA_IMAGE_TOP))


def test_leaf_count_extractor_raises_when_no_leaf_detected() -> None:
    extractor = LeafCountExtractor()

    class _NoLeafModel:
        def predict(self, *_args, **_kwargs):
            return [type("Result", (), {"masks": None, "boxes": []})()]

    extractor.model = _NoLeafModel()

    with pytest.raises(RuntimeError, match="No leaves detected"):
        extractor.extract(_build_snapshot(Topics.CAMERA_IMAGE_TOP))


def test_plant_height_extractor_raises_when_apriltag_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = PlantHeightExtractor()
    monkeypatch.setattr(extractor, "detect_april_tag", lambda _image: None)

    with pytest.raises(RuntimeError, match="AprilTag"):
        extractor.extract(_build_snapshot(Topics.CAMERA_IMAGE_SIDE))


def test_plant_height_extractor_raises_when_model_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = PlantHeightExtractor()
    fake_tag = type("FakeTag", (), {"corners": np.array([[0, 0], [10, 0], [10, 10], [0, 10]])})()
    monkeypatch.setattr(extractor, "detect_april_tag", lambda _image: fake_tag)
    extractor.model = None

    with pytest.raises(RuntimeError, match="Plant height model is unavailable"):
        extractor.extract(_build_snapshot(Topics.CAMERA_IMAGE_SIDE))


def test_plant_height_extractor_raises_when_no_plant_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = PlantHeightExtractor()
    fake_tag = type("FakeTag", (), {"corners": np.array([[0, 0], [10, 0], [10, 10], [0, 10]])})()
    monkeypatch.setattr(extractor, "detect_april_tag", lambda _image: fake_tag)

    class _NoPlantModel:
        def predict(self, *_args, **_kwargs):
            return [type("Result", (), {"masks": None, "boxes": []})()]

    extractor.model = _NoPlantModel()

    with pytest.raises(RuntimeError, match="No plant detected"):
        extractor.extract(_build_snapshot(Topics.CAMERA_IMAGE_SIDE))


def test_image_analysis_service_isolates_failing_extractor_and_keeps_publishing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _RecordingMessagingService:
        def __init__(self):
            self.published = []

        def publish(self, topic: str, message: object) -> bool:
            self.published.append((topic, message))
            return True

        def subscribe(self, _topic: str, _handler: object) -> None:
            return None

        def disconnect(self) -> None:
            return None

    class _FailingExtractor:
        source_topic = Topics.CAMERA_IMAGE_TOP
        target_topic = Topics.LEAF_COUNT

        def extract(self, _snapshot: CameraSnapshot) -> float:
            raise RuntimeError("leaf extraction failed")

    class _WorkingExtractor:
        source_topic = Topics.CAMERA_IMAGE_TOP
        target_topic = Topics.GREEN_RATIO

        def extract(self, _snapshot: CameraSnapshot) -> float:
            return 91.0

    messaging_service = _RecordingMessagingService()
    service = ImageAnalysisService(messaging_service=messaging_service)
    service.extractors = [_FailingExtractor(), _WorkingExtractor()]  # type: ignore[assignment]

    snapshot = _build_snapshot(Topics.CAMERA_IMAGE_TOP)
    with caplog.at_level("ERROR"):
        service._on_snapshot(snapshot)

    assert len(messaging_service.published) == 1
    published_topic, reading = messaging_service.published[0]
    assert published_topic == Topics.GREEN_RATIO.raw
    assert reading.topic == Topics.GREEN_RATIO
    assert reading.value == pytest.approx(91.0)
    assert any("Failed to extract dt.sensors.leaf_count" in message for message in caplog.messages)
