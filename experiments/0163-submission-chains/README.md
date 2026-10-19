# 0163 — Submission chains: a queue's consecutive buffers in one kernel submission

**Question.** Does chaining the buffers one call hands over (the game thread's submit ioctl, the
ring thread's poll slice) into one kernel submission — the console's one stream, ADR 0010 — cut
the second title's per-frame host cost enough to show in its frame rate, and does it run without
faults?

**Setup.**
- Box: BC-250, kernel 7.2.4-ogc3.1, Mesa 26.2.3, libdrm 2.4.134 (F13; unchanged), 8C/16T, 40 CU.
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

**Result.** (filled in below)

**Verdict.** (filled in below)
