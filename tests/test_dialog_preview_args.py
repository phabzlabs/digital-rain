"""The settings window's preview child: its command line and the developer flags it uses."""

import contextlib
import io
from unittest import mock

import pytest

from digital_rain import settings
from digital_rain.windows import dialog_preview, matrix_saver


def test_preview_flags_parse_to_their_values():
    argv = [
        "/p",
        "123",
        "--settings-file",
        "x.json",
        "--fps",
        "18",
        "--preview-scale",
        "0.5",
        "--ready-event",
        "Local\\ev",
        "--dialog-size",
        "960x600",
    ]
    mode, hwnd, dev = matrix_saver.parse_args(argv)
    assert (mode, hwnd) == ("p", 123)
    assert dev["settings_file"] == "x.json"
    assert dev["fps"] == 18.0
    assert dev["preview_scale"] == 0.5
    assert dev["ready_event"] == "Local\\ev"
    assert dev["dialog_size"] == (960, 600)


def test_preview_flags_are_none_when_absent():
    _mode, _hwnd, dev = matrix_saver.parse_args([])
    for key in ("settings_file", "fps", "preview_scale", "ready_event", "dialog_size"):
        assert dev[key] is None


@pytest.mark.parametrize(
    "flag, value",
    [
        ("--settings-file", "a"),
        ("--fps", "18"),
        ("--preview-scale", "0.5"),
        ("--ready-event", "e"),
        ("--dialog-size", "960x600"),
    ],
)
@pytest.mark.parametrize("base", [[], ["/s"], ["/c"]])
def test_preview_flags_do_not_change_the_mode(flag, value, base):
    assert matrix_saver.parse_args(base + [flag, value])[0] == matrix_saver.parse_args(base)[0]


@pytest.mark.parametrize("bad", ["960", "960x", "axb", "0x600", "960x600x1", "-5x3"])
def test_bad_dialog_size_exits_with_a_message(bad):
    err = io.StringIO()
    with contextlib.redirect_stderr(err), pytest.raises(SystemExit) as exit_info:
        matrix_saver.parse_args(["/c", "--dialog-size", bad])
    assert exit_info.value.code == 2
    assert err.getvalue()


def test_run_flag_parses_in_decimal_and_hex():
    assert matrix_saver.parse_args(["/s", "--run", "7"])[2]["run"] == 7
    assert matrix_saver.parse_args(["/s", "--run", "0x10"])[2]["run"] == 16
    mode, hwnd, dev = matrix_saver.parse_args(["/p", "123", "--run", "5"])
    assert (mode, hwnd, dev["run"]) == ("p", 123, 5)


@pytest.mark.parametrize("bad", ["-1", "x", "4294967296"])
def test_bad_run_value_exits_with_a_message(bad):
    err = io.StringIO()
    with contextlib.redirect_stderr(err), pytest.raises(SystemExit) as exit_info:
        matrix_saver.parse_args(["/s", "--run", bad])
    assert exit_info.value.code == 2
    assert err.getvalue()


def test_child_args_carry_run_only_when_given_one():
    assert dialog_preview.child_args(1, "x.json", "ev", run=5)[-2:] == ["--run", "5"]
    assert "--run" not in dialog_preview.child_args(1, "x.json", "ev")


class FakeRoot:
    def after(self, _ms, _fn):
        return None

    def after_cancel(self, _job):
        pass


def test_full_screen_command_ends_with_the_dialog_session_run_value():
    cfg = settings.clean({"preset": "film_1999"})
    preview = dialog_preview.Preview(
        FakeRoot(), None, None, lambda: (cfg, cfg, "#53EEAB"), force=True
    )
    with mock.patch.object(dialog_preview.subprocess, "Popen") as popen:
        preview.full_screen()
    for path in preview.temps:
        dialog_preview._remove(path)
    assert popen.called
    command = popen.call_args[0][0]
    assert "/s" in command
    assert command[-2:] == ["--run", str(preview.run)]
