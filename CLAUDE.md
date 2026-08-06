# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

The v1 pipeline described below is implemented and has been run end-to-end against a
sample video (detection → tracking → counting → plate OCR → SQLite → Streamlit dashboard).
The Streamlit app is now multipage (`app/streamlit_app.py` is a thin shell) with a
Dashboard page and an Upload & Detect page for ad hoc image/video uploads — see
docs/decisions.md D-014. No git repo is initialized yet. It holds the planning artifacts for a
"Smart City Traffic ANPR System" (automatic number-plate recognition for traffic
counting/monitoring):

- `docs/SPEC.md` — problem statement, objectives, functional/non-functional requirements,
  architecture, and planned repo layout. This is the source of truth for *what* to build.
- `docs/rules.md` — process and implementation rules that govern *how* code gets written.
- `docs/decisions.md` — decision log (accepted architectural/tooling choices with rationale).
- `docs/blocked.md` — open questions that block implementation; not yet resolved.

Before writing any code, read `docs/SPEC.md` for the requirement it maps to, and check
`docs/rules.md` + `docs/decisions.md` for constraints already agreed on. Do not invent architecture
that contradicts these docs.

## Working rules (from docs/rules.md)

- **No code without a spec line.** Every function/module should trace back to an FR/NFR
  ID in `docs/SPEC.md` (e.g. `# implements FR3`). If it doesn't map to anything, log the gap in
  `docs/blocked.md` rather than building it anyway.
- **Spec deviations are logged, not silent.** Any new dependency, changed threshold, or
  changed schema gets an entry in `docs/decisions.md` — not just a code comment.
- **Unresolved ambiguity blocks, it doesn't get guessed.** Underspecified requirements
  (e.g. "real-time" with no target FPS) go in `docs/blocked.md` instead of picking an arbitrary
  value.
- **One pipeline stage, one module.** Detection, tracking, line-crossing, plate detection,
  OCR, and storage must stay separately testable units — don't collapse stages together.
- **Pretrained-first.** Use pretrained YOLOv8 (COCO) for vehicle detection and a
  pretrained/Roboflow ANPR model for plates. Custom training is out of scope for v1 unless
  a decision entry says otherwise.
- **Plate numbers are PII.** Treat `plate_number` and any frame with a readable plate as
  sensitive — never commit raw sample footage, exported logs with real plates, or DB
  dumps.
- **Vehicles are counted once per line crossing**, using tracker ID + crossing-event
  state, never per-frame presence.
- **Plate detection/OCR only runs on a crossing event** — never on every frame (perf/cost
  control, FR4).
- **Low-confidence OCR reads are stored with a confidence/flag field**, not discarded and
  not treated as ground truth.
- **`database/schema.sql` is the single source of truth for the schema.** No ad hoc table
  creation elsewhere. Avoid SQLite-only syntax since Postgres is the later migration
  target.
- **The analytics Dashboard page (`app/pages/dashboard.py`) only reads from the
  database** — it must not contain detection/tracking/OCR logic. The separate
  Upload & Detect page (`app/pages/upload_detect.py`) is an explicit, documented
  exception (docs/decisions.md D-014), not a violation.
- **Keep interchangeable stages swappable**: DeepSORT vs ByteTrack, EasyOCR vs Tesseract.

## Architecture (planned — docs/SPEC.md §4)

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

Planned repo layout (docs/SPEC.md §8):

```
smart-traffic-anpr/
├── data/{videos,images}/
├── notebooks/{vehicle_detection, tracking_and_counting, license_plate_ocr}.ipynb
├── models/{vehicle_model.pt, plate_model.pt}
├── database/{traffic.db, schema.sql}
├── app/streamlit_app.py, app/pages/{dashboard.py,upload_detect.py}, app/assets/style.css
├── .streamlit/config.toml
├── pipeline/image_detection.py
├── output/{results_video.mp4, logs.csv}
├── requirements.txt
└── README.md
```

Tech stack: Python, OpenCV, YOLOv8, DeepSORT/ByteTrack, EasyOCR/Tesseract, FastAPI,
Streamlit, SQLite (→ PostgreSQL later).

## Commands

Set `KMP_DUPLICATE_LIB_OK=TRUE` in the environment before running anything that imports
`torch` — this Anaconda install links two OpenMP runtimes and crashes on import otherwise.

```bash
# install dependencies
pip install -r requirements.txt

# run the full pipeline on a video (writes output video, CSV log, and DB rows)
python -m pipeline.run_pipeline --source data/videos/traffic.mp4
# optional: --db, --output-video, --output-csv, --line-ratio (virtual line y-position, 0-1)

# launch the dashboard (reads database/traffic.db)
streamlit run app/streamlit_app.py
```

`ffmpeg` on PATH is optional but recommended: the Upload & Detect page's
in-browser video preview needs it to transcode the pipeline's mp4v output to
browser-playable H.264 (docs/decisions.md D-015). Without it, the preview player is
skipped but the download button still works.

No test suite or linter is configured yet.

## Known limitations from the current build (see docs/decisions.md D-011, D-013)

- **No dedicated plate-detector model.** No no-auth-required pretrained license-plate
  YOLO weights could be sourced at build time (Roboflow requires an API key; several
  public HuggingFace/GitHub URLs were 401/404/HTML-not-a-checkpoint). `pipeline/plate_detection.py`
  falls back to OCR-ing the lower third of each vehicle's bounding box. Drop real weights
  at `models/plate_model.pt` to use a real detector — no code changes needed, it's picked
  up automatically if present.
- **Plate OCR accuracy is low in this configuration** as a direct consequence of the
  above — expect garbled/low-confidence reads until a real plate model is added.
- Runs on CPU (`torch` installed here is a `+cpu` build despite a GPU being present).
  Works, just slow; installing a CUDA build of torch would speed up detection/OCR.

## Open blockers to check before making judgment calls

B-001, B-002, B-004, B-005, B-006 were resolved for v1 in `docs/decisions.md` (D-006 through
D-013) — see `docs/blocked.md` for the resolution notes. **B-003 (data retention/privacy
policy) is still genuinely open** — this build is local/dev only, has no purge policy,
and must not be deployed further without answering it first.

Do not silently resolve new ambiguities — add to `docs/blocked.md`, and move to
`docs/decisions.md` once actually decided.
