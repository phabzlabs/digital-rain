"""mac_settings: the settings blob and where the saver reads it from."""

import json

from digital_rain import settings
from digital_rain.mac import mac_settings


def test_encode_is_cleaned_sorted_json_that_decodes_back():
    cfg = dict(settings.DEFAULTS, bloom=7, color="amber")
    blob = mac_settings.encode(cfg)
    assert json.loads(blob)["bloom"] == 1.0
    assert blob == json.dumps(json.loads(blob), sort_keys=True, ensure_ascii=False)
    decoded, problem = mac_settings.decode(blob)
    assert problem is None
    assert decoded == settings.clean(cfg)


def test_decode_none_is_not_a_problem():
    assert mac_settings.decode(None) == (None, None)


def test_decode_reports_what_is_wrong():
    for bad, words in ((5, "not a string"), ("{nope", "not valid JSON"), ("[1]", "not an object")):
        cfg, problem = mac_settings.decode(bad)
        assert cfg is None
        assert words in problem


def test_defaults_blob_wins_over_the_legacy_file(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text(json.dumps({"color": "amber"}), encoding="utf-8")
    blob = mac_settings.encode(dict(settings.DEFAULTS, color="film"))
    cfg, source, problems = mac_settings.resolve(blob, str(legacy))
    assert source == "defaults"
    assert cfg["color"] == "film"
    assert problems == []


def test_legacy_file_is_used_when_there_is_no_blob(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text(json.dumps({"color": "amber"}), encoding="utf-8")
    cfg, source, problems = mac_settings.resolve(None, str(legacy))
    assert (source, cfg["color"], problems) == ("file", "amber", [])


def test_built_in_values_when_nothing_is_saved(tmp_path):
    cfg, source, problems = mac_settings.resolve(None, str(tmp_path / "missing.json"))
    assert (source, problems) == ("built-in", [])
    assert cfg == settings.clean(None)


def test_a_bad_blob_falls_through_and_is_reported(tmp_path):
    cfg, source, problems = mac_settings.resolve("{nope", str(tmp_path / "missing.json"))
    assert source == "built-in"
    assert len(problems) == 1


def test_an_unreadable_legacy_file_is_reported(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text("{nope", encoding="utf-8")
    _cfg, source, problems = mac_settings.resolve(None, str(legacy))
    assert source == "built-in"
    assert "not read" in problems[0]
