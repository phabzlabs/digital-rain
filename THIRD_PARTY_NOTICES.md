# Third-party notices

## Original project

This project began as a fork of madkoding's matrix-screensaver
(<https://github.com/madkoding/matrix-screensaver>), Copyright (C) 2026 madkoding, released
under the GPL-3.0. Parts of that code remain (notably `digital_rain/fsr.py` and `digital_rain/easter_egg.py`), so the
whole is distributed under the GPL-3.0 with madkoding's copyright notice kept.

## AMD FidelityFX Super Resolution 1.0

`digital_rain/fsr.py` is a GLSL port of the EASU and RCAS passes from AMD's FidelityFX Super
Resolution 1.0 (`ffx_fsr1.h` / `ffx_a.h`, v1.20210629), available at
<https://github.com/GPUOpen-Effects/FidelityFX-FSR> under the MIT licence.

```
FidelityFX Super Resolution Sample

Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files(the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions :
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

Changes made in the port: scalar 32-bit path only; `textureGather` is replaced
by `texelFetch` so it runs on OpenGL 3.3; clamp-to-edge is done by hand; small
epsilons guard divisions by zero in RCAS; an optional dither is added at the end.

## Rezmason matrix assets

The Matrix Code font (`assets/rezmason/Matrix-Code.ttf`) and the glyph atlases
`resurrections_msdf.png`, `resurrections_glint_msdf.png`, `matrixcode_msdf.png`, `megacity_msdf.png`,
`Matrix-Resurrected.ttf` and `glyph-order.txt` come from Rezmason's
`matrix` project (https://github.com/Rezmason/matrix) and are used at run time by the
`film_1999`, `reloaded` and `resurrections` looks. They are distributed under the MIT
License, Copyright (c) 2018 Rezmason. The full licence text is in
[`assets/rezmason/LICENSE`](assets/rezmason/LICENSE), which ships in the `.scr` bundle
next to the assets (build.ps1 bundles `assets\rezmason`). Sources and commit are listed in
[`assets/README.md`](assets/README.md).

## Depth Anything V2 Small (Core ML)

`assets/models/DepthAnythingV2SmallF16.mlpackage` is Apple's Core ML conversion of Depth Anything V2
Small (Yang et al., 2024), used on macOS to estimate the depth of background pictures in grid mode.
The Small model is released under the Apache License 2.0 (the larger Depth Anything V2 models are not,
and are not used here). Apache-2.0 is compatible with distributing this project under the GPL-3.0.

Source: https://huggingface.co/apple/coreml-depth-anything-v2-small

## Depth Anything V2 Small (ONNX)

`assets/models/depth_anything_v2_small_q.onnx` is the quantised ONNX export of Depth Anything V2 Small
(`onnx/model_quantized.onnx`, SHA-256 `fcf51f1b230362b28690bb9d1809bf0431f29cad20534e3f589bd7285547f20d`),
used on Windows to estimate the depth of background pictures in grid mode. Apache License 2.0.

Source: https://huggingface.co/onnx-community/depth-anything-v2-small

## Libraries bundled in the `.scr`

The released `.scr` is a PyInstaller bundle. It includes these third-party
components, each under its own licence (see each project for the full text):

| Component | Licence |
|---|---|
| Python (CPython) | PSF License |
| pygame-ce and SDL2 | LGPL-2.1 (pygame-ce), zlib (SDL2) |
| NumPy | BSD-3-Clause |
| psutil | BSD-3-Clause |
| moderngl and glcontext | MIT |
| ONNX Runtime | MIT |
| protobuf | BSD-3-Clause |
| FlatBuffers | Apache-2.0 |
| Tcl/Tk (settings window) | Tcl/Tk license (BSD-style) |
| PyInstaller bootloader | GPL-2.0-or-later with a bootloader exception |

All of them are compatible with distributing this project under the GPL-3.0.
The complete source code of this project is in this repository.

## Film stills

The reference frames from the Matrix films used while tuning the look are not distributed with
this project. They stay in a local, gitignored folder (`assets/reference/`). *The Matrix* is a
trademark and copyright of Warner Bros. Entertainment Inc.; this project is Matrix-inspired and unofficial.

## Glyph artwork

Rezmason's MIT licence covers Rezmason's project. The glyph shapes themselves were recovered from
film and promotional material owned by Warner Bros. Entertainment Inc., and the MIT licence does
not settle who owns that artwork. This project relies on Rezmason's licence for those files and
claims nothing further.

## Documentation photo

`docs/picture.png` is a screenshot of the saver forming "Cat portrait" by Anton Petrov out of rain glyphs. The photo is released under CC0 on Wikimedia Commons (https://commons.wikimedia.org/wiki/File:Cat_portrait_(Unsplash).jpg). The photo itself is not distributed in this repository.
