"""rain_message: masks, the message schedule, the letter front and the head latch."""

import re

import numpy as np
import pytest

from digital_rain import rain_message, settings


def schedule(**extra):
    return rain_message.MessageSchedule(
        dict(settings.DEFAULTS, message="clock", clock_24h=True, **extra)
    )


def test_clock_mask_fits_the_grid():
    mask, col0, _row0 = rain_message.message_mask("12:34", 96, 51)
    assert mask.shape[0] == 13
    assert mask.any()
    assert col0 + mask.shape[1] <= 96


def test_preview_sized_grids_get_no_mask():
    assert rain_message.message_mask("12:34", 25, 14) is None
    assert rain_message.message_mask("Wake up, Neo...", 25, 14) is None


def test_text_wraps_to_two_lines_on_a_narrow_grid_and_one_on_a_wide_one():
    narrow = rain_message.message_mask("Wake up, Neo...", 96, 38)
    wide = rain_message.message_mask("Wake up, Neo...", 172, 51)
    assert 15 <= narrow[0].shape[0] <= 27
    assert 7 <= wide[0].shape[0] <= 13


@pytest.mark.parametrize("text", ["   ", "​", "日本"])
def test_text_without_drawable_glyphs_gives_no_mask(text):
    assert rain_message.message_mask(text, 96, 38) is None


@pytest.mark.parametrize("index, position", list(enumerate(settings.CLOCK_POSITIONS)))
def test_each_clock_position_stays_in_its_third_of_the_screen(index, position):
    anchor = rain_message.anchor_of(position)
    mask, col0, row0 = rain_message.message_mask("12:34", 96, 51, anchor)
    column, row = index % 3, index // 3
    mid_col = col0 + mask.shape[1] / 2
    mid_row = row0 + mask.shape[0] / 2
    assert col0 >= 0
    assert col0 + mask.shape[1] <= 96
    assert row0 >= 0
    assert row0 + mask.shape[0] <= 51
    assert column * 32 <= mid_col < column * 32 + 32
    assert row * 17 <= mid_row < row * 17 + 17


def test_schedule_reveals_holds_and_hides():
    sched = schedule()
    assert sched.state(0.2) is None
    text, reveal, hide, cycle = sched.state(3.0)
    assert (reveal, hide, cycle) == (rain_message.REVEAL_AT, 8.5, 0)
    assert re.fullmatch(r"\d{2}:\d{2}", text)
    assert sched.state(20.0) is None
    assert sched.state(37.0)[3] == 1


def test_twelve_hour_clock_has_no_leading_zero():
    sched = rain_message.MessageSchedule(dict(settings.DEFAULTS, message="clock", clock_24h=False))
    assert re.fullmatch(r"(1[0-2]|[1-9]):\d{2}", sched.state(3.0)[0])


def test_both_alternates_clock_and_text():
    sched = rain_message.MessageSchedule(
        dict(settings.DEFAULTS, message="both", message_text="Wake up, Neo...")
    )
    assert sched.state(37.0)[0] == "WAKE UP, NEO..."


def test_off_shows_nothing():
    sched = rain_message.MessageSchedule(dict(settings.DEFAULTS, message="off"))
    assert sched.state(3.0) is None


def test_fixed_clock_stays_up():
    sched = rain_message.MessageSchedule(dict(settings.DEFAULTS, message="clock_fixed"))
    assert sched.state(0.2) is None
    first = sched.state(3.0)
    later = sched.state(500.0)
    assert later[1] == first[1]
    assert later[3] == first[3]


def test_front_sweeps_down_the_lanes_then_rubs_out():
    mask = np.ones((3, 3), bool)
    lane = np.zeros((3, 3), int)
    along = np.repeat(np.arange(3)[:, None], 3, axis=1).astype(float)
    zero = np.zeros(1)

    def column(t):
        states = rain_message.cell_states(mask, 0, 0, lane, along, zero, zero, t, 0.0, 8.0)
        return states[:, 0].tolist()

    assert column(0.01) == [2, 0, 0]
    assert column(0.04) == [1, 2, 0]
    assert column(1.0) == [1, 1, 1]
    assert column(8.01) == [0, 1, 1]
    assert column(8.05) == [0, 0, 1]


def test_latch_notes_a_new_message_once():
    latch = rain_message.MessageLatch()
    assert latch.note_message(0, "12:34", False) is True
    assert latch.note_message(0, "12:34", False) is False
    assert latch.note_message(1, "12:35", False) is True
    assert latch.previous_text is None


def test_latch_keeps_the_previous_clock_text_for_the_always_up_clock():
    latch = rain_message.MessageLatch()
    latch.note_message(0, "12:34", True)
    latch.note_message(1, "12:35", True)
    assert latch.previous_text == "12:34"


def test_latch_converts_reveal_and_freezes_the_deletion():
    latch = rain_message.MessageLatch()
    latch.note_message(0, "hi", False)
    latch.update_clocks(0, "hi", reveal=1.0, hide=9.0, t=2.0, rain_offset=10.0)
    assert latch.reveal_clock == 11.0
    assert latch.hide_clock == 19.0
    # Once the hide time has passed, a changed rain offset must not move the deletion.
    latch.update_clocks(0, "hi", reveal=1.0, hide=9.0, t=9.5, rain_offset=50.0)
    assert latch.hide_clock == 19.0


def test_latch_never_deletes_the_always_up_clock():
    latch = rain_message.MessageLatch()
    latch.note_message(0, "12:34", True)
    latch.update_clocks(0, "12:34", reveal=1.0, hide=1.0e6, t=2.0, rain_offset=3.0)
    assert latch.hide_clock == -1.0


def style_of(pt):
    return rain_message.text_style(dict(settings.DEFAULTS, message_font_size=pt))


@pytest.mark.parametrize(
    "pt, c, cols, rows",
    [(10, 10 / 36, 345, 183), (18, 0.5, 192, 102), (36, 1.0, 96, 51), (72, 1.0, 96, 51)],
)
def test_fine_grid_follows_the_point_size(pt, c, cols, rows):
    got = rain_message.fine_grid(96, 51, style_of(pt)[0])
    assert got[0] == pytest.approx(c)
    assert got[1:] == (cols, rows)


def test_fine_grid_stops_shrinking_at_a_quarter_cell():
    assert rain_message.fine_grid(96, 51, style_of(8)[0]) == (0.25, 384, 204)
    assert rain_message.fine_grid(96, 51, 0.05)[0] == 0.25


def test_fine_grid_counts_from_the_rounded_pixel_cell():
    # 1920 x 1080 px, main cell 20 x 30: the 10 pt cell is round(5.56) x round(8.33) = 6 x 8
    c, cols, rows = rain_message.fine_grid(96, 36, style_of(10)[0], (1920, 1080, 20, 30))
    assert (cols, rows) == (320, 135)
    assert rain_message.fine_cell((20, 30), c) == (6, 8)


@pytest.mark.parametrize("pt", [10, 18, 27])
@pytest.mark.parametrize("anchor", [None, (2, 0)])
def test_small_sizes_keep_the_letter_rows_of_36_pt(pt, anchor):
    reference = rain_message.message_mask("12:34", 192, 102, anchor, style_of(36))
    c, got = rain_message.message_layout("12:34", 192, 102, anchor, style_of(pt))
    assert c < 1.0
    assert got[0].shape[0] == reference[0].shape[0]
    assert got[0].any()


def test_layout_at_36_pt_and_above_is_the_main_grid_mask():
    for pt in (36, 72):
        c, got = rain_message.message_layout("12:34", 96, 51, None, style_of(pt))
        want = rain_message.message_mask("12:34", 96, 51, None, style_of(pt))
        assert c == 1.0
        assert got[1:] == want[1:]
        assert np.array_equal(got[0], want[0])


def test_fine_anchor_keeps_the_two_cell_margin_on_the_fine_grid():
    c, (mask, col0, row0) = rain_message.message_layout(
        "12:34", 96, 51, rain_message.anchor_of("top_right"), style_of(10)
    )
    _c, fcols, _frows = rain_message.fine_grid(96, 51, style_of(10)[0])
    assert row0 == 2
    assert col0 + mask.shape[1] == fcols - 2


def test_fine_states_for_a_changed_clock_keep_stable_cells_and_swap_the_rest():
    old = (np.ones((2, 3), bool), 0, 0)
    new = (np.array([[1, 1, 0], [1, 0, 1]], bool), 0, 0)
    codes = rain_message.change_codes(old, new)[0]
    along, lane = np.mgrid[0:2, 0:3]
    zero = np.zeros(3)
    args = (codes, 0, 0, lane, along, zero, zero)
    before = rain_message.fine_states(*args, 9.0, 10.0, 1e6, "down", True)
    after = rain_message.fine_states(*args, 20.0, 10.0, 1e6, "down", True)
    stable = codes == rain_message.STABLE
    assert (before[stable] == 1).all() and (after[stable] == 1).all()
    gone = codes == rain_message.VANISH
    assert (before[gone] == 1).all()
    assert (after[gone] == 0).all()
    came = codes == rain_message.APPEAR
    assert (after[came] > 0).all()
