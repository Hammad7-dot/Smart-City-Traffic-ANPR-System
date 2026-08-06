# implements FR3 (trigger only on crossing), FR4 (perf: not run per-frame)
"""License plate localization, invoked only from a line-crossing event (rules.md #8).

D-011: no no-auth pretrained plate-detector weights could be sourced for v1.
Fallback: crop the lower third of the vehicle bounding box (where plates sit
on most vehicle silhouettes) and hand that region to OCR. This is a known
accuracy limitation, not a silent substitution — see decisions.md D-011.
"""

import numpy as np

PLATE_MODEL_PATH = "models/plate_model.pt"


def load_plate_detector():
    """Returns an Ultralytics YOLO plate detector if weights are present, else None."""
    import os

    if not os.path.exists(PLATE_MODEL_PATH):
        return None
    from ultralytics import YOLO

    return YOLO(PLATE_MODEL_PATH)


def crop_plate_region(frame: np.ndarray, box: tuple[float, float, float, float], detector=None) -> np.ndarray | None:
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, y1 = max(x1, 0), max(y1, 0)
    x2, y2 = min(x2, frame.shape[1]), min(y2, frame.shape[0])
    if x2 <= x1 or y2 <= y1:
        return None
    vehicle_crop = frame[y1:y2, x1:x2]

    if detector is not None:
        results = detector.predict(vehicle_crop, verbose=False)
        if results and len(results[0].boxes) > 0:
            best = results[0].boxes.xyxy[0].cpu().numpy().astype(int)
            px1, py1, px2, py2 = best
            plate_crop = vehicle_crop[py1:py2, px1:px2]
            if plate_crop.size > 0:
                return plate_crop

    # Fallback: lower third of the vehicle crop, where plates typically sit.
    h = vehicle_crop.shape[0]
    lower_third = vehicle_crop[int(h * 0.65):h, :]
    return lower_third if lower_third.size > 0 else None
