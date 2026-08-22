import csv
import sqlite3

import cv2
import numpy as np

import pipeline.run_pipeline as run_pipeline
from pipeline.tracking import TrackedBox


def _write_tiny_video(path, width=64, height=48, fps=10.0, frames=1):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for _ in range(frames):
        writer.write(np.zeros((height, width, 3), dtype=np.uint8))
    writer.release()


def test_run_end_to_end_writes_one_crossing_to_db_csv_and_video(tmp_path, monkeypatch):
    width, height = 64, 48
    source = tmp_path / "source.mp4"
    _write_tiny_video(source, width=width, height=height)

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    fake_frames = [
        (0, frame.copy(), [TrackedBox(track_id=1, vehicle_type="car", x1=5, y1=0, x2=15, y2=10)]),  # above line
        (1, frame.copy(), [TrackedBox(track_id=1, vehicle_type="car", x1=5, y1=40, x2=15, y2=48)]),  # crosses below
    ]

    monkeypatch.setattr(run_pipeline, "load_detector", lambda: object())
    monkeypatch.setattr(run_pipeline, "load_plate_detector", lambda: None)
    monkeypatch.setattr(run_pipeline, "load_reader", lambda: object())
    monkeypatch.setattr(run_pipeline, "iter_tracked_frames", lambda *a, **k: iter(fake_frames))
    monkeypatch.setattr(run_pipeline, "read_plate", lambda reader, crop: ("ABC123", 0.9))

    db_path = tmp_path / "traffic.db"
    output_video = tmp_path / "out.mp4"
    output_csv = tmp_path / "out.csv"

    run_pipeline.run(str(source), str(db_path), str(output_video), str(output_csv), line_ratio=0.5)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT track_id, vehicle_type, plate_number FROM vehicle_events").fetchall()
    conn.close()
    assert rows == [(1, "car", "ABC123")]

    with open(output_csv, newline="") as f:
        csv_rows = list(csv.reader(f))
    assert len(csv_rows) == 2  # header + one crossing
    assert csv_rows[1][2] == "ABC123"

    assert output_video.exists()
    assert output_video.stat().st_size > 0


def test_run_no_crossing_writes_nothing(tmp_path, monkeypatch):
    width, height = 64, 48
    source = tmp_path / "source.mp4"
    _write_tiny_video(source, width=width, height=height)

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Both frames stay on the same side of the line - never crosses.
    fake_frames = [
        (0, frame.copy(), [TrackedBox(track_id=1, vehicle_type="car", x1=5, y1=0, x2=15, y2=10)]),
        (1, frame.copy(), [TrackedBox(track_id=1, vehicle_type="car", x1=5, y1=1, x2=15, y2=11)]),
    ]

    monkeypatch.setattr(run_pipeline, "load_detector", lambda: object())
    monkeypatch.setattr(run_pipeline, "load_plate_detector", lambda: None)
    monkeypatch.setattr(run_pipeline, "load_reader", lambda: object())
    monkeypatch.setattr(run_pipeline, "iter_tracked_frames", lambda *a, **k: iter(fake_frames))
    monkeypatch.setattr(run_pipeline, "read_plate", lambda reader, crop: ("ABC123", 0.9))

    db_path = tmp_path / "traffic.db"
    output_video = tmp_path / "out.mp4"
    output_csv = tmp_path / "out.csv"

    run_pipeline.run(str(source), str(db_path), str(output_video), str(output_csv), line_ratio=0.5)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM vehicle_events").fetchone()[0]
    conn.close()
    assert count == 0

    with open(output_csv, newline="") as f:
        csv_rows = list(csv.reader(f))
    assert len(csv_rows) == 1  # header only
