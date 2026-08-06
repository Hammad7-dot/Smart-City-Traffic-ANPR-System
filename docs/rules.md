# rules.md — Working Rules for This Project

These rules govern how any contributor (human or AI agent) implements against
`SPEC.md`. If a rule and the spec conflict, stop and log it in `blocked.md`
rather than silently choosing one.

## Process Rules
1. **No code without a spec line.** Every function/module should trace back to
   an FR/NFR ID in `SPEC.md` (e.g. `# implements FR3`). If it doesn't map to
   anything, either the spec is missing something (log in `blocked.md`) or the
   work is out of scope.
2. **Spec changes are logged, not silent.** Any deviation from `SPEC.md`
   (new dependency, changed threshold, changed schema) gets an entry in
   `decisions.md` before or immediately after the change — never only in code
   comments or commit messages.
3. **Unresolved ambiguity blocks, it doesn't get guessed.** If a requirement is
   underspecified (e.g. "real-time" without a target FPS/latency), add it to
   `blocked.md` instead of picking an arbitrary number and moving on.
4. **One pipeline stage, one module.** Keep detection, tracking, line-crossing,
   plate detection, OCR, and storage as separately testable units — mirrors the
   architecture diagram in `SPEC.md` §4. Don't collapse stages for convenience.
5. **Pretrained-first.** Use pretrained YOLOv8 (COCO) for vehicle detection and
   a pretrained/roboflow ANPR model for plates in v1. Custom training is
   out-of-scope unless a decision entry says otherwise.

## Data & Privacy Rules
6. **Plate numbers are PII.** Treat `plate_number` and any frame containing a
   readable plate/face as sensitive. Do not commit raw sample footage, exported
   logs with real plates, or DB dumps to a public repo.
2. Retention: log how long raw video and plate logs are kept before purge —
   this must be decided (see `blocked.md`) before any deployment beyond local
   testing.

## Detection & Tracking Rules
7. A vehicle is counted **once** per line crossing, never per frame. Counting
   logic must use the tracker ID + crossing-event state, not per-frame presence.
8. Plate detection/OCR only runs on a crossing event (perf + cost control) —
   never on every frame (per FR4).
9. Low-confidence OCR reads are stored with a confidence/flag field, not
   discarded and not silently treated as ground truth.

## Database Rules
10. `database/schema.sql` is the single source of truth for the schema. Code
    must not create tables ad hoc outside migrations/schema file.
11. SQLite is the v1 target; anything that would break a later move to
    PostgreSQL (e.g. SQLite-only syntax) should be flagged in `decisions.md`.

## Dashboard Rules
12. The analytics Dashboard page (`app/pages/dashboard.py`) only reads from the
    database — it must not contain detection/tracking/OCR logic itself. The
    separate Upload & Detect page is an explicit, documented exception (see
    decisions.md D-014), not a violation.

## Review Rules
13. Before marking any objective (O1–O5) "done," check it against its
    Acceptance Criteria row in `SPEC.md` §5 — not against "it ran once."
14. When in doubt between two implementations, prefer the one that keeps
    stages swappable (e.g. DeepSORT vs ByteTrack, EasyOCR vs Tesseract) since
    the spec lists both as options.
