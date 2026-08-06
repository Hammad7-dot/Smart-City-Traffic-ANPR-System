# implements FR3, rules.md #7 (count once per crossing), D-008 (dedupe)
"""Virtual-line crossing detection: one count per tracker ID, ever."""


class LineCrossingCounter:
    def __init__(self, line_y: float):
        self.line_y = line_y
        self._last_side: dict[int, int] = {}
        self._already_counted: set[int] = set()

    def _side(self, cy: float) -> int:
        return 1 if cy >= self.line_y else -1

    def update(self, track_id: int, centroid: tuple[float, float]) -> bool:
        """Returns True exactly once per track_id, the frame it crosses the line."""
        cy = centroid[1]
        side = self._side(cy)
        prev_side = self._last_side.get(track_id)
        self._last_side[track_id] = side

        if track_id in self._already_counted:
            return False
        if prev_side is not None and prev_side != side:
            self._already_counted.add(track_id)
            return True
        return False
