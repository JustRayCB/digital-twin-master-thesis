import base64
import binascii

import cv2
import numpy as np


def decode_base64_image(image_b64: str) -> np.ndarray:
    """Decode a base64 image payload into an RGB numpy array."""
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise ValueError("Invalid base64 image payload") from exc

    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    # WARNING: OpenCV uses BGR color order by default, so we need to convert it to RGB.
    bgr_image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if bgr_image is None:
        raise ValueError("Invalid image payload")

    return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)


def compute_excess_green_mask(image: np.ndarray, threshold: float) -> np.ndarray:
    """Return a boolean mask of pixels whose ExG value exceeds the threshold."""
    rgb = image.astype(np.float32, copy=False)

    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    sum_rgb = r + g + b
    # Avoid division by zero by adding a small epsilon to the denominator.
    epsilon = 1e-6
    sum_rgb_safe = sum_rgb + epsilon
    exg = 2 * g - r - b

    # We normalize the ExG value by the total intensity to account for varying lighting conditions.
    exg_normalized = exg / sum_rgb_safe
    return (exg_normalized > threshold).astype(np.uint8) * 255


def compute_green_ratio(image_b64: str, threshold: float = 0.05) -> float:
    """Compute the fraction of pixels classified as green."""
    # The threshold is a tunable parameter that determines how strict the classification is.
    # 0 is very lenient, 0.05 is a bit strict, and 0.1 is stricter.
    image = decode_base64_image(image_b64)
    green_mask = compute_excess_green_mask(image, threshold)
    if green_mask.size == 0:
        raise ValueError("Image contains no pixels")

    green_pixel_count = np.sum(green_mask > 0)
    total_pixel_count = green_mask.size
    return green_pixel_count / total_pixel_count
