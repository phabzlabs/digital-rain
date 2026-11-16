Golden frames of the film looks, checked by tools/checks/check_film.py and tools/checks/check_looks.py.

Eight GPU frames (gpu_<preset>_<upscaling>.png: film_1999, reloaded, resurrections and custom at
1024x576 with upscaling off and quality, t = 5 s) and the SHA-256 of four software
frames (soft_hashes.json: the same presets at 800x600, t = 5 s), all rendered by
tools/checks/frame_harness.py.

Which commit each set comes from (the hashes and #36 refer to the development history before
the project was published, which this repository does not contain):

  custom                       2575ea6 (the base SHA before the film looks), unchanged since.
  film_1999                    the commit that added the clustered lanes (`cluster`), lead_ratio 0.46,
                               lead_cap 0.55 and the ink_dots mask on top of the leader core.
  reloaded                     the film look retune of #36 (toe palette floor), re-recorded on
                               Windows at 25182de. Before that: the glyph size and clarity commit.
  resurrections                the film look retune of #36, re-recorded on Windows at 25182de. Before
                               that: the depth slices commit (six slices with depth on). These guard against
                               later drift only; custom is the proof that neutral values skip the
                               new code paths (film_1999 and reloaded moved with the clarity work).

Commands, from the repository root (a worktree at the base SHA gives the old renderer):

    git worktree add %TEMP%\mx_base_2575ea6 2575ea6
    .venv\Scripts\python.exe tools/checks/frame_harness.py --root %TEMP%\mx_base_2575ea6 --out tools/checks/golden golden --presets custom
    git worktree remove %TEMP%\mx_base_2575ea6

    .venv\Scripts\python.exe tools/checks/frame_harness.py --root . --out tools/checks/golden golden --presets film_1999
    .venv\Scripts\python.exe tools/checks/frame_harness.py --root . --out tools/checks/golden golden --presets reloaded
    .venv\Scripts\python.exe tools/checks/frame_harness.py --root . --out tools/checks/golden golden

`golden --presets NAME[,NAME]` writes GPU PNGs only for the presets named and merges
their soft_<preset> hashes into soft_hashes.json; the default is resurrections (the only
preset whose goldens change with the code). Regenerate film_1999 and reloaded only when digital_rain/looks.py changes their values on purpose;
the custom run needs a worktree at the commit named above, so it can only be re-run from that
history; leave the custom goldens as they are.

The GPU frames are valid for the build machine's GPU and driver. After a GPU or
driver change, regenerate them with the same commands. The software hashes do not
depend on the GPU.

Checks: tools/checks/check_looks.py compares the software hashes exactly; tools/checks/check_film.py
compares the GPU frames (at most 0.1 percent of pixels with any channel off by more
than 1 unit, and no channel off by more than 8 units).
