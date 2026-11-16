"""Where the Mac saver keeps its settings: one JSON blob in
ScreenSaverDefaults, validated by settings.clean.

The saver runs sandboxed in legacyScreenSaver, so the options sheet
(mac_options.py) cannot write the old settings.json in the real home. It saves
to ScreenSaverDefaults under the bundle identifier instead. The old file is
still read when no blob was saved (resolve).

Plain Python: ScreenSaver is imported inside open_defaults only, so
tools/checks/check_mac_options.py runs everything else on Windows.
"""

import json
import traceback

from digital_rain import osapi, settings

MODULE_NAME = "net.phabzlabs.matrixrain"  # the .saver's CFBundleIdentifier
BLOB_KEY = "settings_json"
CHANGED_NOTE = "net.phabzlabs.matrixrain.settingschanged"


def encode(cfg):
    """The blob saved for cfg: settings.clean of a JSON round trip, as JSON text."""
    return json.dumps(
        settings.clean(json.loads(json.dumps(cfg))), sort_keys=True, ensure_ascii=False
    )


def decode(blob):
    """-> (cfg or None, problem or None). None blob: (None, None)."""
    if blob is None:
        return None, None
    if not isinstance(blob, str):
        return None, f"settings blob is a {type(blob).__name__}, not a string"
    try:
        parsed = json.loads(blob)
    except ValueError as exc:
        return None, f"settings blob is not valid JSON ({exc})"
    if not isinstance(parsed, dict):
        return None, f"settings blob is JSON {type(parsed).__name__}, not an object"
    return settings.clean(parsed), None


def resolve(blob, file_path):
    """-> (cfg, source, problems). The defaults blob, else the legacy file, else
    built-in values. source is "defaults", "file" or "built-in"."""
    problems = []
    cfg, problem = decode(blob)
    if problem:
        problems.append(problem)
    if cfg is not None:
        return cfg, "defaults", problems
    if file_path:
        try:
            with open(file_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            problems.append(f"settings file {file_path} not read ({exc})")
        else:
            return settings.clean(raw), "file", problems
    return settings.clean(None), "built-in", problems


def check_module_name(bundle_id, bundle_path):
    """A warning when the .saver's bundle id is not MODULE_NAME, else None. Under
    tools/dev/mac_host.py the class's bundle is Python's own, which is not an error."""
    if str(bundle_path or "").rstrip("/").endswith(".saver") and bundle_id != MODULE_NAME:
        return (
            f"bundle identifier {bundle_id!r} is not {MODULE_NAME!r}; settings are "
            f"saved under {MODULE_NAME!r}, which macOS may not read for this bundle"
        )
    return None


def open_defaults():
    from ScreenSaver import ScreenSaverDefaults

    return ScreenSaverDefaults.defaultsForModuleWithName_(MODULE_NAME)


def read_blob(defaults):
    """The saved blob as str, or whatever else is stored (decode reports it)."""
    defaults.synchronize()
    value = defaults.objectForKey_(BLOB_KEY)
    if isinstance(value, str):  # NSString arrives as a str subclass (objc.pyobjc_unicode)
        return str(value)
    return value


def read_saved_blob(who):
    """The saved blob, or None when ScreenSaverDefaults cannot be read. The failure is
    logged under `who` and the blob then counts as absent."""
    try:
        return read_blob(open_defaults())
    except Exception:  # PyObjC raises several types; the saver must still start
        osapi.log(
            f"{who}: ScreenSaverDefaults read FAILED, blob counts as absent\n"
            + traceback.format_exc()
        )
        return None


def write_blob(defaults, cfg):
    """Save cfg; True when synchronize reports success."""
    defaults.setObject_forKey_(encode(cfg), BLOB_KEY)
    return bool(defaults.synchronize())
