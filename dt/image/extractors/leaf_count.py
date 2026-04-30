import os
from typing import Any

from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics
from dt.image.extractors.base import ImageMetricExtractor
from dt.utils import get_logger

logger = get_logger(__name__)


class LeafCountExtractor(ImageMetricExtractor):
    """Extractor for counting leaves in a top-down image using a YOLOv11n model."""

    def __init__(self, model_path: str = "dt/image/models/leaf_count.pt") -> None:
        super().__init__(source_topic=Topics.CAMERA_IMAGE_TOP, target_topic=Topics.LEAF_COUNT)
        self.model_path = model_path
        self.model = None
        self.IMGSZ = 640  # Inference image size
        self.CONF = 0.45  # Confidence threshold
        self.IOU = 0.45  # NMS IoU threshold wich is used when there are multiple boxes for the same object. The one with the highest confidence will be kept.
        self.DEVICE = "cpu"  # Use CPU for inference
        self.RETINA_MASKS = (
            False  # Whether to return high-resolution masks (if supported by the model)
        )

        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 0:
            try:
                from ultralytics import YOLO

                self.model = YOLO(self.model_path)
            except Exception as e:
                logger.error(f"Failed to load YOLO model from {self.model_path}: {e}")
        else:
            logger.warning(f"YOLO model file is missing or empty at {self.model_path}")

    def extract(self, snapshot: CameraSnapshot, **kwargs: Any) -> float:
        """Count the number of leaves in the image.
        """
        if self.model is None:
            logger.error(
                f"Leaf count model is unavailable for plant_id {snapshot.plant_id}; extraction skipped."
            )
            raise RuntimeError("Leaf count model is unavailable")

        image_np = self.decode_base64_image(snapshot.image)
        resized_image = self.resize_image(image_np, 640)

        # Run inference
        results = self.model.predict(
            resized_image,
            imgsz=self.IMGSZ,
            conf=self.CONF,
            iou=self.IOU,
            device=self.DEVICE,
            retina_masks=self.RETINA_MASKS,
            verbose=False,
        )

        # In segmentation, masks are usually found in results[0].masks
        # Even without masks, the number of detected instances (boxes) is len(results[0].boxes)
        if results[0].masks is None or results[0].boxes is None or len(results[0].boxes) == 0:
            logger.error("No leaves detected from inference outputs")
            raise RuntimeError("No leaves detected")

        leaf_count = len(
            results[0].boxes
        )  # boxes should correspond to detected leaves, even if masks are not available
        logger.info(f"Detected {leaf_count} leaves in the image")
        return float(leaf_count)
