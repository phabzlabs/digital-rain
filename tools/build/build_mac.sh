#!/bin/bash
# Builds Digital Rain.saver with py2app and checks the bundle.
#   bash tools/build/build_mac.sh [--reuse-venv] [--install] [OUT_DIR]
#   bash tools/build/build_mac.sh --collect [OUT_DIR]
#
# Build (default): creates build/mac-venv from scratch with python.org Python
# 3.14, the version the Windows build and CI use too (PYTHON=/path/to/python3.x picks another), installs the pinned
# requirements/requirements-mac-build.txt, runs `python setup_mac.py py2app`, signs the
# bundle ad hoc (codesign -s -), checks it, zips it to MatrixRain-mac.zip (a local build
# output) and makes DigitalRain.dmg, the release file (the saver plus Install.txt).
# --reuse-venv keeps an existing build/mac-venv. --install also copies the
# bundle to ~/Library/Screen Savers (replacing an older copy).
#
# --collect: after trying the installed saver in System Settings, copies the
# sandboxed saver.log and the last 30 minutes of legacyScreenSaver log lines into
# OUT_DIR. Does not build.
#
# OUT_DIR (default: mac-build-results in the checkout) gets the build output,
# checks.txt, the Info.plist, a file list of the bundle, codesign output,
# package versions and macOS version. Exit code 0 when every check passed.
# Built for bash 3.2 (/bin/bash on macOS).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$ROOT/build/mac-venv"
SAVER="$ROOT/dist/Digital Rain.saver"
ZIP="$ROOT/MatrixRain-mac.zip"
DMG="$ROOT/DigitalRain.dmg"
INSTALLED="$HOME/Library/Screen Savers/Digital Rain.saver"
CONTAINER="$HOME/Library/Containers/com.apple.ScreenSaver.Engine.legacyScreenSaver/Data"
SANDBOX_LOG="$CONTAINER/Library/Application Support/MatrixRain/logs/saver.log"

reuse=0; install=0; collect=0; OUT=""
for a in "$@"; do
    case "$a" in
        --reuse-venv) reuse=1 ;;
        --install) install=1 ;;
        --collect) collect=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        -*) echo "Unknown option $a"; exit 2 ;;
        *) OUT="$a" ;;
    esac
done
OUT="${OUT:-$ROOT/mac-build-results}"

if [ "$(uname)" != "Darwin" ]; then
    echo "build_mac.sh runs on macOS only (Windows: build.ps1)."
    exit 2
fi

# --collect
if [ "$collect" -eq 1 ]; then
    mkdir -p "$OUT"
    S="$OUT/collect-summary.txt"
    : > "$S"
    note() { echo "$*" | tee -a "$S"; }
    note "collect at $(date '+%Y-%m-%d %H:%M:%S')"

    # The container is behind macOS's "access data from other apps" privacy
    # check, so a missing file and a denied read look alike. ls tells them apart.
    if ! ls "$CONTAINER/Library" > /dev/null 2> "$OUT/container-ls-error.txt"; then
        note "CONTAINER NOT READABLE: $(head -1 "$OUT/container-ls-error.txt")"
        note "  Allow Terminal when macOS asks to access other apps' data, or turn on"
        note "  System Settings > Privacy & Security > Full Disk Access > Terminal, then rerun --collect."
    else
        if [ -f "$SANDBOX_LOG" ]; then
            cp "$SANDBOX_LOG" "$OUT/saver-sandbox.log"
            note "sandbox log: copied, $(wc -l < "$SANDBOX_LOG" | tr -d ' ') lines"
        else
            note "sandbox log: none at $SANDBOX_LOG (container readable, so the saver never wrote it)"
        fi
        # mac_saver writes this with the stdlib alone when `import osapi` fails.
        EARLY="$CONTAINER/Library/Logs/MatrixRain-early.log"
        if [ -f "$EARLY" ]; then
            cp "$EARLY" "$OUT/saver-early.log"
            note "EARLY LOG FOUND: the saver failed before osapi loaded, see saver-early.log"
        else
            note "early log: none (the saver did not fail at import osapi)"
        fi
        find "$CONTAINER/Library/Application Support" "$CONTAINER/Library/Logs" -maxdepth 3 \
            2>/dev/null > "$OUT/container-files.txt"
    fi

    # ScreenSaverDefaults lives in the container's Preferences folder (plain
    # and ByHost). Copy each plist and dump it with plutil.
    found_defaults=0
    for f in "$CONTAINER"/Library/Preferences/ByHost/net.phabzlabs.matrixrain*              "$CONTAINER"/Library/Preferences/net.phabzlabs.matrixrain*; do
        [ -f "$f" ] || continue
        found_defaults=1
        b="$(basename "$f")"
        cp "$f" "$OUT/$b"
        plutil -p "$f" > "$OUT/defaults-$b.txt" 2>&1
        note "ScreenSaverDefaults file: $b (see defaults-$b.txt)"
    done
    if [ "$found_defaults" -eq 0 ]; then
        note "no ScreenSaverDefaults file found"
    fi

    # Python's syslog text arrives redacted as <private>, so match on the
    # process instead of the message (the 10 November trial's predicate).
    log show --last 30m --style compact --info --debug \
        --predicate 'process BEGINSWITH "legacyScreenSaver" OR eventMessage CONTAINS[c] "MatrixRain"' \
        > "$OUT/syslog.txt" 2>&1
    note "system log: $(grep -c 'legacyScreenSaver' "$OUT/syslog.txt") legacyScreenSaver lines, $(grep -ci 'MatrixRain' "$OUT/syslog.txt") mentioning MatrixRain"
    grep -iE "principalClass|ScreenSaverView is NULL|MatrixRain|Traceback|Error" "$OUT/syslog.txt" \
        | grep -v "^Timestamp" | tail -40 > "$OUT/syslog-highlights.txt"

    # Where the bundle is now: the user and system screen saver folders.
    for d in "$HOME/Library/Screen Savers" "/Library/Screen Savers"; do
        note "contents of $d:"
        ls -la "$d" 2>&1 | sed 's/^/  /' | tee -a "$S" > /dev/null
    done
    if [ -d "$INSTALLED" ]; then
        codesign -dv --verbose=2 "$INSTALLED" > "$OUT/codesign-installed.txt" 2>&1
        note "installed: $INSTALLED"
    elif [ -d "/Library/Screen Savers/Digital Rain.saver" ]; then
        codesign -dv --verbose=2 "/Library/Screen Savers/Digital Rain.saver" > "$OUT/codesign-installed.txt" 2>&1
        note "installed for all users: /Library/Screen Savers/Digital Rain.saver"
    else
        note "NOT INSTALLED in either Screen Savers folder"
    fi
    pgrep -fl legacyScreenSaver > "$OUT/processes.txt" 2>&1
    sw_vers > "$OUT/macos.txt"
    echo "Results in $OUT (start with collect-summary.txt)"
    exit 0
fi

# Build
rm -rf "$OUT"
mkdir -p "$OUT"
LOG="$OUT/build-output.txt"
CHECKS="$OUT/checks.txt"
: > "$CHECKS"
sw_vers > "$OUT/macos.txt"
uname -m >> "$OUT/macos.txt"

if [ "$reuse" -eq 0 ] || [ ! -x "$VENV/bin/python" ]; then
    PY="${PYTHON:-}"
    if [ -z "$PY" ]; then
        for v in 3.14; do
            c="/Library/Frameworks/Python.framework/Versions/$v/bin/python$v"
            if [ -x "$c" ]; then PY="$c"; break; fi
        done
    fi
    if [ -z "$PY" ]; then
        echo "No python.org Python 3.14 found (https://www.python.org/downloads/macos/)." | tee -a "$LOG"
        exit 1
    fi
    echo "Creating $VENV with $PY" | tee -a "$LOG"
    rm -rf "$VENV"
    mkdir -p "$ROOT/build"
    "$PY" -m venv "$VENV" 2>&1 | tee -a "$LOG"
    [ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
    "$VENV/bin/pip" install --disable-pip-version-check --upgrade pip 2>&1 | tee -a "$LOG"
    "$VENV/bin/pip" install --disable-pip-version-check -r "$ROOT/requirements/requirements-mac-build.txt" 2>&1 | tee -a "$LOG"
    [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "pip install failed, see $LOG"; exit 1; }
fi
"$VENV/bin/python" -VV > "$OUT/versions.txt"
"$VENV/bin/pip" freeze >> "$OUT/versions.txt"

cd "$ROOT"
rm -rf "$ROOT/build/bdist.macosx"* "$ROOT/build/lib" "$SAVER" "$ZIP" "$DMG"
echo "== compile the Core ML depth model" | tee -a "$LOG"
rm -rf "$ROOT/build/coreml"
"$VENV/bin/python" tools/build/compile_coreml.py assets/models/DepthAnythingV2SmallF16.mlpackage "$ROOT/build/coreml" 2>&1 | tee -a "$LOG"
echo "== python setup_mac.py py2app" | tee -a "$LOG"
"$VENV/bin/python" setup_mac.py py2app 2>&1 | tee -a "$LOG"
rc=${PIPESTATUS[0]}
echo "exit code $rc" | tee -a "$LOG"
grep -h "^PREFLIGHT" "$LOG" >> "$CHECKS"
if [ "$rc" -ne 0 ] || [ ! -d "$SAVER" ]; then
    # Put the reason in checks.txt, not only in the long build output: the
    # preflight lines, any "No module named" (the PyObjCTools namespace
    # package failure from an early build) and the last error line.
    {
        echo "FAIL  py2app exit code $rc, no bundle at $SAVER"
        grep -E "No module named|ImportError|ModuleNotFoundError" "$LOG" | sort -u | sed 's/^/FAIL  /'
        grep -E "Error" "$LOG" | tail -1 | sed 's/^/      last error: /'
    } | tee -a "$CHECKS"
    echo "py2app failed (exit $rc). Send back $OUT."
    exit 1
fi

# py2app copies digital_rain whole (it uses __file__), ignoring excludes: drop the
# Windows-only code, then precompile so loading the bundle never writes into it.
PKG="$SAVER/Contents/Resources/lib/python$("$VENV/bin/python" -c 'import sys;print("%d.%d"%sys.version_info[:2])')/digital_rain"
rm -rf "$PKG/windows" "$PKG/osapi/windows.py" "$PKG/soft_renderer.py"
find "$PKG" -name __pycache__ -prune -exec rm -rf {} +
"$VENV/bin/python" -m compileall -q "$PKG" | tee -a "$LOG"

echo "== codesign -s -" | tee -a "$LOG"
codesign --force --deep -s - "$SAVER" 2>&1 | tee -a "$LOG"

# Checks
fails=0
pass() { echo "PASS  $*" | tee -a "$CHECKS"; }
fail() { echo "FAIL  $*" | tee -a "$CHECKS"; fails=$((fails + 1)); }
warn() { echo "WARN  $*" | tee -a "$CHECKS"; }
check() {   # check "description" command...
    local what="$1"; shift
    if "$@" > /dev/null 2>&1; then pass "$what"; else fail "$what"; fi
}

C="$SAVER/Contents"
R="$C/Resources"
PLIST="$C/Info.plist"
cp "$PLIST" "$OUT/Info.plist" 2>/dev/null
plutil -convert xml1 -o "$OUT/Info.plist" "$PLIST" 2>/dev/null
(cd "$ROOT/dist" && find "Digital Rain.saver" | sort) > "$OUT/bundle-files.txt"
du -sh "$SAVER" > "$OUT/bundle-size.txt"

key() { /usr/libexec/PlistBuddy -c "Print :$1" "$PLIST" 2>/dev/null; }
expect_key() {   # expect_key KEY VALUE
    local got; got="$(key "$1")"
    if [ "$got" = "$2" ]; then pass "Info.plist $1 = $2"; else fail "Info.plist $1 = '$got', expected '$2'"; fi
}
echo "== Info.plist" | tee -a "$CHECKS"
check "Info.plist is valid" plutil -lint "$PLIST"
expect_key CFBundlePackageType BNDL
expect_key NSPrincipalClass MatrixRainView
expect_key CFBundleIdentifier net.phabzlabs.matrixrain
expect_key CFBundleName "Digital Rain"
EXE="$(key CFBundleExecutable)"
check "CFBundleExecutable '$EXE' exists in Contents/MacOS" test -x "$C/MacOS/$EXE"
echo "      CFBundleShortVersionString $(key CFBundleShortVersionString)" | tee -a "$CHECKS"
echo "      main stub archs: $(lipo -archs "$C/MacOS/$EXE" 2>/dev/null)" | tee -a "$CHECKS"
if lipo -archs "$C/MacOS/$EXE" 2>/dev/null | grep -qw arm64; then
    pass "main stub has arm64"
else
    fail "main stub has no arm64 slice"
fi

echo "== Python runtime" | tee -a "$CHECKS"
check "embedded Python.framework" test -d "$C/Frameworks/Python.framework"
check "boot script Resources/__boot__.py" test -f "$R/__boot__.py"
check "main script Resources/mac_saver.py" test -f "$R/mac_saver.py"
check "screen saver tile Resources/thumbnail.png" test -f "$R/thumbnail.png"
check "screen saver tile Resources/thumbnail@2x.png" test -f "$R/thumbnail@2x.png"
PYLIB="$(cd "$R/lib" 2>/dev/null && ls -d python3.* 2>/dev/null | head -1)"
echo "      Resources/lib/$PYLIB" | tee -a "$CHECKS"
# py2app's plist template builds these from sys.version[:3] ("3.1" on 3.15);
# setup_mac.py sets them itself. Each must exist: when Python is already
# running in the host process they are the bundle's whole sys.path.
i=0
while p="$(key "PyResourcePackages:$i")" && [ -n "$p" ]; do
    if [ -e "$R/$p" ]; then pass "PyResourcePackages $p exists"
    else fail "PyResourcePackages $p does not exist in Resources"; fi
    i=$((i + 1))
done
[ "$i" -gt 0 ] || fail "Info.plist has no PyResourcePackages"
i=0
while p="$(key "PyRuntimeLocations:$i")" && [ -n "$p" ]; do
    real="${p/@executable_path/$C/MacOS}"
    if [ -e "$real" ]; then pass "PyRuntimeLocations $p exists"
    else warn "PyRuntimeLocations $p does not exist"; fi
    i=$((i + 1))
done

echo "== Binaries" | tee -a "$CHECKS"
has_file() {   # has_file "description" find-args...
    local what="$1"; shift
    local hit; hit="$(find "$SAVER" "$@" 2>/dev/null | head -1)"
    if [ -n "$hit" ]; then
        pass "$what: ${hit#$ROOT/dist/}"
        echo "      archs: $(lipo -archs "$hit" 2>/dev/null)" | tee -a "$CHECKS"
    else
        fail "$what not found"
    fi
}
# math is its own extension on 3.14; 3.15 splits out _math_integer
has_file "math extension" \( -name 'math.cpython*.so' -o -name 'math.so' -o -name '_math_integer*.so' \)
has_file "moderngl binary" -path '*moderngl*' -name '*.so'
has_file "glcontext binary" -path '*glcontext*' -name '*.so'
has_file "pygame base binary" -path '*pygame*' -name 'base*.so'
has_file "pygame SDL2 dylib" -name 'libSDL2*.dylib'
has_file "numpy core binary" -path '*numpy*' -name '_multiarray_umath*.so'
has_file "psutil binary" -path '*psutil*' -name '_psutil_osx*.so'
has_file "PyObjC objc binary" -path '*objc*' -name '_objc*.so'
if find "$SAVER" -path '*tkinter*' | grep -q .; then warn "tkinter is in the bundle"; fi
# Pure-Python modules land in Resources/lib/python3XX.zip or as loose files.
MODS="$OUT/python-modules.txt"
{ find "$R" -name '*.pyc' -o -name '*.py'
  find "$R/lib" -name '*.zip' -exec unzip -Z1 {} \; 2>/dev/null; } > "$MODS"
for m in digital_rain/__init__ digital_rain/osapi/__init__ digital_rain/osapi/common digital_rain/osapi/mac \
         digital_rain/resources digital_rain/settings digital_rain/looks digital_rain/glyphs digital_rain/gl_renderer \
         digital_rain/fsr digital_rain/exit_gate digital_rain/easter_egg digital_rain/live_load digital_rain/rain_message \
         digital_rain/dialog_model digital_rain/mac/__init__ digital_rain/mac/mac_saver digital_rain/mac/mac_settings \
         digital_rain/mac/mac_options AppKit/__init__ Foundation/__init__ \
         ScreenSaver/__init__ objc/__init__ PyObjCTools/KeyValueCoding moderngl/__init__ glcontext/__init__ pygame/__init__; do
    if grep -Eq "(^|/)$m\.pyc?$" "$MODS"; then
        pass "module $m"
    else
        fail "module $m not in the bundle"
    fi
done
for m in digital_rain/windows/config_dialog digital_rain/windows/dialog_widgets digital_rain/windows/dialog_preview; do
    if grep -Eq "(^|/)$m\.pyc?$" "$MODS"; then
        fail "module $m (Tk dialog code) is in the bundle"
    else
        pass "module $m is not in the bundle"
    fi
done

echo "== Assets" | tee -a "$CHECKS"
for d in shaders presets rezmason fonts; do
    want=$(find "$ROOT/assets/$d" -type f | wc -l | tr -d ' ')
    got=$(find "$R/assets/$d" -type f 2>/dev/null | wc -l | tr -d ' ')
    if [ "$got" -eq "$want" ] && [ "$want" -gt 0 ]; then pass "assets/$d: $got files"
    else fail "assets/$d: $got files in the bundle, $want in the checkout"; fi
done
check "film font assets/rezmason/Matrix-Code.ttf" test -f "$R/assets/rezmason/Matrix-Code.ttf"
check "shader assets/shaders/scene.frag" test -f "$R/assets/shaders/scene.frag"
check "Core ML depth model assets/models/DepthAnythingV2SmallF16.mlmodelc" test -f "$R/assets/models/DepthAnythingV2SmallF16.mlmodelc/coremldata.bin"
if [ -d "$R/assets/reference" ]; then warn "assets/reference (film stills) is in the bundle"; fi

echo "== Load test" | tee -a "$CHECKS"
# Load the built bundle with NSBundle from the venv's Python, the way a host
# that already runs Python loads it, and ask for the principal class. A file
# check cannot see a sys.path problem; this does (the "No module named
# 'osapi'" failure seen in an early build). The saver's log lines from this
# load go to ~/Library/Application Support/MatrixRain/logs/saver.log.
PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" -I -B -c '
import signal, sys
signal.alarm(90)
from Foundation import NSBundle
b = NSBundle.bundleWithPath_(sys.argv[1])
ok, err = b.loadAndReturnError_(None)
cls = b.principalClass()
print("loaded", ok, "error", err, "principalClass", cls)
sys.exit(0 if ok and cls is not None and cls.__name__ == "MatrixRainView" else 1)
' "$SAVER" > "$OUT/load-test.txt" 2>&1
lrc=$?
if [ "$lrc" -eq 0 ]; then
    pass "NSBundle load: $(tail -1 "$OUT/load-test.txt")"
else
    fail "NSBundle load (exit $lrc): $(tail -1 "$OUT/load-test.txt")"
    grep -E "No module named|Error" "$OUT/load-test.txt" | sort -u | sed 's/^/FAIL  /' | tee -a "$CHECKS"
fi

echo "== Signature" | tee -a "$CHECKS"
codesign -dv --verbose=2 "$SAVER" > "$OUT/codesign.txt" 2>&1
codesign --verify --deep --strict --verbose=2 "$SAVER" >> "$OUT/codesign.txt" 2>&1 \
    && pass "codesign --verify --deep --strict" || fail "codesign --verify (see codesign.txt)"
grep -q "Signature=adhoc" "$OUT/codesign.txt" && pass "ad-hoc signature" || warn "signature is not ad hoc"

ditto -c -k --keepParent "$SAVER" "$ZIP" && pass "zipped to $(basename "$ZIP")" || fail "ditto zip"

# The release file: a disk image holding the saver and a short install note. The saver is
# copied with ditto so the bundle, its symlinks and the ad hoc signature stay intact.
echo "== DigitalRain.dmg" | tee -a "$CHECKS"
DMGDIR="$ROOT/build/dmg"
rm -rf "$DMGDIR" "$DMG"
mkdir -p "$DMGDIR"
if ditto "$SAVER" "$DMGDIR/Digital Rain.saver"; then
    cat > "$DMGDIR/Install.txt" <<'EOF_INSTALL'
Digital Rain for macOS

To install, double-click "Digital Rain.saver". macOS offers to install it
and opens System Settings > Screen Saver.

This build is signed ad hoc only and is not notarised, so macOS may block
it the first time ("Apple could not verify..."). To allow it:

  1. Open System Settings > Privacy & Security.
  2. Scroll down to the message about "Digital Rain.saver" and click
     Open Anyway, then confirm.

Or, before opening it, remove the quarantine flag in Terminal:

  xattr -dr com.apple.quarantine "Digital Rain.saver"

To uninstall, delete "Digital Rain.saver" from ~/Library/Screen Savers.
EOF_INSTALL
    if hdiutil create -volname "Digital Rain" -srcfolder "$DMGDIR" -format UDZO -fs HFS+ -ov "$DMG" > "$OUT/dmg.txt" 2>&1 \
        && [ -s "$DMG" ]; then
        pass "disk image $(basename "$DMG"), $(du -h "$DMG" | cut -f1)"
        if hdiutil verify "$DMG" >> "$OUT/dmg.txt" 2>&1; then pass "hdiutil verify $(basename "$DMG")"
        else fail "hdiutil verify $(basename "$DMG") (see dmg.txt)"; fi
    else
        fail "hdiutil create $(basename "$DMG") (see dmg.txt)"
    fi
else
    fail "copy of the saver into the disk image folder"
fi
rm -rf "$DMGDIR"

if [ "$install" -eq 1 ]; then
    echo "== Install" | tee -a "$CHECKS"
    mkdir -p "$HOME/Library/Screen Savers"
    rm -rf "$INSTALLED"
    if ditto "$SAVER" "$INSTALLED"; then pass "installed to $INSTALLED"
    else fail "copy to $INSTALLED"; fi
    # A running legacyScreenSaver keeps the old bundle loaded.
    killall legacyScreenSaver 2>/dev/null || true
    # Warm-up: Gatekeeper/XProtect check freshly written libraries the first time they
    # load, which made the first start after an install slow. Load the installed bundle
    # (not $SAVER: the checks are per file) and the libraries the renderer imports lazily,
    # so that cost is paid here. Every module must come from inside the installed bundle,
    # or this warmed the venv's copies instead.
    PYTHONDONTWRITEBYTECODE=1 "$VENV/bin/python" -I -B -c '
import signal, sys, time
signal.alarm(120)
t0 = time.time()
from Foundation import NSBundle
b = NSBundle.bundleWithPath_(sys.argv[1])
ok, err = b.loadAndReturnError_(None)
if not ok or b.principalClass() is None:
    sys.exit("bundle did not load: %s" % err)
import numpy, pygame, moderngl, glcontext
from digital_rain import gl_renderer
outside = [m.__name__ for m in (numpy, pygame, moderngl, glcontext, gl_renderer)
           if not m.__file__.startswith(sys.argv[1])]
if outside:
    sys.exit("loaded from outside the bundle: %s" % ", ".join(outside))
print("warm-up %.1f s" % (time.time() - t0))
' "$INSTALLED" > "$OUT/warm-up.txt" 2>&1
    wrc=$?
    if [ "$wrc" -eq 0 ]; then pass "$(tail -1 "$OUT/warm-up.txt")"
    else warn "warm-up (exit $wrc): $(tail -1 "$OUT/warm-up.txt")"; fi
fi

echo
echo "$fails checks failed. Bundle: $SAVER"
echo "Results in $OUT"
[ "$fails" -eq 0 ]
