import numpy as np
import warnings

import pipeline.ocr as ocr

from pipeline.ocr import LOW_CONFIDENCE_THRESHOLD, read_plate


class _FakeReader:
    def __init__(self, results=None, raises=False):
        self._results = results or []
        self._raises = raises

    def readtext(self, crop):
        if self._raises:
            raise RuntimeError("decode failure")
        return self._results


def test_none_crop_returns_none_and_zero_confidence():
    text, confidence = read_plate(_FakeReader(), None)
    assert text is None
    assert confidence == 0.0


def test_empty_crop_returns_none_and_zero_confidence():
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    text, confidence = read_plate(_FakeReader(), empty_crop)
    assert text is None
    assert confidence == 0.0


def test_no_detections_returns_none_and_zero_confidence():
    crop = np.zeros((10, 10, 3), dtype=np.uint8)
    text, confidence = read_plate(_FakeReader(results=[]), crop)
    assert text is None
    assert confidence == 0.0


def test_reader_exception_is_swallowed():
    crop = np.zeros((10, 10, 3), dtype=np.uint8)
    text, confidence = read_plate(_FakeReader(raises=True), crop)
    assert text is None
    assert confidence == 0.0


def test_joins_multiple_boxes_and_uppercases_strips_non_alnum():
    crop = np.zeros((10, 10, 3), dtype=np.uint8)
    results = [
        (None, "ab-1", 0.9),
        (None, "23!", 0.5),
    ]
    text, confidence = read_plate(_FakeReader(results=results), crop)
    assert text == "AB123"
    assert confidence == 0.7


def test_all_non_alnum_text_becomes_none():
    crop = np.zeros((10, 10, 3), dtype=np.uint8)
    results = [(None, "---", 0.8)]
    text, confidence = read_plate(_FakeReader(results=results), crop)
    assert text is None
    assert confidence == 0.8


def test_low_confidence_threshold_value():
    assert LOW_CONFIDENCE_THRESHOLD == 0.4


def test_cpu_pin_memory_notice_is_scoped_to_ocr_call():
    class Reader:
        device = "cpu"

        def readtext(self, crop):
            warnings.warn_explicit(
                "'pin_memory' argument is set as true but no accelerator is found, then device pinned memory won't be used.",
                UserWarning, "dataloader.py", 759, module="torch.utils.data.dataloader",
            )
            warnings.warn("unrelated OCR warning", UserWarning)
            return [(None, "ABC123", 0.9)]

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        assert read_plate(Reader(), np.zeros((10, 10, 3), dtype=np.uint8)) == ("ABC123", 0.9)
        warnings.warn("outside OCR", UserWarning)
    assert [str(w.message) for w in captured] == ["unrelated OCR warning", "outside OCR"]


def test_reader_load_scopes_known_upstream_quantization_notice(monkeypatch):
    def reader(*args, **kwargs):
        warnings.warn_explicit(
            "torch.quantize_per_tensor, torch.quantize_per_channel and other quantized tensor creation functions that produce tensors with dtype torch.quint8, torch.qint8, and torch.qint32 are deprecated and will be removed in a future PyTorch release.",
            UserWarning, "rnn.py", 162, module="torch.ao.nn.quantized.dynamic.modules.rnn",
        )
        warnings.warn("another initialization warning", UserWarning)
        return object()

    monkeypatch.setattr(ocr.easyocr, "Reader", reader)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        ocr.load_reader()
    assert [str(w.message) for w in captured] == ["another initialization warning"]
