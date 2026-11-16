"""matrix_saver.parse_args: the Windows screensaver switches and the developer flags."""

import sys

import pytest

from digital_rain.windows import matrix_saver

parse = matrix_saver.parse_args


@pytest.mark.parametrize(
    "argv, mode", [(["/s"], "s"), (["/w"], "w"), (["-W"], "w"), (["/c"], "c"), ([], "c")]
)
def test_legacy_switches_choose_the_mode(argv, mode):
    assert parse(argv)[0] == mode


def test_removed_wallpaper_switch_exits_cleanly_and_draws_nothing(monkeypatch):
    """/w is still recognised, so a leftover shortcut or task ends at once with status 0."""

    def refuse(*_args, **_kwargs):
        raise AssertionError("/w must not start a session")

    monkeypatch.setattr(sys, "argv", ["matrix_saver.py", "/w"])
    monkeypatch.setattr(matrix_saver, "run_session", refuse)
    monkeypatch.setattr(matrix_saver.osapi, "make_dpi_aware", refuse)
    assert matrix_saver.main() is None


def test_wallpaper_flag_is_gone():
    assert "wallpaper" not in parse(["--seconds", "3"])[2]
