"""exit_gate: when mouse movement ends the saver."""

import random

from digital_rain import exit_gate

MOUSE_THRESHOLD_PX = 25


def reference_exit_rule(events, threshold=MOUSE_THRESHOLD_PX):
    """Total travel after the first 0.6 s passes the threshold."""
    moved, last = 0, None
    for index, (t, pos) in enumerate(events):
        if t > 0.6 and last is not None:
            moved += abs(pos[0] - last[0]) + abs(pos[1] - last[1])
            if moved > threshold:
                return index
        last = pos
    return None


def test_exit_gate_matches_the_reference_rule():
    rng = random.Random(12345)
    for _ in range(200):
        t, pos, events = 0.0, (rng.randrange(500), rng.randrange(500)), []
        for _ in range(rng.randrange(1, 60)):
            t += rng.choice((0.01, 0.05, 0.3, 1.2))
            pos = (pos[0] + rng.randrange(-6, 7), pos[1] + rng.randrange(-6, 7))
            events.append((t, pos))
        gate = exit_gate.ExitGate(MOUSE_THRESHOLD_PX)
        got = next((i for i, (t, p) in enumerate(events) if gate.motion(t, p)), None)
        assert got == reference_exit_rule(events), events


def test_movement_in_the_first_moments_is_ignored():
    gate = exit_gate.ExitGate(MOUSE_THRESHOLD_PX)
    assert not gate.motion(0.2, (0, 0))
    assert not gate.motion(0.5, (500, 500))
