"""Fill the surface-detection cache for a folder of pictures (see digital_rain/surfaces.py).

Needs onnxruntime and Pillow, which the saver's own Python may have no wheel for, so run it
from any other Python (3.12 or 3.13):

    python tools/dev/surface_cache.py PICTURE_FOLDER [--model depth_anything_v2_small_q.onnx]

The model is onnx-community/depth-anything-v2-small, onnx/model_quantized.onnx (27 MB,
Apache 2.0). Without --model it is looked for as MATRIX_DEPTH_MODEL or in the cache folder.
The saver reads the cache with numpy alone; pictures with no entry keep the older drawing.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from digital_rain import surfaces  # noqa: E402

EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def load_rgb(path, max_size):
    from PIL import Image

    with Image.open(path) as picture:
        picture.thumbnail((max_size, max_size))
        return np.asarray(picture.convert("RGB"), np.uint8)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder")
    parser.add_argument("--model")
    parser.add_argument("--force", action="store_true", help="redo pictures already cached")
    args = parser.parse_args()
    model = args.model or surfaces.model_path()
    if not model:
        sys.exit("no model: pass --model or set %s" % surfaces.MODEL_ENV)
    print("cache folder:", surfaces.cache_dir())
    for name in sorted(os.listdir(args.folder)):
        path = os.path.join(args.folder, name)
        if not name.lower().endswith(EXTENSIONS):
            continue
        if not args.force and os.path.isfile(surfaces.cache_path(path)):
            print("cached   ", name)
            continue
        surfaces._store(path, surfaces.estimate_disparity(load_rgb(path, 1024), model))
        found = surfaces.detect(surfaces._load_cached(path))
        kinds = ", ".join(surfaces.KIND_NAMES[p.kind] for p in found.planes)
        print("analysed ", name, "|", kinds, "| vanishing", found.vanishing)


main()
