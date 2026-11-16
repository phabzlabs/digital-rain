"""Shared pytest setup: no window, no GPU, and a private settings folder per test."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture(autouse=True)
def private_appdata(tmp_path, monkeypatch):
    """Point the settings file at a temp folder so no test touches the real one."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    if sys.platform == "darwin":
        # macOS reads the legacy settings file from the real home (password database), not HOME
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr("digital_rain.osapi.mac._real_home", lambda: str(home))
    return tmp_path
