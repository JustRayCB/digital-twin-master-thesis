import base64
import binascii
from abc import ABC, abstractmethod
from typing import Any

import cv2
import numpy as np

from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics


class ImageMetricExtractor(ABC):
    """Base class for all image metric extractors."""

    def __init__(self, source_topic: Topics, target_topic: Topics) -> None:
        self.source_topic = source_topic
        self.target_topic = target_topic

    def decode_base64_image(self, image_b64: str) -> np.ndarray:
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

    def resize_image(self, image: np.ndarray, target_size: int = 640) -> np.ndarray:
        """Resize the image to a square of the target size while maintaining aspect ratio."""
        # taken from Stack overflow London Guy https://beta.stackoverflow.com/questions/44720580/resize-image-to-maintain-aspect-ratio-in-python-opencv
        h, w = image.shape[:2]
        sh, sw = target_size, target_size

        # interpolation method
        if h > sh or w > sw:  # shrinking image
            interp = cv2.INTER_AREA

        else:  # stretching image
            interp = cv2.INTER_CUBIC

        # aspect ratio of image
        aspect = float(w) / h
        saspect = float(sw) / sh

        if (saspect >= aspect) or ((saspect == 1) and (aspect <= 1)):  # new horizontal image
            new_h = sh
            new_w = np.round(new_h * aspect).astype(int)
            pad_horz = float(sw - new_w) / 2
            pad_left, pad_right = np.floor(pad_horz).astype(int), np.ceil(pad_horz).astype(int)
            pad_top, pad_bot = 0, 0

        elif (saspect < aspect) or ((saspect == 1) and (aspect >= 1)):  # new vertical image
            new_w = sw
            new_h = np.round(float(new_w) / aspect).astype(int)
            pad_vert = float(sh - new_h) / 2
            pad_top, pad_bot = np.floor(pad_vert).astype(int), np.ceil(pad_vert).astype(int)
            pad_left, pad_right = 0, 0

        # scale and pad
        scaled_img = cv2.resize(image, (new_w, new_h), interpolation=interp)
        scaled_img = cv2.copyMakeBorder(
            scaled_img,
            pad_top,
            pad_bot,
            pad_left,
            pad_right,
            borderType=cv2.BORDER_CONSTANT,
            value=[0, 0, 0],
        )

        return scaled_img

    @abstractmethod
    def extract(self, snapshot: CameraSnapshot, **kwargs: Any) -> float:
        """Extract a metric from a camera snapshot.

        Parameters
        ----------
        snapshot : CameraSnapshot
            The raw camera snapshot to process.

        Returns
        -------
        float
            The extracted metric value.
        """
        pass
