import numpy as np

from pipeline.tracking import iter_tracked_frames


class _FakeTensor:
    """Stands in for a torch tensor: .cpu().numpy() round-trips to the wrapped array."""

    def __init__(self, array):
        self._array = array

    def cpu(self):
        return self

    def numpy(self):
        return self._array


class _FakeBoxes:
    def __init__(self, xyxy, ids, clss):
        self.xyxy = _FakeTensor(np.array(xyxy, dtype=float))
        self.id = _FakeTensor(np.array(ids))
        self.cls = _FakeTensor(np.array(clss))


class _FakeResult:
    def __init__(self, orig_img, boxes=None):
        self.orig_img = orig_img
        self.boxes = boxes


class _FakeDetector:
    def __init__(self, results):
        self._results = results
        self.track_kwargs = None

    def track(self, **kwargs):
        self.track_kwargs = kwargs
        return iter(self._results)


def test_yields_tracked_boxes_with_mapped_vehicle_type():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    boxes = _FakeBoxes(xyxy=[[1, 2, 3, 4]], ids=[7], clss=[2])
    detector = _FakeDetector([_FakeResult(frame, boxes)])

    frames = list(iter_tracked_frames(detector, "video.mp4", {2: "car"}))

    assert len(frames) == 1
    frame_index, orig_img, tracked = frames[0]
    assert frame_index == 0
    assert orig_img is frame
    assert len(tracked) == 1
    box = tracked[0]
    assert box.track_id == 7
    assert box.vehicle_type == "car"
    assert box.x1 == 1 and box.y1 == 2 and box.x2 == 3 and box.y2 == 4


def test_unmapped_class_id_falls_back_to_generic_vehicle():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    boxes = _FakeBoxes(xyxy=[[0, 0, 1, 1]], ids=[1], clss=[99])
    detector = _FakeDetector([_FakeResult(frame, boxes)])

    _, _, tracked = next(iter(iter_tracked_frames(detector, "video.mp4", {2: "car"})))

    assert tracked[0].vehicle_type == "vehicle"


def test_result_with_no_boxes_yields_empty_list():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    detector = _FakeDetector([_FakeResult(frame, boxes=None)])

    _, _, tracked = next(iter(iter_tracked_frames(detector, "video.mp4", {2: "car"})))

    assert tracked == []


def test_passes_vehicle_class_ids_and_conf_to_detector():
    detector = _FakeDetector([])

    list(iter_tracked_frames(detector, "video.mp4", {2: "car", 5: "bus"}, conf=0.5))

    assert detector.track_kwargs["classes"] == [2, 5]
    assert detector.track_kwargs["conf"] == 0.5
    assert detector.track_kwargs["tracker"] == "bytetrack.yaml"


def test_tracked_box_centroid():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    boxes = _FakeBoxes(xyxy=[[0, 0, 4, 8]], ids=[1], clss=[2])
    detector = _FakeDetector([_FakeResult(frame, boxes)])

    _, _, tracked = next(iter(iter_tracked_frames(detector, "video.mp4", {2: "car"})))

    assert tracked[0].centroid == (2.0, 4.0)
