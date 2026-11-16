"""GPU renderer: the whole rain is computed procedurally in a fragment shader.

Pipeline per frame
    scene   -> RGBA8 texture covering the virtual desktop (rain layers + text)
    bloom   -> 1/4 and 1/16 resolution blurs of the scene
    final   -> scene + bloom, vignette, flicker and animated interlaced
               scanlines, straight to the window

Film presets (looks.py) draw a sawtooth brightness into the scene (R) and a leader flag (G),
and the final pass tone-maps scene + bloom through the film's colour palette. `custom` keeps
the original one-drop-per-column model.
"""

import math

import moderngl
import numpy as np
import pygame

from digital_rain import glyphs, image_layer, live_load, looks, rain_message
from digital_rain.easter_egg import EasterEgg
from digital_rain.fsr import FSR
from digital_rain.resources import shader
from digital_rain.settings import (
    CELL_H,
    CELL_W,
    OVERRIDE_KEYS,
    TRAIL_LEN_ROWS,
    UPSCALE_RATIO,
    active_layers,
    main_layer_index,
    monitor_cfg,
)

MAX_MON = 8
MSG_HOLD = 0.95  # brightness a letter cell holds once the first stream lands on it
# pale cursor tint of a latched letter (the leader channel; the film presets amplify it)
MSG_WHITE = 0.3
MAX_LAYERS = 8
# Atlas cell = glyph area (80x112, the 20:28 grid-cell aspect) + 8 px margin.
ATLAS_CELL = (96, 128)
ATLAS_MARGIN = (8, 8)
ATLAS_COLUMNS = 10
ATLAS_ANISOTROPY = 4.0
PALETTE_STOPS = 8
# Ink dots of a look with none: pitch, strength 0 (off), x share.
NO_INK_DOTS = (2.0, 0.0, 0.0)
# The bloom pyramid levels, as shifts of the render size (1/2 to 1/16).
PYRAMID_LEVELS = (1, 2, 3, 4)
# Texture units. The scene pass reads the atlases, the message mask and both pictures with
# their depth fields; the final pass reads the scene, the bloom levels and the pyramid.
UNIT_ATLAS, UNIT_BLOOM_NEAR, UNIT_BLOOM_FAR = 0, 1, 2
UNIT_MESSAGE, UNIT_ATLAS_RESURRECTIONS, UNIT_ATLAS_FILL = 3, 4, 5
UNIT_PICTURE0, UNIT_PICTURE1, UNIT_FIELD0, UNIT_FIELD1 = 6, 7, 8, 9
UNIT_SURFACE0, UNIT_SURFACE1 = 10, 11  # surface label maps of the two pictures (grid mode)
UNIT_REVEAL = 12  # the reveal cache: the picture's reveal per main-layer cell, this frame
UNIT_PYRAMID = 3
# Units of the two pictures when the final or FSR post pass draws them (debug switch only).
FINAL_PICTURE_UNITS = (7, 8)
POST_PICTURE_UNITS = (2, 3)

COMMON_GLSL = shader("common.glsl")

FULLSCREEN_VS = shader("fullscreen.vert")
HDR_FS = shader("hdr.frag")

SCENE_PARAMS = dict(
    MAX_MON=MAX_MON,
    MAX_LAYERS=MAX_LAYERS,
    CELL_W=CELL_W,
    CELL_H=CELL_H,
    TRAIL_MIN=TRAIL_LEN_ROWS[0],
    TRAIL_MAX=TRAIL_LEN_ROWS[1],
    MSG_WHITE=MSG_WHITE,
    COMMON=COMMON_GLSL,
)
# The scene program (rain, particles, classic picture glyphs, reveal cache) and the grid picture
# passes, compiled apart (STAGE in scene.frag) and drawn one over the other with a screen blend.
SCENE_FS = shader("scene.frag", STAGE=1, **SCENE_PARAMS)
SCENE_PIC_FS = shader("scene.frag", STAGE=2, **SCENE_PARAMS)

DOWN_FS = shader("down.frag")

BLUR_FS = shader("blur.frag")

# Film grain on the ink about the palette floor, shared by the final and FSR post passes.
INK_GRAIN = shader("ink_grain.glsl")

IMG_GLSL = shader("image_layer.glsl", MAX_MON=MAX_MON)

FINAL_FS = shader(
    "final.frag", MAX_MON=MAX_MON, COMMON=COMMON_GLSL, INK_GRAIN=INK_GRAIN, IMG_GLSL=IMG_GLSL
)

# With FSR the frame is composed at render resolution, upscaled, and only then gets the
# scanlines and flicker, so they stay one real pixel row thick. That finish runs inside
# FSR's sharpening pass.
FSR_POST = shader(
    "scan_post.glsl", MAX_MON=MAX_MON, COMMON=COMMON_GLSL, INK_GRAIN=INK_GRAIN, IMG_GLSL=IMG_GLSL
)

OVERLAY_VS = shader("overlay.vert")

OVERLAY_FS = shader("overlay.frag")

DIRECTION_MODES = {"down": 0, "sideways": 1, "diagonal": 2}


def looks_dir(name):
    return DIRECTION_MODES.get(name, 0)


# Grid mode with a picture folder renders at quality upscaling or coarser on displays this wide
# (px) or wider, whatever the upscaling setting (see GLRenderer._choose_resolution).
GRID_UPSCALE_WIDTH = 2000


def grid_upscaled(cfg, width):
    """True when grid mode forces quality upscaling at this canvas width (px)."""
    return (
        cfg.get("image_mode", "classic") == "grid"
        and bool(cfg.get("image_dir"))
        and width >= GRID_UPSCALE_WIDTH
    )


def blob(array, dtype="f4"):
    """Raw bytes of an array, as written to a uniform array."""
    return np.ascontiguousarray(array, dtype=dtype).tobytes()


def floats(values):
    return tuple(float(v) for v in values)


def palette_array(palette):
    """The look palette as the (stops, rgb + position) array the shaders read."""
    stops = np.zeros((PALETTE_STOPS, 4), "f4")
    for j, (position, rgb) in enumerate(palette[:PALETTE_STOPS]):
        stops[j] = (*rgb, position)
    return stops


class Uniforms:
    """Sets the uniforms of one program, or of several that share them (the two scene
    programs). Names the compiler optimised away are ignored, and each handle is looked up
    once. A bytes value is written to a uniform array."""

    def __init__(self, *programs):
        self._handles = [{name: program[name] for name in program} for program in programs]

    def set(self, name, value):
        for handles in self._handles:
            handle = handles.get(name)
            if handle is None:
                continue
            if isinstance(value, bytes):
                handle.write(value)
            else:
                handle.value = value

    def apply(self, values):
        """Set every uniform in a {name: value} dict."""
        for name, value in values.items():
            self.set(name, value)


class GLRenderer:
    name = "gpu"

    def __init__(self, mons, cfg, origin, size, run=None, hdr=None):
        # hdr: None (SDR), or osapi.hdr_info() when the caller built a float16 back buffer.
        self.hdr = hdr
        self.cfg = cfg
        self.mons = mons[:MAX_MON]
        self.size = size
        self.ctx = moderngl.create_context()
        self.ctx.disable(moderngl.DEPTH_TEST)
        self._gl_objects = []  # everything to release on close
        self.rng = np.random.default_rng()
        # Per-run layout value: production draws a nonzero one, checks pass 0 for the fixed layout.
        self.run = int(self.rng.integers(1, 2**32)) if run is None else int(run) & 0xFFFFFFFF
        self._choose_looks()
        self._choose_resolution()
        self._build_atlases()
        self._build_programs()
        self._build_targets()
        self.images = None
        self._build_image_layer()
        self._init_static_uniforms()
        self._init_scissors()
        self._build_reveal_cache()
        # grid mode draws its picture passes as a second scene program (film looks, rain down)
        self.grid_passes = self.cfg.get("image_mode", "classic") == "grid" and any(
            look["film"] and look["direction"] == "down" for look in self.looks
        )
        self.egg = EasterEgg(cfg["easter_egg"] and cfg["message"] == "off")
        self.text_cache = {}
        self.rain_off = 0.0
        self.latch = rain_message.MessageLatch()
        self.msg_tex = self.ctx.texture((1, 1), 1, bytes(1))
        self.msg_boxes = None
        self.msg = rain_message.MessageSchedule(cfg)
        self.live = live_load.LiveControl(cfg)

    def _own(self, gl_object):
        """Remember a GL object so close() can release it."""
        self._gl_objects.append(gl_object)
        return gl_object

    def _choose_looks(self):
        """Per-monitor effective settings, looks and layers. Monitor 0 also drives the easter
        egg and the non-split path."""
        cfg = self.cfg
        self.mon_cfgs = [monitor_cfg(cfg, m.get("id", "")) for m in self.mons]
        self.looks = [looks.resolve(c) for c in self.mon_cfgs]
        self.mon_layers = [
            active_layers(c, lk, slices=True)[:MAX_LAYERS]
            for c, lk in zip(self.mon_cfgs, self.looks, strict=True)
        ]
        self.look = self.looks[0]
        self.base = tuple(c / 255 for c in self.look["base"])
        self.head = tuple(c / 255 for c in self.look["head"])
        # Monitors that differ in any overridable key are drawn one scissored rectangle at a
        # time; otherwise one full-screen draw.
        first = tuple(self.mon_cfgs[0][k] for k in OVERRIDE_KEYS)
        self.split = any(tuple(c[k] for k in OVERRIDE_KEYS) != first for c in self.mon_cfgs[1:])

    def _choose_resolution(self):
        """AMD FSR: render at 1/ratio of the resolution per axis, then upscale. Skipped in the
        tiny preview window where it would only blur. Grid mode on a large display renders at
        least at quality: its picture passes cost about twice the plain rain per pixel, and at
        full resolution there they hold the frame rate near 20 fps."""
        vw, vh = self.size
        ratio = UPSCALE_RATIO[self.cfg["upscaling"]] if vw >= 1000 else 1.0
        if grid_upscaled(self.cfg, vw):
            ratio = max(ratio, UPSCALE_RATIO["quality"])
        self.upscale_ratio = ratio
        self.k = 1.0 / ratio
        self.rsize = (max(2, int(round(vw / ratio))), max(2, int(round(vh / ratio))))

    def _build_atlases(self):
        self.atlas, self.atlas_info = self._build_atlas()
        self.atlas2 = self.atlas2_info = None
        if any(lk["glyph_set"] != "classic" for lk in self.looks):
            self.atlas2, self.atlas2_info = self._build_atlas2()
            if self.atlas2 is None:  # PNGs missing: those looks use the classic set
                for lk in self.looks:
                    lk["glyph_set"] = "classic"
            elif self.looks[0]["glyph_set"] != "classic":
                # reported on the saver's stdout line
                self.glyph_source = "resurrections"
        # classic tiles with the ink stretched, for looks that set ink_fill
        self.atlas_fill = self.atlas_fill_info = None
        fills = {
            tuple(lk["ink_fill"])
            for lk in self.looks
            if lk.get("ink_fill") is not None and lk["glyph_set"] == "classic"
        }
        if len(fills) > 1:
            raise ValueError("looks with different ink_fill values: %s" % sorted(fills))
        if fills:
            self.atlas_fill, self.atlas_fill_info = self._build_atlas(fills.pop())

    def _build_programs(self):
        ctx = self.ctx
        self.fsr = self._own(FSR(ctx, FSR_POST)) if self.upscale_ratio > 1.0 else None
        sources = {
            "scene": (FULLSCREEN_VS, SCENE_FS),
            "scene_pic": (FULLSCREEN_VS, SCENE_PIC_FS),
            "down": (FULLSCREEN_VS, DOWN_FS),
            "blur": (FULLSCREEN_VS, BLUR_FS),
            "final": (FULLSCREEN_VS, FINAL_FS),
            "over": (OVERLAY_VS, OVERLAY_FS),
        }
        if self.hdr:
            sources["hdr"] = (FULLSCREEN_VS, HDR_FS)
        self.vao = {}
        self.uniforms = {}
        for key, (vertex, fragment) in sources.items():
            program = self._own(ctx.program(vertex_shader=vertex, fragment_shader=fragment))
            self.vao[key] = self._own(ctx.vertex_array(program, []))
            self.uniforms[key] = Uniforms(program)
        # one set of scene uniforms for both scene programs
        self.uniforms["scene"] = Uniforms(self.vao["scene"].program, self.vao["scene_pic"].program)
        del self.uniforms["scene_pic"]
        if self.fsr:
            # the finishing code lives in FSR's sharpening program
            self.uniforms["post"] = Uniforms(self.fsr.rcas)

    def _target(self, width, height, dtype="f1"):
        """A render target: (texture, framebuffer)."""
        tex = self._own(self.ctx.texture((max(1, width), max(1, height)), 4, dtype=dtype))
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        return tex, self._own(self.ctx.framebuffer(color_attachments=[tex]))

    def _build_targets(self):
        vw, vh = self.size
        rw, rh = self.rsize
        target = self._target
        self.scene_tex, self.scene_fbo = target(rw, rh)
        self.q = [
            target(rw // 4, rh // 4),
            target(rw // 4, rh // 4),
            target(rw // 16, rh // 16),
            target(rw // 16, rh // 16),
        ]
        # Bloom pyramid: level and blur scratch at 1/2 .. 1/16 of the render size, floor of
        # each axis and at least 1 px.
        self.pyr = None
        if any(look["pyramid"] for look in self.looks):
            self.pyr = [
                (target(rw >> lv, rh >> lv), target(rw >> lv, rh >> lv)) for lv in PYRAMID_LEVELS
            ]
        self.legacy_bloom = any(not look["pyramid"] for look in self.looks)
        if self.fsr:
            # composed frame, render res
            self.post_tex, self.post_fbo = target(rw, rh)
        # display-referred frame at display size, then converted to linear HDR
        if self.hdr:
            self.hdr_tex, self.hdr_fbo = target(vw, vh, "f2")

    def _build_image_layer(self):
        folder = image_layer.folder(self.cfg)
        if not (
            folder and self.look["film"] and self.look["direction"] == "down" and not self.split
        ):
            return
        try:
            self.images = image_layer.ImageLayer(self.ctx, folder, cfg=self.cfg)
        # a bad image folder must never stop the saver
        except (OSError, ValueError) as exc:
            print("image layer off:", exc)
            return
        # the depth field keeps its far glyphs at least detail_min_px thick on the smallest
        # rain cell
        self.images.cell_px = min(self.rain_grid(i)[4] * self.k for i in range(len(self.mons)))

    def _init_scissors(self):
        rw, rh = self.rsize
        qw, qh = self.q[0][0].size
        self.rects_r = self._scissor_rects(self.k, self.k, rh)
        self.rects_q = self._scissor_rects(self.k * qw / rw, self.k * qh / rh, qh)
        self.rects_d = self._scissor_rects(1.0, 1.0, self.size[1])

    def _atlas_texture(self, size, components, data):
        """A mipmapped glyph atlas texture."""
        tex = self._own(self.ctx.texture(size, components, data))
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        tex.build_mipmaps()
        tex.anisotropy = ATLAS_ANISOTROPY
        return tex

    def _build_atlas(self, fill=None):
        """The classic glyph sheet. With `fill` (a look's ink_fill) the ink of every glyph is
        stretched on the inner tile by glyphs.ink_stretch."""
        custom = glyphs.custom_font_path(self.cfg["font_path"])
        pairs, self.glyph_source = glyphs.glyph_set(4.0, custom)
        count = len(pairs)
        gx = ATLAS_COLUMNS
        gy = (count + gx - 1) // gx
        cw, ch = ATLAS_CELL
        sheet = pygame.Surface((gx * cw, gy * ch))
        if fill is not None:
            mx, my = ATLAS_MARGIN
            inner_w, inner_h = cw - 2 * mx, ch - 2 * my
            stretch = glyphs.ink_stretch(pairs, inner_w, inner_h, fill)
        for i, (g, font, fx, fy) in enumerate(pairs):
            if fill is not None:
                sheet.blit(
                    glyphs.render_glyph(g, font, fx, fy, inner_w, inner_h, stretch),
                    ((i % gx) * cw + mx, (i // gx) * ch + my),
                )
            else:
                sheet.blit(
                    glyphs.render_glyph(g, font, fx, fy, cw, ch), ((i % gx) * cw, (i // gx) * ch)
                )
        data = pygame.image.tobytes(sheet, "RGB")
        red = np.frombuffer(data, np.uint8).reshape(-1, 3)[:, 0].copy()
        tex = self._atlas_texture(sheet.get_size(), 1, red.tobytes())
        info = (float(gx), float(gy), ATLAS_MARGIN[0] / cw, ATLAS_MARGIN[1] / ch, count)
        return tex, info

    def _build_atlas2(self):
        """The Resurrections tiles as a second texture (R glyph, G glint), in columns of
        ATLAS_CELL tiles with the glyph in the inner area."""
        res = glyphs.resurrection_set()
        if res is None:
            return None, None
        cov, glint = res
        gx = ATLAS_COLUMNS
        gy = (len(cov) + gx - 1) // gx
        cw, ch = ATLAS_CELL
        mx, my = ATLAS_MARGIN
        sheet = np.zeros((gy * ch, gx * cw, 2), np.uint8)
        for i, (a, b) in enumerate(zip(cov, glint, strict=True)):
            x0, y0 = (i % gx) * cw + mx, (i // gx) * ch + my
            sheet[y0 : y0 + a.shape[0], x0 : x0 + a.shape[1], 0] = a
            sheet[y0 : y0 + b.shape[0], x0 : x0 + b.shape[1], 1] = b
        tex = self._atlas_texture((gx * cw, gy * ch), 2, sheet.tobytes())
        return tex, (float(gx), float(gy), mx / cw, my / ch, len(cov))

    def _monitor_origin(self):
        return min(m["x"] for m in self.mons), min(m["y"] for m in self.mons)

    def _init_static_uniforms(self):
        """Set the uniforms that never change after start-up, and build the per-monitor plans
        (applied every frame in split mode, once otherwise)."""
        self._init_scene_static()
        self._init_final_static()
        self._init_post_static()
        self._init_image_static()
        if self.hdr:
            self._init_hdr_static()
        for key in ("down", "blur"):
            self.uniforms[key].set("u_tex", 0)
        count = len(self.mons)
        self.scene_plans = [self._scene_plan(i) for i in range(count)]
        self.final_plans = [self._final_plan(i) for i in range(count)]
        self.post_plans = [self._post_plan(i) for i in range(count)]
        self.uniforms["scene"].apply(self.scene_plans[0])
        self.uniforms["final"].apply(self.final_plans[0])
        if self.fsr:
            self.uniforms["post"].apply(self.post_plans[0])
        self.bloom_on = any(float(look["bloom"]) > 0 for look in self.looks)

    def _mon_arrays(self):
        """Monitor rectangles and dpi at render resolution (glyphs keep their on-screen size
        after upscaling)."""
        k = self.k
        mons = np.zeros((MAX_MON, 4), "f4")
        dpi = np.ones(MAX_MON, "f4")
        ox, oy = self._monitor_origin()
        for i, m in enumerate(self.mons):
            mons[i] = ((m["x"] - ox) * k, (m["y"] - oy) * k, m["w"] * k, m["h"] * k)
            dpi[i] = m["dpi"] * k
        return mons, dpi

    def _init_scene_static(self):
        rw, rh = self.rsize
        mons, dpi = self._mon_arrays()
        gx, gy, mx, my, _count = self.atlas_info
        s = self.uniforms["scene"]
        s.set("u_res", (float(rw), float(rh)))
        s.set("u_nmon", len(self.mons))
        s.set("u_mon", blob(mons))
        s.set("u_dpi", blob(dpi))
        s.set("u_dirmode", looks_dir(self.look["direction"]))
        s.set("u_run", self.run)
        s.set("u_atlas", UNIT_ATLAS)
        s.set("u_atl", (gx, gy, mx, my))
        s.set("u_atlas2", UNIT_ATLAS_RESURRECTIONS)
        s.set("u_atlas3", UNIT_ATLAS_FILL)
        if self.atlas2_info is not None:
            s.set("u_atl2", self.atlas2_info[:4])
        s.set("u_msg", UNIT_MESSAGE)
        s.set("u_img0", UNIT_PICTURE0)
        s.set("u_img1", UNIT_PICTURE1)
        s.set("u_imgf0", UNIT_FIELD0)
        s.set("u_imgf1", UNIT_FIELD1)
        s.set("u_surf0", UNIT_SURFACE0)
        s.set("u_surf1", UNIT_SURFACE1)
        s.set("u_rev", UNIT_REVEAL)
        s.set("u_rev_pass", 0)
        s.set("u_msg_on", 0)
        # letter cells latch on their own lane's heads; picture glyphs scale by the hold level
        s.set("u_msg_new", 1)
        s.set("u_msg_hold", MSG_HOLD)
        depth_flags = [1 if c["depth"] else 0 for c in self.mon_cfgs] + [0] * MAX_MON
        s.set("u_msg_lay", blob(depth_flags[:MAX_MON], "i4"))

    def _init_final_static(self):
        rw, rh = self.rsize
        mons, _dpi = self._mon_arrays()
        f = self.uniforms["final"]
        f.set("u_res", (float(rw), float(rh)))
        f.set("u_nmon", len(self.mons))
        f.set("u_mon", blob(mons))
        f.set("u_scene", 0)
        f.set("u_bloom1", UNIT_BLOOM_NEAR)
        f.set("u_bloom2", UNIT_BLOOM_FAR)
        for j in range(len(PYRAMID_LEVELS)):
            f.set(f"u_pyr{j + 1}", UNIT_PYRAMID + j)
        self.uniforms["over"].set("u_res", (float(rw), float(rh)))  # render resolution
        # The ink dot pitch follows each monitor's dpi, so the shaders look the monitor up
        # (final.frag by u_mon, scan_post.glsl by display rectangles) rather than take monitor 0's.
        ddpi = np.ones(MAX_MON, "f4")
        for i, m in enumerate(self.mons):
            ddpi[i] = m["dpi"]
        f.set("u_ddpi", blob(ddpi))
        self._ddpi = ddpi

    def _init_post_static(self):
        if not self.fsr:
            return
        s = self.uniforms["post"]
        display_rects = np.zeros((MAX_MON, 4), "f4")
        for i, rect in enumerate(self._scissor_rects(1.0, 1.0, self.size[1])):
            display_rects[i] = rect
        s.set("u_ddpi", blob(self._ddpi))
        s.set("u_drect", blob(display_rects))
        s.set("u_dn", len(self.mons))

    def _init_hdr_static(self):
        h = self.uniforms["hdr"]
        h.set("u_tex", 0)
        h.set("u_white", float(self.hdr["white"]))
        # Windows reports no peak luminance here, so its headroom is capped at 8x SDR white
        # (the dialog help text says so); the Mac supplies its screen's EDR limit.
        headroom = min(
            float(self.cfg["hdr_peak"]) / float(self.hdr["sdr_nits"]),
            float(self.hdr.get("max_headroom", 8.0)),
            8.0,
        )
        h.set("u_headroom", max(1.0, headroom))

    def _init_image_static(self):
        """Image layer uniforms that never change. The final and FSR post passes draw the picture
        itself only for the debug switch; the scene pass draws it as glyphs."""
        for key in self._image_passes():
            self.uniforms[key].set("u_img_on", 0)
        if self.images is None:
            return
        tune = image_layer.TUNING
        ox, oy = self._monitor_origin()
        monitor_rects = np.zeros((MAX_MON, 4), "f4")
        for i, m in enumerate(self.mons):
            monitor_rects[i] = (m["x"] - ox, m["y"] - oy, m["w"], m["h"])
        palette = self.look["palette"]
        cell_w = self.rain_grid(0)[3]
        soften = (0.5 * cell_w * self.k / self.rsize[0], 0.5 * cell_w * self.k / self.rsize[1])
        for key, reveal_unit, (unit0, unit1) in (
            ("final", 0, FINAL_PICTURE_UNITS),
            ("post", 1, POST_PICTURE_UNITS),
        ):
            if key not in self.uniforms:
                continue
            u = self.uniforms[key]
            u.set("u_irect", blob(monitor_rects))
            u.set("u_imon", len(self.mons))
            u.set("u_ipal", blob(palette_array(palette)))
            u.set("u_inpal", len(palette[:PALETTE_STOPS]))
            u.set("u_img_amt", tune.blend_uniform)
            u.set("u_img_soft", soften)
            u.set("u_imgrev", reveal_unit)
            u.set("u_img0", unit0)
            u.set("u_img1", unit1)
        s = self.uniforms["scene"]
        octaves, thinnest = self.images.detail_uniforms()
        s.set("u_img_oct", octaves)
        s.set("u_img_detail", thinnest)
        s.set("u_img_lv", tune.level_uniform)
        s.set("u_img_dim", tune.dim)
        s.set("u_img_surf", tune.surface_uniform)
        s.set("u_img_sdens", tune.density_uniform)
        s.set("u_img_sopen", tune.open_edge_uniform)
        s.set("u_img_depthbias", tune.depth_bias)
        s.set("u_img_orient", tune.orient)
        s.set("u_img_persp", tune.perspective_uniform)
        s.set("u_img_tone", tune.tone)
        s.set("u_img_settle", tune.settle_uniform)
        s.set("u_img_move", tune.move)
        s.set("u_img_fill", tune.fill)
        s.set("u_img_rain", tune.rain)
        s.set("u_img_gfloor", tune.grid_rain)
        s.set("u_img_ggamma", tune.grid_gamma)
        s.set("u_img_gedge", tune.grid_edge)
        s.set("u_img_gridge", tune.grid_ridge)
        s.set("u_img_gscale", (tune.grid_scale * tune.grid_aspect, tune.grid_scale))
        s.set("u_img_gdepth", 1.0 if tune.grid_depth else 0.0)
        for name, size in (
            ("u_img_gs0", tune.grid_near),
            ("u_img_gs1", tune.grid_mid),
            ("u_img_gs2", tune.grid_far),
        ):
            s.set(name, (size * tune.grid_aspect, size))
        s.set(
            "u_img_gcoarse",
            (tune.grid_tone_far, tune.grid_coarse, tune.grid_layer, tune.grid_sil),
        )
        s.set("u_img_gcgamma", tune.grid_cgamma)
        s.set("u_img_gdpow", tune.grid_detail_gamma)
        s.set(
            "u_img_gdet",
            (tune.grid_detail, tune.grid_detail_far, tune.grid_seg, tune.grid_sil_side),
        )
        s.set("u_img_gback", tune.grid_back)
        s.set("u_img_gfw", tune.grid_floor_width)
        s.set("u_img_glane", tune.grid_lane)
        s.set("u_img_gstr", tune.grid_string)
        s.set("u_img_gglow", tune.grid_glow)
        s.set("u_img_gedgep", (tune.grid_outline, tune.grid_outline_min))
        s.set("u_img_gwhite", (tune.grid_white_lanes, tune.grid_white, tune.grid_rain_head))
        s.set("u_img_grain", (tune.grid_subject_rain, tune.grid_subject_rain_gamma,
                              tune.grid_subject_lanes))
        s.set("u_img_gedgecap", tune.grid_outline_cap)
        s.set("u_img_gsgam", tune.grid_string_gamma)
        s.set("u_img_gpar", tune.grid_parallax)
        s.set("u_img_gboost", tune.grid_boost)
        s.set("u_img_gpart", (tune.grid_part, tune.grid_part_level))
        s.set("u_img_wdir", tune.grid_wall_dir)
        s.set("u_img_hold", tune.grid_hold)
        s.set("u_img_grid", 1 if self.cfg.get("image_mode", "classic") == "grid" else 0)
        s.set("u_img_nfill", tune.near_fill_uniform)

    def _build_reveal_cache(self):
        """The reveal cache: one RGBA32F texel per cell of each monitor's main layer, filled by
        the scene program's pre-pass (u_rev_pass) once a frame while a picture is up, so the
        picture's reveal is worked out once per cell instead of several times per pixel. Sized
        from rain_grid (the shader's own grid, rev_grid in scene.frag), two cells of margin."""
        grids = [self.rain_grid(i) for i in range(len(self.mons))]
        cols = max(g[5] for g in grids) + 2
        rows = max(g[6] for g in grids) + 2
        self.rev_rows = rows
        self.rev_size = (cols, rows * len(self.mons))
        self.rev_tex = self._own(self.ctx.texture(self.rev_size, 4, dtype="f4"))
        self.rev_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.rev_fbo = self._own(self.ctx.framebuffer(color_attachments=[self.rev_tex]))
        self.uniforms["scene"].set("u_rev_rh", rows)

    def _reveal_pass(self, t, rain_t):
        """Fill the reveal cache for this frame (scene program, u_rev_pass 1)."""
        ctx, scene = self.ctx, self.uniforms["scene"]
        cols, rows = self.rev_size
        self.rev_fbo.use()
        ctx.viewport = (0, 0, cols, rows)
        scene.set("u_rev_pass", 1)
        if self.split:
            for i, lk in enumerate(self.looks):
                ctx.scissor = (0, i * self.rev_rows, cols, self.rev_rows)
                scene.apply(self.scene_plans[i])
                self._frame_scene_uniforms(lk, t, rain_t)
                self._fullscreen("scene")
            ctx.scissor = None
        else:
            self._frame_scene_uniforms(self.look, t, rain_t)
            self._fullscreen("scene")
        scene.set("u_rev_pass", 0)
        self.rev_tex.use(UNIT_REVEAL)

    def _picture_pass(self):
        """The grid picture passes (scene_pic), screened onto the rain in the scene target:
        rg = pic + rain * (1 - pic). Blue and alpha (the reveal, read by the final pass) stay."""
        ctx = self.ctx
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_COLOR
        self.scene_fbo.color_mask = (True, True, False, False)
        self._fullscreen("scene_pic")
        self.scene_fbo.color_mask = (True, True, True, True)
        ctx.disable(moderngl.BLEND)

    def _image_passes(self):
        """The programs that can draw the picture itself (debug switch only)."""
        return ("final", "post") if self.fsr else ("final",)

    def _image_frame(self, t, rain_off):
        """Per-frame image layer uniforms; remembers the textures to bind. True when a
        picture is up."""
        if self.images is None:
            return False
        scene = self.uniforms["scene"]
        try:
            state = self.images.update(t, rain_off)
        except Exception as exc:  # a bad picture must never stop the saver
            print("image layer off:", exc)
            self.images.close()
            self.images = None
            scene.set("u_img_on", 0)
            return False
        if self.images.dead:  # no usable picture left: plain rain from now on
            self.images.close()
            self.images = None
            scene.set("u_img_on", 0)
            for key in self._image_passes():
                self.uniforms[key].set("u_img_on", 0)
            return False
        scene.set("u_img_on", state.mode)
        scene.set("u_img_par", state.parity)
        scene.set("u_img_rt", (float(state.current_start), float(state.previous_start)))
        scene.set("u_img_end", float(state.end))
        scene.set("u_img_pend", float(state.previous_end))
        show = image_layer.TUNING.show_picture
        if show:  # the picture itself is never drawn unless this debug switch is on
            for key in self._image_passes():
                self.uniforms[key].set("u_img_on", state.mode)
        if state.mode:
            tex0, tex1, size0, size1, vp0, vp1 = self.images.textures()
            field0, field1, info0, info1 = self.images.fields()
            scene.set("u_img_fv0", info0)
            scene.set("u_img_fv1", info1)
            scene.set("u_img_size0", size0)
            scene.set("u_img_size1", size1)
            scene.set("u_img_vp0", vp0)
            scene.set("u_img_vp1", vp1)
            if show:
                for key in self._image_passes():
                    self.uniforms[key].set("u_img_size0", size0)
                    self.uniforms[key].set("u_img_size1", size1)
            self._image_tex = (tex0, tex1, field0, field1) + tuple(self.images.label_textures())
        return state.mode != 0

    def _scene_plan(self, i):
        """Scene-shader uniforms for monitor i (its look, layers and settings)."""
        look, layers = self.looks[i], self.mon_layers[i]
        lay0 = np.zeros((MAX_LAYERS, 4), "f4")
        lay1 = np.zeros((MAX_LAYERS, 4), "f4")
        for j, lay in enumerate(layers):
            lay0[j] = (lay["scale"], lay["dim"], lay["speed"], lay["density"])
            lay1[j] = (lay["trail"], lay["soft"], 0, 0)
        period, sequential, sync = look["cycle"]
        cluster = look["cluster"] or (8.0, 0.0)
        resurrections = look["glyph_set"] != "classic" and self.atlas2_info is not None
        stretched = (
            not resurrections and look.get("ink_fill") is not None and self.atlas_fill is not None
        )
        # depth slices (screen blend, per-lane jitter) when depth is on and the look has them
        slices = bool(self.mon_cfgs[i]["depth"] and look.get("depth_slices"))
        atlas_info = self.atlas2_info if resurrections else self.atlas_info
        return {
            "u_nlay": len(layers),
            "u_lay0": blob(lay0),
            "u_lay1": blob(lay1),
            "u_base": tuple(c / 255 for c in look["base"]),
            "u_head": tuple(c / 255 for c in look["head"]),
            "u_falloff": float(look["falloff"]),
            "u_gscale": float(self.cfg["glyph_scale"]) * float(look["cell_scale"]),
            "u_film": 1 if look["film"] else 0,
            "u_speed": floats(look["speed"]),
            "u_saw": (
                float(look["tooth"]),
                float(look["contrast"]),
                float(look["bias"]),
                float(look["flat"]),
            ),
            "u_lead": float(look["lead_ratio"]),
            "u_cycle": (float(period), float(sequential), float(sync), 0.0),
            "u_rip_lay": main_layer_index(self.mon_cfgs[i]),
            "u_gamma": float(look["gamma"]),
            "u_exit_hold": float(look["exit_hold"]),
            "u_lanes": float(look["lanes"]),
            "u_clus": (float(cluster[0]), float(cluster[1])),
            "u_defocus": float(look["defocus"]),
            "u_set": 1 if resurrections else (2 if stretched else 0),
            "u_nglyph": int(atlas_info[4]),
            "u_cols": float(look["columns"]),
            "u_glint": float(look["glint_gain"]) if resurrections else 0.0,
            "u_slices": 1.0 if slices else 0.0,
            "u_pjit": float(look["depth_jitter"]) if slices else 0.0,
        }

    def _frame_scene_uniforms(self, look, t, rain_t):
        """Per-frame clocks of one look: the stepped rain and pulse clocks (the camera's frame
        rate) and the changing-glyph phase on the wall clock."""
        s, fps = self.uniforms["scene"], float(look["step_fps"])
        s.set("u_time", float(t))
        s.set("u_rain_time", float(looks.step_time(rain_t, fps)))
        s.set("u_ptime", float(looks.step_time(looks.pulse_time(rain_t, look["pulse"]), fps)))
        slot, prev, mix = looks.glyph_phase(t, float(look["cycle"][0]), fps, look["crossfade"])
        s.set("u_gslot", int(slot))
        s.set("u_gprev", int(prev))
        s.set("u_gmix", float(mix))

    def _final_plan(self, i):
        """Final-pass uniforms for monitor i."""
        look = self.looks[i]
        bloom = float(look["bloom"])
        dots = look["ink_dots"] or NO_INK_DOTS
        return {
            "u_vig": float(look["vignette"]),
            "u_g1": bloom * 0.55,
            "u_g2": bloom * 0.9,
            "u_scan": 0.0 if self.fsr else float(look["scanlines"]),
            "u_film": 1 if look["film"] else 0,
            "u_pal": blob(palette_array(look["palette"])),
            "u_npal": len(look["palette"][:PALETTE_STOPS]),
            "u_cursor": floats(look["cursor"]),
            "u_grain": float(look["grain"]),
            "u_toe": float(look["toe"]),
            "u_pyr_on": 1 if (look["pyramid"] and self.pyr is not None) else 0,
            "u_wr": tuple(bloom * float(w) for w in look["glow_r"]),
            "u_wg": tuple(bloom * float(w) for w in look["glow_g"]),
            "u_lcore": float(look["lead_core"]),
            "u_lglow": float(look["lead_glow"]),
            "u_lcap": float(look["lead_cap"]),
            "u_grain_ink": float(look["grain_ink"]),
            "u_ink_in_final": 1 if self.fsr is None else 0,
            "u_dots": floats(dots),
        }

    def _post_plan(self, i):
        """FSR post-pass uniforms for monitor i (display resolution)."""
        look = self.looks[i]
        dots = look["ink_dots"] or NO_INK_DOTS
        palette_floor = looks.palette_rgb(look["palette"], 0.0) if look["palette"] else (0.0,) * 3
        return {
            "u_scan": float(look["scanlines"]),
            "u_grain_ink": float(look["grain_ink"]),
            "u_dots": floats(dots),
            "u_floor": floats(palette_floor),
        }

    def _scissor_rects(self, sx, sy, height):
        """Per-monitor scissor rectangles (bottom-left origin) for a target of the given height.
        Edges are rounded so a pixel belongs to the monitor whose rectangle holds its centre,
        as in the shaders, so neighbours tile exactly."""
        ox, oy = self._monitor_origin()

        def edge(e):
            return math.ceil(e - 0.5)

        out = []
        for m in self.mons:
            x0, x1 = edge((m["x"] - ox) * sx), edge((m["x"] - ox + m["w"]) * sx)
            y0, y1 = edge((m["y"] - oy) * sy), edge((m["y"] - oy + m["h"]) * sy)
            out.append((x0, height - y1, x1 - x0, y1 - y0))
        return out

    def _msg_anchor(self):
        if self.cfg["message"] != "clock_fixed":
            return None
        return rain_message.anchor_of(self.cfg["clock_position"])

    def _message_masks(self, text, prev=None):
        """Per-monitor masks for `text`: (boxes (MAX_MON, 4), offsets, texture or None).

        With `prev` (always-up clock, minute change) the texture holds change codes: 255
        stays, 192 appears, 96 vanishes (the legacy front reads > 0.5: the new text)."""
        boxes = np.zeros((MAX_MON, 4), "f4")
        self.msg_fine_boxes = np.zeros((MAX_MON, 4), "f4")
        self.msg_fine_cells = np.zeros((MAX_MON, 2), "f4")
        offs = np.zeros(MAX_MON, "f4")
        masks = []
        row = 0
        for i, m in enumerate(self.mons):
            cols, rows, cw, ch = rain_message.main_grid(
                m["w"],
                m["h"],
                m["dpi"],
                self.cfg["glyph_scale"],
                self.looks[i]["cell_scale"],
                self.k,
                True,
                self.looks[i]["columns"],
            )[:4]
            anchor, style = self._msg_anchor(), rain_message.text_style(self.cfg)
            px = (m["w"] * self.k, m["h"] * self.k, cw, ch)
            c, old = (
                rain_message.message_layout(prev, cols, rows, anchor, style, px)
                if prev
                else (1.0, None)
            )
            c, new = rain_message.message_layout(text, cols, rows, anchor, style, px)
            got = rain_message.change_codes(old, new)
            if got is None:
                continue
            codes, col0, row0 = got
            mask = np.choose(codes, [0, 96, 192, 255]).astype(np.uint8)
            if c < 1.0:
                # the message's own finer grid: the shader draws it apart from the main rain cells
                self.msg_fine_boxes[i] = (col0, row0, mask.shape[1], mask.shape[0])
                self.msg_fine_cells[i] = rain_message.fine_cell((cw, ch), c)
            else:
                boxes[i] = (col0, row0, mask.shape[1], mask.shape[0])
            offs[i] = row
            masks.append(mask)
            row += mask.shape[0]
        if not masks:
            return boxes, offs, None
        width = max(mk.shape[1] for mk in masks)
        data = np.zeros((row, width), np.uint8)
        y = 0
        for mk in masks:
            data[y : y + mk.shape[0], : mk.shape[1]] = mk
            y += mk.shape[0]
        tex = self.ctx.texture((width, row), 1, data.tobytes())
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        tex.repeat_x = tex.repeat_y = False
        return boxes, offs, tex

    def _message_uniforms(self, t):
        """Set the per-frame rain message uniforms; True while a message is shown."""
        s = self.uniforms["scene"]
        state = self.msg.state(t)
        if state is None:
            s.set("u_msg_on", 0)
            return False
        text, reveal, hide, n = state
        fixed = self.cfg["message"] == "clock_fixed"
        if self.latch.note_message(n, text, fixed):
            boxes, offs, tex = self._message_masks(text, self.latch.previous_text)
            self.msg_tex.release()
            self.msg_tex = tex or self.ctx.texture((1, 1), 1, bytes(1))
            self.msg_boxes = boxes if tex is not None else None
            s.set("u_msg_box", blob(boxes))
            s.set("u_msg_fbox", blob(self.msg_fine_boxes))
            s.set("u_msg_fcell", blob(self.msg_fine_cells))
            s.set("u_msg_off", blob(offs))
        if self.msg_boxes is None:
            s.set("u_msg_on", 0)
            return True
        s.set("u_msg_on", 1)
        s.set("u_msg_t", (float(reveal), float(hide)))
        s.set("u_msg_n", int(n))
        self.latch.update_clocks(n, text, reveal, hide, t, self.rain_off)
        s.set("u_msg_rt", (self.latch.reveal_clock, self.latch.hide_clock))
        s.set("u_msg_ch", (self.latch.change_clock, rain_message.CLOCK_GLITCH))
        return True

    def _fullscreen(self, key):
        self.vao[key].render(moderngl.TRIANGLES, vertices=3)

    def _blur_chain(self, src_tex, a, b, thresh=0.0, thresholds=None):
        """src -> downsample into a -> separable blur a<->b.

        thresholds: optional [(scissor, thresh)] pairs; the downsample then runs once per pair
        inside its scissor (per-monitor high-pass)."""
        (a_tex, a_fbo), (b_tex, b_fbo) = a, b
        down, blur = self.uniforms["down"], self.uniforms["blur"]
        w, h = a_tex.size
        a_fbo.use()
        self.ctx.viewport = (0, 0, w, h)
        src_tex.use(0)
        down.set("u_texel", (1.0 / src_tex.size[0], 1.0 / src_tex.size[1]))
        if thresholds is None:
            down.set("u_thresh", float(thresh))
            self._fullscreen("down")
        else:
            self.ctx.scissor = None
            a_fbo.clear(0, 0, 0, 1)
            for scissor, th in thresholds:
                self.ctx.scissor = scissor
                down.set("u_thresh", float(th))
                self._fullscreen("down")
            self.ctx.scissor = None
        for src, dst, dx, dy in ((a_tex, b_fbo, 1.0 / w, 0.0), (b_tex, a_fbo, 0.0, 1.0 / h)):
            dst.use()
            src.use(0)
            blur.set("u_dir", (dx, dy))
            self._fullscreen("blur")

    def _pyramid(self):
        """Fill the bloom pyramid: each level is a 2x down-sample of the previous one (level 1
        of the scene), blurred once per axis."""
        src = self.scene_tex
        down, blur = self.uniforms["down"], self.uniforms["blur"]
        down.set("u_thresh", 0.0)
        for (a_tex, a_fbo), (b_tex, b_fbo) in self.pyr:
            w, h = a_tex.size
            a_fbo.use()
            self.ctx.viewport = (0, 0, w, h)
            src.use(0)
            down.set("u_texel", (0.5 / src.size[0], 0.5 / src.size[1]))
            self._fullscreen("down")
            for s_tex, d_fbo, dx, dy in (
                (a_tex, b_fbo, 1.0 / w, 0.0),
                (b_tex, a_fbo, 0.0, 1.0 / h),
            ):
                d_fbo.use()
                s_tex.use(0)
                blur.set("u_dir", (dx, dy))
                self._fullscreen("blur")
            src = a_tex

    def rain_grid(self, mi):
        """(mon_x, mon_y, pad_x, cell_w, cell_h, cols, rows) of monitor mi's main layer in
        window-client pixels, computed as the shader does."""
        f32 = np.float32
        m, k = self.mons[mi], self.k
        lay = self.mon_layers[mi][main_layer_index(self.mon_cfgs[mi])]
        look = self.looks[mi]
        w, h = m["w"] * k, m["h"] * k
        if look["columns"] > 0:
            cw = ch = float(
                looks.cell_px(look, w, lay["scale"], self.cfg["glyph_scale"], m["dpi"] * k)[0]
            )
        else:
            sc = (
                f32(lay["scale"])
                * f32(m["dpi"] * k)
                * f32(float(self.cfg["glyph_scale"]) * float(look["cell_scale"]))
            )
            cw = float(np.floor(f32(CELL_W) * sc + f32(0.5)))
            ch = float(np.floor(f32(CELL_H) * sc + f32(0.5)))
        cols, rows = math.floor(w / cw), math.floor(h / ch)
        pad = math.floor((w - cols * cw) * 0.5)
        ox, oy = self._monitor_origin()
        return (m["x"] - ox, m["y"] - oy, pad / k, cw / k, ch / k, cols, rows)

    def render(self, t, dt, frame):
        ctx = self.ctx
        rw, rh = self.rsize
        ctx.disable(moderngl.BLEND)
        scene = self.uniforms["scene"]

        self.scene_fbo.use()
        ctx.viewport = (0, 0, rw, rh)
        self.atlas.use(UNIT_ATLAS)
        if self.atlas2 is not None:
            self.atlas2.use(UNIT_ATLAS_RESURRECTIONS)
        if self.atlas_fill is not None:
            self.atlas_fill.use(UNIT_ATLAS_FILL)
        speed_k, density_k = self.live.update(dt)
        self.rain_off += dt * (speed_k - 1.0)
        rain_t = t + self.rain_off
        showing = self._message_uniforms(t)
        image_on = self._image_frame(t, self.rain_off)
        self.msg_tex.use(UNIT_MESSAGE)
        if image_on:
            picture_units = (
                UNIT_PICTURE0,
                UNIT_PICTURE1,
                UNIT_FIELD0,
                UNIT_FIELD1,
                UNIT_SURFACE0,
                UNIT_SURFACE1,
            )
            for unit, tex in zip(picture_units, self._image_tex, strict=True):
                tex.use(unit)
        scene.set("u_live_density", float(density_k))
        if image_on:
            self._reveal_pass(t, rain_t)
            self.scene_fbo.use()
            ctx.viewport = (0, 0, rw, rh)
        pictures = image_on and self.grid_passes
        if self.split:
            ctx.scissor = None
            self.scene_fbo.clear(0, 0, 0, 1)
            for i, lk in enumerate(self.looks):
                ctx.scissor = self.rects_r[i]
                scene.apply(self.scene_plans[i])
                self._frame_scene_uniforms(lk, t, rain_t)
                self._fullscreen("scene")
                if pictures:
                    self._picture_pass()
            ctx.scissor = None
        else:
            self._frame_scene_uniforms(self.look, t, rain_t)
            self._fullscreen("scene")
            if pictures:
                self._picture_pass()
        if not showing:
            self._draw_egg(t)

        self._bloom()
        gains, fields = self._flicker(frame)
        self._compose(frame, gains, fields, image_on)
        if self.fsr:
            self._upscale(frame, gains, fields, image_on)
        if self.hdr:
            self._hdr_present()

    def _bloom(self):
        """The bloom pyramid, and the older two-level blur for looks that use it."""
        ctx = self.ctx
        if self.pyr is not None:
            ctx.disable(moderngl.BLEND)
            self._pyramid()
        if not (self.bloom_on and self.legacy_bloom):
            return
        ctx.disable(moderngl.BLEND)
        if self.split:
            pairs = [
                (self.rects_q[i], lk["hipass"] if lk["film"] else 0.0)
                for i, lk in enumerate(self.looks)
            ]
            self._blur_chain(self.scene_tex, self.q[0], self.q[1], thresholds=pairs)
        else:
            self._blur_chain(
                self.scene_tex,
                self.q[0],
                self.q[1],
                self.look["hipass"] if self.look["film"] else 0.0,
            )
        self._blur_chain(self.q[0][0], self.q[2], self.q[3])

    def _flicker(self, frame):
        """Per-monitor flicker gain and interlace field for this frame."""
        r = float(self.rng.random())
        gains, fields = [], []
        for lk in self.looks if self.split else [self.look]:
            gains.append(1.0 + lk["flicker"] * (r - 0.5) * 2.0)
            fields.append(float(frame % 2) if lk["interlace"] else 0.0)
        return gains, fields

    def _compose(self, frame, gains, fields, image_on):
        """Scene plus bloom through the palette, to the screen (or the FSR input)."""
        ctx = self.ctx
        rw, rh = self.rsize
        final = self.uniforms["final"]
        target = self.post_fbo if self.fsr else self._out()
        target.use()
        ctx.viewport = (0, 0, rw, rh)
        ctx.disable(moderngl.BLEND)
        self.scene_tex.use(0)
        self.q[0][0].use(UNIT_BLOOM_NEAR)
        self.q[2][0].use(UNIT_BLOOM_FAR)
        if self.pyr is not None:
            for j, ((p_tex, _fbo), _scratch) in enumerate(self.pyr):
                p_tex.use(UNIT_PYRAMID + j)
        if image_on and not self.fsr and image_layer.TUNING.show_picture:
            for unit, tex in zip(FINAL_PICTURE_UNITS, self._image_tex[:2], strict=True):
                tex.use(unit)
        final.set("u_seed", float(frame % 997))
        if self.split:
            ctx.scissor = None
            target.clear(0, 0, 0, 1)
            for i in range(len(self.looks)):
                ctx.scissor = self.rects_r[i]
                final.apply(self.final_plans[i])
                final.set("u_gain", 1.0 if self.fsr else gains[i])
                final.set("u_field", fields[i])
                self._fullscreen("final")
            ctx.scissor = None
        else:
            final.set("u_gain", 1.0 if self.fsr else gains[0])
            final.set("u_field", fields[0])
            self._fullscreen("final")

    def _upscale(self, frame, gains, fields, image_on):
        """FSR upscale to display size. Its sharpening pass also applies the scanlines,
        flicker and ink effects there."""
        ctx = self.ctx
        rw, rh = self.rsize
        vw, vh = self.size
        post = self.uniforms["post"]
        fsr = self.fsr
        eased = fsr.resample(self.post_tex, (rw, rh), (vw, vh))
        out = self._out()
        fsr.begin_sharpen(eased, out, (vw, vh), float(self.cfg["sharpness"]))
        if image_on and image_layer.TUNING.show_picture:
            self.scene_tex.use(1)
            for unit, tex in zip(POST_PICTURE_UNITS, self._image_tex[:2], strict=True):
                tex.use(unit)
        post.set("u_seed", float(frame % 997))
        if self.split:
            ctx.scissor = None
            out.clear(0, 0, 0, 1)
            for i in range(len(self.looks)):
                ctx.scissor = self.rects_d[i]
                post.set("u_gain", gains[i])
                post.set("u_field", fields[i])
                post.apply(self.post_plans[i])
                fsr.sharpen()
            ctx.scissor = None
        else:
            post.set("u_gain", gains[0])
            post.set("u_field", fields[0])
            fsr.sharpen()

    def _out(self):
        """Where the finished frame is drawn: the screen, or the HDR frame buffer."""
        return self.hdr_fbo if self.hdr else self.ctx.screen

    def _hdr_present(self):
        """Convert the finished frame to linear light on the float16 screen."""
        ctx = self.ctx
        vw, vh = self.size
        ctx.scissor = None
        ctx.screen.use()
        ctx.viewport = (0, 0, vw, vh)
        ctx.disable(moderngl.BLEND)
        self.hdr_tex.use(0)
        self._fullscreen("hdr")

    def _text_texture(self, text, height):
        key = (text, height)
        if key not in self.text_cache:
            _size, family, bold, italic = rain_message.text_style(self.cfg)
            font = glyphs.text_font(height, family, bold, italic)
            surf = font.render(text, True, (255, 255, 255), (0, 0, 0))
            data = pygame.image.tobytes(surf, "RGB")
            red = np.frombuffer(data, np.uint8).reshape(-1, 3)[:, 0].copy()
            tex = self.ctx.texture(surf.get_size(), 1, red.tobytes())
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            for old_tex, _size in self.text_cache.values():
                old_tex.release()
            self.text_cache = {key: (tex, surf.get_size())}  # keep only one
        return self.text_cache[key]

    def _draw_egg(self, t):
        state = self.egg.update(t)
        if state is None:
            return
        text, shown, alpha, cursor = state
        mon = self.mons[0]
        ox, oy = self._monitor_origin()
        k = self.k
        size = rain_message.text_style(self.cfg)[0]
        height = max(8, int(mon["h"] * 0.05 * mon["dpi"] ** 0.5 * k * size))
        tex, (tw, th) = self._text_texture(text, height)
        x = (mon["x"] - ox + mon["w"] * 0.10) * k
        y = (mon["y"] - oy + mon["h"] * 0.42) * k
        ctx, over = self.ctx, self.uniforms["over"]
        ctx.enable(moderngl.BLEND)

        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        pad = height * 0.6
        over.set("u_rect", (x - pad, y - pad * 0.6, tw + pad * 2 + height, th + pad * 1.2))
        over.set("u_use_tex", 0)
        over.set("u_color", (0.0, 0.0, 0.0, 0.88 * alpha))
        self.vao["over"].render(moderngl.TRIANGLE_STRIP, vertices=4)

        ctx.blend_func = moderngl.ONE, moderngl.ONE
        tex.use(0)
        over.set("u_tex", 0)
        over.set("u_use_tex", 1)
        over.set("u_rect", (x, y, float(tw), float(th)))
        over.set("u_reveal", shown / len(text))
        film = self.look["film"]
        over.set("u_color", (0.9, 0.0, 0.0, alpha) if film else (*self.head, alpha))
        self.vao["over"].render(moderngl.TRIANGLE_STRIP, vertices=4)

        if cursor and alpha > 0.0:
            cw = tw / len(text)
            over.set("u_use_tex", 0)
            over.set("u_rect", (x + cw * shown, y + th * 0.12, cw * 0.8, th * 0.76))
            over.set(
                "u_color",
                (0.7 * alpha, 0.0, 0.0, 1.0) if film else (*(c * alpha for c in self.base), 1.0),
            )
            self.vao["over"].render(moderngl.TRIANGLE_STRIP, vertices=4)
        ctx.disable(moderngl.BLEND)

    def screenshot(self, path):
        vw, vh = self.size
        # With HDR the screen is linear float16; the display-referred frame is in hdr_fbo.
        data = self._out().read(components=3)
        surf = pygame.image.frombuffer(data, (vw, vh), "RGB")
        pygame.image.save(pygame.transform.flip(surf, False, True), path)

    def close(self):
        """Release every GL object this renderer created."""
        self.live.close()
        if self.images is not None:
            self.images.close()
        self.msg_tex.release()
        for tex, _size in self.text_cache.values():
            tex.release()
        self.text_cache = {}
        for gl_object in reversed(self._gl_objects):
            gl_object.release()
        self._gl_objects = []
