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

import shutil
import subprocess

import cv2
import pandas as pd
import streamlit as st

from pipeline import run_pipeline
from pipeline.detection import load_detector
from pipeline.image_detection import annotate_detections, detect_image
from pipeline.ocr import load_reader
from pipeline.plate_detection import load_plate_detector

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


def make_browser_preview(src_path: str) -> str | None:
    """Transcode to H.264 for in-browser <video> playback (see decisions.md D-015).

    pipeline.run_pipeline.run() writes MPEG-4 Part 2 ("mp4v") video, which
    browsers won't play natively in a <video> tag even though it downloads
    and plays fine in a native player. This produces a throwaway H.264 copy
    for preview only; the original file (returned to the user via the
    download button) is untouched. Returns None if ffmpeg isn't available or
    transcoding fails — callers must fall back gracefully, not crash.
    """
    if shutil.which("ffmpeg") is None:
        return None
    preview = tempfile.NamedTemporaryFile(suffix="_preview.mp4", delete=False)
    preview.close()
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", preview.name],
            check=True, capture_output=True, timeout=300,
        )
        return preview.name
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        try:
            os.unlink(preview.name)
        except OSError:
            pass
        return None


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
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(uploaded.getvalue())
    tmp.close()
    tmp_path = tmp.name

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
                    run_pipeline.run(
                        source=tmp_path,
                        db_path=str(DB_PATH),
                        output_video=output_video,
                        output_csv=output_csv,
                        line_ratio=line_ratio,
                    )
            except RuntimeError as e:
                st.error(f"Could not process this video: {e}")
                st.session_state.pop("upload_result", None)
            else:
                preview_path = make_browser_preview(output_video)
                preview_bytes = None
                if preview_path:
                    try:
                        preview_bytes = Path(preview_path).read_bytes()
                    finally:
                        try:
                            os.unlink(preview_path)
                        except OSError:
                            pass

                st.session_state["upload_result"] = {
                    "kind": "video",
                    "output_video": output_video,
                    "output_csv": output_csv,
                    "crossing_count": len(pd.read_csv(output_csv)),
                    "preview_bytes": preview_bytes,
                }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError as e:
            st.warning(f"Could not remove temporary file: {e}")

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

    if result["preview_bytes"] is not None:
        st.video(result["preview_bytes"])
    else:
        st.info(
            "Couldn't generate an in-browser preview (requires `ffmpeg` on PATH). "
            "The downloaded file below plays fine in a normal video player (e.g. VLC)."
        )

    video_bytes = Path(output_video).read_bytes()
    st.download_button("Download annotated video", data=video_bytes, file_name=Path(output_video).name, mime="video/mp4")
    st.download_button(
        "Download CSV log", data=Path(output_csv).read_bytes(), file_name=Path(output_csv).name, mime="text/csv"
    )
