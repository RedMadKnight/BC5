# 0294 — the compute-ring refusal plus the breadcrumbs: let the recoverable hang name its dispatch

**Question.** Exp 0290 turned S6N's ~2-minute machine-down into a GFX-ring hang the kernel recovers from, six
times out of six (F356), but neither the probe's dumps nor the coredumps could name the packet the GFX ring
stood in. Exp 0277's breadcrumbs (a reached mark before and a done mark after every dispatch; the probe reports
the first one reached and not done at a fence timeout) ran for 63 minutes of play in exp 0281 (RT off) with every
sampled mark written, but never caught a hang. One private emulator with both — the refusal's backend archive and
the breadcrumb unit — on S6N's route with RT on: at each recovered hang, which dispatch, of which program, was
reached and not done? The second tree family's builders (F339), the BVH chain (F332), or the fast-launch draws'
neighbourhood (F208/F234)?

**Setup.**
- **The binary** (`build0294.sh`, a relink only, no compile): the shared normal build's objects (binary 893f8ab4,
  `ninja -t compdb -x` for the link command) with two substitutions — the breadcrumb unit
  `~/bc5-work/exp0281/obj/bc5LleAgc.cpp.o` (built 2026-10-24 22:34 from `bc5LleAgc.bc.cpp` md5 55fa73a4, the tree's
  5bccbb80 plus exp 0277's 16 hunks; exp 0276 later touched only `audio.cpp` and `libAmpr.cpp`) and exp 0290's
  archive `~/bc5-work/exp0290/build/libbc5_backend.a` (md5 825ae1d1, the `DISPATCH_INDIRECT` refusal). The script
  refuses on any checksum mismatch and writes nothing shared; the result is `~/bc5-work/exp0294/kyty_emulator`.
- **The runs** (`s6n0294.sh`, exp 0290's chain with exp 0281's breadcrumb extracts): the second title, `play-pkg.sh`
  with its defaults (RT on, the compute ring, the compaction skipped), plus `BC5_DIRECT_BREADCRUMBS=1` and the
  probe; S6N's route from exp 0196's saves through `ab-restore.sh`; up to 4 × 600 s, each run with its own save
  restore; exp 0290's rule — a GFX-ring hang the kernel recovers from (ring reset succeeded, no failed reset, no
  MODE1 within 25 s) is a pass, the host's 2-s fence timeout is part of it; the chain stops on a failed reset,
  MODE1, a crash or saves not back. Per run the breadcrumb health lines and the probe's "breadcrumbs (exp 0277)"
  lines go to `<tag>-crumbs.txt`; `stream0294.sh` on the laptop streams the kernel log and the journal extracts.
- **Reading a hang** (exp 0277's README): the probe's breadcrumb lines of the timed-out buffer give how many
  breadcrumbs were reached, done, and reached but not done; the first one reached and not done with its three
  neighbours before and after (offset and program); the last reached and the first not reached; and per ring the
  oldest reached-not-done on the device. The dispatch named is the one the GPU never finished.
- The maintainer approved this run type in this session (0290's S6N chain, "masz zgodę na działanie"); the
  supervisor's GO covers the relink and the runs under his overnight authority; a machine-down costs nothing
  before the morning (the rings have recovered six of six under the refusal).


**Result** (the supervisor's GO at ~02:05; relink 02:06:11–02:06:14, binary 30c39bd2 = shared 893f8ab4 objects +
exp 0281's unit + exp 0290's archive, both strings present, nothing shared written; chain `s6n0294.sh 4 600` from
02:06:38, saves c0ee58b92c0cadc2, `stream0294.sh` on the laptop):
- **S1 (02:06:38–02:16:53): pass, no hang** — the full 600 s with RT on, 0 kernel amdgpu lines, 0 TIMEOUT, 0 probe
  lines, saves verified. Breadcrumbs: 34.4 M inserted by the end, 62–64 k a second (RT on: about three times exp
  0281's RT-off rate), every health sample "4096 reached and 4096 done". The route's ~2-minute hang, six of six in
  exp 0290 without breadcrumbs, did not come.
- **S2 (02:16:53–02:19:05): the machine went down.** Kernel (laptop stream): 02:18:59.268 one `[gfxhub]` page fault,
  client SQC (data), at 0xb20407c00000, status 0x00601430 — the same address as exp 0290 S2's fault; 02:19:01.315
  `comp_1.1.0` timeout, reset succeeded; 02:19:01.316 `gfx_0.0.0` timeout, **reset failed**, "GPU reset begin!
  Source: 1", 02:19:05.585 MODE1, "VRAM is lost", PSP resuming; ssh reset, the box unreachable afterwards (ping
  intermittent, ssh timed out) — a power-cycle in the morning. The journal stream's last probe lines, dcb #129933
  (32,374 dwords, 60 direct dispatches, 32 kept waits, draws of the `DRAW_INDEX_2` kind with ES 0x11d0125d00, not
  the fast-launch kind): **"breadcrumbs (exp 0277) of #129933 dcb: 60 in the buffer, 60 reached by the CP, 60 done,
  0 reached and not done — every dispatch the CP reached is done: the ring stopped outside them"**; the last reached
  dispatch op 15 at 21182 (title offset 20230), program 0x11d04cc300, 4×32×4, done. The compute-ring job that timed
  out first (comp_1.1.0) was an acb without indirect dispatches, which the refusal leaves on the compute ring; its
  breadcrumb lines were not seen before the connection fell.

**Verdict.** Two runs, two different answers, both of them findings:
1. **The breadcrumbs change the hang.** With a reached mark (`WRITE_DATA`) before and a done mark (`RELEASE_MEM`
   BOTTOM_OF_PIPE_TS) after every dispatch, S1 ran the whole 600 s on a route where exp 0290's binary hung at ~2 min
   six of six times. An end-of-pipe release between consecutive dispatches is a synchronisation, not a passive
   probe — the same kind of ordering F107's CP DMA wait gave the refit. That points at a race between back-to-back
   dispatches in the RT work at that point of the route (a consumer reading a producer's output before it lands, or
   two writers to one record), which an EOP release after each dispatch hides; it also means the breadcrumbs cannot
   name that dispatch, because they remove the hang. A per-dispatch release (or a CS_PARTIAL_FLUSH) in the RT build
   families is a fix candidate to test on its own.
2. **The refusal is not a complete safety net.** In S2 the GFX-ring reset failed after a compute-ring job had timed
   out first, and the kernel fell to MODE1 — the first failed GFX reset in eight hangs (0290's six, 0294's one
   recovered S1 none). The breadcrumbs' verdict for the GFX ring's buffer — every dispatch reached and done, "the
   ring stopped outside them" — says the GFX ring did not stand in a dispatch at all: in a draw, a wait, or behind
   the compute ring (the acb that timed out two milliseconds earlier was one the refusal leaves on the compute
   ring, having no indirect dispatch). This also corrects the reading of exp 0290 and F332/F339 that every hang of this route is
   a BVH dispatch that never ends: in the one hang where the marks were in place, every dispatch of the GFX ring's
   buffer had finished, and the ring stood in a draw, a wait, or behind the compute ring. The SQC data fault at 0xb20407c00000, seen in exp 0290 S2 and here, precedes
   both of those GFX hangs; its program is not yet named. Open: the compute-side breadcrumb lines of S2 (on the box,
   `~/bc5-work/exp0294/raw/S2-*` if the chain's end ran, else the journal `~/bc5-data/captures/play-20261025-0216/gc/
   direct.log`), the coredump of 02:19:01 (`~/bc5-data/captures/devcoredump/`, if the fsync beat the reset), and
   whether a failed GFX reset after a compute-ring timeout is a pattern (F332's compute reset failed; here the gfx
   one did). Nothing of this experiment is integrated; the morning: the power-cycle, then those three reads.
