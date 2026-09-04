# orchestrates FR1-FR6; entry point for the full ANPR pipeline
"""End-to-end pipeline: video -> detect -> track -> count -> plate OCR -> DB + logs.

Usage:
    python -m pipeline.run_pipeline --source data/videos/traffic.mp4
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # avoid OpenMP double-init crash

import argparse
import csv
import logging
from contextlib import ExitStack, closing
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

import av
import cv2

from pipeline.detection import VEHICLE_CLASS_MAP, load_detector
from pipeline.line_crossing import LineCrossingCounter
from pipeline.ocr import LOW_CONFIDENCE_THRESHOLD, load_reader, read_plate
from pipeline.plate_detection import crop_plate_region, load_plate_detector
from pipeline.storage import EventStore
from pipeline.tracking import iter_tracked_frames

logger = logging.getLogger(__name__)


def run(source: str, db_path: str, output_video: str, output_csv: str,
        line_ratio: float = 0.6, conf: float = 0.3):
    if not 0 <= line_ratio <= 1:
        raise ValueError("line_ratio must be between 0 and 1")
    if not 0 <= conf <= 1:
        raise ValueError("conf must be between 0 and 1")
    cap = cv2.VideoCapture(source)
    try:
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video source: {source}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    finally:
        cap.release()

    detector = load_detector()
    plate_detector = load_plate_detector()  # None -> crop_plate_region falls back (D-011)
    ocr_reader = load_reader()

    line_y = height * line_ratio
    counter = LineCrossingCounter(line_y=line_y)

    Path(output_video).parent.mkdir(parents=True, exist_ok=True)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now()
    crossing_count = 0
    frame_count = 0

    # Register resources as soon as they open, including during partial setup.
    with ExitStack() as resources:
        store = resources.enter_context(closing(EventStore(db_path)))
        # H.264 is browser-playable; OpenCV's default mp4v is not (D-016).
        container = resources.enter_context(closing(av.open(output_video, mode="w")))
        stream = container.add_stream("libx264", rate=Fraction(fps).limit_denominator())
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"

        csv_file = resources.enter_context(open(output_csv, "w", newline="", encoding="utf-8"))
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            ["track_id", "vehicle_type", "plate_number", "ocr_confidence", "is_low_confidence", "frame_number", "event_timestamp"]
        )

        for frame_index, frame, boxes in iter_tracked_frames(detector, source, VEHICLE_CLASS_MAP, conf=conf):
            frame_count += 1
            annotated = frame.copy()
            cv2.line(annotated, (0, int(line_y)), (width, int(line_y)), (0, 255, 255), 2)

            for box in boxes:
                cv2.rectangle(annotated, (int(box.x1), int(box.y1)), (int(box.x2), int(box.y2)), (0, 200, 0), 2)
                cv2.putText(
                    annotated, f"{box.vehicle_type}#{box.track_id}", (int(box.x1), max(int(box.y1) - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 2,
                )

                crossed = counter.update(box.track_id, box.centroid)
                if not crossed:
                    continue

                crossing_count += 1
                event_time = start_time + timedelta(seconds=frame_index / fps)
                event_timestamp = event_time.isoformat()

                # NFR reliability: a failed plate stage must not lose the crossing.
                try:
                    plate_crop = crop_plate_region(frame, (box.x1, box.y1, box.x2, box.y2), plate_detector)
                    plate_text, confidence = read_plate(ocr_reader, plate_crop)
                except Exception:
                    # Do not log exception text: model errors may contain plate PII.
                    logger.warning("Plate recognition failed at frame %s; preserving crossing", frame_index)
                    plate_text, confidence = None, 0.0
                is_low_confidence = not plate_text or confidence < LOW_CONFIDENCE_THRESHOLD

                written = store.record_event(
                    track_id=box.track_id,
                    vehicle_type=box.vehicle_type,
                    plate_number=plate_text,
                    ocr_confidence=confidence,
                    is_low_confidence=is_low_confidence,
                    frame_number=frame_index,
                    event_timestamp=event_timestamp,
                )
                if written:
                    csv_writer.writerow(
                        [box.track_id, box.vehicle_type, plate_text, f"{confidence:.3f}", int(is_low_confidence), frame_index, event_timestamp]
                    )

            av_frame = av.VideoFrame.from_ndarray(annotated, format="bgr24")
            for packet in stream.encode(av_frame):
                container.mux(packet)

        for packet in stream.encode():
            container.mux(packet)
    print(f"Processed {frame_count} frames, {crossing_count} crossing events.")
    print(f"Output video: {output_video}")
    print(f"Output CSV:   {output_csv}")
    print(f"Database:     {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Run the Smart City Traffic ANPR pipeline")
    parser.add_argument("--source", default="data/videos/traffic.mp4")
    parser.add_argument("--db", default="database/traffic.db")
    parser.add_argument("--output-video", default="output/results_video.mp4")
    parser.add_argument("--output-csv", default="output/logs.csv")
    parser.add_argument("--line-ratio", type=float, default=0.6, help="Virtual line y-position as a fraction of frame height")
    args = parser.parse_args()

    run(args.source, args.db, args.output_video, args.output_csv, args.line_ratio)


if __name__ == "__main__":
    main()
