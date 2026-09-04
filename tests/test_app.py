"""FR8: exercise the upload result UI without model downloads or real footage."""

from pathlib import Path

import numpy as np
from streamlit.testing.v1 import AppTest

from pipeline.image_detection import ImageDetection

UPLOAD_PAGE = Path(__file__).resolve().parents[1] / "app" / "pages" / "upload_detect.py"


def test_image_results_render_without_deprecated_width_warnings(caplog):
    app = AppTest.from_file(UPLOAD_PAGE)
    app.session_state["upload_result"] = {
        "kind": "image", "name": "synthetic.png",
        "annotated": np.zeros((32, 32, 3), dtype=np.uint8),
        "detections": [ImageDetection("car", 0, 0, 20, 20, None, 0.0, True)],
    }
    app.run(timeout=30)
    assert not app.exception
    assert len(app.dataframe) == 1
    assert all("use_container_width" not in record.getMessage() for record in caplog.records)


def test_expired_video_result_does_not_crash_page(tmp_path):
    app = AppTest.from_file(UPLOAD_PAGE)
    app.session_state["upload_result"] = {
        "kind": "video", "crossing_count": 1,
        "output_video": str(tmp_path / "expired.mp4"),
        "output_csv": str(tmp_path / "expired.csv"),
    }
    app.run(timeout=30)
    assert not app.exception
    assert any("expired" in message.value.lower() for message in app.info)
    assert "upload_result" not in app.session_state
