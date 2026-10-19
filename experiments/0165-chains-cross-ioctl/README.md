# 0165 — Submission chains for the game thread: `COND_EXEC` segment-local, chains across its ioctls

**Question.** With a `COND_EXEC` no longer closing a chain (ADR 0010 §A) and the game thread's chain
held across its submit ioctls (ADR 0010 §B, `BC5_DIRECT_CHAIN=2`, 2 ms hold), do the second title's
graphics buffers share kernel submissions, does its render thread's host cost fall with them (F210,
F213), does the frame rate follow, and does it run without faults of its own?

**Setup.**
- Box: BC-250, kernel 7.2.9-ogc3.1 (as 0163), Mesa 26.2.3, libdrm 2.4.134, 8C/16T, 40 CU.
- KytyPlus `f266548` + `backend/kytyplus-patches/0001-bc5-lle-agc.patch` of this commit: the chain
  slot (`ChainSlot`, `chain_submit`, the `bc5-chainwd` watchdog, `chain_observe`,
  `chain_soft_push`, the kept waits captured per segment, the `COND_EXEC` count growth in the
  compute-form `DISPATCH_INDIRECT` rebuild), the event-queue hook in `kernel/eventQueue.cpp`;
  the regenerated patch also carries the window-menu session's in-progress edits of the same tree
  (experiment 0164). Backend of this commit: the PFP-sync insertion through `insert_before`, the
  GPU check's per-range overflow fallback (`indirect_check::apply`), 55 unit tests passing
  (MSVC, Windows). Built with `cmake --build ~/bc5-work/backend-ubuntu` and
  `cmake --build ~/bc5-work/kytyplus-build --target kyty_emulator` in the `ubuntu` distrobox
  (`~/bc5-work/seq0165.sh`, `build-0165.log`).
- Route and driver as experiments 0162/0163: `input799.cmd` (start screen, slot 1, Continue; the
  save loads into the night-scene gameplay at about +121 s), `play-pkg-log.sh` settings, 200 s per
  run, `drive0163.sh N` (`cpu-sampler.sh` from +125 s for 70 s, the kernel log before and after),
  `KYTY_BC5_VIDEOOUT_TRACE=1`. The three runs ran back to back from one script.
- Runs 801 (`BC5_DIRECT_CHAIN=1`) and 802 (`=2`) of the first build deadlocked at the first
  submission (the submission path's mapping sync calls `wait_jobs` → `chain_flush` on the same
  thread, which took the new flush lock twice; no flip, no journal line, `raw/drive801.log`,
  `drive802.log`); fixed (the early empty check before the lock, the lock recursive) and rerun as
  804 and 805 with the binary of 09:55.
- Run 803: chains off (the baseline with this build; run 799 of 0163 is the earlier baseline).
- Run 804: `BC5_DIRECT_CHAIN=1` (the chains of one call, `COND_EXEC` segment-local, §A).
- Run 805: `BC5_DIRECT_CHAIN=2` (also across the game thread's ioctls, §B; `BC5_DIRECT_CHAIN_HOLD_US`
  at its default 2000).
- `chains.py` here (0163's, plus the dwords per submission by kind): flips per second from the
  trace, the threads' CPU from the sampler, submissions per second and the chain statistics from
  the direct journal. `analyze0165.sh` ran it on the box; `raw/` holds the sampled trace, the CPU
  samples, the journal excerpts (`chains:` lines, every 50th CPU-side wait, the hold and rebuild
  lines), the kernel log after each run and the driver logs.

**Result.**
- **All three runs played the full 200 s** (start screen, menu, the save load, the night-scene
  gameplay from about +153 s), with the F208 geometry-engine fault bursts in each (9 `page fault`
  lines in the last 40 of each kernel log, client GE2, pages 0x0–0xf000, `Render Thread`), no ring
  timeout, no reset, no failed submission (`raw/kernel-80N-after.txt`, `journal-80N-excerpt.txt`).
- **Gameplay, t 155–200 s of each run** (`chains.py`):

  | | run 803 (off) | run 804 (`=1`) | run 805 (`=2`) |
  |---|---|---|---|
  | kernel submissions/s | 4,463 | 2,638 | 1,658 |
  | dwords per graphics submission (`dcb`) | 2,586 | 2,584 | 13,084 |
  | dwords per compute submission (`acb`) | 403 | 1,543 | 1,237 |
  | flips/s (mean / median) | 33.1 / 32.8 | 35.0 / 34.7 | **45.1 / 45.7** |
  | flips/s (min / max over the 45 s) | 30.3 / 38.9 | 28.2 / 41.2 | 42.2 / 47.9 |
  | `Render Thread` CPU (mean / median) | 92.7 / 94 % | 99.1 / 101 % | **82.7 / 86 %** |
  | `game-main` CPU | 59 % | 61 % | 63 % |
  | `bc5-ring` CPU | 33 % | 19 % | 32 % |
  | `kyty-gpu` CPU | 8 % | 25 % | 11 % |
  | CPU-side waits given up in the window | 0 | 0 | 1 |

  The whole-run flip counts of the last trace second: 36 (803), 38 (804), 48 (805).
- **Chains.** Run 804 (one call): 382,450 chains for 679,765 buffers at +200 s, 1.78 a chain,
  73 % single; 129,885 segments held `COND_EXEC` and none closed a chain (`cond_exec 0`); closings:
  the end of the call 93 %, a CPU-side wait 7 %. The graphics buffers still went one per submission
  (2,584 dwords, as 803): the game thread hands over one `dcb` per ioctl, so §A alone changes its
  count by nothing; the ring thread's ACBs chained as in 0163 (`bc5-ring` 33 → 19 %).
  Run 805 (across ioctls): 210,432 chains for 868,955 buffers, **4.1 a chain, 34 % single**; the
  graphics submissions carry five buffers on average (13,084 dwords); closings: a CPU-side wait
  41 % (the ring thread's waits on graphics labels and the game thread's cross-queue waits), the
  end of a ring slice 40 %, the ACB head split 11 %, the flip's drain 3 %, the hold bound 3 %
  by the watchdog (6,424 chains) and 2.8 % by the owner at the ioctl's end, the observe points 0
  (the title never asked "submit done"/"wait idle" and its event-queue waits found no held chain).
  `mec rebuild` overflow lines: none in any run.
- **Given-up waits.** Run 805 has 23 in the whole run, all between t 5.2 and 9.2 s (the intro: the
  ring thread's 233-dword ACBs waiting on two labels, given up after 10–28 ms), none after; run
  803 has 4 (the same place and kind), run 804 none. The window's one in 805 is the chains.py
  attribution of a start-up line by the nearest timing line, not a gameplay wait.
- **Where the time went.** The render thread's share fell with the submissions (F210: three quarters
  of it was the per-submission path); the frame rate rose from 33 to 45 of the 60 asked. The
  `kyty-gpu` thread's CPU rose in 804 (8 → 25 %) and less in 805 (11 %): not understood (the
  compute chains' completion handling?), noted for the next run with `eu-sampler.sh`.
- Runs 804 and 805 ran on a tree that also held the window-menu session's in-progress edits
  (experiment 0164); the binary of 09:55 was linked with them. The patch of this commit is the
  union patch of origin/main (ports 1–4 + the menu) with this experiment's host edits on top,
  regenerated from a scratch worktree at `f266548`; it was not compiled as a whole here (the
  host objects of this experiment compiled on the box tree).

**Verdict.** Positive. §A on its own moves nothing for the game thread (its buffers were one per
ioctl, and stay so), §B is the step that reaches it: 1,658 kernel submissions a second instead of
4,463, five graphics buffers a submission, the render thread 93 → 83 % and the title's frame rate
33 → 45 flips/s in the night scene, without a fault of its own in 200 s. The hold bound (2 ms)
closed 6 % of the chains; most closed at waits and slices, so a longer hold would not change
much — the next levers are the ring thread's slices (kept per poll here) and the CPU-side waits
of the compute queue on graphics labels. Not in the play settings yet: the maintainer decides
whether `BC5_DIRECT_CHAIN=2` goes into `bc5-run.env` for the second title; the F208 bursts are in
every gameplay run (survived three times today, reset the box once in 0163) and remain the hazard
of a longer session. Open: the `kyty-gpu` CPU rise with chains on, a run with
`BC5_DIRECT_CHAIN_HOLD_US=1000` and `=4000`, ASTRO BOT with `=2` (its own observe points may differ).
