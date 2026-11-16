"""image_layer: the numpy analysis on small synthetic pictures, and the layer's show timing.

No GPU: ImageLayer is given a fake context whose textures only record that they were made
and released, and MATRIX_IMAGE_SYNC=1 makes the preparation run inline.
"""

import dataclasses
import os
import threading
import time

import numpy as np
import pygame
import pytest

from digital_rain import image_layer as il


# Synthetic pictures
def converging_lines(width=320, height=240, vanish=(160, 100)):
    """Dark lines fanning out from one point on a light ground: a perspective drawing."""
    lum = np.full((height, width), 200, np.uint8)
    for angle in np.linspace(0.3, np.pi - 0.3, 18):
        for radius in range(400):
            x = int(vanish[0] + radius * np.cos(angle))
            y = int(vanish[1] + radius * np.sin(angle))
            if 0 <= x < width and 0 <= y < height:
                lum[y, x] = 20
    return lum


def save_png(path, lum):
    rgb = np.stack([lum] * 3, axis=2)
    surface = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
    pygame.image.save(surface, str(path))


# Filters
def test_box_blur_of_a_constant_stays_constant():
    values = np.full((12, 9), 0.4)
    for mode in ("edge", "constant"):
        blurred = il._box_blur(values, 2, mode)
        if mode == "edge":
            assert np.allclose(blurred, 0.4)
        assert blurred.shape == values.shape


def test_box_blur_spreads_an_impulse_over_the_window_and_keeps_its_mass():
    values = np.zeros((21, 21))
    values[10, 10] = 1.0
    blurred = il._box_blur(values, 2, "constant")
    assert blurred.sum() == pytest.approx(1.0, abs=1e-5)
    assert np.count_nonzero(blurred) == 25
    assert blurred[10, 10] == pytest.approx(1 / 25)


def test_box_blur_radius_zero_is_the_identity():
    values = np.arange(12.0).reshape(3, 4)
    assert il._box_blur(values, 0) is values


def test_flood_fills_only_connected_passable_cells():
    passable = np.zeros((5, 7), bool)
    passable[:, 0:3] = True
    passable[:, 5:7] = True
    seed = np.zeros_like(passable)
    seed[0, 0] = True
    filled = il._flood(seed, passable)
    assert filled[:, 0:3].all()
    assert not filled[:, 5:7].any()


def test_flood_does_not_cross_a_diagonal_gap():
    passable = np.array([[1, 0], [0, 1]], bool)
    seed = np.array([[1, 0], [0, 0]], bool)
    assert il._flood(seed, passable).tolist() == [[True, False], [False, False]]


# Geometry
def test_vanishing_point_of_converging_lines_is_where_they_meet():
    point = il.vanishing_point(converging_lines())
    assert point.x == pytest.approx(0.5, abs=0.05)
    assert point.y == pytest.approx(0.4, abs=0.05)
    assert point.confidence > 0.1


def test_a_flat_picture_has_no_vanishing_point():
    point = il.vanishing_point(np.full((240, 320), 128, np.uint8))
    assert point.confidence == 0.0


def test_depth_field_of_a_flat_picture_is_a_uniform_table():
    flat = np.full((240, 320), 128, np.uint8)
    sizes, horizon_y, mode = il.depth_field(flat, il.vanishing_point(flat))
    assert sizes.shape == (il.TUNING.field_size, il.TUNING.field_size)
    assert sizes.dtype == np.float32
    assert sizes.min() > 0
    assert 0.0 <= horizon_y <= 1.0
    assert mode in (0, 1)


def test_depth_field_with_a_confident_point_and_no_sky_is_a_street_canyon():
    lum = converging_lines()
    point = il.VanishingPoint(0.5, 0.4, 0.9)
    sizes, _horizon, mode = il.depth_field(lum, point)
    if il.TUNING.field_on > 0.0:
        assert sizes.min() > 0
    assert mode in (1, 2)


def test_finer_detail_never_grows_the_glyphs_and_respects_the_pixel_floor():
    size = 1.0
    assert il._finer(size, 0.5, 0.0, 20.0) == size
    assert il._finer(size, 0.5, 1.0, 0.0) == pytest.approx(0.5)
    floor = il.TUNING.detail_min_px / 20.0
    assert il._finer(size, 0.01, 1.0, 20.0) == pytest.approx(max(0.01, floor))
    assert il._finer(size, 2.0, 1.0, 20.0) <= size


def test_field_tables_are_consistent_for_a_uniform_field():
    rows, cols = 32, 32
    sizes = np.full((rows, cols), 0.5, np.float32)
    tables, (v_min, v_max) = il.field_tables(sizes, 0.5, 0.5, 4 / 3)
    assert tables.shape == (rows, cols, 3)
    assert tables.dtype == np.float32
    assert tables.flags["C_CONTIGUOUS"]
    assert v_min < 0.0 < v_max
    assert np.allclose(tables[:, :, 2], 0.5)
    # a uniform size gives rows and columns that advance at a steady rate
    row_steps = np.diff(tables[:, 0, 0])
    assert np.allclose(row_steps, row_steps[0], rtol=1e-3)
    col_steps = np.diff(tables[0, :, 1])
    assert col_steps.min() > 0
    assert np.allclose(col_steps, col_steps[0], rtol=1e-3)


# Tone and open areas
def test_local_lift_with_no_amount_changes_nothing():
    lum = np.random.default_rng(1).random((40, 50)).astype(np.float32)
    assert il.local_lift(lum, 0.0) is lum


def test_local_lift_only_brightens_and_stays_in_range():
    rng = np.random.default_rng(2)
    lum = (rng.random((60, 80)) * 0.3).astype(np.float32)
    lum[:, :40] *= 0.2
    lifted = il.local_lift(lum, 0.8)
    assert lifted.min() >= 0.0
    assert lifted.max() <= 1.0
    assert (lifted >= lum - 1e-6).all()
    assert lifted.mean() > lum.mean()


def test_background_mask_marks_the_open_border_not_the_subject():
    lum = np.zeros((120, 160), np.float32)
    lum[:] = 0.95
    lum[40:80, 60:100] = 0.1
    mask = il.background_mask(lum)
    assert mask.shape == lum.shape
    assert mask[2, 2] > 0.9
    assert mask[60, 80] < 0.1


def test_background_mask_ignores_a_bright_area_not_connected_to_the_border():
    lum = np.full((120, 160), 0.1, np.float32)
    lum[40:80, 60:100] = 0.95
    mask = il.background_mask(lum)
    assert mask[60, 80] < 0.1


def test_surface_tone_returns_full_size_uint8_planes():
    lum = np.random.default_rng(3).random((90, 120)).astype(np.float32)
    tone, open_mask = il.surface_tone(lum)
    assert tone.shape == open_mask.shape == lum.shape
    assert tone.dtype == open_mask.dtype == np.uint8


# Settings and files
def test_detail_comes_from_the_environment_then_the_setting(monkeypatch):
    monkeypatch.delenv("MATRIX_IMAGE_DETAIL", raising=False)
    assert il.detail_of({"image_detail": 0.4}) == pytest.approx(0.4)
    assert il.detail_of() == 0.0
    monkeypatch.setenv("MATRIX_IMAGE_DETAIL", "3")
    assert il.detail_of({"image_detail": 0.4}) == 1.0
    monkeypatch.setenv("MATRIX_IMAGE_DETAIL", "nonsense")
    assert il.detail_of({"image_detail": 0.4}) == 0.0


def test_folder_prefers_the_setting_to_the_environment(tmp_path, monkeypatch):
    chosen = tmp_path / "chosen"
    other = tmp_path / "other"
    chosen.mkdir()
    other.mkdir()
    monkeypatch.setenv("MATRIX_IMAGE_DIR", str(other))
    assert il.folder({"image_dir": str(chosen)}) == str(chosen)
    assert il.folder({"image_dir": ""}) == str(other)
    # a configured folder that is gone is not replaced by the environment's
    assert il.folder({"image_dir": str(tmp_path / "missing")}) != str(other)


def test_folder_is_off_for_an_empty_setting_or_a_missing_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("MATRIX_IMAGE_DIR", raising=False)
    assert il.folder({"image_dir": ""}) is None
    assert il.folder({"image_dir": str(tmp_path / "gone")}) is None
    assert il.folder({"image_dir": str(tmp_path)}) == str(tmp_path)


def test_analyse_packs_four_channels_and_a_field(tmp_path):
    path = tmp_path / "lines.png"
    save_png(path, converging_lines(160, 120, (80, 50)))
    image = il.analyse(str(path), max_size=4096, detail=0.0, cell_px=0.0)
    assert (image.width, image.height) == (160, 120)
    assert len(image.texels) == 160 * 120 * 4
    field = image.field
    assert len(field.data) == field.width * field.height * 3 * 4
    assert field.info.v_min < field.info.v_max
    assert 0 <= image.vanishing_point.x <= 1


def test_analyse_shrinks_a_picture_larger_than_the_limit(tmp_path):
    path = tmp_path / "big.png"
    save_png(path, converging_lines(320, 240))
    image = il.analyse(str(path), max_size=160, detail=0.0, cell_px=0.0)
    assert max(image.width, image.height) == 160


# The layer
class FakeTexture:
    def __init__(self, store):
        self.released = False
        self.store = store
        store.append(self)

    def build_mipmaps(self):
        pass

    def release(self):
        self.released = True


class FakeContext:
    def __init__(self):
        self.textures = []

    def texture(self, *_args, **_kwargs):
        return FakeTexture(self.textures)


@pytest.fixture
def folder_of_pictures(tmp_path, monkeypatch):
    monkeypatch.setenv("MATRIX_IMAGE_SYNC", "1")
    monkeypatch.delenv("MATRIX_IMAGE_PERIOD", raising=False)
    for name in ("a.png", "b.png", "c.png"):
        save_png(tmp_path / name, converging_lines(64, 48, (32, 20)))
    (tmp_path / "notes.txt").write_text("not a picture", encoding="utf-8")
    return tmp_path


def make_layer(folder, **cfg):
    return il.ImageLayer(FakeContext(), str(folder), cfg=dict(image_period=10.0, **cfg))


def test_layer_needs_at_least_one_picture(tmp_path):
    with pytest.raises(ValueError, match="no images"):
        il.ImageLayer(FakeContext(), str(tmp_path))


def test_layer_lists_only_picture_files_in_name_order(folder_of_pictures):
    layer = make_layer(folder_of_pictures)
    assert [f.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for f in layer.files] == [
        "a.png",
        "b.png",
        "c.png",
    ]
    layer.close()


def test_layer_is_off_until_the_start_time_then_shows_the_first_picture(folder_of_pictures):
    layer = make_layer(folder_of_pictures)
    assert layer.update(il.TUNING.start - 0.5, 0.0) == il.IMAGE_OFF
    state = layer.update(il.TUNING.start + 0.1, 5.0)
    assert state.mode == 1
    assert state.parity == 0
    assert state.current_start == pytest.approx(il.TUNING.start + 0.1 + 5.0)
    assert state.end == -1.0
    first, second, size0, size1, *_ = layer.textures()
    assert first is second
    assert size0 == (64.0, 48.0)
    layer.close()


def test_layer_sweeps_to_the_next_picture_each_period(folder_of_pictures):
    layer = make_layer(folder_of_pictures)
    start = il.TUNING.start
    layer.update(start + 0.1, 0.0)
    state = layer.update(start + 10.1, 0.0)
    assert state.mode == 2
    assert state.parity == 1
    assert state.previous_start == pytest.approx(start + 0.1)
    first, second, *_ = layer.textures()
    assert first is not second
    layer.close()


def test_layer_releases_pictures_it_no_longer_needs(folder_of_pictures):
    # four pictures: one is let go
    save_png(folder_of_pictures / "d.png", converging_lines(64, 48, (32, 20)))
    layer = make_layer(folder_of_pictures)
    start = il.TUNING.start
    for number in range(4):
        layer.update(start + number * 10.0 + 0.1, 0.0)
    assert len(layer.textures_by_pic) <= 3   # current, previous, and the next one uploaded ahead
    live = list(layer.ctx.textures)
    released = [texture for texture in live if texture.released]
    assert released
    layer.close()
    assert all(texture.released for texture in live)
    assert not layer.textures_by_pic


def test_gap_mode_ends_the_picture_before_the_next_one(folder_of_pictures):
    layer = make_layer(folder_of_pictures, image_gap=4.0)
    start = il.TUNING.start
    layer.update(start + 0.1, 0.0)
    assert layer.update(start + 9.0, 0.0).end == -1.0
    state = layer.update(start + 11.0, 2.0)
    assert state.end == pytest.approx(start + 11.0 + 2.0)
    assert state.mode == 1
    # the next picture starts a whole gap after the period, not at the period
    layer.update(start + 13.0, 0.0)
    assert layer.number == 0
    layer.update(start + 14.1, 0.0)
    assert layer.number == 1


def test_gap_mode_keeps_the_leaving_picture_while_the_next_one_starts(folder_of_pictures):
    # slow lanes can still hold a picture when the next one starts: its exit runs on underneath
    layer = make_layer(folder_of_pictures, image_gap=4.0)
    start = il.TUNING.start
    layer.update(start + 0.1, 0.0)
    end = layer.update(start + 11.0, 2.0).end
    state = layer.update(start + 14.1, 2.0)
    assert layer.number == 1
    assert state.mode == 2
    assert state.previous_end == pytest.approx(end)
    assert state.previous_start == pytest.approx(start + 0.1)
    assert state.end == -1.0


def test_shuffle_shows_every_picture_once_per_round_and_never_repeats_across_rounds(
    folder_of_pictures,
):
    layer = make_layer(folder_of_pictures, image_order="shuffle")
    shown = [layer._pic(number) for number in range(12)]
    for round_start in range(0, 12, 3):
        assert sorted(shown[round_start : round_start + 3]) == [0, 1, 2]
    assert all(a != b for a, b in zip(shown, shown[1:], strict=False))
    layer.close()


def test_a_broken_picture_is_skipped_and_the_rest_still_show(folder_of_pictures):
    (folder_of_pictures / "a.png").write_bytes(b"not a png")
    layer = make_layer(folder_of_pictures)
    state = layer.update(il.TUNING.start + 0.1, 0.0)
    assert state.mode == 0
    assert layer.bad == {0}
    assert not layer.dead
    assert layer.update(il.TUNING.start + 0.2, 0.0).mode == 1
    layer.close()


def test_a_folder_with_only_broken_pictures_kills_the_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("MATRIX_IMAGE_SYNC", "1")
    (tmp_path / "bad.png").write_bytes(b"not a picture")
    layer = make_layer(tmp_path)
    for seconds in (3.0, 4.0, 5.0):
        assert layer.update(seconds, 0.0).mode == 0
    assert layer.dead
    assert layer.bad == {0}


def test_only_one_preparation_runs_at_a_time_and_stale_jobs_are_dropped(
    folder_of_pictures, monkeypatch
):
    monkeypatch.delenv("MATRIX_IMAGE_SYNC")
    layer = make_layer(folder_of_pictures)
    release = threading.Event()

    def slow(_pic):
        release.wait(5)
        raise ValueError("fake")

    layer._prepare = slow
    for pic in (1, 2, 0):
        layer._want(pic)
    assert len(layer.jobs) == 1
    release.set()
    layer.jobs[1].exception(5)
    # the clock jumps to picture 2: the finished job for picture 1 is stale
    layer.update(il.TUNING.start + 25.0, 0.0)
    assert 1 not in layer.jobs
    layer.close()
    assert layer.dead
    assert not layer.jobs


def test_each_picture_is_prepared_once_while_the_show_runs(folder_of_pictures, monkeypatch):
    monkeypatch.delenv("MATRIX_IMAGE_SYNC")
    layer = make_layer(folder_of_pictures)
    prepared = []
    real = layer._prepare

    def counted(pic):
        prepared.append(pic)
        return real(pic)

    layer._prepare = counted
    t = il.TUNING.start
    while t < il.TUNING.start + 25.0:  # two and a half periods of 10 s
        layer.update(t, 0.0)
        # let a worker finish between frames, as a real frame does
        for future in list(layer.jobs.values()):
            future.exception(5)
        t += 0.25
    layer.close()
    assert layer.number >= 2
    # a picture staged for upload must not be handed to a second job
    assert len(prepared) == len(set(prepared))


# Surface detection
def _corridor_disparity(width=96, height=64):
    """Disparity of a corridor seen down its axis: floor, left wall, right wall, back wall."""
    u = (np.arange(width) + 0.5) / width
    v = (np.arange(height) + 0.5) / height
    x, y = np.meshgrid(u, v)
    floor = 1.2 * (y - 0.5)
    left = 1.2 * (0.5 - x)
    right = 1.2 * (x - 0.5)
    return (np.maximum.reduce([floor, left, right, np.full_like(x, 0.05)]) + 0.2).astype(np.float32)


def test_detect_labels_a_corridor_and_finds_its_vanishing_point():
    from digital_rain import surfaces

    found = surfaces.detect(_corridor_disparity())
    kinds = {p.kind for p in found.planes}
    assert {surfaces.FLOOR, surfaces.WALL_LEFT, surfaces.WALL_RIGHT} <= kinds
    labels = found.labels
    assert labels[-4, 48] == surfaces.FLOOR
    assert labels[32, 3] == surfaces.WALL_LEFT
    assert labels[32, -4] == surfaces.WALL_RIGHT
    x, y, confidence = found.vanishing
    assert abs(x - 0.5) < 0.1 and abs(y - 0.5) < 0.1 and confidence >= 0.5


def test_detect_marks_an_object_in_front_of_a_wall_as_frontal():
    from digital_rain import surfaces

    disparity = _corridor_disparity()
    disparity[20:40, 5:15] += 0.4  # something standing nearer than the left wall
    assert surfaces.detect(disparity).labels[30, 10] == surfaces.FRONT


def test_lookup_without_a_cache_or_model_gives_nothing(tmp_path, monkeypatch):
    from digital_rain import surfaces

    monkeypatch.setenv(surfaces.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.delenv(surfaces.MODEL_ENV, raising=False)
    picture = tmp_path / "a.png"
    picture.write_bytes(b"x")
    assert surfaces.lookup(str(picture)) is None


def test_analyse_uses_cached_surfaces_in_grid_mode(tmp_path, monkeypatch):
    from digital_rain import surfaces

    monkeypatch.setenv(surfaces.CACHE_ENV, str(tmp_path / "cache"))
    path = tmp_path / "a.png"
    save_png(path, converging_lines(160, 90, (80, 45)))
    surfaces._store(str(path), _corridor_disparity())
    image = il.analyse(str(path), max_size=4096, detail=0.0, cell_px=0.0, detect=True)
    assert image.labels.width > 1 and image.vanishing_point.confidence >= 0.5
    plain = il.analyse(str(path), max_size=4096, detail=0.0, cell_px=0.0)
    assert plain.labels == il.NO_LABELS


def test_fill_cache_uses_the_core_ml_backend_when_it_is_there(tmp_path, monkeypatch):
    from digital_rain import surfaces
    from digital_rain.mac import depth_coreml

    monkeypatch.setenv(surfaces.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.setattr(depth_coreml, "available", lambda: True)
    monkeypatch.setattr(depth_coreml, "predict", lambda rgb: _corridor_disparity())
    picture = tmp_path / "a.png"
    picture.write_bytes(b"x")
    assert surfaces.can_estimate()
    assert surfaces.fill_cache(str(picture), lambda path, size: np.zeros((90, 160, 3), np.uint8))
    assert surfaces.lookup(str(picture)) is not None


def test_fill_cache_without_any_backend_is_false(tmp_path, monkeypatch):
    from digital_rain import surfaces
    from digital_rain.mac import depth_coreml

    monkeypatch.setenv(surfaces.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.delenv(surfaces.MODEL_ENV, raising=False)
    monkeypatch.setattr(depth_coreml, "available", lambda: False)
    # hide the model bundled in assets/models
    monkeypatch.setattr(surfaces.resources, "asset_path", lambda *parts: str(tmp_path / "none"))
    picture = tmp_path / "a.png"
    picture.write_bytes(b"x")
    assert not surfaces.can_estimate()
    assert not surfaces.fill_cache(str(picture), lambda path, size: np.zeros((9, 9, 3), np.uint8))


def test_model_path_finds_the_bundled_model(tmp_path, monkeypatch):
    from digital_rain import resources, surfaces

    monkeypatch.setenv(surfaces.CACHE_ENV, str(tmp_path / "cache"))
    monkeypatch.delenv(surfaces.MODEL_ENV, raising=False)
    bundled = resources.asset_path("models", surfaces.MODEL_NAME)
    assert os.path.isfile(bundled)
    assert surfaces.model_path() == bundled


def test_grid_detail_and_outline_settings_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("MATRIX_IMAGE_GRID_DETAIL", "0.25")
    monkeypatch.setenv("MATRIX_IMAGE_GRID_SIL_SIDE", "0")
    tune = il.ImageTuning.from_env()
    assert tune.grid_detail == 0.25
    assert tune.grid_sil_side == 0.0
    # defaults: outlines on the object only, far parts keep little of their detail, and the
    # picture is lit by its own light, so depth does not dim far parts (grid_tone_far 0)
    assert il.ImageTuning().grid_sil_side == 1.0
    assert 0.0 < il.ImageTuning().grid_detail_far < 1.0
    assert il.ImageTuning().grid_tone_far == 0.0
    assert il.ImageTuning().grid_own > 0.0


# Pictures of people
def test_load_rgb_turns_a_phone_photo_upright(tmp_path):
    """A portrait phone photo is stored on its side with an EXIF tag saying how to turn it."""
    from PIL import Image

    stored = Image.new("RGB", (60, 40), (0, 0, 0))
    stored.paste((255, 255, 255), (0, 0, 10, 40))  # a white strip on the stored left edge
    exif = Image.Exif()
    exif[274] = 6  # orientation: turn 90 degrees clockwise to view
    path = tmp_path / "phone.jpg"
    stored.save(path, exif=exif)
    rgb = il.load_rgb(str(path), 1024)
    assert rgb.shape[:2] == (60, 40)  # upright: taller than wide
    assert rgb[:5].mean() > 200 and rgb[-5:].mean() < 50  # the strip is now at the top


def test_portrait_pictures_are_padded_to_the_frame_not_cropped():
    assert il.pad_columns(1600, 900) == (0, 0)
    assert il.pad_columns(1600, 1200) == (0, 0)  # 4:3 landscape is cropped as before
    left, right = il.pad_columns(300, 400)
    assert left + right + 300 == round(400 * il.FRAME_ASPECT) and abs(left - right) <= 1
    padded = il.pad_sides(np.ones((400, 300), np.float32))
    assert padded.shape[1] == 300 + left + right
    assert padded[:, :left].max() == 0.0 and padded[:, left : left + 300].min() == 1.0


def test_subject_mask_finds_objects_in_front_but_not_planes():
    from digital_rain import surfaces

    ys, xs = np.mgrid[0:96, 0:128] / 96.0
    floor = (0.2 + 0.6 * ys).astype(np.float32)  # a plane: disparity linear in the picture
    none = np.zeros_like(floor)
    assert surfaces.subject_mask(floor, none).max() < 0.05  # edges included
    person = floor.copy()
    person[30:80, 50:70] = 0.95
    mask = surfaces.subject_mask(person, none)
    assert mask[40:70, 55:65].min() > 0.9 and mask[:, :30].max() < 0.05
    # the open sky is not part of anything's surroundings: a building against it is no object
    sky = np.zeros_like(floor)
    sky[:30] = 1.0
    wall = np.where(sky > 0, 0.0, 0.5).astype(np.float32)
    assert surfaces.subject_mask(wall, sky).max() < 0.05


def test_refine_upsamples_labels_and_depth():
    from digital_rain import surfaces

    labels = np.zeros((48, 64), np.uint8)
    labels[:, 32:] = surfaces.FLOOR
    depth = np.linspace(0, 1, 48 * 64, dtype=np.float32).reshape(48, 64)
    found = surfaces.Detected(labels, (), None, depth)
    fine = surfaces.refine(found, 128)
    assert fine.labels.shape == (96, 128) and fine.depth.shape == (96, 128)
    assert set(np.unique(fine.labels)) == {0, surfaces.FLOOR}
    assert surfaces.refine(found, 32) is found


def test_own_light_tone_lifts_a_dark_person_before_a_bright_wall():
    from digital_rain import surfaces

    lum = np.full((96, 128), 0.8, np.float32)
    lum[30:80, 50:70] = 0.15  # dark clothes against a bright wall
    lum[40, 55:65] = 0.6
    near = np.zeros_like(lum)
    near[30:80, 50:70] = 1.0
    none = np.zeros_like(lum)
    plain = surfaces.own_light_tone(lum, lum.shape, none, 0.2, 1.6)
    lifted = surfaces.own_light_tone(
        lum, lum.shape, none, 0.2, 1.6, near=near, near_body=0.35, behind=0.6
    )
    person, beside = (slice(45, 70), slice(55, 65)), (slice(45, 70), slice(72, 76))
    assert plain[person].mean() < plain[beside].mean()  # the photo's light: a dark hole
    assert lifted[person].mean() > plain[person].mean()
    assert lifted[beside].mean() < plain[beside].mean()  # the wall right behind is dimmed
    assert lifted[:, :10].mean() == plain[:, :10].mean()  # far from the person, unchanged


def _box(labels, vanishing, camera=0, planes=None):
    from digital_rain import surfaces

    if planes is None:
        planes = (surfaces.Plane(surfaces.FLOOR, 0.0, 1.0, 0.0, 0.8),)
    return surfaces.Detected(labels, planes, vanishing, np.zeros(labels.shape, np.float32), camera)


def _corridor(wall_slope=1.5):
    """A corridor seen down its length, receding to (0.5, 0.4): walls left and right, a floor
    below the point, the far end frontal."""
    from digital_rain import surfaces

    labels = np.full((40, 60), surfaces.FRONT, np.uint8)
    labels[24:, :] = surfaces.FLOOR
    labels[:, :15] = surfaces.WALL_LEFT
    labels[:, -15:] = surfaces.WALL_RIGHT
    planes = (
        surfaces.Plane(surfaces.WALL_LEFT, -wall_slope, 0.0, 0.75, 0.25),
        surfaces.Plane(surfaces.WALL_RIGHT, wall_slope, 0.0, -0.75, 0.25),
        surfaces.Plane(surfaces.FLOOR, 0.0, 2.0, -0.8, 0.3),
    )
    return labels, planes


def test_a_floor_with_only_a_guessed_vanishing_point_draws_no_fans():
    from digital_rain import surfaces

    labels = np.full((40, 60), surfaces.FRONT, np.uint8)
    labels[18:] = surfaces.FLOOR
    guessed = (0.5, 0.4, surfaces.ESTIMATE_CONFIDENCE)
    assert surfaces.has_box(_box(labels, guessed))
    assert not surfaces.confident_box(_box(labels, guessed))


def test_a_floor_and_a_backdrop_are_no_box_even_with_a_fixed_point():
    # a car on a road, a field below a cliff: no side wall, no fans
    from digital_rain import surfaces

    labels = np.full((40, 60), surfaces.FRONT, np.uint8)
    labels[18:] = surfaces.FLOOR
    labels[:18, -6:] = surfaces.WALL_RIGHT
    assert not surfaces.confident_box(_box(labels, (0.5, 0.4, 0.9)))
    corridor, planes = _corridor()
    assert surfaces.confident_box(_box(corridor, (0.5, 0.4, 0.9), planes=planes))


def test_a_corridor_or_an_up_view_keeps_its_fans_with_a_guessed_point():
    from digital_rain import surfaces

    labels, planes = _corridor()
    guessed = (0.5, 0.4, surfaces.ESTIMATE_CONFIDENCE)
    assert surfaces.confident_box(_box(labels, guessed, planes=planes))
    floor = np.full((40, 60), surfaces.FLOOR, np.uint8)
    assert surfaces.confident_box(_box(floor, guessed, surfaces.CAMERA_UP))


def test_a_shallow_depth_ramp_is_no_corridor():
    # a portrait's backdrop or a graphic: "walls" on both sides, but barely receding
    from digital_rain import surfaces

    labels, planes = _corridor(wall_slope=0.4)
    guessed = (0.5, 0.4, surfaces.ESTIMATE_CONFIDENCE)
    assert not surfaces.confident_box(_box(labels, guessed, planes=planes))


def test_surfaces_on_the_wrong_side_of_the_point_are_no_box():
    from digital_rain import surfaces

    labels, planes = _corridor()
    swapped = labels.copy()
    swapped[labels == surfaces.WALL_LEFT] = surfaces.WALL_RIGHT
    swapped[labels == surfaces.WALL_RIGHT] = surfaces.WALL_LEFT
    assert not surfaces.confident_box(_box(swapped, (0.5, 0.4, 0.9), planes=planes))


def test_on_side_makes_a_wrong_side_patch_frontal():
    from digital_rain import surfaces

    labels, planes = _corridor()
    labels[2:8, 20:26] = surfaces.FLOOR  # a "floor" above the vanishing point
    labels[30:34, 50:54] = surfaces.WALL_LEFT  # a left wall right of it
    fixed = surfaces.on_side(_box(labels, (0.5, 0.4, 0.9), planes=planes)).labels
    assert (fixed[2:8, 20:26] == surfaces.FRONT).all()
    assert (fixed[30:34, 50:54] == surfaces.FRONT).all()
    assert (fixed[:, :15] == surfaces.WALL_LEFT).all()
    assert (fixed[30:, 20:40] == surfaces.FLOOR).all()
    up = surfaces.on_side(_box(labels, (0.5, 0.4, 0.9), surfaces.CAMERA_UP, planes))
    assert (up.labels == labels).all()


def test_a_stray_ceiling_does_not_unfix_the_vanishing_point():
    from digital_rain import surfaces

    _, planes = _corridor()
    point = surfaces._vanishing(planes)
    assert point[2] > surfaces.ESTIMATE_CONFIDENCE
    stray = planes + (surfaces.Plane(surfaces.CEILING, -0.3, -0.5, 0.3, 0.06),)
    again = surfaces._vanishing(stray)
    assert again[2] > surfaces.ESTIMATE_CONFIDENCE
    assert abs(again[0] - point[0]) < 0.01 and abs(again[1] - point[1]) < 0.01


def test_detect_stable_is_the_same_for_every_run():
    from digital_rain import surfaces

    h, w = 64, 96
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    disparity = np.maximum(np.abs(u[None, :] - 0.5) * 1.6, (v[:, None] - 0.4) * 1.5)
    disparity = disparity.astype(np.float32)
    first, again = surfaces.detect_stable(disparity), surfaces.detect_stable(disparity)
    assert surfaces.confident_box(first) == surfaces.confident_box(again)
    assert first.vanishing == again.vanishing


# Listing subfolders
def _names(paths, root):
    return [str(p)[len(str(root)) + 1 :].replace("\\", "/") for p in paths]


@pytest.fixture
def tree_of_pictures(tmp_path):
    for rel in ("top.png", "b/two.jpg", "a/one.png", "a/deep/three.webp", "a/notes.txt"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.png").write_bytes(b"x")
    (tmp_path / "$RECYCLE.BIN").mkdir()
    (tmp_path / "$RECYCLE.BIN" / "gone.png").write_bytes(b"x")
    (tmp_path / "folder.png").mkdir()  # a folder with a picture's name is not a picture
    return tmp_path


def test_listing_without_subfolders_reads_only_the_top_folder(tree_of_pictures):
    assert _names(il.list_images(str(tree_of_pictures)), tree_of_pictures) == ["top.png"]


def test_listing_with_subfolders_reads_every_folder_in_name_order(tree_of_pictures):
    found = il.list_images(str(tree_of_pictures), subfolders=True)
    assert _names(found, tree_of_pictures) == [
        "top.png",
        "a/one.png",
        "a/deep/three.webp",
        "b/two.jpg",
    ]


def test_listing_skips_folders_with_the_hidden_attribute(tree_of_pictures):
    if not hasattr(il.stat, "FILE_ATTRIBUTE_HIDDEN"):
        pytest.skip("Windows file attributes")
    import ctypes

    folder = tree_of_pictures / "b"
    assert ctypes.windll.kernel32.SetFileAttributesW(str(folder), il.stat.FILE_ATTRIBUTE_HIDDEN)
    found = il.list_images(str(tree_of_pictures), subfolders=True)
    assert "b/two.jpg" not in _names(found, tree_of_pictures)


def test_listing_stops_at_the_depth_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(il, "MAX_FOLDER_DEPTH", 2)
    folder = tmp_path
    for level in range(4):
        (folder / f"p{level}.png").write_bytes(b"x")
        folder = folder / "deeper"
        folder.mkdir()
    found = il.list_images(str(tmp_path), subfolders=True)
    assert [os.path.basename(p) for p in found] == ["p0.png", "p1.png", "p2.png"]


def test_listing_stops_at_the_picture_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(il, "MAX_PICTURES", 3)
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        for k in range(2):
            (tmp_path / sub / f"{k}.png").write_bytes(b"x")
    assert len(il.list_images(str(tmp_path), subfolders=True)) == 3


def test_layer_reads_subfolders_only_when_the_setting_is_on(tmp_path, monkeypatch):
    monkeypatch.setenv("MATRIX_IMAGE_SYNC", "1")
    (tmp_path / "trips").mkdir()
    save_png(tmp_path / "trips" / "a.png", converging_lines(64, 48, (32, 20)))
    with pytest.raises(ValueError, match="no images"):
        make_layer(tmp_path)
    layer = make_layer(tmp_path, image_subfolders=True)
    assert _names(layer.files, tmp_path) == ["trips/a.png"]
    layer.close()


def _blocked_depth(monkeypatch):
    """Grid-mode depth network that finishes a picture only when the returned event is set."""
    release = threading.Event()
    done = []

    def fill(path, _load):
        release.wait(5)
        done.append(os.path.basename(path))
        return True

    monkeypatch.setattr(il.surfaces, "can_estimate", lambda: True)
    monkeypatch.setattr(il.surfaces, "fill_cache", fill)
    return release, done


def test_first_picture_waits_for_its_depth_map(folder_of_pictures, monkeypatch):
    monkeypatch.delenv("MATRIX_IMAGE_SYNC")
    release, done = _blocked_depth(monkeypatch)
    layer = make_layer(folder_of_pictures, image_mode="grid")
    # the network is still loading: no preparation starts, plain rain carries on
    assert layer.update(il.TUNING.start, 0.0) == il.IMAGE_OFF
    assert not layer.jobs
    assert layer.depth_next == 0
    release.set()
    deadline = time.monotonic() + 5
    while 0 not in layer.depth_done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done[0] == "a.png"
    t = il.TUNING.start
    while layer.number < 0 and time.monotonic() < deadline:
        layer.update(t, 0.0)
        for future in list(layer.jobs.values()):
            future.exception(5)
        t += 0.1
    layer.close()
    assert layer.number == 0


def test_depth_wait_has_a_limit(folder_of_pictures, monkeypatch):
    monkeypatch.delenv("MATRIX_IMAGE_SYNC")
    release, _ = _blocked_depth(monkeypatch)
    monkeypatch.setattr(il, "TUNING", dataclasses.replace(il.TUNING, depth_wait=0.05))
    layer = make_layer(folder_of_pictures, image_mode="grid")
    layer.update(il.TUNING.start, 0.0)
    assert not layer.jobs
    time.sleep(0.1)
    # past the limit the picture is prepared without its depth map
    layer.update(il.TUNING.start + 0.1, 0.0)
    assert 0 in layer.jobs
    release.set()
    layer.close()


def test_classic_mode_and_sync_layers_never_wait(folder_of_pictures, monkeypatch):
    _blocked_depth(monkeypatch)[0].set()
    sync_grid = make_layer(folder_of_pictures, image_mode="grid")
    assert not sync_grid._depth_pending(0)
    sync_grid.close()
    monkeypatch.delenv("MATRIX_IMAGE_SYNC")
    classic = make_layer(folder_of_pictures, image_mode="classic")
    assert not classic.warming
    assert not classic._depth_pending(0)
    classic.close()
