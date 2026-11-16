"""Depth estimation through Core ML (macOS only): Apple's Depth Anything V2 Small, in process.

The model is a folder: DepthAnythingV2SmallF16.mlmodelc (compiled at build time, see
tools/build/build_mac.sh) or the .mlpackage next to it (compiled on first use into a temporary
folder). Loading takes several seconds the first time (the Neural Engine compiles it), a
prediction about 25 ms, so use it from a background thread only. Everything imports lazily:
without pyobjc Core ML or the model, available() is False and the caller falls back.
"""

import os

import numpy as np

from digital_rain import resources

MODEL_DIRS = ("DepthAnythingV2SmallF16.mlmodelc", "DepthAnythingV2SmallF16.mlpackage")
INPUT_SIZE = (518, 392)  # the model's fixed input, width and height
ENV = "MATRIX_COREML_MODEL"

_model = None


def model_path():
    """The compiled or source model folder, or None."""
    candidates = [os.environ.get(ENV)]
    candidates += [resources.asset_path("models", name) for name in MODEL_DIRS]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return None


def available():
    """True when Core ML can run here: pyobjc's CoreML and Quartz bindings and the model."""
    if model_path() is None:
        return False
    try:
        import CoreML  # noqa: F401
        from Quartz import CoreVideo  # noqa: F401
    except ImportError:
        return False
    return True


def _load():
    global _model
    if _model is not None:
        return _model
    import CoreML
    from Foundation import NSURL

    path = model_path()
    url = NSURL.fileURLWithPath_(path)
    if path.endswith(".mlpackage"):
        url, error = CoreML.MLModel.compileModelAtURL_error_(url, None)
        if url is None:
            raise OSError("Core ML could not compile the depth model: %s" % error)
    config = CoreML.MLModelConfiguration.alloc().init()
    config.setComputeUnits_(CoreML.MLComputeUnitsAll)
    model, error = CoreML.MLModel.modelWithContentsOfURL_configuration_error_(url, config, None)
    if model is None:
        raise OSError("Core ML could not load the depth model: %s" % error)
    _model = model
    return model


def _pixel_buffer(bgra):
    from Quartz import CoreVideo

    height, width = bgra.shape[:2]
    status, buffer = CoreVideo.CVPixelBufferCreate(
        None, width, height, CoreVideo.kCVPixelFormatType_32BGRA, None, None
    )
    if status != 0:
        raise OSError("CVPixelBufferCreate failed: %d" % status)
    CoreVideo.CVPixelBufferLockBaseAddress(buffer, 0)
    try:
        stride = CoreVideo.CVPixelBufferGetBytesPerRow(buffer)
        target = np.frombuffer(
            CoreVideo.CVPixelBufferGetBaseAddress(buffer).as_buffer(stride * height), np.uint8
        ).reshape(height, stride)
        target[:, : width * 4] = bgra.reshape(height, width * 4)
    finally:
        CoreVideo.CVPixelBufferUnlockBaseAddress(buffer, 0)
    return buffer


def predict(rgb):
    """Relative disparity (larger is nearer) of an RGB uint8 picture as float32, at the model's
    own size (INPUT_SIZE, height by width). Raises OSError or ImportError when Core ML fails."""
    import CoreML
    from Quartz import CoreVideo

    from digital_rain import surfaces  # the shared resampler

    width, height = INPUT_SIZE
    small = surfaces._resize(rgb.astype(np.float32), height, width)
    bgra = np.empty((height, width, 4), np.uint8)
    bgra[..., 0] = np.clip(small[..., 2], 0, 255)
    bgra[..., 1] = np.clip(small[..., 1], 0, 255)
    bgra[..., 2] = np.clip(small[..., 0], 0, 255)
    bgra[..., 3] = 255
    model = _load()
    feature = CoreML.MLFeatureValue.featureValueWithPixelBuffer_(_pixel_buffer(bgra))
    provider, error = CoreML.MLDictionaryFeatureProvider.alloc().initWithDictionary_error_(
        {"image": feature}, None
    )
    if provider is None:
        raise OSError("Core ML input failed: %s" % error)
    out, error = model.predictionFromFeatures_error_(provider, None)
    if out is None:
        raise OSError("Core ML prediction failed: %s" % error)
    buffer = out.featureValueForName_("depth").imageBufferValue()
    rows = CoreVideo.CVPixelBufferGetHeight(buffer)
    cols = CoreVideo.CVPixelBufferGetWidth(buffer)
    CoreVideo.CVPixelBufferLockBaseAddress(buffer, 1)
    try:
        stride = CoreVideo.CVPixelBufferGetBytesPerRow(buffer)
        raw = np.frombuffer(
            CoreVideo.CVPixelBufferGetBaseAddress(buffer).as_buffer(stride * rows), np.uint8
        ).reshape(rows, stride)
        depth = raw[:, : cols * 2].copy().view(np.float16).astype(np.float32)
    finally:
        CoreVideo.CVPixelBufferUnlockBaseAddress(buffer, 1)
    return depth
