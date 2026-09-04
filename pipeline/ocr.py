# implements FR5, rules.md #9 (low-confidence reads flagged, not dropped)
"""OCR over a cropped plate-region image."""

import re
import warnings

import easyocr

LOW_CONFIDENCE_THRESHOLD = 0.4
_PLATE_CHARS = re.compile(r"[^A-Z0-9]")


def load_reader() -> easyocr.Reader:
    # EasyOCR 1.7.x still uses dynamic quantization. Preserve the CPU speedup;
    # filter only its known upstream notice, never all warnings (D-028).
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"torch\.quantize_per_tensor, torch\.quantize_per_channel and other quantized tensor creation functions.*deprecated.*",
            category=UserWarning,
            module=r"torch\.ao\.nn\.quantized\.dynamic\.modules\.rnn",
        )
        return easyocr.Reader(["en"], gpu=False)


def read_plate(reader: easyocr.Reader, plate_crop) -> tuple[str | None, float]:
    """Returns (plate_text_or_None, confidence). Never raises on a bad crop."""
    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0
    try:
        with warnings.catch_warnings():
            if getattr(reader, "device", None) == "cpu":
                warnings.filterwarnings(
                    "ignore",
                    message=r"'pin_memory' argument is set as true but no accelerator is found, then device pinned memory won't be used\.",
                    category=UserWarning,
                    module=r"torch\.utils\.data\.dataloader",
                )
            results = reader.readtext(plate_crop)
    except Exception:
        return None, 0.0
    if not results:
        return None, 0.0

    text = "".join(r[1] for r in results)
    text = _PLATE_CHARS.sub("", text.upper())
    confidence = sum(r[2] for r in results) / len(results)
    return (text or None), float(confidence)
