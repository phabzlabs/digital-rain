"""Compile the Core ML depth model for the macOS bundle.

Usage: tools/build/compile_coreml.py SRC.mlpackage OUT_DIR.

Core ML compiles a .mlpackage on first use into a temporary folder, which a sandboxed screen
saver may not be allowed to write; so the build compiles it once and ships the .mlmodelc.
Run with the build venv's Python (needs pyobjc-framework-CoreML).
"""

import os
import shutil
import sys

import CoreML
from Foundation import NSURL


def main():
    source, out_dir = sys.argv[1], sys.argv[2]
    url = NSURL.fileURLWithPath_(os.path.abspath(source))
    compiled, error = CoreML.MLModel.compileModelAtURL_error_(url, None)
    if compiled is None:
        sys.exit("compile failed: %s" % error)
    target = os.path.join(out_dir, os.path.basename(source).replace(".mlpackage", ".mlmodelc"))
    os.makedirs(out_dir, exist_ok=True)
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(compiled.path(), target)
    print("compiled", target)


main()
