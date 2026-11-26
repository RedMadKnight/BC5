# 0163 — Submission chains: a queue's consecutive buffers in one kernel submission

**Question.** Does chaining the buffers one call hands over (the game thread's submit ioctl, the
ring thread's poll slice) into one kernel submission — the console's one stream, ADR 0010 — cut
the second title's per-frame host cost enough to show in its frame rate, and does it run without
faults?

**Setup.**
- Box: BC-250, **kernel 7.2.9-ogc3.1** (a staged ostree update was finalised by the 08:35 reboot; F13
  recorded 7.2.4), Mesa 26.2.3, libdrm 2.4.134, 8C/16T, 40 CU (`bc250-cu-live-manager status`).
- KytyPlus `f266548` + `backend/kytyplus-patches/0001-bc5-lle-agc.patch` of this commit (the chain
  code: `chain_append` / `chain_flush` / `submit_now` in `bc5LleAgc.cpp`), backend unchanged
  (`Device::submit` takes the chain as one IB). Built with `cmake --build ~/bc5-work/kytyplus-build
  --target kyty_emulator` in the `ubuntu` distrobox.
- Route as experiment 0162 (`input794.cmd`: start screen, slot 1, Continue; the save loads into the
  night-scene gameplay at +121 s), `play-pkg-log.sh` settings, 200 s per run, killed by the driver
  (`drive0163.sh`: `cpu-sampler.sh` from +125 s for 70 s, the kernel log before and after).
- Run 799: baseline, `KYTY_BC5_VIDEOOUT_TRACE=1` (`run799.sh`).
- Run 800: as 799 with `BC5_DIRECT_CHAIN=1` (`run800.sh`).
- `chains.py` here: flips per second from the trace, the threads' CPU from the sampler, and from
  the direct journal the submissions per second (one `timing: t` line per kernel submission), the
  chain statistics (`chains:` lines, every 10 s), CPU-side waits, failures.

- The box rebooted twice during the session: at 08:35:33 (a clean systemd shutdown in the previous
  boot's log, 35 s into the first attempt at run 799; not a GPU event) and at 08:59:14 (run 800,
  below). After each reboot it sits at the login greeter until someone logs in at the box.
- The F207/F208 session ran on the same box between the two (run 788, 08:44–08:52, with this build
  and the knob off); `box-claims.txt` in `~/bc5-work` records who started what.

**Result.**
- **The knob works.** Run 800 ran 162 s with `BC5_DIRECT_CHAIN=1` through the start screen, the
  menu, the save load and 10 s of night-scene gameplay: 306,926 chains for 512,995 buffers, no
  failed submission, no CPU-side wait given up, the picture as in 799 (`chains-800.txt`,
  `videoout-800-sampled.txt`).
- **Chains are short: 1.67 buffers each, 77 % single.** Of the closings, 59 % were the end of the
  call (an ioctl with one buffer, a poll slice with one ACB), 35 % a buffer with `COND_EXEC`
  (every large `dcb` of this title has them, so the game thread's buffers go alone, as before),
  6 % a CPU-side wait. The ring thread's ACBs did chain: 403 → 1,581 dwords per compute
  submission in gameplay (3.9 ACBs a chain); the graphics submissions stayed at ~2,500 dwords.
- **Gameplay, t 155–162 s of each run** (`chains.py`; the only steady window both runs share):

  | | run 799 (off) | run 800 (chains) |
  |---|---|---|
  | kernel submissions/s | 4,412 | 2,705 |
  | flips/s (mean / median) | 30.1 / 30.3 | 30.8 / 33.0 |
  | `Render Thread` CPU (gameplay samples) | 90 % mean, 92 % median | 99 % mean, 103 % median |
  | `bc5-ring` CPU | 35 % | 17 % |
  | `game-main` CPU | 60 % | 67 % |
  | MemAvailable / swap used at the end | 0.8 GiB / 1.4 GiB | 0.7 GiB / 1.8 GiB |

  Over the longer 799 window t 155–200 s: 32.5 flips/s mean, 4,400 submissions/s. The ring
  thread's cost halved with the submissions it makes; the render thread's did not fall — its
  buffers were not chained (above), and both runs were swapping (the pinned set, §4 of
  `docs/console-vs-host.md`), run 800 a little more.
- **The machine-down.** Both gameplay runs show the F208 geometry-engine fault bursts (client
  GE2, pages 0x0–0xf000, `GCVM_L2_PROTECTION_FAULT_STATUS 0x00500631`) on the `Render Thread`'s
  jobs from the night scene on, with the compaction program skipped as the launcher does: run 799
  from 08:54:54 to 08:55:55 (+142 to +200 s, ~14 bursts of up to 10 faults, survived, killed by
  the driver at +200 s; `kernel-799-after.txt` holds the last one), run 800 from 08:58:53 (+142 s,
  8 bursts) until the box reset itself at 08:59:14 (+162 s) in the middle of a burst, with no ring
  timeout or reset message before the log ends (`kernel-800-prevboot-excerpt.txt`). The sibling's
  run 788 had the same bursts (08:47–08:52) and survived. F208: the first burst is survivable, a
  repeat can hang a job and reset the machine. Whether the chain made the reset more likely (a
  burst inside a longer job; the compute chains hold several ACBs) cannot be told from one run.

**Verdict.** Inconclusive on the frame rate, positive on the mechanism, with a hazard noted. The
chains as scoped (one submit ioctl, one poll slice) cut the kernel submissions by 39 % and the ring
thread's CPU by half without a fault of their own, but they do not reach the render thread: the
game thread hands over one `dcb` per ioctl, and every large `dcb` carries `COND_EXEC`, so its
buffers stayed single and its frame did not get shorter (30 → 31 flips/s, within the noise of a
7 s window). The knob stays off in the play settings. Next, in order: (1) make the two passes that
give up on an IB with `COND_EXEC` segment-aware (the backend's PFP-sync insertion, the host's
compute-form `DISPATCH_INDIRECT` rebuild; the other insertions already grow the skip counts around
themselves, experiment 0052) so that graphics buffers can share a chain; (2) chain across the
game thread's ioctls — the console's queue does not return to the CPU between buffers — closing
the chain at label reads, flips and waits; (3) settle the F208 bursts of the night scene before
more gameplay measurements: they are in every run now (788, 799, 800), survivable until they are
not, and a run that dies at +162 s measures nothing. Rerun 799/800 for the full 200 s with (1) once
the box is free and watched.
