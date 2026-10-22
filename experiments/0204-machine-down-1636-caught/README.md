# 0204 — a machine-down caught off the box: after a cross-ring wait the host gave up on, both rings time out

**Question.** The box went down without a fault line at 07:44, 13:41 and 14:50 (F250, F256, F260).
The fourth time it is recorded off the box. What does it show, and what do the machine-downs share?

**Setup.**
- Passive watch from 15:31 to 20:30, agreed with the box supervisor: `watch-local.sh` and
  `remote-journal.sh` (copies here). It streams `journalctl -k -f` and the newest play journal's
  timeout/fault/reopen lines, filtered on the box, to the laptop. Nothing is written on the box.
- The run that went down: the water session's scripted X4c (experiment 0201), started about
  16:33:30.
  - Binary: `~/bc5-work/exp0197/kyty_emulator`.
  - Switches: the launcher's defaults plus `KYTY_BC5_APR_PARALLEL=1` and `KYTY_BC5_APR_SYNC=1`. No
    PRT.
  - Private save copy; title press at 110 s.
  - Journal: `~/bc5-data/captures/play-20261022-1633/gc/direct.log`.
- Box: kernel 7.2.9-ogc3.1. The maintainer was away and restarted the box remotely.
- The base rates (step 4 below) come from the full journals of the sessions named there, read while
  no emulator ran.

**Result.**
1. **The sequence** (`raw/stream-kernel.txt`, `raw/stream-journal.txt`):
   - Journal t 166.083 s: graphics buffer #70816 (7,899 dwords) and compute buffer #70826 (875
     dwords) were submitted. At 16:36:24 both FAILED with TIMEOUT after 2.0 s.
   - The host's fault query: "timeout: fault 0x0 status 0x00000000", i.e. no GPU fault.
   - Kernel, 16:36:24.49: "Dumping IP State", device coredump, `gfx_0.0.0` timeout (thread
     bc5-ring), "Ring gfx_0.0.0 reset failed", "GPU reset begin".
   - 16:36:28.80: MODE1 reset, "VRAM is lost due to GPU reset", PSP resuming.
   - The SSH streams died at 16:36:53–57.
   - Nothing amdgpu between 15:31 and 16:36:24, so the sessions before it (1542, 1555, 1601, 1612,
     1622, 1627) had no timeout or fault.
2. **What survived** (`raw/after-reboot.txt`):
   - The crashed boot's journal stops at 16:35:57.
   - The play journal stops at the two TIMEOUT lines, with no probe lines.
   - The two dumps the probe reported writing (`ib-timeout-00070816-dcb-7899.bin`,
     `-00070826-acb-875.bin`) are not on disk.
   - There is no devcoredump.
   - The first reboot (16:37:03) reports "a parity error occurred". The second (16:37:50, the
     restart) reports "software wrote 0x6 to reset control register 0xCF9" plus the parity error.
3. **The probe, only in the stream** (345 lines). It walked the timed-out graphics buffer to dword
   7,759 of 7,899.
   - Every draw and dispatch it lists either ran, or is one of 17 `DRAW_INDIRECT`s that the host's
     indirect-draw check dropped.
   - So the stall is at or after the end of that buffer, not in one of its draws. (The probe lists
     draws and dispatches, not waits.)
4. **A shared precursor** (`raw/journal-waits-before-timeout.txt`,
   `raw/same-wait-in-earlier-machine-downs.txt`).
   - In each of the three machine-downs with the launcher's skips, 29–71 ms before the timed-out
     pair, the host gave up on the same wait:
     - 16:36: t 166.012 s, "two rings: dcb 2260 dwords waits at 418 on 0x12004b3c38: NOT served
       after 4.05 ms, head split off", then "cpu-wait WAIT_REG_MEM64 at 418 on 0x12004b3c38: GIVEN UP
       after 10.2 ms". The timed-out pair followed at 166.083 s (71 ms).
     - 14:50: t 1153.433 s, the same give-up at dword 418 on 0x12004b3c38. The pair followed at
       1153.462 s (29 ms).
     - 13:41: t 251.326 s, the same "NOT served … GIVEN UP after 39.9 ms" at 418 on 0x12004b3c38.
       The timed-out graphics buffer followed at 251.362 s (36 ms).
   - The wait is a graphics-buffer WAIT_REG_MEM64 with `function 3` (equal), `reference 0x0` and a
     full mask. The label held 0x907616589 ("wait detail"). So the graphics side waits for the
     label, which the compute side writes, to be cleared to 0.
   - After a give-up the host marks the wait done for its software CP and still submits the buffer,
     so the GPU then waits on the label itself (patch 0001, the two-ring split and `cpu-wait` code).
   - Base rate of that give-up in whole sessions (`raw/given-up-base-rate.txt`):
     | Session | Length | Give-ups on 0x12004b3c38 | Outcome |
     | --- | --- | --- | --- |
     | 1136 | 17 min | 68 | no hang |
     | 1601 | 10 min | 16 | no hang |
     | 1555 | 5.5 min | 3 | no hang |
     | 1430 | 19 min | 65 | hang |
     | 1633 | 2.8 min | 9 | hang |
     | 1337 | 4 min | 11 | hang |
   - It happens about every 15–20 s of play. A chance landing within 71 ms before a hang is about
     0.4 % per hang, so three of three is very unlikely to be chance.
   - The 07:44 machine-down (exp 0192, `BC5_DIRECT_FLAT_APERTURE=1`, nothing skipped) does not show
     it. Its last give-up was at another label (0x12004b5438), 6 s before.
5. **Reset failure, not the timeout, takes the box down.** The ring timeouts at 08:16, 09:55,
   10:28, 10:51, 12:01 and 12:47 had "reset succeeded" for every ring, and the box stayed up
   (`raw/ring-resets-morning-boot.txt`). The 09:55 one is a different case: a fault-less timeout 3 s
   after a start, on another label, whose wait was kept for the GPU rather than given up. At 14:50 and 16:36
   the GFX ring's reset failed and the kernel went to a MODE1 reset, after which the box rebooted
   with a parity error. For 07:44 and 13:41 the kernel lines were lost.

**Verdict.** Narrowed, not proven.
- Three of the four machine-downs follow, within 29–71 ms, a graphics wait on label 0x12004b3c38
  (for 0) that the host gave up on and left to the GPU.
- The likely chain: the wait is never served. The graphics and compute rings both time out at
  2 s, the GFX ring's queue reset fails (the CP presumably still in the wait,
  TODO(verify)), and the kernel's MODE1 reset is what this board does not survive.
- What writes 0x12004b3c38, and why it is not served in the rare case, is open. So is whether the
  writer sits in the compute buffer that timed out alongside, which would make it a cross-ring
  deadlock.

Next, in order:
1. Offline: the label's writers. The direct journal knows which ring wrote a label last
   (`g_label_ring`); the captured buffers of earlier sessions can show who sets 0x12004b3c38 to
   0x907616589 and who clears it.
2. A journal-only probe, off by default: when a given-up wait is left in a GPU buffer, journal the
   label's last writer and whether that writer is already queued.
3. Only then, a mitigation behind a switch, one short watched run (D16). For example, the existing
   `BC5_DIRECT_SPEC_WAIT_MS` watchdog, which writes the awaited value when a kept wait stays
   unserved, extended to given-up waits.
- Box rule from this run: a machine-down's evidence survives only off the box. The stream did its
  job; the probe's dumps should stream too.
