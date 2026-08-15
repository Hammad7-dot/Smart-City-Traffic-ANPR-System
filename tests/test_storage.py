from pipeline.storage import EventStore


def _event(plate_number="ABC123", event_timestamp="2026-01-01T12:00:00", **overrides):
    kwargs = dict(
        track_id=1,
        vehicle_type="car",
        plate_number=plate_number,
        ocr_confidence=0.9,
        is_low_confidence=False,
        frame_number=1,
        event_timestamp=event_timestamp,
    )
    kwargs.update(overrides)
    return kwargs


def _count(store):
    return store.conn.execute("SELECT COUNT(*) FROM vehicle_events").fetchone()[0]


def test_first_event_is_recorded(tmp_path):
    store = EventStore(str(tmp_path / "test.db"))
    assert store.record_event(**_event()) is True
    assert _count(store) == 1
    store.close()


def test_duplicate_plate_within_window_is_skipped(tmp_path):
    store = EventStore(str(tmp_path / "test.db"))
    store.record_event(**_event(event_timestamp="2026-01-01T12:00:00"))
    assert store.record_event(**_event(event_timestamp="2026-01-01T12:00:03")) is False
    assert _count(store) == 1
    store.close()


def test_same_plate_after_window_is_recorded(tmp_path):
    store = EventStore(str(tmp_path / "test.db"))
    store.record_event(**_event(event_timestamp="2026-01-01T12:00:00"))
    assert store.record_event(**_event(event_timestamp="2026-01-01T12:00:06")) is True
    assert _count(store) == 2
    store.close()


def test_missing_plate_number_is_never_a_duplicate(tmp_path):
    store = EventStore(str(tmp_path / "test.db"))
    store.record_event(**_event(plate_number=None, event_timestamp="2026-01-01T12:00:00"))
    assert store.record_event(**_event(plate_number=None, event_timestamp="2026-01-01T12:00:01")) is True
    assert _count(store) == 2
    store.close()


def test_different_plates_within_window_both_recorded(tmp_path):
    store = EventStore(str(tmp_path / "test.db"))
    store.record_event(**_event(plate_number="AAA111", event_timestamp="2026-01-01T12:00:00"))
    assert store.record_event(**_event(plate_number="BBB222", event_timestamp="2026-01-01T12:00:01")) is True
    assert _count(store) == 2
    store.close()
