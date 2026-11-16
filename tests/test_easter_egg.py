"""easter_egg: timing of the typed message."""

import random

from digital_rain import easter_egg
from digital_rain.settings import PHRASES


def make(seed=1, enabled=True):
    return easter_egg.EasterEgg(enabled=enabled, rng=random.Random(seed))


def test_disabled_never_shows():
    egg = make(enabled=False)
    assert all(egg.update(t) is None for t in (0.0, 30.0, 500.0))


def test_nothing_before_the_first_delay():
    egg = make()
    low, _high = easter_egg.FIRST_DELAY
    assert egg.update(low - 0.1) is None


def test_types_holds_fades_then_waits_for_the_next_one():
    egg = make()
    start = egg.next_start
    first = egg.update(start)
    text, shown, alpha, _cursor = first
    assert text in PHRASES
    assert shown == 1
    assert alpha == 1.0
    type_time = len(text) * easter_egg.TYPE_SPEED
    mid = egg.update(start + type_time / 2)
    assert 1 < mid[1] < len(text)
    held = egg.update(start + type_time + easter_egg.HOLD / 2)
    assert held[1] == len(text)
    assert held[2] == 1.0
    fading = egg.update(start + type_time + easter_egg.HOLD + easter_egg.FADE / 2)
    assert 0.0 < fading[2] < 1.0
    end = start + type_time + easter_egg.HOLD + easter_egg.FADE + 0.01
    assert egg.update(end) is None
    gap_low, _gap_high = easter_egg.GAP
    assert egg.next_start >= end + gap_low
    assert egg.update(end + gap_low - 1.0) is None


def test_characters_shown_never_decrease_while_typing():
    egg = make()
    start = egg.next_start
    previous = 0
    for step in range(60):
        state = egg.update(start + step * 0.05)
        if state is None:
            break
        assert state[1] >= previous
        previous = state[1]


def test_the_cursor_blinks():
    egg = make()
    start = egg.next_start
    cursors = {egg.update(start + step * 0.1)[3] for step in range(10)}
    assert cursors == {True, False}
