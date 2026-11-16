#!/bin/bash
# Test set for the Mac saver view, run from Terminal without a .saver bundle.
#   bash tools/dev/mac_host.sh [OUT_DIR]
# Builds a venv in ~/.matrix-rain-venv the first time (python.org Python 3.15
# or 3.14), then runs tools/dev/mac_host.py in each mode and writes PNGs, the
# saver log, a report and the terminal output to OUT_DIR (default:
# mac-host-results in the checkout). PYTHON=/path/to/python3.x picks the
# interpreter; delete ~/.matrix-rain-venv to rebuild it.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$HOME/.matrix-rain-venv"
OUT="${1:-$ROOT/mac-host-results}"

if [ ! -x "$VENV/bin/python" ]; then
    PY="${PYTHON:-}"
    if [ -z "$PY" ]; then
        for v in 3.15 3.14; do
            c="/Library/Frameworks/Python.framework/Versions/$v/bin/python$v"
            if [ -x "$c" ]; then PY="$c"; break; fi
        done
    fi
    if [ -z "$PY" ]; then
        echo "No python.org Python 3.15 or 3.14 found (https://www.python.org/downloads/macos/)."
        exit 1
    fi
    echo "Creating $VENV with $PY"
    "$PY" -m venv "$VENV" || exit 1
    "$VENV/bin/pip" install --disable-pip-version-check --upgrade pip || exit 1
    "$VENV/bin/pip" install --disable-pip-version-check -r "$ROOT/requirements/requirements-mac.txt" || exit 1
fi

rm -rf "$OUT"
mkdir -p "$OUT"
"$VENV/bin/pip" freeze > "$OUT/versions.txt"
sw_vers > "$OUT/macos.txt"
cd "$ROOT"
fails=0
run() {
    echo "== mac_host.py $*" | tee -a "$OUT/host-output.txt"
    "$VENV/bin/python" tools/dev/mac_host.py --out "$OUT" "$@" 2>&1 | tee -a "$OUT/host-output.txt"
    rc=${PIPESTATUS[0]}
    echo "exit code $rc" | tee -a "$OUT/host-output.txt"
    [ "$rc" -eq 0 ] || fails=$((fails + 1))
}
run --mode window --seconds 10
run --mode window --seconds 8 --preset film_1999
run --mode window --seconds 8 --preset reloaded
run --mode window --seconds 8 --preset resurrections
run --mode preview --seconds 6 --sheet
run --mode fullscreen --seconds 8
run --mode covered --seconds 8
echo
echo "$fails of 7 runs failed. Results in $OUT"
