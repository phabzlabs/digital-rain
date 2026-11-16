"""Live load mode: the rain follows the machine's CPU or GPU load.

LoadSampler runs a daemon thread that samples once a second and keeps a smoothed
load (0..1). LiveControl turns that load into speed and density factors for the
renderers and eases them, so neither a load jump nor a sampler failure makes the
rain jump. Any failure leaves the rain normal; nothing here raises into the
render loop.
"""

import contextlib
import math
import sys
import threading

from digital_rain import osapi

SAMPLE_PERIOD = 1.0
TAU = 3.0  # smoothing and easing time constant, s
ALPHA = 1.0 - math.exp(-SAMPLE_PERIOD / TAU)
MAX_FAILS = 3


class UnavailableError(Exception):
    pass


class LoadSampler:
    def __init__(self, source):
        self.source = source
        self._value = None
        self._ready = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="live-load", daemon=True)
        self._thread.start()

    def value(self):
        return self._value if self._ready else None

    def alive(self):
        return self._thread.is_alive()

    def stop(self):
        self._stop.set()
        self._thread.join(1.5)

    def _run(self):
        closer = None
        try:
            if self.source == "cpu":
                sample, closer = self._cpu_sampler()
            elif self.source == "gpu":
                sample, closer = self._gpu_sampler()
            else:
                raise UnavailableError("unknown source")
            self._loop(sample)
        except UnavailableError as exc:
            self._fail(str(exc))
        except Exception as exc:  # never reaches the render loop
            self._fail(f"{type(exc).__name__}: {exc}")
        finally:
            if closer is not None:
                with contextlib.suppress(Exception):
                    closer()

    def _fail(self, reason):
        self._ready = False
        self._value = None
        print(f"live load unavailable ({reason}); rain stays normal", file=sys.stderr)

    def _loop(self, sample):
        sample()  # priming sample, discarded
        fails = 0
        avg = None
        while not self._stop.wait(SAMPLE_PERIOD):
            try:
                load = sample()
            except UnavailableError:
                raise
            except Exception:
                load = False
            if load is False:
                fails += 1
                if fails >= MAX_FAILS:
                    raise UnavailableError(f"{MAX_FAILS} failed samples in a row")
                continue
            fails = 0
            avg = load if avg is None else avg + (load - avg) * ALPHA
            self._value = avg
            self._ready = True

    def _cpu_sampler(self):
        try:
            import psutil
        except ImportError as exc:
            raise UnavailableError(f"psutil missing: {exc}") from exc
        # kept: a new Process always reads 0.0
        proc = psutil.Process()
        ncpu = psutil.cpu_count() or 1
        psutil.cpu_percent(interval=None)
        proc.cpu_percent(interval=None)

        def sample():
            total = psutil.cpu_percent(interval=None)
            own = proc.cpu_percent(interval=None) / ncpu
            return min(100.0, max(0.0, total - own)) / 100.0

        return sample, None

    def _gpu_sampler(self):
        try:
            return osapi.gpu_load_sampler()  # PDH on Windows
        except Exception as exc:
            raise UnavailableError(str(exc)) from exc


class LiveControl:
    def __init__(self, cfg, sampler=None):
        self.cfg = cfg
        self.speed_k = 1.0
        self.density_k = 1.0
        self.load = None
        self.sampler = sampler
        if sampler is None and cfg.get("live_source", "off") != "off":
            self.sampler = LoadSampler(cfg["live_source"])

    def update(self, dt):
        if self.sampler is None:
            return 1.0, 1.0
        load = self.sampler.value()
        self.load = load
        s = float(self.cfg.get("live_strength", 0.6))
        target = self.cfg.get("live_target", "both")
        tspeed = tdens = 1.0
        if load is not None:
            if target in ("speed", "both"):
                tspeed = 1.0 + s * (2.0 * load - 1.0) * 0.5
            if target in ("density", "both"):
                tdens = 1.0 - s * 0.75 * (1.0 - load)
        a = 1.0 - math.exp(-max(dt, 0.0) / TAU)
        self.speed_k += (tspeed - self.speed_k) * a
        self.density_k += (tdens - self.density_k) * a
        return self.speed_k, self.density_k

    def close(self):
        if self.sampler is not None:
            self.sampler.stop()
