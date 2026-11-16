"""The screensaver exit gate (pure Python, no pygame or ctypes)."""


class ExitGate:
    """True from `motion` when mouse movement must end the saver: more than
    threshold_px of travel in total, ignoring the first 0.6 s."""

    def __init__(self, threshold_px=25):
        self.threshold = threshold_px
        self.last_pos = None
        self.moved = 0

    def motion(self, t, pos):
        prev = self.last_pos
        self.last_pos = pos
        if t <= 0.6 or prev is None:
            return False
        self.moved += abs(pos[0] - prev[0]) + abs(pos[1] - prev[1])
        return self.moved > self.threshold
