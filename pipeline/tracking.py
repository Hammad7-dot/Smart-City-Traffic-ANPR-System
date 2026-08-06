# implements FR2
"""Persistent per-vehicle tracking, built on Ultralytics' bundled ByteTrack (D-010)."""

from dataclasses import dataclass


@dataclass
class TrackedBox:
    track_id: int
    vehicle_type: str
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


def iter_tracked_frames(detector, source: str, vehicle_class_map: dict, conf: float = 0.3):
    """Yields (frame_index, frame_bgr, list[TrackedBox]) for each frame of `source`."""
    results = detector.track(
        source=source,
        classes=list(vehicle_class_map.keys()),
        conf=conf,
        tracker="bytetrack.yaml",
        stream=True,
        persist=True,
        verbose=False,
    )
    for frame_index, result in enumerate(results):
        boxes = []
        if result.boxes is not None and result.boxes.id is not None:
            xyxy = result.boxes.xyxy.cpu().numpy()
            ids = result.boxes.id.cpu().numpy().astype(int)
            clss = result.boxes.cls.cpu().numpy().astype(int)
            for (x1, y1, x2, y2), tid, cls_id in zip(xyxy, ids, clss):
                boxes.append(
                    TrackedBox(
                        track_id=int(tid),
                        vehicle_type=vehicle_class_map.get(int(cls_id), "vehicle"),
                        x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2),
                    )
                )
        yield frame_index, result.orig_img, boxes
