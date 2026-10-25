# 0291 — what output resolution the host reports to the second title

**Question.** Which display or output resolution does the host report to the second title, and does the title choose
its internal render resolution from it? If the title is told "4K" and renders for it while the maintainer's TV is Full
HD (the launcher runs fullscreen at the display's resolution), reporting 1080p could cut GPU time. This is the top
session's item 2 on lowering GPU load, added at the maintainer's request.

**Setup.**
- Step 1, offline, from these sources:
  - the KytyPlus base f266548 (`refs/Coder787-source_KytyPlus`), with patch 0001 on main
    (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`) applied to its `src/` in a scratch copy;
  - the launcher copies in the repo (`experiments/0188-audioout2-advanced-grains/play-pkg.sh`, the newest);
  - HANDOFF F67, F101, F102, F155, F159, F237 and exp 0095.
  - The box was not touched: the maintainer was playing, and the top session's pause holds until its GO.
- Step 2 (prepared, not run): a switch and an A/B, described under Plan.

**Result (step 1).**
1. **What the host answers.**
   - `VideoOutGetOutputStatus` sets `resolution = 2` when the VideoOut size is at least 3840 wide or 2160 high, and
     `1` otherwise. `dynamicRange` is always 1. `refreshRate` is 59.94 Hz, or 119.88 Hz in the 120-Hz output mode or
     with `--vblank-frequency` ≥ 119 (`src/graphics/presentation/videoOut.cpp`, f266548:1650-1676).
   - The VideoOut size is set once, in `VideoOutDriver::Impl::Init`, from `Config::GetScreenWidth/Height()`
     (`src/libs/agc.cpp:55-60`). Those come only from `--screen-width`/`--screen-height` (`src/main.cpp`), default
     1280×720 (`emulatorConfig.h:62-63`).
   - The launcher passes `--fullscreen` plus `PLAY_ARGS` from `bc5-run.env`, which was empty in the play logs of
     2026-10-24 (exp 0268). `--fullscreen` sets only `fullscreen_enabled`, which makes the SDL window
     `SDL_WINDOW_FULLSCREEN_DESKTOP` (`window.cpp`). It does not change the VideoOut size.
   - Patch 0001 changes none of this. No hunk touches `screen_width`/`screen_height`, the output status or the
     VideoOut size; `Init` is the only writer of `ctx.width`.
   - So today the title is told **resolution 1, SDR, 59.94 Hz**, i.e. not 4K, if it asks at all.
   - Output modes: `VideoOutIsOutputSupported` and `VideoOutConfigureOutput` accept only
     `VIDEO_OUT_OUTPUT_MODE_DEFAULT` (1) and the 119.88-Hz mode (0xF). Any other mode is
     `VIDEO_OUT_ERROR_UNSUPPORTED_OUTPUT_MODE` (`ValidateOutputConfig`).
   - TODO(verify) what 1 and 2 stand for on the console. The base's comparison suggests "not 4K" and "4K".
2. **What the title does anyway.**
   - It registers two 3840×2160 display buffers (`sceVideoOutRegisterBuffers2`, run 351 of exp 0095; F155).
   - Its UI layers are 3840×2160 (F159).
   - At the menu it renders its scene at 2560×1440 and upscales it to the 3840×2160 display buffer in the pass that
     composites the UI (exp 0095).
   - So with "not 4K" reported it still builds a 4K output, and the presenter scales it down to the 1920×1080
     display (F67 noted the same downscale for ASTRO BOT).
   - Not known: whether the title asks `GetOutputStatus` or the output-mode calls at all. With logging off in play
     (`--printf-direction Silent`), no log shows the calls, and no committed log has them (searched
     `experiments/`).
   - For comparison: ASTRO BOT asks nothing about the output mode and registers its own 4K buffers (F67). Its 3D
     size follows the GPU timestamp scale (F101, F102). The second title instead slows down at a higher timestamp
     scale rather than lowering its resolution (F237).
3. **Reading.**
   - Reporting 1080p is already what the host does, so a "1080p" switch would change nothing.
   - The 4K display pass (the upscale plus the UI composite at 3840×2160) and the 4K UI layers are the title's own
     choice. The data give no sign that they follow the reported output.
   - A host-side lever exists only if the title reads the status or the output modes and reacts. That is what the
     A/B below decides.

**Setup (step 2, run 2026-10-25 02:11–02:24 on the top session's GO).**
- The switch (`patch_0291-lf.diff`, the change as text with LF endings):
  - `KYTY_BC5_VIDEOOUT_REPORT=<2160p|4k|1080p|n>`, unset by default, overrides the `resolution` field of
    `VideoOutGetOutputStatus`.
  - Diagnostic stderr lines, one each, beginning "bc5 videoout:":
    - the first `GetOutputStatus` call and any call that gets a different answer;
    - each `RegisterBuffers2` (size, pitch, pixel format, tiling);
    - the first 16 `IsOutputSupported` modes;
    - every `ConfigureOutput` mode.
  - Unset, the host's answers are unchanged; only the lines are new.
- `apply0291.py` applies the change to a copy of the shared tree's `videoOut.cpp` on the box, keeping its line
  endings. Each new line takes the ending of the line it follows. The file is mostly CRLF, and editing it on the
  Windows laptop had rewritten every ending.
- `prep0291.sh` (one file plus a link, no GPU, about 5 min under a lock):
  - writes the exact `patch_0291.diff` against the tree, checks it with `git apply --check` (the tree is not
    written), and checks that its changed lines equal `patch_0291-lf.diff`'s;
  - regenerates the normal shared build's compile database and builds `~/bc5-work/exp0291/bin/kyty_emulator` with
    `build0291.py`. The shared builds are not written. The file name stays `kyty_emulator`, so the process name
    matches the box's guards.
- `run0291.sh <tag> <report|-> 300`: exp 0203's O2 route through `play-pkg.sh` with `BC5_EMU` set to the test
  binary.
  - The live saves are kept aside and checked with `diff -rq`; only the run's own PID is stopped; the box's memory
    is sampled.
  - The run's "bc5 videoout:" lines go to `raw/<tag>-videoout.txt`.
  - `gpu0291.py` gives flips/s, mean and median GPU-busy ms per frame, and frames over 100/250 ms from the journal.
- Runs, one each, the same route and the launcher's defaults in both:
  - A: `-`, today's answer, 1;
  - B: `2160p`.
  - Both arms run with RT off (`KYTY_BC5_RT=0`), at the top session's request for the overnight slot. `run0291.sh`
    sets it by default; `EXTRA_ENV` overrides it.
- Reading:
  - No "GetOutputStatus" or output-mode line in A: the title never asks, and no reported value can change its
    output. The 4K display pass stays; GPU savings must come from elsewhere (for this title not the timestamp
    scale, F237).
  - It asks, and B registers the same 3840×2160 buffers with the same GPU time: the answer is ignored.
  - It asks, and B differs (buffers, GPU busy, flips): the field is a lever. A third run with a lower value (`0`)
    follows, then a check of the scene size at the menu.
- On the laptop:
  - `kstream0291.sh` streamed the kernel log for the whole stretch and ended by itself.
  - `arm0291.sh` ran each arm attended and would have stopped the run's emulator at the first new amdgpu line, as
    the top session asked.
- The box's `play-pkg.sh` (md5 65d35963…) passes `--fullscreen` and an empty `PLAY_ARGS` (`bc5-run.env`), no
  `--screen-width`. `KYTY_BC5_RT=0` is read by the emulator itself (the launcher's line 89).
- Boot 831e5915.

**Result (step 2).**
4. **Build (02:12; `raw/build.txt`).**
   - `apply0291.py` kept the file's endings: 2,201 lines with 2,173 CRLF became 2,254 with 2,226 CRLF, the 53 new
     lines taking CRLF from their neighbours.
   - The exact `patch_0291.diff` passes `git apply --check` on the tree, and its changed lines equal
     `patch_0291-lf.diff`'s. The tree was not written. That patch stays on the box (`~/bc5-work/exp0291`), because
     its CRLF lines would not survive this laptop's checkout; `apply0291.py` remakes it.
   - The first try failed on ninja's response file (`raw/build-try1.txt`). `ninja -t compdb -x` expands it, as in
     exp 0193.
   - The test binary `bin/kyty_emulator` (md5 5c487284…) has two warnings, neither in the new lines: a deprecation in
     `stringUtils.h`, and `Bc5VideoOutEventName` unused, which predates this change.
5. **The title asks once, and builds 4K whatever it is told (`raw/A-videoout.txt`, `raw/B-videoout.txt`).**
   - In both arms the title calls `GetOutputStatus` once at start (handle 1) and then registers its display buffers.
   - It asks `IsOutputSupported` for the 119.88-Hz mode (0xF) at least 16 times (the cap of the line). It gets
     false (vblank 60) and never calls `ConfigureOutput`.
   - A, told 1 (today's answer, base 1, VideoOut size 1280×720), refresh rate 3 (59.94 Hz): two 3840×2160 buffers,
     pixel format 0x8100000022000000, tiling 0.
   - B, told 2: the same two 3840×2160 buffers, same format and tiling.
6. **The same GPU time and frame rate (`raw/A-gpu.txt`, `raw/B-gpu.txt`).**

   | arm | told | flips/s (t ≥ 100 s) | GPU busy per frame, mean / median (t ≥ 100 s) | frames > 250 ms |
   | --- | --- | --- | --- | --- |
   | A | 1 | 40.0 (42.1) | 14.4 / 13.9 ms (13.7 / 13.8) | 4 |
   | B | 2 | 39.4 (41.5) | 14.3 / 13.7 ms (13.6 / 13.4) | 4 |

7. **Safety.**
   - Both arms ran the full 300 s, with no crash line and no kernel line. The laptop's stream
     (`raw/kernel-stream.txt`) has only IPv6 MLD lines, 0 amdgpu.
   - The live saves were back and identical after each run (`raw/*-restore-back.txt`). The fingerprint of
     `_SaveData` (md5 of the sorted per-file md5s) was 9a570264db730059 before and after.

**Verdict.**
- **The reported output resolution is no lever for the second title.** It asks `sceVideoOutGetOutputStatus` once at
  start, but registers 3840×2160 display buffers whether it is told 1 or 2. Its GPU time per frame (14.3–14.4 ms)
  and frame rate (39–40 flips/s) do not change.
- The host already tells it "not 4K" (1, from the default 1280×720 VideoOut size), so a "report 1080p" switch has
  nothing to change either.
- Its 4K display pass and 4K UI layers are its own fixed choice. The presenter scales the 4K output to the 1080p
  display, as for ASTRO BOT (F67).
- GPU savings for this title have to come from elsewhere. Lowering the output would mean rewriting its own passes
  (F67). The timestamp scale slows it rather than lowering its resolution (F237).
- `KYTY_BC5_VIDEOOUT_REPORT` and the "bc5 videoout:" lines live only in the test binary, `patch_0291` was not put
  into the tree, and the launchers are unchanged.
