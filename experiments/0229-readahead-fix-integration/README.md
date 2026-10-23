# 0229 — the read-ahead fix in the shared builds

**Question.** Exp 0228 (F287) found that exp 0227's read-ahead fix loads the second title as fast as the read-ahead
off, and gives the clock voice's queue the best tail, with no frame, timeout or crash regression. The top session
decided to integrate it under the maintainer's rule; it sets the launchers back to `KYTY_BC5_APR_READAHEAD=4` itself. Do
both shared builds work with the fix?

**Setup.**
- The patch is `patch_0227-readahead-fix.diff` (copied from exp 0227) against the tree since exp 0222.
  - `libAmpr.cpp` md5 `eaef1da1…` → `5f2ec30b…`, the source of exp 0228's FIX binary.
  - A reader leaves to the worker any buffer over `KYTY_BC5_APR_READAHEAD_MAX_KIB` (default 1024) and any buffer the
    worker would read on `KYTY_BC5_APR_PARALLEL` threads (`ra_state = 4`).
  - `git apply --check` passes. No other file under `src/` is newer than the shared binaries: normal `7a37a560…`, lean
    `a3456df9…`, exp 0222's builds.
- `rebuild0229.sh` is exp 0222's `rebuild0222.sh` with this patch.
  - It keeps `~/bc5-work/exp0229/kyty_emulator{,-lean}.before-fix` and `src/libAmpr.before-fix.cpp`.
  - A failure puts all three back; the source gets a new mtime, so ninja recompiles it.
- `chain0229.sh` holds one lock line for the rebuild and three smoke runs. Any failure rolls everything back.
  - S4N: the second title, normal build, O2's route, 300 s, with the clock voice's journal (`run0229.sh`, exp 0222's
    runner with `KYTY_BC5_APR_READAHEAD=4` set; the launchers default to 0 until the top session changes them).
  - S4L: the lean build, 150 s.
  - S4A: ASTRO BOT, normal build, read-ahead on, 100 s (`run0229a.sh`, exp 0228's runner with this directory and a
    launcher copy `play-astro-0229.sh`). The launchers will turn the read-ahead on for both titles.
  - Pass criteria:
    - S4N: the full time, reader threads, read-ahead lines, in-order copies, the completion sequence increasing, no
      crash or kernel line, the live saves back;
    - S4L and S4A: the full time, no crash or kernel line, the live saves back.
  - Afterwards S4N's GPU journal is read with exp 0214's `ra0214.py` and `gu0214.py`.
- Box use: only after the user's approval in this session and the top session's Go.
  - The maintainer's "zgoda" in the top session was relayed here but not acted on: writes to the shared tree need the
    user's own approval in this session.
  - The user approved here at ~11:29; the chain ran 11:30:04–11:40:36 under one lock line.
  - The kernel log was streamed to the laptop (`raw/kernel-stream.txt`). The stream's ssh was reset by the network at
    ~11:31, so it was restarted with `--since 11:30` (`raw/kernel-stream-2.txt`). The chain's own dmesg checks cover
    the whole run.

**Result** (`raw/chain.out`, `raw/rebuild.out`, `raw/S4*-summary.txt`, `raw/S4N-frames.txt`, `raw/S4N-giveups.txt`).
1. **The tree and the rebuild.**
   - `libAmpr.cpp` `eaef1da1…` → `5f2ec30b…`.
   - Each build compiled only `libAmpr.cpp.o` and relinked: 14 s and 12 s, rc 0, only the three old warnings.
   - Normal `7a37a560…` → `2780a9a6…`, lean `a3456df9…` → `1fc8ae07…`; synced.
   - The old files are kept as `~/bc5-work/exp0229/kyty_emulator{,-lean}.before-fix` and `src/libAmpr.before-fix.cpp`.
2. **S4N, the second title, normal build, 300 s (11:30:32–11:35:46). Passed.**
   - 12 reader threads, 258 read-ahead lines, 360 in-order copies, the completion sequence never decreased.
   - No crash or kernel line; the live saves were back identical.
   - Frames:
     - 39.2 flips/s (41.6 for t ≥ 100 s), 25.5 ms mean between flips;
     - over 100 ms 39, over 250 ms 4, over 1 s 0, max 533 ms;
     - TIMEOUT, fault and reopen 0.
   - Given-up waits 9: 0x12004b5438 7, 0x12004b4838 2.
   - The readers used 1.5 s of CPU in 286 s (0.53 % of one core), the workers 1.39 %.
   - Drive probe 588 MB/s; read_ahead_kb 1024 (the maintainer's setting) in all three runs.
3. **S4L, the lean build, 150 s (11:35:46–11:38:29). Passed.** 12 reader threads, no crash or kernel line, saves
   identical.
4. **S4A, ASTRO BOT, normal build, read-ahead on, 100 s (11:38:29–11:40:22). Passed.**
   - `KYTY_BC5_APR_READAHEAD=4` reached the emulator (`/proc/<pid>/environ`).
   - No crash or kernel line; the live saves were back identical.
   - It read 12.5 GB (rchar) in 200 samples. The summary line says "0 MiB" because the sampler's last line was taken
     as the emulator exited and is empty.

**Verdict.**
- **Exp 0227's read-ahead fix is in `~/src/KytyPlus` and both shared builds since 2026-10-23 11:30.** All three smoke
  runs passed, with read-ahead on for both titles.
- The top session switches the launchers back to `KYTY_BC5_APR_READAHEAD=4` and regenerates patch 0001 from the tree.
- Rollback: copy the `*.before-fix` files back; copy the source without `cp -p`, so ninja recompiles it.
- Still to watch, as in F273 and F287: given-up waits on 0x12004b5438 (7 in S4N).
