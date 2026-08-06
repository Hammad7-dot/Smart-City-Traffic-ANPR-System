# implements FR8, rules.md #4 (one pipeline stage, one module) — see decisions.md D-014
"""Single-still-image detection: vehicle detect -> plate crop -> OCR, no tracking/crossing.

A standalone image has no previous frame, so pipeline.line_crossing.LineCrossingCounter
(which requires a prior side to compare against) can never fire on it — that's why this
module composes pipeline.detection / pipeline.plate_detection / pipeline.ocr directly
instead of going through pipeline.tracking or pipeline.line_crossing.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # avoid OpenMP double-init crash

from dataclasses import dataclass

import cv2
import numpy as np

from pipeline.detection import VEHICLE_CLASS_MAP
from pipeline.ocr import LOW_CONFIDENCE_THRESHOLD, read_plate
from pipeline.plate_detection import crop_plate_region


@dataclass
class ImageDetection:
    vehicle_type: str
    x1: float
    y1: float
    x2: float
    y2: float
    plate_number: str | None
    ocr_confidence: float
    is_low_confidence: bool


def detect_image(frame: np.ndarray, detector, plate_detector, ocr_reader, conf: float = 0.3) -> list[ImageDetection]:
    """Runs vehicle detection + plate OCR on a single BGR image. No tracking/counting."""
    results = detector.predict(frame, classes=list(VEHICLE_CLASS_MAP.keys()), conf=conf, verbose=False)
    detections: list[ImageDetection] = []
    if not results or results[0].boxes is None:
        return detections

    boxes = results[0].boxes
    xyxy = boxes.xyxy.cpu().numpy()
    clss = boxes.cls.cpu().numpy().astype(int)

    for (x1, y1, x2, y2), cls_id in zip(xyxy, clss):
        vehicle_type = VEHICLE_CLASS_MAP.get(int(cls_id), "vehicle")
        plate_crop = crop_plate_region(frame, (float(x1), float(y1), float(x2), float(y2)), plate_detector)
        plate_text, confidence = read_plate(ocr_reader, plate_crop)
        detections.append(
            ImageDetection(
                vehicle_type=vehicle_type,
                x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2),
                plate_number=plate_text,
                ocr_confidence=confidence,
                is_low_confidence=confidence < LOW_CONFIDENCE_THRESHOLD,
            )
        )
    return detections


def annotate_detections(frame: np.ndarray, detections: list[ImageDetection]) -> np.ndarray:
    """Returns a copy of frame (BGR) with bounding boxes + vehicle/plate labels drawn."""
    annotated = frame.copy()
    for det in detections:
        cv2.rectangle(annotated, (int(det.x1), int(det.y1)), (int(det.x2), int(det.y2)), (0, 200, 0), 2)
        label = f"{det.vehicle_type}: {det.plate_number or '?'}"
        cv2.putText(
            annotated, label, (int(det.x1), max(int(det.y1) - 8, 0)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2,
        )
    return annotated
