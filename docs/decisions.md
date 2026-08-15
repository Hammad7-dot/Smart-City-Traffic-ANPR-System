# decisions.md — Decision Log

Format per entry:
```
## D-00X: <short title>
Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded
Context: why this came up
Decision: what was decided
Alternatives considered: what else was on the table
Consequences: what this affects downstream (spec, rules, code)
```

Seed entries below are pulled directly from the source PDF (things it already
committed to). Add new entries as the project evolves — do not edit history,
append and mark old ones "Superseded" if reversed.

---

## D-001: Use pretrained YOLOv8 (COCO) for vehicle detection
Date: (source doc)
Status: Accepted
Context: Need to detect car/bike/truck/bus without collecting a custom dataset.
Decision: Use a pretrained YOLOv8 model trained on COCO rather than training
from scratch.
Alternatives considered: Custom-trained detector on city-specific footage.
Consequences: Faster to ship; accuracy is bounded by COCO's vehicle classes
and won't be tuned to local vehicle types (e.g. rickshaws) unless revisited.

## D-002: Use DeepSORT / ByteTrack for tracking
Date: (source doc)
Status: Accepted
Context: Need unique IDs per vehicle to avoid double-counting.
Decision: Support either DeepSORT or ByteTrack as the tracker.
Alternatives considered: Simple centroid tracking (rejected — too fragile
under occlusion).
Consequences: Two trackers must stay interchangeable per rules.md #14.

## D-003: Trigger plate detection/OCR only on line-crossing
Date: (source doc)
Status: Accepted
Context: Running plate detection on every frame is wasteful.
Decision: Plate detection + OCR fire only when a tracked vehicle crosses the
virtual line.
Alternatives considered: Run plate detection continuously and dedupe later
(rejected — higher compute cost, no clear benefit).
Consequences: Plate read quality depends entirely on the single frame at
crossing time — see blocked.md B-002 (multi-frame voting).

## D-004: SQLite for v1 storage, PostgreSQL as later option
Date: (source doc)
Status: Accepted
Context: Need structured storage for vehicle_type, plate, timestamp.
Decision: Ship v1 on SQLite; document schema so a PostgreSQL migration is
straightforward later.
Alternatives considered: PostgreSQL from day one (rejected for v1 — adds
ops overhead with no immediate benefit for a single-node prototype).
Consequences: rules.md #11 — avoid SQLite-only syntax where avoidable.

## D-005: Streamlit for dashboard, FastAPI for service layer
Date: (source doc)
Status: Accepted
Context: Need both a human-facing dashboard and a possible service interface.
Decision: Streamlit app for visualization; FastAPI available as the service
layer if/when an API is needed.
Alternatives considered: Single Flask/Django app doing both (rejected —
mixes concerns, harder to keep dashboard read-only per rules.md #12).
Consequences: Two codepaths to maintain; acceptable for prototype scope.

---

## D-006: "Real-time" = faster-than-playback on recorded video (resolves B-001, B-006)
Date: 2026-08-06
Status: Accepted
Context: B-001/B-006 flagged that "real-time video streams" was unquantified
and that deliverables only listed recorded sample video, not a live feed.
Decision: v1 treats "real-time" as "process recorded video faster than its
own playback duration"; input is file-based only (`data/videos/*.mp4`), no
RTSP/live-camera ingestion.
Alternatives considered: Building a streaming/RTSP input adapter now.
Consequences: `pipeline/run_pipeline.py` takes a file path via `--source`.
Live-feed ingestion is a follow-up, not implemented.

## D-007: No formal accuracy threshold gate for v1 (resolves B-004)
Date: 2026-08-06
Status: Accepted
Context: B-004 noted no mAP/OCR-accuracy target was ever specified.
Decision: v1 ships without a benchmark-based accuracy gate. Correctness is
verified qualitatively: annotated output video, `output/logs.csv`, and DB
rows are inspected per run rather than compared against a labeled
validation set.
Alternatives considered: Blocking release on a formal mAP/OCR accuracy
number (rejected — no stakeholder-supplied target exists to test against).
Consequences: FR1/FR5 acceptance criteria remain qualitative until a
threshold is supplied; revisit if this moves beyond prototype stage.

## D-008: Dedupe crossing events by track ID + short plate time-window (resolves B-005)
Date: 2026-08-06
Status: Accepted
Context: B-005 asked how to prevent a tracker ID switch from producing a
duplicate crossing/plate row for the same physical vehicle.
Decision: `pipeline/line_crossing.py`'s `LineCrossingCounter` counts each
track_id at most once, ever. As a second guard against ID switches,
`pipeline/storage.py`'s `EventStore` rejects a new row if the same
`plate_number` was already recorded within the last 5 seconds.
Alternatives considered: Dedupe by spatial proximity of centroids (rejected
for v1 — more complex, marginal benefit given the time-window+track-ID
combination already catches the common case).
Consequences: A genuine second vehicle with the exact same (misread) plate
text within 5 seconds would be incorrectly dropped — acceptable trade-off
for v1, documented here rather than silently accepted.

## D-009: No data retention/purge policy implemented (partial resolution of B-003)
Date: 2026-08-06
Status: Accepted
Context: B-003 asked how long raw video, plate crops, and DB rows are kept,
and whether anonymization is required outside law enforcement use.
Decision: Out of scope for this local/dev build. `database/traffic.db`,
`data/`, `output/`, and the source video are all gitignored so PII never
reaches the repo, but no automatic purge/retention job exists.
Alternatives considered: none — this remains genuinely unresolved for any
real deployment.
Consequences: B-003 stays Open in blocked.md; do not deploy this build
beyond local testing without answering it first.

## D-010: Ultralytics built-in ByteTrack instead of standalone DeepSORT
Date: 2026-08-06
Status: Accepted
Context: D-002 accepted either DeepSORT or ByteTrack as the tracker.
Decision: `pipeline/tracking.py` uses `model.track(..., tracker="bytetrack.yaml")`
from Ultralytics directly rather than integrating a separate DeepSORT
dependency.
Alternatives considered: `deep-sort-realtime` package (rejected for v1 —
extra dependency surface for no clear v1 benefit; ByteTrack ships built into
`ultralytics` already installed for detection).
Consequences: Swapping to `botsort.yaml` or a standalone DeepSORT later only
requires changing `pipeline/tracking.py` (rules.md #14 — stages stay
swappable); no other module depends on the tracker's internals.

## D-011: No dedicated plate-detector model — OCR runs on vehicle-crop lower third
Date: 2026-08-06
Status: Accepted
Context: SPEC.md §7 names a Roboflow dataset (`license-plate-recognition-rxg4e`)
for training/sourcing a plate model, but that requires a Roboflow API
key/account not available in this environment. Several public no-auth
weight URLs were tried (see below) and none resolved to valid Ultralytics
checkpoints (401 auth-gated, 404 not found, or an HTML page instead of a
`.pt` file).
Decision: `pipeline/plate_detection.py` supports loading a real YOLO plate
detector from `models/plate_model.pt` if present, but falls back to
cropping the lower third of each vehicle's bounding box (where plates
typically sit) and running OCR directly on that region when no model file
exists — which is the current state.
Alternatives considered: Training a plate detector from the Roboflow
dataset (out of scope per rules.md #5, pretrained-first); blocking the
whole pipeline on obtaining credentials (rejected — user asked to get an
end-to-end build running now).
Consequences: Plate read accuracy in this build is materially lower than a
real ANPR model would give (confirmed in testing: several low-confidence/
garbled reads). This is a known, documented limitation — swap in real
weights at `models/plate_model.pt` to improve it; no code changes needed.

## D-013: Single-frame OCR read, stored with confidence (resolves B-002)
Date: 2026-08-06
Status: Accepted
Context: B-002 asked whether a low-confidence single-frame plate read should
be improved via multi-frame voting before storage.
Decision: v1 stores exactly one OCR read per crossing event, tagged with
its confidence score and an `is_low_confidence` flag (rules.md #9) — no
multi-frame voting.
Alternatives considered: Multi-frame voting across the crossing window
(rejected for v1 — real complexity increase; D-003 already limits OCR to
one triggered read per crossing for perf reasons).
Consequences: Documented limitation, consistent with D-011's accuracy
caveat; revisit together if plate-read quality needs to improve.

## D-014: Multipage Streamlit app — Upload & Detect page narrows rule #12's scope; image detections are session-only, not persisted
Date: 2026-08-06
Status: Accepted
Context: User requested an in-app upload-and-detect capability (image or video)
with a nicer, multipage UI. rules.md #12 states "the dashboard only reads from
the database — it must not contain detection/tracking/OCR logic," written when
the Streamlit app was a single page. Adding a second, upload-driven page that
directly invokes the pipeline contradicts that rule as globally stated.
Separately, `database/schema.sql`'s `vehicle_events` table is crossing-event-
shaped (`track_id`/`frame_number` are NOT NULL), which doesn't semantically fit
a standalone uploaded image that has no track or frame index.
Decision:
  1. rules.md #12 is narrowed to apply specifically to the analytics Dashboard
     page (`app/pages/dashboard.py`), not the app as a whole. The new Upload &
     Detect page (`app/pages/upload_detect.py`) is explicitly permitted to call
     pipeline stages directly (composed via the new `pipeline/image_detection.py`
     for images, and `pipeline.run_pipeline.run()` unchanged for videos) — this
     is by design, not a violation.
  2. Detections from an uploaded still image are shown in-session only
     (annotated image + results table + download button) and are NOT written
     to `vehicle_events`. Forcing a schema fit (e.g. faking a track_id/
     frame_number) was rejected as a schema hack.
  3. Detections from an uploaded video continue to flow through the existing
     tracking -> line-crossing -> OCR -> EventStore path unchanged, and ARE
     written to the database exactly as a CLI-driven pipeline run would be —
     this is pre-existing accepted behavior extended to a new source (an
     uploaded file's temp path), not a new decision in itself.
  4. Uploaded source files (image or video) are written to a tempfile-managed
     path, processed, and deleted in a finally block — never persisted beyond
     the request. This does not change B-003's Open status; it just avoids
     adding a new persistent-storage surface while B-003 remains unresolved.
Alternatives considered:
  - Adding nullable track_id/frame_number to the schema so image detections
    could be stored (rejected — schema hack for a case that isn't really a
    "crossing event"; touches database/schema.sql for a UI-only feature).
  - A separate `image_detections` table (deferred — real option if this becomes
    a persistent need; not built speculatively).
  - Keeping rule #12 unmodified and building Upload & Detect as a separate
    FastAPI service instead (rejected — user wants everything in the same
    Streamlit app for v1).
Consequences: rules.md #12 and its CLAUDE.md mirror are edited to add a
"(Dashboard page specifically)" qualifier. CLAUDE.md's repo layout is updated
to include `app/pages/`, `app/assets/`, `.streamlit/config.toml`, and
`pipeline/image_detection.py`. No schema change. No change to B-003's Open
status.

## D-015: Optional ffmpeg transcode for in-browser video preview on Upload & Detect
Date: 2026-08-06
Status: Accepted
Context: `pipeline/run_pipeline.py`'s `cv2.VideoWriter` writes MPEG-4 Part 2
("mp4v" fourcc) video. That file downloads and plays fine in a native player
(VLC etc.), which is how it was always consumed before (CLI run -> download
from `output/`). The Upload & Detect page (D-014) is the first place this
video is streamed directly in a browser via `st.video()`, and browsers don't
support mp4v/MPEG-4 Part 2 playback in a `<video>` element (only H.264/H.265/
VP8/VP9/AV1) — so the preview player showed "No video with supported format."
Decision: `app/pages/upload_detect.py` shells out to `ffmpeg` (if present on
PATH) to transcode a throwaway H.264 copy of the annotated video, purely for
the in-browser `<video>` preview; the copy is written to a tempfile and
deleted immediately after use. The original file written by
`pipeline.run_pipeline.run()` is untouched and is what the "Download
annotated video" button serves — `run_pipeline.py` itself is not modified.
If `ffmpeg` isn't on PATH or transcoding fails for any reason, the page
degrades gracefully: skips the preview player, shows an info message, and
the download button still works.
Alternatives considered: Changing `cv2.VideoWriter`'s fourcc to an H.264
identifier (e.g. `avc1`) in `run_pipeline.py` directly (rejected — OpenCV's
built-in H.264 encoder support is unreliable/absent on a stock Windows
install without extra codec packs, would risk silently breaking the CLI
video-writing path that already works, and contradicts the D-014 decision to
reuse `run_pipeline.run()` unchanged). Not previewing at all, download-only
(rejected — worse UX for a feature whose whole point is showing results
inline; download-only remains the fallback when ffmpeg is unavailable).
Consequences: `ffmpeg` becomes an optional external (non-pip) dependency for
full Upload & Detect functionality; not added to `requirements.txt` since
it's a system binary, not a Python package, and the feature degrades
gracefully without it. No change to `pipeline/run_pipeline.py`'s output
format — CLI users and the "Download annotated video" button are unaffected.

## D-012: Test video is user-supplied `Brasil1.mp4`
Date: 2026-08-06
Status: Accepted
Context: No sample video existed under `data/videos/` at build time.
Decision: Used the user-supplied `Brasil1.mp4` (1920x1080, 30fps, 1115
frames, ~37s), copied to `data/videos/traffic.mp4` per the SPEC.md §8
deliverables layout.
Alternatives considered: Downloading a public sample clip (not needed once
the user supplied a video).
Consequences: `Brasil1.mp4` and `data/` are gitignored (PII rules.md #6).

## D-016: `pipeline/run_pipeline.py` writes H.264 directly via PyAV, superseding D-015's ffmpeg transcode
Date: 2026-08-06
Status: Accepted
Context: D-015's `ffmpeg`-shellout preview workaround has a real failure
mode it documents itself: if `ffmpeg` isn't on the user's PATH, the
in-browser preview silently degrades to a download-only info message. A
sibling project (RoadGuard AI) hit the identical root cause — `cv2.VideoWriter`
with `mp4v` fourcc producing video browsers can't decode — and fixed it by
writing H.264 directly with PyAV (`av`) instead of transcoding after the
fact. `av` is already effectively proven in this stack's dependency
neighborhood (same Python/OpenCV/YOLO environment) and removes an external
non-pip dependency entirely.
Decision: `pipeline/run_pipeline.py` now encodes its output video directly
as H.264 using PyAV (`av.open(..., mode="w")`, `add_stream("libx264", ...)`,
`stream.pix_fmt = "yuv420p"`) instead of `cv2.VideoWriter(..., fourcc="mp4v")`.
`app/pages/upload_detect.py`'s `make_browser_preview()` ffmpeg-shellout
function is removed; `st.video()` now plays the pipeline's own output file
directly, no separate preview copy needed. `av` is added to
`requirements.txt` (pinned `>=15.1,<19`, matching the same pin RoadGuard
uses and for the same reason: avoids a broken source build seen with newer
`av`/Python combos).
Alternatives considered: Keeping D-015's ffmpeg shim (rejected — leaves the
PATH-dependent failure mode in place for no benefit, now that a
process-internal fix is proven to work in this exact stack). Switching
`cv2.VideoWriter`'s fourcc to `avc1` (still rejected for the same reason
D-015 rejected it — unreliable/absent H.264 encoder support in stock
OpenCV builds on Windows).
Consequences: `ffmpeg` is no longer needed anywhere in this project. One
video file serves both the in-browser preview and the download button —
no more separate preview tempfile. D-015 is superseded, not deleted, per
this log's append-only convention.

## D-017: Normalize uploaded video codec via PyAV before the pipeline reads it
Date: 2026-08-13
Status: Accepted
Context: A real upload hit `RuntimeError: Could not open video source: <tmp path>`
from `pipeline/run_pipeline.py::run()`'s `cv2.VideoCapture(...).isOpened()` check.
Leading hypothesis going in: OpenCV's Windows pip wheels bundle a minimal
FFMPEG build that historically lacks an HEVC/H.265 decoder (licensing), and
modern phones default to recording `.mp4` in HEVC — `cv2.getBuildInformation()`
reporting `FFMPEG: YES` only confirms FFMPEG integration exists, not which
codecs it was built with. This was tested directly: a synthetic HEVC clip was
generated with PyAV/libx265 and opened fine via `cv2.VideoCapture` in this
environment, so HEVC-decode-missing is **not confirmed** as this specific
failure's root cause — the exact trigger for the original error remains
unconfirmed (candidates not ruled out: an unusual/rarer codec such as AV1, a
partially-written or corrupt upload, or the dual `opencv-python` /
`opencv-python-headless` install noted below). Regardless of the precise
trigger, normalizing to a codec OpenCV reliably supports is a direct, general
fix for "some video codec OpenCV's wheel can't read," and Ultralytics'
`detector.track(source=...)` (used by `pipeline/tracking.py`) also reads the
source via OpenCV internally, so a fix limited to the explicit
`cv2.VideoCapture` check in `run()` would not be sufficient on its own even
if the codec were the cause.
Decision: New module `pipeline/video_io.py` exposes
`normalize_for_opencv(input_path) -> str`, which opens the file with PyAV
(`av`, already a dependency since D-016), checks the video stream's codec,
and returns the path unchanged if it's already H.264. Otherwise it transcodes
to a new temp H.264 `.mp4` (same `add_stream("libx264", ...)`/`yuv420p`
pattern as D-016's output encoding) and returns that path instead.
`app/pages/upload_detect.py` calls this on every uploaded video's tempfile
before passing it to `run_pipeline.run()`, and cleans up the normalized
tempfile in its existing `finally` block if a new one was created. Scoped to
the upload path only (extends the D-014 exception) — the CLI
(`--source ...`) is unchanged and still assumes the operator supplies a
known-good source file.
Alternatives considered: Fixing only the `cv2.VideoCapture` check in
`run_pipeline.py` (rejected — Ultralytics' internal reader would still fail
on HEVC, since it also goes through OpenCV). Requiring users to
pre-transcode uploads themselves (rejected — defeats the point of an upload
UI). Switching to a different OpenCV build/wheel with full FFMPEG codecs
(rejected — bigger environment change for a problem PyAV already solves
within the existing dependency set).
Consequences: Every non-H.264 upload now pays a one-time transcode cost
before detection starts (on top of the existing CPU-bound detection/OCR
cost); H.264 uploads (including re-uploads of this pipeline's own output)
pay no extra cost. Secondary, unaddressed observation from investigating
this: both `opencv-python` and `opencv-python-headless` are installed
side-by-side in this environment (pulled in transitively by different
deps) — a known source of DLL/binding conflicts on Windows; not fixed here
since it wasn't confirmed as the actual cause, but worth resolving if
similar OpenCV issues recur.

## D-018: Bump `requirements.txt` floors to match versions verified working in this environment
Date: 2026-08-15
Status: Accepted
Context: A full pipeline test pass (CLI run, unit tests, D-017's codec-normalization path) was run
against this environment's actually-installed package versions, all of which sit above
`requirements.txt`'s `>=` floors: ultralytics 8.4.93, lap 0.5.13, streamlit 1.60.0, pandas 2.2.3,
numpy 2.1.3, av 17.1.0. The old floors (some dating to pre-D-016/D-017) would let a fresh
`pip install` resolve to an untested combination, including a numpy 1.x install that was never
exercised against this codebase.
Decision: Raise each floor to the version confirmed working: `ultralytics>=8.4.93`,
`lap>=0.5.13`, `streamlit>=1.60.0`, `pandas>=2.2.3`, `numpy>=2.1.3`, `av>=17.1,<19` (keeping
D-016's upper bound). `opencv-python>=4.10.0` and `easyocr>=1.7.2` were already at the installed
version and are unchanged.
Alternatives considered: Leaving the floors as-is (rejected — the whole point of a floor is that
it's been exercised; these hadn't been, most notably the numpy 1.x/2.x boundary, which is a
breaking change for some compiled extensions). Pinning exact versions with `==` (rejected — same
reasoning as the existing partial pins here: floors are already the convention this file uses).
Consequences: This has not been validated against a truly clean `pip install -r requirements.txt`
in a fresh environment — only against the already-populated environment these versions came from.
The numpy 1.x→2.x floor bump in particular is worth a clean-install smoke test before this is
treated as fully confirmed.
