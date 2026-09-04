# Smart City Traffic ANPR System

**Live demo:** https://smart-city-traffic-anpr-system-q5skn4nku6cqwkuukr4mam.streamlit.app/

Real-time traffic monitoring pipeline: YOLOv8 vehicle detection → tracking →
line-crossing vehicle counts → license plate OCR → SQLite → Streamlit dashboard.
Built pretrained-first (no custom training) for a smart-city ANPR use case.

![Dashboard demo](docs/demo.gif)

## Architecture

```
Video Input
  → Frame Extraction (OpenCV)
  → YOLOv8 Vehicle Detection (pretrained, COCO)
  → DeepSORT / ByteTrack Tracking (unique ID per vehicle)
  → Line Crossing Detection (centroid-based)
  → License Plate Detection (YOLO ANPR model)
  → OCR (EasyOCR / Tesseract)
  → Database (SQLite → PostgreSQL later)
  → Dashboard (Streamlit) / Service (FastAPI)
```

Full requirements and design rationale: [docs/SPEC.md](docs/SPEC.md),
[docs/decisions.md](docs/decisions.md).

## Features

- Detects vehicle classes (car, bike, truck, bus) in video with pretrained YOLOv8
- Assigns a persistent tracker ID per vehicle across frames
- Counts each vehicle exactly once, on virtual-line crossing (not per-frame presence)
- Runs plate detection + OCR only on crossing events, not every frame
- Stores vehicle type, plate number (with confidence flag for low-confidence reads),
  and timestamp in SQLite (`database/schema.sql`)
- Streamlit **Dashboard** page for live/historical counts and plate logs (DB-only, read-only)
- Streamlit **Upload & Detect** page for ad hoc image/video uploads outside the CLI pipeline

## Known limitations

- Model weights are gitignored, not bundled with a fresh clone. A locally trained plate
  detector is documented in D-021; place its weights at `models/plate_model.pt` to use it.
  Without that file, plate detection falls back to OCR of the vehicle crop's lower third.
- OCR accuracy depends on plate resolution and footage quality, even with a dedicated
  detector (see the sample-video baseline in D-022). Low-confidence and missing reads
  are flagged; they are not reliable plate identifications.
- OCR is configured for CPU. Processing high-resolution footage can be slow.

See [docs/decisions.md](docs/decisions.md) (D-011, D-013, D-021, D-022) for details.

## Setup

```bash
pip install -r requirements.txt
```

Set `KMP_DUPLICATE_LIB_OK=TRUE` in the environment before running anything that imports
`torch` (this Anaconda install links two OpenMP runtimes and crashes on import otherwise).

Video output is encoded directly as browser-playable H.264 through PyAV; a separate
`ffmpeg` executable is not required. Non-H.264 uploads are normalized through PyAV
before detection (D-016/D-017).

## Usage

```bash
# run the full pipeline on a video (writes output video, CSV log, and DB rows)
python -m pipeline.run_pipeline --source data/videos/traffic.mp4
# optional: --db, --output-video, --output-csv, --line-ratio (virtual line y-position, 0-1)

# launch the dashboard (reads database/traffic.db)
streamlit run app/streamlit_app.py

# purge vehicle_events rows older than N days (retention policy)
python -m pipeline.purge --db database/traffic.db --days 30
```

Test suite: `python -m pytest` (bare `pytest` won't resolve `import pipeline` without an installed
package — see `tests/conftest.py`). CI (`.github/workflows/ci.yml`) runs a clean install + full
test suite on every push/PR.

If an existing Windows pytest temporary directory is inaccessible, use a new, unused
workspace-local path, for example `python -m pytest --basetemp=output/pytest-local-01`.
Pytest clears its base temporary directory, so never point this option at existing data.

The pipeline rejects counting-line positions outside 0–1. Plate-stage failures preserve
the crossing with an empty, low-confidence plate; output resources are closed even when
setup fails. Database parent directories are created automatically. Retention days must
be non-negative. The Upload & Detect confidence slider applies to both images and videos.

## Tech stack

Python, OpenCV, YOLOv8, DeepSORT/ByteTrack, EasyOCR/Tesseract, FastAPI, Streamlit,
SQLite (→ PostgreSQL later).

## Project status & privacy

This is a v1 build, deployed live on Streamlit Community Cloud (see link at the top). Plate
numbers and any frame with a readable plate are treated as PII — raw sample footage, exported
logs with real plates, and DB dumps are never committed (see `.gitignore`).

**Data retention**: `vehicle_events` rows older than 30 days are purged via
`python -m pipeline.purge` (see [docs/decisions.md](docs/decisions.md) D-024, resolving
[docs/blocked.md](docs/blocked.md) B-003) — but the purge is manual/externally-scheduled, not
automatic yet.

## Repo layout

```
├── app/                  # Streamlit dashboard + upload/detect pages
├── database/             # schema.sql (source of truth) + local traffic.db (gitignored)
├── docs/                 # SPEC, rules, decisions, blocked questions
├── models/               # YOLO weights (gitignored)
├── pipeline/             # detection, tracking, line-crossing, plate OCR, storage, run_pipeline
├── data/, output/        # inputs/outputs (gitignored)
└── requirements.txt
```
