# implements FR8 — see decisions.md D-014. Intentionally NOT read-only-from-DB —
# documented exception to rules.md #12. Composes pipeline.image_detection (images)
# and pipeline.run_pipeline.run() unchanged (videos).
"""Upload a video or image and run detection directly from the app."""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    # st.Page executes this file with `app/` (not the repo root) as the import
    # root, so the top-level `pipeline` package isn't importable without this.
    sys.path.insert(0, str(REPO_ROOT))

import cv2
import pandas as pd
import streamlit as st

from pipeline import run_pipeline
from pipeline.detection import load_detector
from pipeline.image_detection import annotate_detections, detect_image
from pipeline.ocr import load_reader
from pipeline.plate_detection import load_plate_detector
from pipeline.video_io import normalize_for_opencv

DB_PATH = REPO_ROOT / "database" / "traffic.db"
OUTPUT_DIR = REPO_ROOT / "output"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}


@st.cache_resource(show_spinner="Loading vehicle detector (first run only)...")
def get_detector():
    return load_detector()


@st.cache_resource(show_spinner="Loading plate detector (first run only)...")
def get_plate_detector():
    return load_plate_detector()


@st.cache_resource(show_spinner="Loading OCR reader (first run only)...")
def get_ocr_reader():
    return load_reader()


def classify_upload(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return "unknown"


st.title("Upload & Detect")

st.sidebar.header("Upload")
uploaded = st.sidebar.file_uploader("Video or image", type=["mp4", "avi", "mov", "jpg", "jpeg", "png"])

st.sidebar.header("Detection settings")
conf = st.sidebar.slider("Detection confidence", 0.10, 0.90, 0.30, 0.05)

kind = classify_upload(uploaded) if uploaded is not None else None

line_ratio = 0.6
if kind == "video":
    line_ratio = st.sidebar.slider("Counting line position (fraction of frame height)", 0.1, 0.9, 0.6, 0.05)

run_clicked = st.sidebar.button(
    "Run detection", type="primary", use_container_width=True, disabled=uploaded is None
)

if not uploaded:
    st.info("Upload a video or image from the sidebar, then click **Run detection**.")
elif kind == "unknown":
    st.error("Unsupported file type. Please upload a .mp4/.avi/.mov video or a .jpg/.jpeg/.png image.")

if run_clicked and kind in ("image", "video"):
    suffix = Path(uploaded.name).suffix.lower()
    uploaded_bytes = uploaded.getvalue()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(uploaded_bytes)
    tmp.close()
    tmp_path = tmp.name
    normalized_path = tmp_path

    if len(uploaded_bytes) == 0:
        st.error("The uploaded file appears to be empty. Please try re-uploading it.")
        st.session_state.pop("upload_result", None)
        os.unlink(tmp_path)
    else:
        try:
            if kind == "image":
                frame = cv2.imread(tmp_path)
                if frame is None:
                    st.error("Could not read this file as an image. It may be corrupt or an unsupported format.")
                    st.session_state.pop("upload_result", None)
                else:
                    with st.spinner("Running detection..."):
                        detections = detect_image(frame, get_detector(), get_plate_detector(), get_ocr_reader(), conf=conf)
                        annotated = annotate_detections(frame, detections)

                    st.session_state["upload_result"] = {
                        "kind": "image",
                        "annotated": annotated,
                        "detections": detections,
                        "name": uploaded.name,
                    }

            elif kind == "video":
                run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_video = str(OUTPUT_DIR / f"results_video_{run_id}.mp4")
                output_csv = str(OUTPUT_DIR / f"logs_{run_id}.csv")

                try:
                    with st.spinner("Processing video — this can take a few minutes on CPU..."):
                        # phone-recorded uploads are often HEVC, which OpenCV's Windows
                        # wheels can't decode — normalize to H.264 first (D-017)
                        normalized_path = normalize_for_opencv(tmp_path)
                        run_pipeline.run(
                            source=normalized_path,
                            db_path=str(DB_PATH),
                            output_video=output_video,
                            output_csv=output_csv,
                            line_ratio=line_ratio,
                            conf=conf,
                        )
                except Exception as e:
                    st.error(f"Could not process this video: {e}")
                    st.session_state.pop("upload_result", None)
                else:
                    st.session_state["upload_result"] = {
                        "kind": "video",
                        "output_video": output_video,
                        "output_csv": output_csv,
                        "crossing_count": len(pd.read_csv(output_csv)),
                    }
        finally:
            try:
                os.unlink(tmp_path)
            except OSError as e:
                st.warning(f"Could not remove temporary file: {e}")
            if normalized_path != tmp_path:
                try:
                    os.unlink(normalized_path)
                except OSError:
                    pass

result = st.session_state.get("upload_result")
if result and result["kind"] == "image":
    detections = result["detections"]
    annotated = result["annotated"]

    st.image(annotated, channels="BGR", use_container_width=True, caption=f"{len(detections)} vehicle(s) detected")

    if not detections:
        st.warning("No vehicles detected. Try lowering the confidence threshold in the sidebar.")
    else:
        results_df = pd.DataFrame(
            [
                {
                    "vehicle_type": d.vehicle_type,
                    "plate_number": d.plate_number,
                    "ocr_confidence": round(d.ocr_confidence, 3),
                    "is_low_confidence": d.is_low_confidence,
                }
                for d in detections
            ]
        )
        st.dataframe(results_df, use_container_width=True)

    st.caption("Results shown here are session-only and are not written to the database (see decisions.md D-014).")

    ok, buf = cv2.imencode(".png", annotated)
    if ok:
        st.download_button(
            "Download annotated image",
            data=buf.tobytes(),
            file_name=f"annotated_{Path(result['name']).stem}.png",
            mime="image/png",
        )

elif result and result["kind"] == "video":
    output_video = result["output_video"]
    output_csv = result["output_csv"]

    st.success("Video processed. New crossing events (if any) were written to the database — check the Dashboard page.")
    st.metric("Crossing events detected", result["crossing_count"])
    if result["crossing_count"] == 0:
        st.info("No vehicles crossed the counting line. Try adjusting the line position in the sidebar and re-running.")

    video_bytes = Path(output_video).read_bytes()
    st.video(video_bytes)
    st.download_button("Download annotated video", data=video_bytes, file_name=Path(output_video).name, mime="video/mp4")
    st.download_button(
        "Download CSV log", data=Path(output_csv).read_bytes(), file_name=Path(output_csv).name, mime="text/csv"
    )
