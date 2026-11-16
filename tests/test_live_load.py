"""live_load: how a machine-load reading moves the rain, and the no-psutil fallback."""

import subprocess
import sys
import textwrap

import pytest

from digital_rain import live_load, settings


class FakeSampler:
    def __init__(self, load):
        self.load = load
        self.stopped = False

    def value(self):
        return self.load

    def stop(self):
        self.stopped = True


def control(load, target="both", strength=1.0):
    cfg = dict(settings.DEFAULTS, live_source="cpu", live_strength=strength, live_target=target)
    return live_load.LiveControl(cfg, sampler=FakeSampler(load))


def settled(ctl):
    return ctl.update(30.0)


def test_full_load_speeds_up_and_thickens():
    speed, density = settled(control(1.0))
    assert speed == pytest.approx(1.5, abs=0.01)
    assert density == pytest.approx(1.0, abs=0.01)


def test_idle_slows_and_thins():
    speed, density = settled(control(0.0))
    assert speed == pytest.approx(0.5, abs=0.01)
    assert density == pytest.approx(0.25, abs=0.01)


def test_target_limits_what_moves():
    _speed, density = settled(control(0.0, target="speed"))
    assert density == pytest.approx(1.0, abs=0.01)
    speed, _density = settled(control(0.0, target="density"))
    assert speed == pytest.approx(1.0, abs=0.01)


def test_a_lost_reading_eases_back_instead_of_jumping():
    ctl = control(1.0)
    settled(ctl)
    ctl.sampler.load = None
    speed, _density = ctl.update(1.0)
    assert 1.0 < speed < 1.5


def test_strength_scales_the_effect():
    weak, _ = settled(control(1.0, strength=0.2))
    strong, _ = settled(control(1.0, strength=1.0))
    assert 1.0 < weak < strong


def test_source_off_is_exactly_neutral_and_owns_no_sampler():
    ctl = live_load.LiveControl(dict(settings.DEFAULTS, live_source="off"))
    assert ctl.update(0.016) == (1.0, 1.0)
    assert ctl.sampler is None


def test_close_stops_the_sampler():
    ctl = control(0.5)
    ctl.close()
    assert ctl.sampler.stopped


def test_sampler_without_psutil_gives_no_value_and_says_so():
    """Run in a child that cannot import psutil; the parent keeps the real one."""
    code = textwrap.dedent("""
        import sys, time
        sys.modules["psutil"] = None
        from digital_rain import live_load
        sampler = live_load.LoadSampler("cpu")
        deadline = time.time() + 5.0
        while sampler.alive() and time.time() < deadline:
            time.sleep(0.02)
        assert sampler.value() is None
        assert not sampler.alive()
        sampler.stop()
    """)
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=False
    )
    assert done.returncode == 0, done.stderr
    assert "live load unavailable" in done.stderr
