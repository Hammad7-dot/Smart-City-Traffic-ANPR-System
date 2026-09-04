"""FR8: image results must flag missing plate text, just like video events."""

from types import SimpleNamespace

import numpy as np
import torch

from pipeline.image_detection import detect_image


def test_empty_normalized_plate_is_flagged():
    class Detector:
        def predict(self, *args, **kwargs):
            return [SimpleNamespace(boxes=SimpleNamespace(
                xyxy=torch.tensor([[0, 0, 20, 20]]), cls=torch.tensor([2]),
            ))]

    class Reader:
        def readtext(self, crop):
            return [(None, "---", 0.9)]

    results = detect_image(np.zeros((20, 20, 3), dtype=np.uint8), Detector(), None, Reader())
    assert len(results) == 1
    assert results[0].plate_number is None
    assert results[0].is_low_confidence is True
