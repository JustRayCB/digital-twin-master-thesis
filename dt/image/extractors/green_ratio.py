from typing import Any

import numpy as np

from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics
from dt.image.extractors.base import ImageMetricExtractor


class GreenRatioExtractor(ImageMetricExtractor):
    """Extractor for computing the green ratio of an image."""

    def __init__(self, threshold: float = 0.05) -> None:
        # Assuming we compute the green ratio on the top-down camera
        super().__init__(source_topic=Topics.CAMERA_IMAGE_TOP, target_topic=Topics.GREEN_RATIO)
        self.threshold = threshold

    def compute_excess_green_mask(self, image: np.ndarray) -> np.ndarray:
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
        return (exg_normalized > self.threshold).astype(np.uint8) * 255

    def compute_green_ratio(self, image_b64: str) -> float:
        """Compute the fraction of pixels classified as green."""
        # The threshold is a tunable parameter that determines how strict the classification is.
        # 0 is very lenient, 0.05 is a bit strict, and 0.1 is stricter.
        image = self.decode_base64_image(image_b64)
        green_mask = self.compute_excess_green_mask(image)
        if green_mask.size == 0:
            raise ValueError("Image contains no pixels")

        green_pixel_count = np.sum(green_mask > 0)
        total_pixel_count = green_mask.size
        return green_pixel_count / total_pixel_count

    def extract(self, snapshot: CameraSnapshot, **kwargs: Any) -> float:
        """Compute the green ratio. Returns a percentage."""
        return self.compute_green_ratio(snapshot.image) * 100.0
