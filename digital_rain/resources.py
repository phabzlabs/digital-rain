"""Bundled read-only data (assets/): fonts, glyph atlases, shaders and look presets.

One lookup for every build:
    source checkout  the repository root (the folder above digital_rain/)
    PyInstaller      sys._MEIPASS (build.ps1 adds assets/ with --add-data)
    py2app (.saver)  the bundle's Contents/Resources, which py2app's boot script
                     publishes as RESOURCEPATH (sys.frozen is "macosx_plugin")

Shaders are GLSL `#version 330` core: Windows drivers and macOS's OpenGL 4.1
core profile both compile them as they are.
"""

import os
import sys


def base_dir():
    frozen = getattr(sys, "frozen", False)
    if frozen in ("macosx_plugin", "macosx_app"):
        res = os.environ.get("RESOURCEPATH")
        if res:
            return res
    if frozen:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return meipass
    # source checkout: the repository root, which holds assets/ (this file is in digital_rain/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(*parts):
    """Path of a file under assets/ (it may not exist; callers check)."""
    return os.path.join(base_dir(), "assets", *parts)


def read_text(*parts):
    with open(asset_path(*parts), encoding="utf-8") as fh:
        return fh.read()


def shader(name, **subs):
    """GLSL source of assets/shaders/<name>. With keyword arguments the file is a
    %-template: %(NAME)s placeholders are filled in and %% stands for %."""
    src = read_text("shaders", name)
    return src % subs if subs else src
