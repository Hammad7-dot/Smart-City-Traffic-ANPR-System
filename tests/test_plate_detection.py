import numpy as np

from pipeline.plate_detection import crop_plate_region


def test_in_bounds_box_returns_lower_third():
    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    box = (50, 20, 150, 120)  # 100px tall vehicle box

    crop = crop_plate_region(frame, box, detector=None)

    assert crop is not None
    box_height = 120 - 20
    expected_height = box_height - int(box_height * 0.65)
    assert crop.shape[0] == expected_height
    assert crop.shape[1] == 150 - 50


def test_box_outside_frame_bounds_is_clamped():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    box = (-50, -50, 150, 150)  # extends past every edge

    crop = crop_plate_region(frame, box, detector=None)

    assert crop is not None
    assert crop.shape[1] == 100  # clamped to frame width


def test_degenerate_box_returns_none():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert crop_plate_region(frame, (50, 50, 50, 80), detector=None) is None  # x2 == x1
    assert crop_plate_region(frame, (50, 80, 80, 50), detector=None) is None  # y2 < y1
