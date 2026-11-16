"""settings: load, clean, migrate, save atomicity and the round trip."""

import copy
import json
import os

import pytest
from conftest import FIXTURES

from digital_rain import settings


def write_raw(text):
    path = settings.settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def write_json(obj):
    return write_raw(json.dumps(obj))


def frozen_v1_1_0():
    with open(os.path.join(FIXTURES, "settings_v1_1_0.json"), encoding="utf-8") as handle:
        return json.load(handle)


def test_missing_file_gives_the_defaults():
    assert settings.load() == settings.clean(None)
    assert settings.load()["preset"] == "film_1999"


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", "5", ""])
def test_unreadable_file_gives_the_defaults(text):
    write_raw(text)
    assert settings.load() == settings.clean(None)


def test_frozen_v1_1_0_file_loads_as_custom_with_its_values():
    raw = frozen_v1_1_0()
    write_json(raw)
    cfg = settings.load()
    assert set(cfg) == set(settings.DEFAULTS)
    assert cfg["preset"] == "custom"
    for key, value in raw.items():
        assert cfg[key] == value, key
    assert cfg["upscaling"] == "off"
    assert cfg["sharpness"] == 0.2
    assert cfg["direction"] == "down"
    assert cfg["pulse"] is False
    assert cfg["monitors"] == {}


# One table of migration and cleaning cases: (file contents, expected values by key).
MIGRATION_CASES = {
    "no preset key means custom": ({"color": "amber"}, {"preset": "custom", "color": "amber"}),
    "preset survives": ({"preset": "reloaded"}, {"preset": "reloaded"}),
    "unknown preset is custom": ({"preset": "bogus"}, {"preset": "custom"}),
    "preset of the wrong type is custom": ({"preset": 5}, {"preset": "custom"}),
    "bad direction": ({"direction": "up"}, {"direction": "down"}),
    "bad pulse": ({"pulse": "yes"}, {"pulse": False}),
    "out of range clamps": ({"bloom": 7}, {"bloom": 1.0}),
    "bool is not a number": ({"speed": True}, {"speed": settings.DEFAULTS["speed"]}),
    "bad enum": (
        {"color": "purple", "renderer": 3},
        {"color": settings.DEFAULTS["color"], "renderer": "auto"},
    ),
    "city_dir becomes image_dir": ({"city_dir": "C:/pics"}, {"image_dir": "C:/pics"}),
    "image_dir wins over city_dir": ({"city_dir": "old", "image_dir": "new"}, {"image_dir": "new"}),
    "include subfolders is kept": ({"image_subfolders": True}, {"image_subfolders": True}),
    "include subfolders must be a bool": ({"image_subfolders": "yes"}, {"image_subfolders": False}),
    "message text is trimmed": (
        {"message_text": "a\u0001b" + "x" * 40},
        {"message_text": "abx" + "x" * 21},
    ),
    "bad live values": (
        {"live_source": "disk", "live_target": 3, "message": 5, "live_strength": 7},
        {"live_source": "off", "live_target": "both", "message": "off", "live_strength": 1.0},
    ),
}


@pytest.mark.parametrize("name", MIGRATION_CASES)
def test_migration_table(name):
    raw, expected = MIGRATION_CASES[name]
    write_json(raw)
    cfg = settings.load()
    for key, value in expected.items():
        assert cfg[key] == value, f"{name}: {key}"
    assert settings.clean(raw) == cfg


def test_unknown_keys_are_dropped():
    write_json({"unknown_key": 1, "color": "amber"})
    assert "unknown_key" not in settings.load()


def test_settings_from_the_wallpaper_era_still_load():
    """The removed wallpaper keys are ignored, never an error, and are not written back."""
    old = {"version": 1, "color": "amber", "wallpaper_mode": "window", "wallpaper_monitor": 3}
    write_json(old)
    cfg = settings.load()
    assert cfg["color"] == "amber"
    assert "wallpaper_mode" not in cfg
    assert "wallpaper_monitor" not in cfg
    assert settings.clean(old) == cfg
    settings.save(cfg)
    with open(settings.settings_path(), encoding="utf-8") as fh:
        assert not [k for k in json.load(fh) if k.startswith("wallpaper")]


def test_migrate_does_not_change_its_input():
    raw = {"city_dir": "x"}
    kept = copy.deepcopy(raw)
    settings.migrate(raw)
    assert raw == kept


def test_monitor_overrides_are_cleaned():
    write_json(
        {
            "preset": "reloaded",
            "monitors": {
                "x": {"preset": "bogus", "color": "pink", "speed": "fast", "depth": 1},
                "y": {"name": "Y"},
                "": {"speed": 1.0},
                "z": {"speed": 9, "density": 0.0, "depth": False, "bloom": 0.9, "name": "Z"},
            },
        }
    )
    assert settings.load()["monitors"] == {
        "z": {"speed": 2.5, "density": 0.3, "depth": False, "name": "Z"}
    }


@pytest.mark.parametrize("bad", [[], 5, {"a": 5}])
def test_bad_monitors_give_no_overrides(bad):
    write_json({"preset": "reloaded", "monitors": bad})
    assert settings.load()["monitors"] == {}


def test_load_does_not_share_the_defaults_dict():
    settings.load()["monitors"]["leak"] = {"speed": 1.0}
    assert settings.DEFAULTS["monitors"] == {}


def test_save_writes_the_version_and_round_trips():
    cfg = settings.clean(
        {
            "preset": "reloaded",
            "direction": "diagonal",
            "pulse": True,
            "monitors": {"m": {"speed": 2.0, "name": "M"}},
        }
    )
    settings.save(cfg)
    with open(settings.settings_path(), encoding="utf-8") as handle:
        on_disk = json.load(handle)
    assert on_disk["version"] == settings.SETTINGS_VERSION
    assert settings.load() == cfg


def test_save_leaves_no_temp_file_and_replaces_in_one_step():
    settings.save(settings.clean(None))
    settings.save(dict(settings.clean(None), color="amber"))
    folder = os.path.dirname(settings.settings_path())
    assert os.listdir(folder) == ["settings.json"]
    assert settings.load()["color"] == "amber"


def test_failed_save_keeps_the_old_file(monkeypatch):
    settings.save(dict(settings.clean(None), color="amber"))

    def explode(*_args, **_kwargs):
        raise OSError("disk full")

    with monkeypatch.context() as patch, pytest.raises(OSError, match="disk full"):
        patch.setattr(settings.json, "dump", explode)
        settings.save(dict(settings.clean(None), color="film"))
    assert settings.load()["color"] == "amber"
    folder = os.path.dirname(settings.settings_path())
    assert os.listdir(folder) == ["settings.json"]


def test_clean_matches_a_save_load_round_trip():
    """clean(raw) is what the old save-then-load path produced, byte for byte."""
    for raw in ({}, {"bloom": 0.3, "preset": "resurrections"}, {"speed": 99, "color": "x"}):
        settings.save(settings.clean(raw))
        assert settings.load() == settings.clean(raw)


def test_active_layers_follow_speed_density_and_depth():
    cfg = dict(settings.DEFAULTS, speed=2.0, density=0.5, depth=True)
    layers = settings.active_layers(cfg)
    assert len(layers) == 3
    assert layers[1]["speed"] == settings.LAYERS[1]["speed"] * 2.0
    flat = settings.active_layers(dict(cfg, depth=False))
    assert len(flat) == 1
    assert settings.main_layer_index(cfg) == 1
    assert settings.main_layer_index(dict(cfg, depth=False)) == 0


def test_monitor_cfg_applies_overrides_and_leaves_the_input_alone():
    cfg = dict(
        settings.DEFAULTS,
        monitors={"a": {"preset": "custom", "color": "amber", "speed": 2.0, "depth": False}},
    )
    kept = copy.deepcopy(cfg)
    assert settings.monitor_cfg(cfg, "b") == cfg
    assert settings.monitor_cfg(cfg, "") == cfg
    merged = settings.monitor_cfg(cfg, "a")
    assert (merged["preset"], merged["color"], merged["speed"], merged["depth"]) == (
        "custom",
        "amber",
        2.0,
        False,
    )
    assert merged["density"] == cfg["density"]
    assert cfg == kept


def test_include_subfolders_is_off_by_default_and_round_trips():
    assert settings.clean(None)["image_subfolders"] is False
    cfg = settings.clean({"image_dir": "C:/pics", "image_subfolders": True})
    assert settings.clean(json.loads(json.dumps(cfg))) == cfg
    assert cfg["image_subfolders"] is True


def test_message_font_is_cleaned_to_a_short_printable_family_name():
    cfg = settings.clean({"message_font": "  Georgia\x00\n" + "x" * 200})
    assert cfg["message_font"].startswith("Georgia")
    assert len(cfg["message_font"]) == settings.MESSAGE_FONT_MAX
    assert all(ch >= " " for ch in cfg["message_font"])
    assert settings.clean({"message_font": 7})["message_font"] == ""
    defaults = settings.clean(None)
    assert (defaults["message_font"], defaults["message_bold"], defaults["message_italic"]) == (
        "",
        True,
        False,
    )
    cfg = settings.clean({"message_bold": False, "message_italic": True})
    assert cfg["message_bold"] is False and cfg["message_italic"] is True


def test_message_font_size_is_clamped_and_defaults_to_the_reference_size():
    assert settings.clean(None)["message_font_size"] == settings.MESSAGE_FONT_REF_PT == 36
    assert settings.clean({"message_font_size": 500})["message_font_size"] == 144.0
    assert settings.clean({"message_font_size": 1})["message_font_size"] == 8.0
    assert settings.clean({"message_font_size": 72})["message_font_size"] == 72.0
    assert "message_size" not in settings.clean(None)
    from digital_rain import rain_message

    assert rain_message.text_style({"message_font_size": 72})[0] == 2.0
    assert rain_message.text_style({})[0] == 1.0
