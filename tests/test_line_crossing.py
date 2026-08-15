from pipeline.line_crossing import LineCrossingCounter


def test_first_update_never_counts():
    counter = LineCrossingCounter(line_y=100)
    assert counter.update(1, (0, 50)) is False


def test_crossing_the_line_counts_once():
    counter = LineCrossingCounter(line_y=100)
    counter.update(1, (0, 50))  # above the line
    assert counter.update(1, (0, 150)) is True  # crosses below


def test_staying_on_one_side_never_counts():
    counter = LineCrossingCounter(line_y=100)
    counter.update(1, (0, 50))
    assert counter.update(1, (0, 60)) is False
    assert counter.update(1, (0, 70)) is False


def test_recrossing_after_counted_does_not_count_again():
    counter = LineCrossingCounter(line_y=100)
    counter.update(1, (0, 50))
    assert counter.update(1, (0, 150)) is True  # first crossing, counted
    assert counter.update(1, (0, 50)) is False  # crosses back, already counted
    assert counter.update(1, (0, 150)) is False  # crosses again, still already counted


def test_track_ids_are_independent():
    counter = LineCrossingCounter(line_y=100)
    counter.update(1, (0, 50))
    counter.update(2, (0, 50))
    assert counter.update(1, (0, 150)) is True
    assert counter.update(2, (0, 60)) is False
