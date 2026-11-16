"""looks: preset resolution, the film clock helpers, palette and pulse maths."""

import copy
import math

import numpy as np
import pytest

from digital_rain import looks, settings, soft_renderer

FILM = ("film_1999", "reloaded", "resurrections")
# Keys that a look adds on top of the original renderer; neutral values skip the new paths.
FILM_LOOK_KEYS = (
    "step_fps",
    "gamma",
    "crossfade",
    "defocus",
    "pyramid",
    "glow_r",
    "glow_g",
    "grain_ink",
    "lanes",
    "lead_core",
)
CLARITY_KEYS = ("ink_fill", "lead_glow", "lead_cap", "cluster", "ink_dots")


def resolved(preset, **extra):
    return looks.resolve(dict(settings.DEFAULTS, preset=preset, **extra))


@pytest.mark.parametrize("name", FILM)
def test_film_presets_own_the_screen_effects(name):
    look = resolved(name)
    assert look["scanlines"] == 0
    assert look["interlace"] is False
    assert look["flicker"] == 0
    assert look["vignette"] == 0.15
    assert look["bloom"] == looks.PRESETS[name]["bloom"]
    assert look["film"] is True
    assert look["model"] == "saw"


def test_custom_follows_the_settings():
    cfg = dict(
        settings.DEFAULTS,
        preset="custom",
        bloom=0.77,
        scanlines=0.31,
        interlace=True,
        vignette=0.22,
        flicker=0.05,
        trail_falloff=2.5,
        color="amber",
    )
    kept = copy.deepcopy(cfg)
    look = looks.resolve(cfg)
    for key in ("bloom", "scanlines", "interlace", "vignette", "flicker"):
        assert look[key] == cfg[key], key
    assert look["falloff"] == cfg["trail_falloff"]
    assert look["film"] is False
    assert look["model"] == "drop"
    assert cfg == kept


def test_custom_look_is_neutral():
    look = resolved("custom")
    for key in FILM_LOOK_KEYS:
        assert look[key] == looks.NEUTRAL[key], key


@pytest.mark.parametrize("name", ["film_1999", "reloaded"])
def test_film_look_values_come_from_the_preset(name):
    look = resolved(name)
    for key in FILM_LOOK_KEYS:
        assert look[key] == looks.PRESETS[name][key], key
    assert look["crossfade"] is (name == "film_1999")
    assert look["step_fps"] == (24.0 if name == "film_1999" else 0.0)
    assert look["pyramid"] is True


def test_clarity_keys_are_neutral_outside_film_1999():
    for name in ("custom", "reloaded", "resurrections"):
        look = resolved(name)
        for key in CLARITY_KEYS:
            assert look[key] == looks.NEUTRAL[key], f"{name}: {key}"
    look = resolved("film_1999")
    for key in CLARITY_KEYS:
        assert look[key] == looks.PRESETS["film_1999"][key] != looks.NEUTRAL[key], key


def test_resurrections_has_its_own_glyphs_and_layers():
    look = resolved("resurrections")
    assert look["glyph_set"] == "resurrections"
    assert look["columns"] == 70
    assert look["glint_gain"] > 0
    assert len(look["layers"]) == 3


def test_resurrections_depth_slices():
    look = resolved("resurrections")
    slices = look["depth_slices"]
    scales = [one["scale"] for one in slices]
    assert len(slices) == 6
    assert scales == sorted(scales)
    assert dict(slices[1]) == dict(look["layers"][1])
    main = slices[1]["scale"]
    assert 3.5 <= max(scales) / main <= 4.5
    assert 0.65 <= min(scales) / main <= 0.75
    for name in ("film_1999", "reloaded", "custom"):
        other = resolved(name)
        assert other["depth_slices"] is None
        assert other["depth_jitter"] == 0.0
    on = dict(settings.DEFAULTS, depth=True)
    off = dict(settings.DEFAULTS, depth=False)
    assert len(settings.active_layers(on, look, slices=True)) == 6
    assert len(settings.active_layers(on, look)) == 3
    assert settings.active_layers(off, look, slices=True) == settings.active_layers(off, look)


@pytest.mark.parametrize("width, cell", [(1280, 18), (1920, 27), (2560, 37), (3840, 55)])
def test_resurrections_cell_size_by_width(width, cell):
    look = resolved("resurrections")
    cell_w, cell_h = looks.cell_px(look, width, 1.0, 1.0, 1.0)
    assert cell_w == cell_h == cell
    assert 69 <= width // cell_w <= 72


def test_resolve_leaves_the_config_alone():
    cfg = dict(settings.DEFAULTS)
    kept = copy.deepcopy(cfg)
    for name in settings.PRESET_NAMES:
        looks.resolve(dict(cfg, preset=name))
    assert cfg == kept


def test_step_time_snaps_to_the_frame_clock():
    assert looks.step_time(1.0417, 24) == 25 / 24
    for value in (0.0, 0.3, 1234.567):
        assert looks.step_time(value, 0) == value
        assert looks.step_time(value, -1) == value


def test_glyph_phase_changes_slot_every_three_frames_with_crossfade():
    changes, mixes, last = 0, 0, None
    for i in range(61):
        t = i / 60
        slot, previous, mix = looks.glyph_phase(t, 0.125, 24, True)
        assert previous == slot - 1
        expected_mix = 0.5 if math.floor(t * 24 + 1e-6) % 3 == 0 else 0.0
        assert mix == expected_mix
        mixes += mix > 0
        changes += last is not None and slot != last
        last = slot
        assert looks.glyph_phase(t, 0.125, 24, False)[2] == 0.0
        free_slot, _, free_mix = looks.glyph_phase(t, 0.125, 0, True)
        assert free_slot == math.floor(t / 0.125)
        assert free_mix == 0.0
    assert changes == 8
    assert mixes == 21


def test_lane_hash_is_fair():
    lanes = np.arange(2000, dtype=np.int64)[:, None]
    salts = np.arange(20, dtype=np.int64)[None, :]
    keys = 500 * soft_renderer.TOOTH_SALT_STRIDE + salts
    share = float((looks.lane_hash(lanes, keys) < 0.2).mean())
    assert abs(share - 0.2) <= 0.03


def test_pulse_off_is_the_identity():
    assert all(looks.pulse_time(t, False) == t for t in (0.0, 0.5, 1.03, 77.7))


def test_pulse_stands_still_then_catches_up():
    previous = -1.0
    for i in range(5001):
        value = looks.pulse_time(i * 0.001, True)
        assert value >= previous - 1e-12
        previous = value
    for k in range(1, 5):
        assert looks.pulse_time(k + 0.03, True) == looks.pulse_time(k, True)
    for k in range(11):
        assert abs(looks.pulse_time(k, True) - k) < 1e-9
    for k in range(1, 5):
        midpoint = looks.pulse_time(k + looks.PULSE_H + 0.46875, True)
        assert abs(midpoint - (k + 0.5)) < 1e-9


def test_pulse_lag_stays_within_one_pause():
    lags = [t - looks.pulse_time(t, True) for t in np.arange(0.0, 400.0, 0.01)]
    assert min(lags) >= -1e-9
    assert max(lags) <= looks.PULSE_H + 1e-9


def test_palette_end_stops():
    stops = looks.PRESETS["film_1999"]["palette"]
    low = looks.palette_rgb(stops, 0.0)
    high = looks.palette_rgb(stops, 1.0)
    scale = 255.0 if low.max() <= 1.0 else 1.0
    assert np.allclose(low * scale, [1, 6, 4], atol=1e-4)
    assert np.allclose(high * scale, [0x28, 0xF5, 0xA0], atol=1e-4)


def test_wobble_never_stalls_or_runs_away():
    x = np.linspace(0, 1000, 200_001)
    slope = np.diff(looks.wobble(x)) / np.diff(x)
    assert slope.min() >= 0.12
    assert slope.max() <= 1.88
