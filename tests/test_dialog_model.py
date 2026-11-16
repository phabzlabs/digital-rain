"""dialog_model: the rules of the settings window, with no window.

tools/checks/check_dialog.py walks every enable rule; these tests cover the model's own contract:
editing, overrides, reset and the round trip back to a settings dict.
"""

from digital_rain import dialog_model as dm
from digital_rain import settings

CONNECTED = [dict(id="MON-A", name="DELL U2720Q"), dict(id="MON-B", name="LG 27GL850")]


def model(raw=None):
    return dm.Model(settings.clean(raw if raw is not None else {"preset": "film_1999"}), CONNECTED)


def test_unchanged_model_gives_back_the_loaded_settings():
    loaded = settings.clean({"preset": "reloaded", "speed": 1.4})
    assert dm.Model(loaded, CONNECTED).to_cfg() == loaded


def test_overrides_gain_the_monitor_name_on_the_way_out():
    loaded = settings.clean({"monitors": {"MON-A": {"speed": 2.0}}})
    out = dm.Model(loaded, CONNECTED).to_cfg()
    assert out["monitors"] == {"MON-A": {"speed": 2.0, "name": "DELL U2720Q"}}


def test_set_changes_the_global_value_and_clamps_it():
    m = model()
    m.set("speed", 1.987)
    assert m.to_cfg()["speed"] == 1.987
    m.set("bloom", 9.0)
    assert m.to_cfg()["bloom"] == settings.RANGES["bloom"][1]


def test_a_film_preset_locks_the_effects_box():
    m = model({"preset": "custom"})
    for key in dm.SHARED_EFFECTS:
        assert m.row(key).enabled
    m.set("preset", "reloaded")
    for key in dm.SHARED_EFFECTS:
        assert not m.row(key).enabled
    for key in dm.FIXED_EFFECTS:
        assert m.value(key) == dm.PRESET_EFFECTS["reloaded"][key]


def test_scope_lists_all_monitors_then_each_display():
    m = model()
    assert [entry["label"] for entry in m.entries()] == [
        "All monitors",
        "Display 1 (primary)",
        "Display 2",
    ]


def test_override_is_created_edited_and_removed():
    m = model()
    m.set_scope("MON-B")
    assert not m.row("speed").enabled
    m.set("speed", 2.0)
    assert not m.overridden("speed")
    m.create_override("speed")
    assert m.overridden("speed")
    m.set("speed", 1.5)
    assert m.to_cfg()["monitors"]["MON-B"]["speed"] == 1.5
    assert m.to_cfg()["speed"] == settings.DEFAULTS["speed"]
    m.remove_override("speed")
    assert "speed" not in m.to_cfg()["monitors"].get("MON-B", {})


def test_reset_restores_the_defaults_and_leaves_a_disconnected_scope():
    m = dm.Model(
        settings.clean(
            {"preset": "reloaded", "speed": 2.0, "monitors": {"GONE": {"density": 0.5}}}
        ),
        CONNECTED,
    )
    m.set_scope("GONE")
    m.reset()
    assert m.to_cfg() == dict(settings.DEFAULTS, monitors={})
    assert m.scope is None


def test_editing_the_model_never_writes_the_settings_file():
    import os

    m = model()
    m.set_scope("MON-A")
    m.set("preset", "custom")
    m.reset()
    assert not os.path.exists(settings.settings_path())


def test_every_page_row_edits_a_known_setting_or_view():
    views = {"effects", "keep_clock"}
    for rows in dm.PAGE_ROWS.values():
        for key, _control in rows:
            assert key in settings.DEFAULTS or key in views, key


def test_preset_sample_colours_match_the_last_palette_stop():
    from digital_rain import looks

    for name in dm.FILM_PRESETS:
        last = "#%02X%02X%02X" % looks.PRESETS[name]["palette"][-1][1]
        assert dm.PRESET_SAMPLE[name] == last
        for key in dm.FIXED_EFFECTS:
            assert dm.PRESET_EFFECTS[name][key] == looks.PRESETS[name][key]


def test_every_setting_is_edited_on_a_page_or_listed_as_not_ui():
    edited = {key for keys in dm.PAGE_KEYS.values() for key in keys}
    for key in settings.DEFAULTS:
        assert key in edited or key in dm.NON_UI_KEYS, key


def test_include_subfolders_sits_under_the_folder_and_needs_one():
    keys = [key for key, _kind in dm.PAGE_ROWS["images"]]
    assert keys[keys.index("image_dir") + 1] == "image_subfolders"
    m = dm.Model(settings.clean(None), ())
    row = m.row("image_subfolders")
    assert not row.enabled
    assert row.help == dm.DISABLED_HELP["image_subfolders"]
    m.set("image_dir", "C:/pics")
    assert m.row("image_subfolders").enabled
    m.control_set("image_subfolders", True)
    assert m.to_cfg()["image_subfolders"] is True
    assert m.summary("images")[0].startswith("Your folder and subfolders")
