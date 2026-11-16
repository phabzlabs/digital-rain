"""py2app build of MatrixRain.saver, the macOS screen saver plugin.

    python setup_mac.py py2app        (tools/build/build_mac.sh runs this in its venv)

The result is dist/MatrixRain.saver: a py2app plugin bundle (CFBundlePackageType
BNDL, extension .saver) whose NSPrincipalClass is MatrixRainView.
legacyScreenSaver loads the bundle's stub, the stub starts the embedded
Python.framework and runs the root mac_saver.py, which imports digital_rain/mac/mac_saver.py
and so defines the class. py2app's
plugin boot script sets sys.frozen = "macosx_plugin" and RESOURCEPATH to
Contents/Resources, which is where resources.base_dir() looks for assets/.

What is bundled:
    assets/        shaders, presets, the film fonts and glyph atlases (rezmason)
                   and assets/fonts, copied to Contents/Resources/assets.
                   assets/reference (20 MB of film stills for the checks) is not.
    packages       pygame-ce, moderngl, glcontext, numpy, psutil and PyObjC are
                   copied as whole folders so their binaries and data files stay
                   next to their modules (not in site-packages.zip).
    PyObjCTools    a namespace package (no __init__.py). py2app 0.28.10 finds
                   `packages` entries with imp_find_module, which cannot see
                   namespace packages ("No module named 'PyObjCTools'"), so its
                   one module the saver needs
                   (objc imports PyObjCTools.KeyValueCoding) goes in `includes`,
                   which modulegraph resolves through the import graph.
                   preflight() refuses any namespace package in PACKAGES.
    _math_integer  Python 3.15 split math's integer functions into this
                   extension module; modulegraph does not see the import.

Settings: the Options button in System Settings > Screen Saver opens the
native options sheet (digital_rain/mac/mac_options.py); the settings are stored in
ScreenSaverDefaults (digital_rain/mac/mac_settings.py).

Signing: py2app signs the bundle ad hoc; build_mac.sh re-signs it ad hoc
(codesign -s -) after the build. Developer ID signing and notarisation are not
done.

macOS only. Windows builds use build.ps1 (PyInstaller); this file is not used there.
"""

import glob
import importlib.util
import os
import re
import sys

if sys.platform != "darwin":
    sys.exit("setup_mac.py builds the macOS .saver and runs on macOS only (Windows: build.ps1).")

from setuptools import setup  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

NAME = "MatrixRain"
DISPLAY_NAME = "Digital Rain"
BUNDLE_ID = "net.phabzlabs.matrixrain"  # matches digital_rain.mac.mac_saver.SAVER_BUNDLE_ID
PRINCIPAL_CLASS = "MatrixRainView"

# Asset folders bundled into Contents/Resources/assets/<folder>.
ASSET_DIRS = ("shaders", "presets", "rezmason", "fonts")

# Our own modules. modulegraph follows the imports from digital_rain/mac/mac_saver.py, but
# several are imported inside functions (glyphs, settings, osapi.mac), so
# they are listed too.
OWN_MODULES = [
    "digital_rain",
    "digital_rain.osapi",
    "digital_rain.osapi.common",
    "digital_rain.osapi.mac",
    "digital_rain.resources",
    "digital_rain.settings",
    "digital_rain.looks",
    "digital_rain.glyphs",
    "digital_rain.gl_renderer",
    "digital_rain.fsr",
    "digital_rain.exit_gate",
    "digital_rain.easter_egg",
    "digital_rain.live_load",
    "digital_rain.rain_message",
    "digital_rain.dialog_model",
    "digital_rain.surfaces",
    "digital_rain.mac",
    "digital_rain.mac.mac_saver",
    "digital_rain.mac.mac_settings",
    "digital_rain.mac.mac_options",
    "digital_rain.mac.depth_coreml",
]


def version():
    """The product version, from the Windows version resource (one source)."""
    with open(os.path.join(ROOT, "version_info.txt"), encoding="utf-8") as fh:
        m = re.search(r"StringStruct\('ProductVersion', '([^']+)'\)", fh.read())
    return m.group(1) if m else "0.0.0"


def asset_files():
    """data_files entries: assets/<dir>/<file> into Resources/assets/<dir>."""
    out = []
    for d in ASSET_DIRS:
        files = sorted(f for f in glob.glob(os.path.join("assets", d, "*")) if os.path.isfile(f))
        if not files:
            sys.exit(f"setup_mac.py: assets/{d} is empty or missing")
        out.append((os.path.join("assets", d), files))
    # System Settings > Screen Saver tile: thumbnail.png / thumbnail@2x.png at the top
    # of Contents/Resources. Without them macOS shows its generic blue swirl.
    thumbs = sorted(glob.glob(os.path.join("assets", "mac", "thumbnail*.png")))
    if len(thumbs) != 2:
        sys.exit("setup_mac.py: assets/mac/thumbnail.png and thumbnail@2x.png are missing")
    out.append(("", thumbs))
    # the compiled Core ML depth model (tools/build/build_mac.sh makes it): a folder tree
    models = os.path.join(ROOT, "build", "coreml")
    for folder, _dirs, names in os.walk(models):
        if names:
            rel = os.path.relpath(folder, models)
            files = [os.path.join(folder, n) for n in sorted(names)]
            out.append((os.path.join("assets", "models", rel), files))
    return out


def patch_pygame_recipe():
    """py2app's pygame recipe copies pygame/pygame_icon.icns, which pygame-ce
    no longer ships, and the build stops on the missing file. Keep the recipe
    but drop the files that do not exist."""
    try:
        from py2app.recipes import pygame as recipe
    except ImportError:
        return
    original = recipe.check

    def check(cmd, mf):
        result = original(cmd, mf)
        if not result:
            return result
        loader = []
        for pkg, files in result.get("loader_files", []):
            kept = [f for f in files if os.path.exists(f)]
            if kept:
                loader.append((pkg, kept))
        result["loader_files"] = loader
        return result

    recipe.check = check


# Copied whole by py2app; each must be a regular package with an __init__.py.
PACKAGES = [
    "pygame",
    "moderngl",
    "glcontext",
    "numpy",
    "psutil",
    "objc",
    "AppKit",
    "Foundation",
    "CoreFoundation",
    "ScreenSaver",
    "CoreML",
    "Quartz",
]
# Modules inside namespace packages: listed one by one in includes.
NAMESPACE_MODULES = ["PyObjCTools.KeyValueCoding"]


def preflight():
    """Fail early, with a line build_mac.sh copies into checks.txt, when a
    `packages` entry is missing or is a namespace package (py2app's
    collect_packagedirs would stop with "No module named ..." instead)."""

    def find(name):
        try:
            return importlib.util.find_spec(name)
        except ImportError:  # a dotted name whose parent is missing
            return None

    bad = []
    for name in PACKAGES:
        spec = find(name)
        if spec is None:
            bad.append(f"{name} is not installed")
        elif not spec.submodule_search_locations:
            bad.append(f"{name} is a module, not a package")
        elif not (spec.origin or "").endswith("__init__.py"):
            bad.append(
                f"{name} is a namespace package (no __init__.py): "
                "list its modules in NAMESPACE_MODULES instead"
            )
    for name in NAMESPACE_MODULES:
        if find(name) is None:
            bad.append(f"{name} is not installed")
    for line in bad:
        print(f"PREFLIGHT FAIL {line}")
    if bad:
        sys.exit("setup_mac.py: preflight failed, see PREFLIGHT FAIL lines above")
    print(f"PREFLIGHT OK {len(PACKAGES)} packages, {len(NAMESPACE_MODULES)} namespace modules")


patch_pygame_recipe()
if "py2app" in sys.argv:
    preflight()

VERSION = version()

PLIST = {
    # Shown in System Settings > Screen Saver. NAME stays the file and folder name so an
    # installed MatrixRain.saver is replaced in place, not listed twice.
    "CFBundleName": DISPLAY_NAME,
    "CFBundleDisplayName": DISPLAY_NAME,
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleShortVersionString": VERSION,
    "CFBundleVersion": VERSION,
    "NSPrincipalClass": PRINCIPAL_CLASS,
    "NSHumanReadableCopyright": (
        "Copyright (C) 2026 madkoding and phabzlabs contributors. GNU GPL v3.0."
    ),
    "LSMinimumSystemVersion": "12.0",
    # py2app 0.28.10's plugin template builds these from sys.version[:3],
    # "3.1" on Python 3.15, so none of them exist. A fresh host process
    # does not need them (PYTHONHOME finds lib/python315.zip), but when
    # Python is already running in the host (another Python .saver loaded
    # first, or an NSBundle load from Python) the stub adds only these to
    # sys.path, and `import digital_rain` fails.
    "PyResourcePackages": [
        f"lib/python{sys.version_info[0]}.{sys.version_info[1]}",
        f"lib/python{sys.version_info[0]}.{sys.version_info[1]}/lib-dynload",
        f"lib/python{sys.version_info[0]}{sys.version_info[1]}.zip",
    ],
}

OPTIONS = {
    "extension": ".saver",
    "plist": PLIST,
    "includes": OWN_MODULES + ["_math_integer"] + NAMESPACE_MODULES,
    "packages": PACKAGES,
    "excludes": [
        "tkinter",
        "_tkinter",
        "digital_rain.osapi.windows",
        "digital_rain.windows",
        "digital_rain.windows.matrix_saver",
        "digital_rain.windows.config_dialog",
        "digital_rain.windows.dialog_preview",
        "digital_rain.windows.dialog_widgets",
        "digital_rain.soft_renderer",
        "matrix_saver",
        "PyInstaller",
        "pywin32_ctypes",
        "win32api",
        "win32con",
        "pytest",
    ],
    "optimize": 0,
    "site_packages": False,
}

setup(
    name=NAME,
    version=VERSION,
    plugin=["mac_saver.py"],
    data_files=asset_files(),
    options={"py2app": OPTIONS},
)
