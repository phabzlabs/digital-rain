"""matrix_saver --warm-up: the hidden one-second run made once after an install."""

import pytest

from digital_rain.windows import matrix_saver


@pytest.mark.parametrize("argv", [["--warm-up"], ["--WARM-UP"], ["/c", "--warm-up"]])
def test_warm_up_runs_the_saver(argv):
    mode, _hwnd, dev = matrix_saver.parse_args(argv)
    assert dev["warm_up"]
    assert mode == "s"


def test_warm_up_is_a_short_timed_run_without_a_shot():
    _mode, _hwnd, dev = matrix_saver.parse_args(["--warm-up", "--shot", "x.png"])
    matrix_saver._warm_up(dev)
    assert dev["seconds"] == matrix_saver.WARM_UP_SECONDS
    assert dev["shot"] is None


def test_warm_up_keeps_an_explicit_length():
    _mode, _hwnd, dev = matrix_saver.parse_args(["--warm-up", "--seconds", "3"])
    matrix_saver._warm_up(dev)
    assert dev["seconds"] == 3


def test_warm_up_takes_no_single_instance_lock(monkeypatch):
    """A timed run never takes the Run lock, so a real launch is never turned away."""
    taken = []
    monkeypatch.setattr(matrix_saver.osapi, "acquire_single_instance", taken.append)
    mode, _hwnd, dev = matrix_saver.parse_args(["--warm-up"])
    matrix_saver._warm_up(dev)
    assert matrix_saver._acquire_instance(mode, dev) is True
    assert taken == []
