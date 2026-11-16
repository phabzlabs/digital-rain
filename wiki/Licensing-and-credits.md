# Licensing and credits

Digital Rain's licence, and the third-party code and assets it uses. This page is a summary. The authoritative text is in the repository: `LICENSE`, `THIRD_PARTY_NOTICES.md` and `assets/README.md`. Where this page and those files differ, the files win.

## Project licence

Digital Rain is free software under the GNU General Public License version 3.0 (GPL-3.0). You can use, study, share and modify it, and you can redistribute modified versions under the same licence. The README's copyright line reads "Copyright (C) 2026 madkoding and phabzlabs contributors". The complete source code is in the repository, and the `.scr` is built from it ([[Build-and-release]]).

## The original project

Digital Rain began as a fork of madkoding's matrix-screensaver (https://github.com/madkoding/matrix-screensaver), a Windows screensaver released under the GPL-3.0. Parts of that code remain, notably `digital_rain/fsr.py` and `digital_rain/easter_egg.py`. The whole project is therefore distributed under the GPL-3.0, and madkoding's copyright notice stays.

## Third-party code and assets

| Component | What it is used for | Licence |
|---|---|---|
| Rezmason's matrix project | The Matrix Code font, the glyph atlases and the Resurrections glyphs, used at run time by the three film looks | MIT, Copyright (c) 2018 Rezmason |
| AMD FidelityFX Super Resolution 1.0 | The GLSL port in `digital_rain/fsr.py` of the EASU and RCAS passes, for optional upscaling | MIT, Copyright (c) 2021 Advanced Micro Devices, Inc. |
| Depth Anything V2 Small (Core ML conversion by Apple) | macOS only: depth estimate of background pictures in the In the rain mode | Apache-2.0 |
| Depth Anything V2 Small (quantised ONNX, onnx-community) | Windows only: depth estimate of background pictures in the In the rain mode | Apache-2.0 |
| ONNX Runtime | Windows only: runs the ONNX depth model | MIT |
| Python (CPython) | The interpreter inside the `.scr` | PSF License |
| pygame-ce and SDL2 | Window, input and CPU drawing | LGPL-2.1 for pygame-ce, zlib for SDL2 |
| NumPy | Array maths | BSD-3-Clause |
| psutil | CPU and battery readings | BSD-3-Clause |
| moderngl and glcontext | OpenGL access | MIT |
| Tcl/Tk | The settings window | Tcl/Tk licence (BSD-style) |
| PyInstaller bootloader | Starts the bundled program | GPL-2.0-or-later with a bootloader exception |

All of these are compatible with distribution of the project under the GPL-3.0, as `THIRD_PARTY_NOTICES.md` states. The bundled libraries keep their own licences, and each project has the full text.

### Rezmason

The Matrix Code font (`assets/rezmason/Matrix-Code.ttf`) and the atlases `resurrections_msdf.png` and `resurrections_glint_msdf.png` come from https://github.com/Rezmason/matrix. `build.ps1` bundles the `assets\rezmason` folder, so Rezmason's licence file `assets/rezmason/LICENSE` ships in the `.scr` next to the assets. All Rezmason files are pinned to one commit, recorded with each file's source in `assets/README.md`. The research behind the looks also relied on Rezmason's reconstruction of the rain's parameters ([[Film-research]]).

Rezmason's MIT licence covers Rezmason's project. The glyph shapes were recovered from film and promotional material owned by Warner Bros. Entertainment Inc., and the MIT licence does not settle who owns that artwork. This project relies on Rezmason's licence for those files and claims nothing further.

### AMD FSR

`digital_rain/fsr.py` is a GLSL port of the EASU and RCAS passes of FidelityFX Super Resolution 1.0 (`ffx_fsr1.h` and `ffx_a.h`, version 1.20210629), from https://github.com/GPUOpen-Effects/FidelityFX-FSR. The port uses the scalar 32-bit path only and replaces `textureGather` with `texelFetch` so it runs on OpenGL 3.3. It clamps to the edge by hand, guards divisions by zero in RCAS with small epsilons and adds an optional dither at the end. The full AMD licence text is in `THIRD_PARTY_NOTICES.md`.

### Depth Anything V2 Small

`assets/models/DepthAnythingV2SmallF16.mlpackage` is Apple's Core ML conversion of Depth Anything V2 Small (Yang et al., 2024), from https://huggingface.co/apple/coreml-depth-anything-v2-small. The Small model is released under Apache-2.0. The larger Depth Anything V2 models are not, and the project does not use them. Apache-2.0 is compatible with distributing this project under the GPL-3.0.

`assets/models/depth_anything_v2_small_q.onnx` is the quantised ONNX export of the same Small model from onnx-community (https://huggingface.co/onnx-community/depth-anything-v2-small). The Windows build runs it with ONNX Runtime, which is under the MIT licence. `build.ps1` bundles both. The licence texts are in `THIRD_PARTY_NOTICES.md`.

## Fonts and film stills

The build bundles the film's code font because Rezmason's project releases it under the MIT licence. It bundles no operating system font. If the saver cannot load the film font, it falls back to MS Gothic and Courier New Bold. Windows ships those fonts, and the saver reads them from the user's machine. The settings window also lets you pick any TTF or OTF you already have.

The project does not distribute the reference frames from the Matrix films that it used to measure and tune the looks. They are third-party material in a local folder that git ignores. The same applies to the fan GIFs used in the research. The repository records only where each one came from.

## Trademark and affiliation

*The Matrix*, its films and its digital rain are the property of Warner Bros. Entertainment Inc. Digital Rain is a Matrix-inspired fan project. It is not affiliated with, endorsed by or sponsored by Warner Bros.

## Credits

- madkoding, for the original Windows screensaver this project grew out of.
- Rezmason, for the glyph atlases and the font, and for the open-source recreation of the rain that the research used.
- Carl Newton, for the frame-by-frame analysis of the 1999 opening that the research used. Nothing from that study is bundled.
- Advanced Micro Devices, for FidelityFX Super Resolution 1.0.
- Apple, onnx-community and the Depth Anything V2 authors, for the Core ML and ONNX depth models.
