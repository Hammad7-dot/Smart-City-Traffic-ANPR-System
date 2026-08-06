# blocked.md — Open Questions & Blockers

Anything that stops implementation from proceeding without a guess. Move an
item to `decisions.md` (as Accepted) once resolved — don't just delete it here.

Format:
```
## B-00X: <short title>
Raised: YYYY-MM-DD
Blocks: which SPEC.md ID(s) this affects
Question: the actual ambiguity
Why it matters: consequence of guessing wrong
Proposed default (if forced to proceed): ...
Status: Open | Resolved (→ D-00X)
```

---

## B-001: "Real-time" is not quantified
Raised: (from source doc review)
Blocks: NFR "Latency" (SPEC.md §6), FR1
Question: What FPS/latency counts as "real-time" here — live camera feed
(e.g. ≥15–30 FPS) or "fast enough on recorded video"? The source doc says
"real-time video streams" but gives no target number and the sample inputs
are recorded test videos, not a live feed.
Why it matters: Determines whether frame-skipping/model size trade-offs are
acceptable, and whether the architecture needs a queue/buffering layer.
Proposed default: Treat as "process recorded video faster than real-time
playback speed" for v1; revisit if a live-feed deployment is required.
Status: Resolved (→ D-006)

## B-002: Single-frame vs multi-frame OCR read
Raised: (from source doc review)
Blocks: FR5
Question: The plate is cropped and OCR'd once, at the crossing frame. Should
low-confidence single reads be improved via multi-frame voting before/after
the crossing, or accepted as-is?
Why it matters: Single-frame reads will misread plates on motion blur/angle;
affects law-enforcement usability of stored data.
Proposed default: Store single read + confidence score for v1; flag as a
known limitation rather than building multi-frame voting now.
Status: Resolved (→ D-013)

## B-003: Data retention / privacy policy for plate + video data
Raised: (from source doc review)
Blocks: rules.md "Data & Privacy Rules" item 2
Question: How long are raw video, cropped plate images, and DB rows retained?
Is anonymization/redaction required for any non-law-enforcement use (e.g. the
analytics dashboard)?
Why it matters: Plate numbers are PII; storing indefinitely without a policy
is a compliance risk the moment this leaves prototype stage.
Proposed default: None — this needs an explicit answer before any deployment
beyond local dev/testing.
Status: Open

## B-004: Accuracy/threshold targets undefined
Raised: (from source doc review)
Blocks: FR1 (detection), FR5 (OCR) acceptance criteria
Question: No mAP / OCR accuracy threshold is specified anywhere in the
source doc — "detect vehicles" and "extract license plate numbers" have no
measurable bar.
Why it matters: Without a target, "done" is subjective and can't be tested.
Proposed default: None proposed — needs stakeholder input on acceptable
false-positive/false-negative rates for a law-enforcement-adjacent system.
Status: Resolved (→ D-007, no formal gate for v1 — still needs a real
stakeholder-supplied threshold before this is trustworthy beyond prototype)

## B-005: Duplicate/near-duplicate crossing events
Raised: (from source doc review)
Blocks: FR3
Question: If tracking loses and re-acquires a vehicle mid-crossing (ID
switch), could the same physical vehicle be counted/logged twice? The doc
assumes tracker IDs are stable but doesn't address ID-switch handling.
Why it matters: Directly affects count accuracy and duplicate plate log rows.
Proposed default: None — needs a dedupe rule (e.g. same plate + timestamp
within N seconds = treat as one event) before this is trustworthy.
Status: Resolved (→ D-008)

## B-006: Live feed vs. recorded video as primary input
Raised: (from source doc review)
Blocks: SPEC.md §4 architecture, §7 data
Question: Deliverables list `data/videos/traffic.mp4` and sample test videos
only — no live RTSP/CCTV feed ingestion is specified, despite objectives
mentioning "real-time video streams."
Why it matters: Changes whether Frame Extraction needs a streaming input
adapter now or can stay file-based for v1.
Proposed default: File-based input for v1 (matches deliverables); live feed
ingestion is a follow-up decision, not in scope yet.
Status: Resolved (→ D-006)

---

## B-007: <next blocker>
Raised:
Blocks:
Question:
Why it matters:
Proposed default:
Status: Open
