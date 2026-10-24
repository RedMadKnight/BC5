# 0275 — a two-ring hang read with probe v2 and the first saved devcoredump

**Question.** At 18:51 on 2026-10-24 the maintainer ran the second title on exp 0273's private binary 91349485 (the
shared normal 9f74965d, which has exp 0260's and 0272's probe, plus the RT switch, on and never toggled). The picture
froze about 1.5 min in while the sound went on, and he closed the game. Kernel (as the box supervisor read it):
- 18:52:55: gfxhub page faults from TCP, RW 0x0 (read), PERMISSION_FAULTS 0x3, status 0x00501031, vmid 5, pasid 108,
  pages 0x1334f81000, 0x1334f82000, …;
- 18:52:57: gfx_0.0.0 timeout, reset succeeded;
- 18:52:59: comp_1.1.0 timeout, reset succeeded. The box stayed up.

It is the first hang with probe v2's dispatch grids (F334) and with a devcoredump saved by the maintainer's udev rule.
Is it F322's pair? What do the coredump's CP state and the probe's grids say?

**Setup.** One read-only copy at 18:55:01–18:55:28, scp only, on the box supervisor's GO. The files went to the tcp
session's scratchpad outside the repo and are not committed (they hold the title's command buffers):
- `~/bc5-data/captures/play-20261024-1851/gc/direct.log` (18,565,980 bytes);
- `ib-timeout-00068401-dcb-27416.bin` and `ib-timeout-00068408-acb-865.bin` (with their `.tfring.bin`);
- `~/bc5-data/captures/devcoredump/20261024-185258-devcd1.txt` (5,812,367 bytes).

Analysed offline with exp 0255's `dec0255.py` approach and short scripts. Committed, derived text only:
- `raw/journal-lines.txt`: the TIMEOUT, probe, wait, fault and learned lines;
- `raw/dispatch-grid-classes.txt`: the graphics buffer's dispatch grids by program;
- `raw/coredump-cp-state.txt`: registers only, no ring or IB contents.

**Result.**

1. **F322's pair again** (`raw/journal-lines.txt`):
   - acb #68408, 865 dwords: the "Lighting Prep" compute buffer of the 22:59 play, L7 and R11B, TIMEOUT 2,036 ms. Its
     only wait (offset 0, WAIT_REG_MEM64 on **0x12004b53c8 == 0**) was kept for the GPU and is **not met**: "now
     0x9076d6d8c". Count line: 8 dispatches, 0 indirect.
   - dcb #68401, 27,416 dwords, TIMEOUT 2,038 ms. Both its waits were kept, and **both are met**: 0x12004b3c38 == 0
     (offset 1269, pfp) and 0x11e0610768 == 1 (offset 1330). 1,915 dispatches, of which 1,180 are indirect.
   - After the timeouts, the host's fault query ("timeout: fault 0x1334f81000 status 0x00501031") and "learned …
     region 0x1332000000+0x6000000 (saved)".

2. **The devcoredump: the first one saved, with per-queue CP state** (`raw/coredump-cp-state.txt`). This answers exp
   0260's TODO(verify): gfx10's IP dump does carry each compute queue's IB read pointer.
   - It was written at the **comp_1.1.0** timeout ("Ring timed out details: IP Type: 1 Ring Name: comp_1.1.0"),
     thread `bc5-ring`, with the fault at 0x1334f81000. That was after the graphics ring's reset, so its GFX CP state
     (IB1 base, RB pointers) is post-reset and says nothing about the hang.
   - **The compute queue** (mec 0, pipe 1, queue 0) has IB_BASE 0x1021_00000000 and IB_RPTR 0x1c (dword 28). Its MEC
     header dump repeats **0xc0079300**, a WAIT_REG_MEM64. So the compute ring is parked on the 865-dword buffer's first
     packet, the kept wait on 0x12004b53c8, as the probe says.
   - There are no SQ/wave registers in the dump.

3. **The order: the graphics ring stopped first, in its own work, not at a wait.**
   - The TCP read faults (18:52:55) came 2 s before the graphics timeout (18:52:57), and the compute timeout came 2 s
     after that (18:52:59).
   - The graphics buffer's waits were met, so it hung inside its dispatches or draws.
   - The compute buffer waits honestly on 0x12004b53c8, the "…c8" slot the next graphics buffer writes (F322), which
     sits behind the hung one.
   - **This revises F322's pair:** it forms because the graphics stream stops, and the compute buffer then waits, at its
     first packet, for the slot the next graphics buffer would have written. The compute timeout is a consequence.

4. **Probe v2's grids for the graphics buffer** (`raw/dispatch-grid-classes.txt`):
   - The 188 direct dispatches (0x11d0287900 ×135, 0x90985f200 ×53) all have sane grids.
   - The 1,180 indirect dispatches belong to eight BVH programs with about 147 each: 0x909974200, 0x909973900,
     0x909973b00, 0x909973d00, 0x909973f00, **0x909974400** (F207's compaction), 0x909977100 and 0x90997a500.
     - Each of the first seven has 1 sane grid, 11–18 with a zero count, and 129–135 with counts of 2^30 and more that
       read as IEEE floats: 0xBFE4F21E ≈ −1.79, 0x3E7DB54A ≈ 0.25, 0x80000000 = −0.0.
     - 0x90997a500 has only zero grids.
     - The first huge grid is at dword 15088 (0x909974200).
   - These are the 3-dword DISPATCH_INDIRECT (offset from the SET_BASE index 1 base; 12 SET_BASE in the buffer). The
     address the probe reads is, for each dispatch, the object record whose pointer the same dispatch gets as user data
     (SET_SH_REG 0x243), plus 0x60. No COND_EXEC or predication guards them.
   - Two readings:
     - **(A) The values are stale.** The slots held valid counts when the CP read them and were overwritten with float
       data later in the frame. The same passes ran every frame for ~90 s, which with such grids would have hung the
       first frame.
     - **(B) The values are what the CP read in this frame.** The producer left float data there this time, the first
       huge dispatch (dword 15088) never ended, its threads read out of range (the TCP read faults at 18:52:55), and the
       graphics ring timed out.
   - This data cannot tell them apart. **So probe v2's indirect grids are not conclusive** where the arguments live in
     memory that later work rewrites.

**Verdict.**
- **F322's two-ring pair is the graphics stream stopping, not a cycle.** In this case the graphics buffer, with its
  waits met, hung in its own work first, and the "Lighting Prep" compute buffer then waited, correctly, at its first
  packet for the slot the next graphics buffer would write. With F332 (a compute chain hung in BVH dispatches, graphics
  waiting on it) the hangs seen so far are a stream that stops inside the title's ray-tracing (BVH) work, and the other
  ring waits on it.
- **The devcoredump helps for the ring whose dump it is.** Here it confirmed the compute queue's wait. The graphics
  ring's state was taken after its reset, so it was lost.
- **Probe v2's grids point at the BVH passes' indirect dispatches, F207's compaction among them.** Their
  arguments read as float data, but whether the CP read those values is open.
- **Next:**
  - A dispatch-arguments capture at dispatch time, i.e. a GPU-side copy of each indirect dispatch's three counts into
    a probe buffer, as exp 0160's GE probe does for draws. That would decide (A) against (B). It changes the stream, so
    it needs its own runs.
  - The BVH session's work on F207 (compaction 0x909974400 writing garbage) is the most direct lead for (B).
