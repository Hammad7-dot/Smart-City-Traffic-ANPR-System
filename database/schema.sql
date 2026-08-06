-- database/schema.sql — single source of truth for the schema (rules.md #10)
-- implements FR6

CREATE TABLE IF NOT EXISTS vehicle_events (
    id INTEGER PRIMARY KEY,
    track_id INTEGER NOT NULL,
    vehicle_type TEXT NOT NULL,
    plate_number TEXT,
    ocr_confidence REAL,
    is_low_confidence INTEGER NOT NULL DEFAULT 0,
    frame_number INTEGER NOT NULL,
    event_timestamp TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_vehicle_events_plate ON vehicle_events(plate_number);
CREATE INDEX IF NOT EXISTS idx_vehicle_events_timestamp ON vehicle_events(event_timestamp);
