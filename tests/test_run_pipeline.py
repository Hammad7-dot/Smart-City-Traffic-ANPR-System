import csv
from pathlib import Path
import sqlite3

import cv2
import numpy as np
import pytest

import pipeline.run_pipeline as run_pipeline
from pipeline.tracking import TrackedBox


@pytest.fixture
def crossing_run(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    _write_tiny_video(source)
    frames = [
        (0, np.zeros((48, 64, 3), dtype=np.uint8),
         [TrackedBox(1, "car", 5, 0, 15, 10)]),
        (1, np.zeros((48, 64, 3), dtype=np.uint8),
         [TrackedBox(1, "car", 5, 40, 15, 48)]),
    ]
    monkeypatch.setattr(run_pipeline, "load_detector", lambda: object())
    monkeypatch.setattr(run_pipeline, "load_plate_detector", lambda: None)
    monkeypatch.setattr(run_pipeline, "load_reader", lambda: object())
    monkeypatch.setattr(run_pipeline, "iter_tracked_frames", lambda *a, **k: iter(frames))
    monkeypatch.setattr(run_pipeline, "read_plate", lambda reader, crop: ("ABC123", 0.9))
    return dict(source=str(source), db_path=str(tmp_path / "traffic.db"),
                output_video=str(tmp_path / "out.mp4"), output_csv=str(tmp_path / "out.csv"),
                line_ratio=0.5)


def test_ocr_receives_unannotated_pixels(crossing_run, monkeypatch):
    observed = []

    def read_clean_crop(reader, crop):
        observed.append(crop.copy())
        return "ABC123", 0.9

    monkeypatch.setattr(run_pipeline, "read_plate", read_clean_crop)
    run_pipeline.run(**crossing_run)
    assert len(observed) == 1
    assert not np.any(observed[0]), "Drawing overlays must not contaminate OCR input"


def test_plate_detection_failure_preserves_crossing(crossing_run, monkeypatch):
    def fail_crop(*args):
        raise RuntimeError("plate inference failed")

    monkeypatch.setattr(run_pipeline, "crop_plate_region", fail_crop)
    run_pipeline.run(**crossing_run)
    with sqlite3.connect(crossing_run["db_path"]) as conn:
        rows = conn.execute("SELECT track_id, plate_number, is_low_confidence FROM vehicle_events").fetchall()
    assert rows == [(1, None, 1)]
    with open(crossing_run["output_csv"], newline="") as handle:
        assert len(list(csv.reader(handle))) == 2


def test_missing_plate_is_flagged_even_with_high_ocr_confidence(crossing_run, monkeypatch):
    monkeypatch.setattr(run_pipeline, "read_plate", lambda *args: (None, 0.9))
    run_pipeline.run(**crossing_run)
    with sqlite3.connect(crossing_run["db_path"]) as conn:
        assert conn.execute("SELECT is_low_confidence FROM vehicle_events").fetchone() == (1,)


@pytest.mark.parametrize("line_ratio", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_line_ratio_rejected_before_creating_outputs(crossing_run, line_ratio):
    crossing_run["line_ratio"] = line_ratio
    with pytest.raises(ValueError, match="line_ratio"):
        run_pipeline.run(**crossing_run)
    assert not Path(crossing_run["db_path"]).exists()
    assert not Path(crossing_run["output_video"]).exists()
    assert not Path(crossing_run["output_csv"]).exists()


def test_bad_source_does_not_create_database(crossing_run):
    crossing_run["source"] += ".missing"
    with pytest.raises(RuntimeError, match="Could not open"):
        run_pipeline.run(**crossing_run)
    assert not Path(crossing_run["db_path"]).exists()


def test_csv_open_failure_closes_database(crossing_run, monkeypatch):
    stores = []
    real_store = run_pipeline.EventStore

    def capture_store(path):
        store = real_store(path)
        stores.append(store)
        return store

    monkeypatch.setattr(run_pipeline, "EventStore", capture_store)
    crossing_run["output_csv"] = str(Path(crossing_run["source"]).parent)
    try:
        with pytest.raises(OSError):
            run_pipeline.run(**crossing_run)
        assert len(stores) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            stores[0].conn.execute("SELECT 1")
    finally:
        for store in stores:
            store.close()


def test_video_uses_requested_detection_confidence(crossing_run, monkeypatch):
    observed = []

    def track(detector, source, classes, conf=0.3):
        observed.append(conf)
        return iter(())

    monkeypatch.setattr(run_pipeline, "iter_tracked_frames", track)
    run_pipeline.run(**crossing_run, conf=0.75)
    assert observed == [0.75]


@pytest.mark.parametrize("conf", [-0.1, 1.1, float("nan")])
def test_invalid_confidence_rejected_before_outputs(crossing_run, conf):
    with pytest.raises(ValueError, match="conf"):
        run_pipeline.run(**crossing_run, conf=conf)
    assert not Path(crossing_run["db_path"]).exists()


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
