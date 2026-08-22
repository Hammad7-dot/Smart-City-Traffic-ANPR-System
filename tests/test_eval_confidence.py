from pipeline.eval_confidence import load_confidences, summarize

_HEADER = "track_id,vehicle_type,plate_number,ocr_confidence,is_low_confidence,frame_number,event_timestamp\n"


def _write_csv(tmp_path, rows):
    path = tmp_path / "logs.csv"
    path.write_text(_HEADER + "\n".join(rows) + "\n")
    return path


def test_load_confidences_reads_column(tmp_path):
    path = _write_csv(tmp_path, [
        "1,car,ABC,0.9,0,1,2026-01-01T00:00:00",
        "2,bike,,0.1,1,2,2026-01-01T00:00:01",
    ])
    assert load_confidences(str(path)) == [0.9, 0.1]


def test_summarize_computes_stats_and_threshold_count():
    stats = summarize([0.9, 0.1, 0.5], threshold=0.4)
    assert stats["count"] == 3
    assert stats["mean"] == (0.9 + 0.1 + 0.5) / 3
    assert stats["min"] == 0.1
    assert stats["max"] == 0.9
    assert stats["below_threshold"] == 1
    assert round(stats["below_threshold_pct"], 2) == round(100 / 3, 2)


def test_summarize_empty_list():
    assert summarize([]) == {"count": 0}
