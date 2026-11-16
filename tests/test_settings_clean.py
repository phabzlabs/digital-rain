"""settings.clean() on a raw dict must equal what load() returns for the same file, and saving
either gives the same bytes: the dialog relies on this to skip a second disk round trip."""

import json
import os
import subprocess
import sys

import pytest
from conftest import FIXTURES, ROOT

from digital_rain import settings

with open(os.path.join(FIXTURES, "settings_v1_1_0.json"), encoding="utf-8") as _handle:
    FIXTURE_V110 = json.load(_handle)

INPUTS = {
    "v1.1.0 fixture": FIXTURE_V110,
    "empty dict": {},
    "bad values": {"speed": 99, "density": "x", "bloom": True, "monitors": {0: {"speed": 5}}},
    "non-dict": [1, 2],
}


def _saved_bytes():
    with open(settings.settings_path(), "rb") as handle:
        return handle.read()


@pytest.mark.parametrize("raw", INPUTS.values(), ids=INPUTS.keys())
def test_clean_equals_load(raw):
    settings.save(raw)
    assert settings.load() == settings.clean(json.loads(json.dumps(raw)))


@pytest.mark.parametrize("raw", INPUTS.values(), ids=INPUTS.keys())
def test_saving_clean_or_loaded_gives_the_same_bytes(raw):
    settings.save(raw)
    settings.save(settings.load())
    from_load = _saved_bytes()
    settings.save(settings.clean(json.loads(json.dumps(raw))))
    assert _saved_bytes() == from_load


def test_the_dialog_module_does_not_import_numpy():
    code = (
        "import sys; from digital_rain.windows import config_dialog; "
        "print('numpy' in sys.modules)"
    )
    env = dict(os.environ, SDL_VIDEODRIVER="dummy")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
