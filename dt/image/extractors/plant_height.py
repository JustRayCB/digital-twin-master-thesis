import os
from typing import Any, Literal

import cv2
import numpy as np
from pupil_apriltags import Detector

from dt.communication.dataclasses import CameraSnapshot
from dt.communication.topics import Topics
from dt.image.extractors.base import ImageMetricExtractor
from dt.utils import get_logger

logger = get_logger(__name__)


PlantDetectionMethod = Literal["yolo", "exg"]


class PlantHeightExtractor(ImageMetricExtractor):
    """Extractor for computing plant height from a side-view image.

    The plant can be detected either with:
    - "yolo": the trained YOLO model
    - "exg": classical Excess Green segmentation
    """

    def __init__(
        self,
        model_path: str = "dt/image/models/plant_height.pt",
        plant_detection_method: PlantDetectionMethod = "yolo",
    ) -> None:
        super().__init__(source_topic=Topics.CAMERA_IMAGE_SIDE, target_topic=Topics.PLANT_HEIGHT)

        if plant_detection_method not in {"yolo", "exg"}:
            raise ValueError(
                "plant_detection_method must be either 'yolo' or 'exg', "
                f"got {plant_detection_method!r}"
            )

        self.model_path = model_path
        self.plant_detection_method = plant_detection_method

        self.model = None
        self.detector: Any | None = None
        self.IMGSZ = 640  # Inference image size
        self.CONF = 0.45  # Confidence threshold
        self.IOU = 0.45  # NMS IoU threshold
        self.DEVICE = "cpu"  # Use CPU for inference
        self.RETINA_MASKS = False  # Whether to return high-resolution masks, if supported

        self.tag_size_mm = 48.0

        if self.plant_detection_method == "yolo":
            if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 0:
                try:
                    from ultralytics import YOLO

                    self.model = YOLO(self.model_path)
                except Exception as e:
                    logger.error(f"Failed to load YOLO model from {self.model_path}: {e}")
            else:
                logger.warning(f"YOLO model file is missing or empty at {self.model_path}")
        else:
            logger.info("Using ExG plant segmentation; YOLO model will not be loaded.")

    def _get_detector(self) -> Any:
        if self.detector is None:
            self.detector = Detector(
                families="tag36h11 tag25h9 tag16h5",
                nthreads=1,
                quad_decimate=1.0,
                quad_sigma=0.4,
                refine_edges=1,
                decode_sharpening=0.25,
                debug=0,
            )
        return self.detector

    def _crop_likely_tag_region(self, image_np: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
        """Crop the lower-center region where the AprilTag is expected.

        This does not resize the image, so the pixel-to-mm scale remains valid.
        """
        h, w = image_np.shape[:2]

        x1 = int(w * 0.25)
        x2 = int(w * 0.75)
        y1 = int(h * 0.45)
        y2 = int(h * 1.00)

        cropped_image = image_np[y1:y2, x1:x2].copy()

        return cropped_image, (x1, y1)

    def _shift_tag_detection_to_full_image(
        self,
        tag: Any,
        x_offset: int,
        y_offset: int,
    ) -> Any:
        """Shift AprilTag coordinates from crop space back to full-image space."""
        tag.corners[:, 0] += x_offset
        tag.corners[:, 1] += y_offset
        tag.center[0] += x_offset
        tag.center[1] += y_offset

        return tag

    def detect_april_tag(self, image_np: np.ndarray) -> Any | None:
        """Detect AprilTags in the lower-center crop.

        Returns the most confident detection, with coordinates shifted back
        into the full-image coordinate system.
        """
        tag_crop, (x_offset, y_offset) = self._crop_likely_tag_region(image_np)

        gray_crop = cv2.cvtColor(tag_crop, cv2.COLOR_RGB2GRAY)

        tags = self._get_detector().detect(np.asarray(gray_crop, dtype=np.uint8))

        logger.info(f"AprilTag crop shape: {tag_crop.shape}")
        logger.info(f"Detected {len(tags)} AprilTag(s) in crop")

        if not tags:
            return None

        best_tag = max(tags, key=lambda t: t.decision_margin)  # pyright: ignore[]

        family = best_tag.tag_family
        if isinstance(family, bytes):
            family = family.decode("utf-8")

        logger.info(
            f"Best AprilTag detection: family={family}, "
            f"id={best_tag.tag_id}, "
            f"hamming={best_tag.hamming}, "
            f"decision_margin={best_tag.decision_margin}"
        )

        return self._shift_tag_detection_to_full_image(
            best_tag,
            x_offset=x_offset,
            y_offset=y_offset,
        )

    def _compute_px_to_mm(self, tag: Any) -> float:
        """Compute pixel-to-mm scale from the AprilTag vertical side length."""
        # Calculate pixels-to-mm ratio based on the tag's pixel height
        # tag.corners is [4, 2] array of corner coordinates
        # Corner order: [top-left, top-right, bottom-right, bottom-left]

        tag_height_px = np.mean(
            [
                np.linalg.norm(tag.corners[0] - tag.corners[3]),
                np.linalg.norm(tag.corners[1] - tag.corners[2]),
            ]
        )

        return float(self.tag_size_mm / tag_height_px)

    def _detect_plant_height_px_yolo(self, image_np: np.ndarray, plant_id: int) -> float:
        """Detect plant height in pixels using the YOLO model."""
        if self.model is None:
            logger.error(
                f"Plant height model is unavailable for plant_id {plant_id}; extraction skipped."
            )
            raise RuntimeError("Plant height model is unavailable")

        resized_image = self.resize_image(image_np, 640)
        results = self.model.predict(
            resized_image,
            imgsz=self.IMGSZ,
            conf=self.CONF,
            iou=self.IOU,
            device=self.DEVICE,
            retina_masks=self.RETINA_MASKS,
            verbose=False,
        )

        # Height is computed from boxes, so boxes are the required output.
        # Masks may be None depending on the model/export, even when boxes exist.
        if results[0].boxes is None or len(results[0].boxes) == 0:
            logger.warning(f"No plant detected in the image for plant_id {plant_id}")
            raise RuntimeError("No plant detected in the image")

        # YOLO inference was on resized image (640), scale back to original height.
        boxes = results[0].boxes.xywh.cpu().numpy()
        max_height_resized = np.max(boxes[:, 3])
        scale_factor = image_np.shape[0] / 640.0

        return float(max_height_resized * scale_factor)

    def _preprocess_image_for_exg(self, image_np: np.ndarray) -> np.ndarray:
        """Apply light smoothing before ExG segmentation."""
        return cv2.GaussianBlur(image_np, (5, 5), 0)

    def _segment_plant_exg(self, image_np: np.ndarray) -> np.ndarray:
        """Segment green vegetation using the Excess Green Index (ExG).

        image_np is expected to be RGB in this pipeline, so channels are split as R, G, B.
        """
        smoothed = self._preprocess_image_for_exg(image_np)
        r, g, b = cv2.split(smoothed.astype(np.float32))

        exg = 2 * g - r - b

        exg_norm = cv2.normalize(  # pyright: ignore[]
            exg,
            None,  # pyright: ignore[]
            alpha=0,
            beta=255,
            norm_type=cv2.NORM_MINMAX,
            dtype=cv2.CV_8U,
        )

        _, mask = cv2.threshold(
            exg_norm,
            0,
            255,
            cv2.THRESH_BINARY | cv2.THRESH_OTSU,
        )

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        return mask

    def _extract_largest_plant_feature_from_mask(
        self,
        mask: np.ndarray,
    ) -> dict[str, Any] | None:
        """Extract the largest contour from the ExG mask.

        This does not reject small contours. The largest detected green region is
        treated as the plant. If self.min_plant_area is set, it is only used for
        logging a warning, not for filtering.
        """
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours:
            return None

        contour_areas = [(contour, float(cv2.contourArea(contour))) for contour in contours]

        largest_contour, largest_area = max(
            contour_areas,
            key=lambda item: item[1],
        )

        x, y, w, h = cv2.boundingRect(largest_contour)

        return {
            "contour": largest_contour,
            "area_px": largest_area,
            "bbox": (x, y, w, h),
            "height_px": h,
            "width_px": w,
        }

    def _detect_plant_height_px_exg(self, image_np: np.ndarray, plant_id: int) -> float:
        """Detect plant height in pixels using ExG segmentation.

        The returned height is the union bounding-box height across all significant
        green contours. This is more stable than using only the largest contour when
        leaves are separated into multiple mask components.
        """
        mask = self._segment_plant_exg(image_np)
        largest_feature = self._extract_largest_plant_feature_from_mask(mask)

        if largest_feature is None:
            logger.warning("No plant contour detected using ExG segmentation")
            raise RuntimeError("No plant detected in the image using ExG segmentation")

        logger.info(
            f"Selected largest ExG plant contour for plant {plant_id}: "
            f"area={largest_feature['area_px']:.2f}px, "
            f"bbox={largest_feature['bbox']}, "
            f"height={largest_feature['height_px']}px"
        )

        return float(largest_feature["height_px"])

    def _detect_plant_height_px(self, image_np: np.ndarray, plant_id: int) -> float:
        """Detect plant height in pixels using the configured method."""
        if self.plant_detection_method == "yolo":
            return self._detect_plant_height_px_yolo(image_np, plant_id)
        if self.plant_detection_method == "exg":
            return self._detect_plant_height_px_exg(image_np, plant_id)

        raise RuntimeError(f"Unsupported plant detection method: {self.plant_detection_method}")

    def extract(self, snapshot: CameraSnapshot, **kwargs: Any) -> float:
        """Compute the height of the plant in cm.

        Uses an AprilTag to calibrate pixels to real-world millimeters, then detects
        plant height using either YOLO or ExG segmentation.
        """
        image_np = self.decode_base64_image(snapshot.image)

        # 1. Detect AprilTag for scale calibration.
        tag = self.detect_april_tag(image_np)
        if tag is None:
            logger.warning(
                f"No AprilTag detected for plant_id {snapshot.plant_id}. "
                "Plant height extraction skipped."
            )
            raise RuntimeError("AprilTag calibration is unavailable")

        px_to_mm = self._compute_px_to_mm(tag)

        # 2. Plant detection and height extraction in pixels.
        plant_height_px = self._detect_plant_height_px(image_np, snapshot.plant_id)

        # 3. Convert pixel height to real-world centimeters.
        real_height_mm = plant_height_px * px_to_mm

        return float(real_height_mm) / 10.0
