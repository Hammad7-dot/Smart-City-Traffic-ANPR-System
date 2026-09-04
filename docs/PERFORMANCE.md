# Performance profile

Date: 2026-09-04

This is a diagnostic baseline, not an accuracy benchmark. Profiling used the
existing gitignored `data/videos/traffic.mp4` and local model weights in the
isolated `.venv`. Outputs and raw profiler data remain under gitignored
`output/performance-20260904/`; the production database was not touched.

## Environment and input

- Python 3.13.5, Torch 2.14.0 CPU build, Ultralytics headless 8.4.138
- 8 logical CPUs; Torch changed from 1 thread before inference to 7 during it
- CUDA unavailable to Torch
- NVIDIA GeForce MX230, 2 GB VRAM, driver 581.95
- Input: 1,115 frames, 1920×1080, 30.005 FPS, 37.16 seconds

## End-to-end baseline

The instrumented pipeline processed 1,115 frames and five crossing events in
205.73 seconds: 5.42 FPS, or 5.54 times slower than playback. Python/library
imports took another 7.00 seconds outside that number.

| Work | Seconds | Share |
|---|---:|---:|
| Vehicle detection, decode, and ByteTrack | 113.56 | 55.2% |
| H.264/x264 encode | 72.96 | 35.5% |
| BGR→PyAV conversion | 8.05 | 3.9% |
| NumPy frame copies | 3.13 | 1.5% |
| EasyOCR reader initialization | 2.79 | 1.4% |
| Plate detection, five calls | 0.94 | 0.5% |
| OCR, five calls | 0.88 | 0.4% |
| SQLite event writes, five calls | 0.01 | <0.1% |

Times are measured wall time for pipeline boundaries and profiler self-time for
C-extension operations. Rounded shares are directional and need not total 100%.
The profile itself adds overhead, so use A/B ratios—not this absolute runtime—to
project changes.

### Findings

1. Per-frame vehicle inference/tracking is the largest bottleneck. Ultralytics
   model inference accounted for about 81 seconds within that boundary;
   ByteTrack association itself was about one second.
2. Software H.264 encoding is the second bottleneck. Packet muxing is negligible.
3. OCR, plate detection, model loading, and SQLite are not throughput bottlenecks.
   Optimizing them cannot materially fix this workload.
4. The isolated environment is substantially faster than the earlier shared-
   Anaconda observation, but still fails D-006's faster-than-playback target.

## Controlled probes

### x264 preset

The same first 300 annotated 1080p frames were decoded and re-encoded once per
preset. Encoding changed one variable only.

| Preset | Encode time | Probe wall time | File size |
|---|---:|---:|---:|
| medium (current default) | 10.82 s | 11.65 s | 4.85 MB |
| ultrafast | 1.63 s | 2.64 s | 14.16 MB |

`ultrafast` made encoding 6.65 times faster and the file 2.92 times larger.
Visual/compression quality was not scored. Based on the baseline proportions,
this is the strongest low-risk speed control when users accept larger output.
It should be an explicit option; changing the default silently is not justified.

### YOLO inference size

Each full-video probe ran tracking without output encoding.

| Image size | Time | Tracked boxes | Unique IDs | Crossings |
|---|---:|---:|---:|---:|
| 640 (current default) | 131.25 s | 310 | 22 | 5 |
| 416 | 91.20 s | 277 | 24 | 5 |

The 416 setting was 30.5% faster but produced 10.6% fewer tracked-box instances
and slightly more ID fragmentation. Five crossings on one clip is too weak an
accuracy gate. Keep 640 as the default until labeled, representative footage
quantifies missed vehicles and OCR impact; a documented optional performance
mode is reasonable.

## Recommended order

1. Add an output-video switch and x264 preset option. For users who need only
   database/CSV events, skipping annotated-video generation should avoid most
   encoding, conversion, and annotation overhead. Benchmark it rather than
   assuming the entire measured time is recoverable.
2. Offer `imgsz=416` as an explicit performance mode, with 640 remaining the
   quality default. Pass the value through the existing tracking-stage boundary.
3. Add progress and final metrics: processed frames, elapsed time, effective
   FPS, source FPS, and real-time factor. This makes regressions observable.
4. Evaluate GPU inference separately. The present Torch build is CPU-only and
   the MX230 has only 2 GB VRAM, so compatibility and benefit must be measured;
   do not replace the validated CPU installation speculatively.
5. Do not spend optimization effort on OCR, SQLite, or ByteTrack association
   for this workload. Improve OCR only for recognition quality, not speed.

A rough combination of the two A/B ratios predicts improvement but is not a
measurement: the effects may overlap, and 416 can reduce quality. Before changing
defaults, run a true end-to-end A/B and compare event output against labels.
