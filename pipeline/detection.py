# implements FR1
"""Vehicle detection via pretrained YOLOv8 (COCO)."""

from ultralytics import YOLO

# COCO class ids -> vehicle_type labels required by SPEC.md FR1
VEHICLE_CLASS_MAP = {
    2: "car",
    3: "bike",   # motorcycle
    5: "bus",
    7: "truck",
}


def load_detector(weights: str = "yolov8n.pt") -> YOLO:
    return YOLO(weights)
