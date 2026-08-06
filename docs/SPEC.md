# SPEC.md — Smart City Traffic ANPR System

## 1. Problem Statement
Manual traffic surveillance is costly, slow, and error-prone. Build an AI-powered
system that detects vehicles, counts them, recognizes license plates in real time,
and stores results for smart-city traffic management and law enforcement.

## 2. Objectives (in-scope)
- O1: Detect vehicles (car, bike, truck, bus) in real-time video streams
- O2: Count vehicles crossing a virtual line, without double-counting
- O3: Extract license plate numbers via OCR, triggered only on line-crossing
- O4: Persist vehicle type, plate number, and timestamp to a database
- O5: Provide an analytics dashboard (live counts, plate logs, historical reports)

## 3. Out of Scope (v1)
- Multi-camera fusion / city-wide deployment
- Real-time law-enforcement alerting or ticketing integration
- Non-CCTV inputs (drone, mobile) unless explicitly added later
- Plate recognition for non-standard/international formats beyond what the
  chosen OCR model supports out of the box

## 4. Architecture (pipeline)
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

## 5. Functional Requirements
| ID | Requirement | Acceptance Criteria |
|----|-------------|----------------------|
| FR1 | Detect vehicle classes: car, bike, truck, bus | ≥ target mAP on validation set (see Decisions for threshold) |
| FR2 | Assign a persistent unique ID per vehicle | Same vehicle retains one ID across consecutive frames while in frame |
| FR3 | Count only on virtual-line crossing | No vehicle counted more than once per crossing event |
| FR4 | Trigger plate detection only on crossing event | Plate pipeline is not run on every frame (perf requirement) |
| FR5 | OCR converts cropped plate image → text | Output stored as string, empty/low-confidence reads flagged, not silently dropped |
| FR6 | Store vehicle_type, plate_number, timestamp | Row written per crossing event; schema in `database/schema.sql` |
| FR7 | Dashboard shows live class-wise counts, plate logs, historical reports | Streamlit app reads from DB, refreshes on new events |
| FR8 | Provide an ad hoc upload-and-detect page for a single image or video, outside the recorded-dataset CLI pipeline run | Streamlit "Upload & Detect" page accepts an image or video upload, runs detection (+ OCR for videos via the existing pipeline; image results shown in-session only per decisions.md D-014), and displays annotated output without requiring a CLI invocation |

## 6. Non-Functional Requirements
- **Latency**: pipeline should process input fast enough for the target use case
  (real-time from live feed vs. batch on recorded video — see Decisions, open item)
- **Reliability**: a crash in OCR/plate stage must not lose the vehicle count already recorded
- **Data integrity**: DB writes must be atomic per event
- **Auditability**: every stored plate read should be traceable to a source frame/timestamp

## 7. Data
- License plate dataset: Roboflow Universe — `license-plate-recognition-rxg4e`
- Sample test videos: provided Google Drive folder (see project links)
- Vehicle detection: pretrained YOLOv8 on COCO (no custom training required for v1)

## 8. Deliverables (repo layout)
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

## 9. Tech Stack
Python, OpenCV, YOLOv8, DeepSORT, EasyOCR, FastAPI, Streamlit, SQLite/PostgreSQL

## 10. Success Metric
System reliably produces the example output shape:

| Vehicle Type | Plate Number | Timestamp |
|---|---|---|
| Truck | ABC-123 | 10:01 AM |

...consumable by the dashboard for live + historical analytics.
