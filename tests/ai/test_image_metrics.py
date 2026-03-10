import base64

import cv2
import numpy as np
import pytest

from dt.ai.image_metrics import compute_green_ratio, decode_base64_image


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

    ratio = compute_green_ratio(image_b64, threshold=0.05)

    assert ratio == pytest.approx(1.0, abs=0.01)


def test_compute_green_ratio_returns_low_ratio_for_red_image() -> None:
    """Non-green images should produce a low green ratio with normalized ExG."""
    image_b64 = _encode_jpeg_base64([[(255, 0, 0)] * 12 for _ in range(12)])

    ratio = compute_green_ratio(image_b64, threshold=0.05)

    assert ratio == pytest.approx(0.0, abs=0.01)


def test_compute_green_ratio_returns_expected_ratio_for_mixed_image() -> None:
    """Mixed images should return the expected green-pixel fraction with normalized ExG."""
    pixels = []
    for _ in range(16):
        pixels.append([(0, 255, 0)] * 8 + [(255, 0, 0)] * 8)
    image_b64 = _encode_jpeg_base64(pixels)

    ratio = compute_green_ratio(image_b64, threshold=0.05)

    assert ratio == pytest.approx(0.5, abs=0.1)


def test_decode_base64_image_rejects_invalid_base64() -> None:
    """Invalid base64 payloads should raise a clear exception."""
    with pytest.raises(ValueError, match="Invalid base64 image payload"):
        decode_base64_image("not-base64")


def test_decode_base64_image_returns_rgb_numpy_array() -> None:
    """Decoded images should be exposed as RGB numpy arrays for metric computation."""
    image_b64 = _encode_jpeg_base64([[(12, 34, 56)] * 6 for _ in range(6)])

    decoded = decode_base64_image(image_b64)

    assert isinstance(decoded, np.ndarray)
    assert decoded.shape == (6, 6, 3)
    assert decoded.dtype == np.uint8


def test_decode_base64_image_rejects_invalid_image_bytes() -> None:
    """Non-image bytes should raise a clear exception."""
    invalid_bytes = base64.b64encode(b"definitely-not-a-jpeg").decode("ascii")

    with pytest.raises(ValueError, match="Invalid image payload"):
        decode_base64_image(invalid_bytes)
