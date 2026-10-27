# 0344 — which dispatch of acb #76004 sat at the CP's fetch point when R2 of exp 0342 hung

**Question.** Exp 0342's R2 (RT on, one ring, both 0341 guards, the S6N route) hung at ~106 s in F403's state
register for register (F416): PFP 0xea1 / ME 0x77b, GRBM_STATUS 0xa0407028, SE0/SE1 busy, no fault, the PFP history
the host's GFX-form `DISPATCH_INDIRECT` with its CP check; IB #0 at 0x100400000000 of 6,584 dwords with
`CP_IB1_BUFSZ` 2,840 (57 % fetched); the host timed out acb #76004 (2,380 dwords) and dcb #76005; the ring reset
recovered. The product staircase does not catch 818 × 820 × 819 (it refuses x > 2^16 only), and F404 read the grids
in memory at a timeout as ≤ 28,644 groups, so the dispatch that does not end may be an ordinary grid whose shader
loops. Three questions, read-only on the box:
- (a) Which checked dispatch of acb #76004 sits at the fetch point of the 6,584-dword job IB? The dump
  `~/bc5-data/captures/play-20261027-1237/gc/ib-timeout-00076004-acb-2605.bin` (2,605 dwords) is **pre-filter**: the
  timeout probe writes `sub_ib`, the buffer the host handed to the backend (the chain's prefix of 225 dwords and the
  2,380-dword acb), before `policy::filter`, the shadow pass, the DMA syncs and the CP checks grew it to 6,584 — so
  the dump's offsets have to be mapped to the job IB's.
- (b) That dispatch's program address and argument triple, read where they exist: the journal's timeout-probe lines
  (`direct.log`: `dispatch op 16 at <q>: program 0x…, groups x × y × z (arguments at 0x…)`, the groups read from memory
  at the timeout), exp 0342's `R2-probe.txt` and `R2-play.log`.
- (c) Whether it is the BVH build / traversal family of F332 and F399, and whether its triple is big or its shader
  loops (a small triple at the fetch point with waves busy in SE0/SE1 and no fault means the loop).

**Setup.** Two files, nothing run yet (the supervisor's GO with a time window; the maintainer may play or reboot).
- `ibmap0344.pl <dump> <IB dwords> <CP_IB1_BUFSZ> [known programs]` reads the dump and replays the *size* effect of
  the passes `Device::submit` runs on a GFX-ring job as the integrated launcher configures them (`backend/src/direct.cpp`
  at main d0c2668; `BC5_DIRECT_MEC_INDIRECT=1 GPU_CHECK=1 DMA_SYNC=1 GPU_CHECK_PRODUCT=1 SHADOW_LABELS=1`, no CU mask,
  no job timestamps, no prologue or epilogue, DMA idle at the end): the filter in place (a compute-form
  `DISPATCH_INDIRECT`, 4 dwords, becomes the GFX form, 3 + a NOP; one whose address high dword is not the IB's base is
  dropped and unchecked — the base is taken as the most frequent high dword); a copy of each writer of a label that a
  memory `WAIT_REG_MEM[64]` waits on after a writer, before the writer (`shadow_labels::apply`, 64 slots); 7 dwords
  before the first dispatch after a `DMA_DATA` without CP_SYNC; the CP check with the staircase before each based
  GFX-form indirect dispatch, **88 dwords** (`indirect_check::apply`: WRITE_DATA 5, WRITE_DATA 5, three COND_WRITE 27,
  two COND_WRITE 18, WRITE_DATA 5, PFP_SYNC_ME 2, COND_EXEC 5, COND_WRITE 9, WRITE_DATA 5, PFP_SYNC_ME 2, COND_EXEC 5;
  35 for a draw; 2 for an unbased one); 7 dwords of DMA idle at the end; padding to 8 (`padded = pro_padded +
  pieces[0].padded`, the size the CS ioctl saw — the nested copies lie after it and are not part of it). It prints the
  computed job size against the CS's (**EQUAL** or the difference, which names a pass not replayed as it ran), both
  readings of `CP_IB1_BUFSZ` (what is left: 6,584 − 2,840 = 3,744 fetched; or what was fetched: 2,840 — F403 left the
  register's meaning as TODO(verify)), the dump packet at each reading (inside the packet or inside the check before
  it), the index of the last dispatch at or before it, the dispatches three on each side with their dump and job
  offsets, form, program (from `SET_SH_REG` 0x20c/0x20d in the buffer; tables in memory are not read) and argument
  address, and the buffer's programs with counts, tagged from `known0344.txt` (the second title's BVH programs named in
  HANDOFF: the build family of F332, the refit, the compaction of F404, the traversal of F113). Only headers, offsets,
  counts, opcodes and addresses are printed; no dword of the buffer leaves it; nothing is written.
- `probe0344.sh` on the box, with the two files beside it: the guard (`pgrep '^kyty_emulator'`, an empty BOX-LOCK, its
  own lock line, released on exit), every step under `ionice -c3 nice -n 19`, text into `~/bc5-work/exp0344/raw/`
  only: `inputs.txt` (sizes, dates and md5 of the inputs), `ibmap.txt` (the walker), `journal-marks.txt` and
  `journal-acb-probe.txt` (the acb's probe section of `direct.log`, from its `dumped` line to its summary line: the
  dispatch, wait and write lines), `journal-before-submit.txt` (the 40 journal lines before the acb's `submit` line),
  `candidates.txt` (the probe's dispatch lines of the dump offsets the walker names: program, groups at the timeout,
  arguments), `probe-summary.txt` and `play-around-the-hang.txt` from exp 0342's extracts. The dump is read once by the
  walker and never copied. The one slow step is a `grep -n` over the 428 MB journal.

*Check done on the laptop.* `perl -c`, `bash -n`; a synthetic 41-dword dump (a `SET_SH_REG` program, an unsynced
`DMA_DATA`, three compute-form dispatches of which one has another high dword, a `RELEASE_MEM` / `WAIT_REG_MEM` pair,
a GFX-form dispatch): the walker computes 41 + 279 + 7 = 327, padded 328 = the given CS size (one copy of 8, one DMA
sync, three checks), and places job dword 228 inside the third dispatch's packet and dword 100 inside the first
dispatch's check; `probe0344.sh` ran end to end in a stand-in home with stub `pgrep` / `ionice`, a fake journal with the
marker lines, and left the lock empty. The real check is the EQUAL line on the box: if the computed size differs from
6,584, a pass did not run as replayed (a CU table in memory, a filter drop among the writers, the tracker) and the
mapping is off by that many dwords, which the README's result will say.


**Result (2026-10-27 13:00–13:13, the supervisor's window; read-only, the lock empty after each step; the text outputs
are `raw/box/`).**

*Hang 1 — R2 of exp 0342 (12:39:19, acb #76004).* The walker's replay is exact: **2,605 + 3,967 inserted + 7 = 6,579,
padded 6,584 = the CS's size** (`raw/box/ibmap.txt`): 45 GFX-form indirect dispatches checked (88 each), 1 DMA sync,
0 shadow copies (one memory wait, no writer before it), 0 dropped. The dump is the host's own conversion of the ring's
compute buffer: 45 `SET_BASE` + `PFP_SYNC_ME` + 3-dword `DISPATCH_INDIRECT` triples, 40 direct dispatches, 49
`ACQUIRE_MEM`, 47 `EVENT_WRITE`.
- (a) `CP_IB1_BUFSZ` read as "what is left": **job dword 3,744 lies inside the CP check before the dispatch at dump
  offset 1427, dispatch #49 of 85** (its `DISPATCH_INDIRECT` sits at job 3,810; the check spans 3,722–3,810, the point
  is its 22nd dword, the second per-dimension `COND_WRITE`). The ME's history ends in two `COND_WRITE`s: the ME was
  executing that check. The other reading (2,840 fetched) would put it inside the check of #38 (0x909939900, the refit);
  F403's three identical dumps and the ME history favour the first (F403 left the register's meaning TODO(verify)).
- (b) #49 is program **0x909873200** (one dispatch of it in the buffer; not named in HANDOFF), arguments at
  **0x11871ed520** (in the learned window 0x1182000000 + 0x6000000, `raw/box/h2-learned-windows.txt`), read by the probe
  two seconds later as **6104 × 4294962046 × 4294959880** (y = −5250, z = −7416 as signed 32-bit) — the "largest grid"
  of the probe's summary (`groups 18114686370935673472, at 1427`). The per-dimension limits are {2^20, 2^10, 2^10}
  (`policy.hpp`): had these been the values when the check ran, the staircase's `COND_WRITE`s would have cleared the
  flag and the `COND_EXEC` skipped the dispatch; whether the GPU wrote them after the check (a stray store, F360's
  shape) or before is not in the record. The dispatches before it are direct and small: #48 **0x90986df00, 1 × 1 × 1**
  (dump 1367), #47 **0x90986e700, 11,520 × 1 × 1** (1340), #46 0x90996a000, 45 × 1 × 1 (1293); between #48 and #49 the
  title's `EVENT_WRITE` + `ACQUIRE_MEM` (1372, 1374) — and the ME was past them, in #49's check, with SE0/SE1 busy.
  So the waves the dump shows busy were launched before #49 and had already passed the title's own flush, or the
  fetch register reads differently than assumed; either way **no large triple was in flight: the busy work is a
  1-group or an 11,520-group dispatch that did not end** — a looping shader, as F404 read it.
- (c) The buffer is the BVH build chain of F332 / F404: 0x909936c00 × 18, 0x909939400 × 8, 0x909939700 × 8 (the build
  family), 0x909939900 × 8 (the refit), 0x90992af00 × 11, 0x9098ea000, 0x9098eb200 (F404's second half), 0x909971300
  × 15, and nine programs once each (`raw/box/ibmap.txt`). The probe's `ran / DROPPED` tags of this section are mixed
  (181 / 135) and not usable: the dcb's probe lines interleave with the acb's in the journal.

*Hang 2 — the maintainer's play (12:52:29, dcb #48055, the machine down).* Read-only too; the walker, the packet
listing and the journal's probe lines (`raw/box/h2-*.txt`):
- The dcb is a chain of the game thread's buffers of 61.465–61.468 s (2,167 + 9,820 + 40 + 16,978 dwords and their
  prefixes = 30,221). Its job IB cannot be replayed to the CS's size (computed 73,768 against 36,360: the chain's own
  passes differ — 435 indirect dispatches, 141 indirect draws, 7 `COND_EXEC`s, 25 shadowed labels), **but the 608
  fetched dwords need no replay: they are the chain's first 58-dword state prefix, the title's `ACQUIRE_MEM` at 58,
  and then `SET_SH_REG`(8) + 3-dword `DISPATCH_INDIRECT` every 11 dwords from offset 74 on**, each dispatch preceded
  in the job by the backend's 2-dword `PFP_SYNC_ME` (the unbased path), which is exactly the PFP history of the dump
  (`PFP_SYNC_ME`, `SET_SH_REG(7)`, `DISPATCH_INDIRECT`). The CP stopped at the sixth of them (job 608 → dump 129).
- **The hypothesis holds, with one correction: these are not compute-form dispatches of an acb.** The 4-dword acb
  #48056 is one `SET_UCONFIG_REG` packet (opcode 0x79; `pass 0 drop 1`), unrelated. The dispatches are the title's own
  **GFX-form `DISPATCH_INDIRECT`s inside its graphics buffer**, 435 of them, all of program **0x90997a500 (the BVH
  bottom-up refit, HANDOFF)**, with offsets 0x9bce4d80, 0x9bce6480, 0x9bce7280, … 0x9bdc9e80 (`h2-ibmap-dcb.txt`) and
  **no `SET_BASE` before them in the IB** (the IB's first is at 16,337, and the title's 167 `SET_BASE` index-1 packets
  serve its 141 `DRAW_INDIRECT`s, not these dispatches: no 3-dword dispatch follows any of them,
  `h2-dispatch-after-setbase.txt`). The title's values are full addresses (0x1193ad3900, 0x11d083a400, 0x2319ff60 + hi
  0x11: inside its learned windows) and **it sets base 1 to 0, twice, at the end of each of its buffers** (dump 20670,
  20674, 24817, 24821, 30043, 30047, `h2-setbase-dword1.txt`). So when the next buffer's refit dispatches ran, base 1
  was 0 — on our ring and, by the same packets, on the console — and the CP read the arguments at **0 + 0x9bce4d80:
  the kernel's fault page 0x9bce4000**, a CPF read with `PERMISSION_FAULTS 0x3`, `MAPPING_ERROR 0` (status 0x600830:
  the PTE existed, the read was not permitted). The host's own submit-time check did not drop them: the run has **0
  "not mapped, DROPPED" lines**, so `base1 + offset` was covered by a host mapping at submit — the carried base 1
  (`g_carried[0].base1`, experiment 0161) or a low mapping; the journal does not say which.
- *What the offsets are.* 0x1100000000 + 0x9bce4d80 = **0x119bce4d80 lies in the title's learned window
  0x1196000000 + 0x6000000** (`h2-learned-windows.txt`); 0x9bce4d80 itself lies in none. The same holds for the
  title's other values (0x1193ad3900 in 0x1192000000 + 0x6000000, 0x11d083a400 in 0x11ce000000 + …). The offsets are
  the low dwords of addresses in the title's 4-GiB window at 0x1100000000: the console resolves a base-1 of 0 within the
  process's window (RPCSX models the same: a process's GPU memory at `vmId << 40`, a guest address ORed in; HANDOFF's
  junk-top-byte note), the BC-250 translates the full 48 bits and reads page 0x9bce4000.
- *Which conversion path.* None converts them: the title's packet is already the GFX form. The backend's
  `indirect_check::apply` finds no `SET_BASE` in the IB and no `mec_indirect_base` (a dcb's is 0), takes the **unbased
  branch — a `PFP_SYNC_ME` and the dispatch as written, no `COND_WRITE`s** — and the CP runs it against its current
  base-1 register, which on one ring is whatever the last job left: here the title's own 0 (an acb job's host `SET_BASE`
  would have left an argument page of the 0x12 window instead). With two rings this class could not have faulted
  differently: the same base-1 of 0 would have been there. Before 0341/0342 the title never reached this spot with RT
  on (the plays hung earlier), and the 12:51 journal counts **0 unbased dispatches before this frame** (`gpu check: …
  0 without a base` at 50 s); the refit's 435 dispatches are the first.
- *Why the reset failed.* A CPF fault stops the fetcher; the ring reset could not recover it (12:52:32 "reset FAILED"),
  MODE1 followed. The 12:39 hang (hang 1) had no fault and its ring reset succeeded.

**Verdict.**
- (a)–(c) of hang 1: the CP stood inside the check of dispatch #49 (program 0x909873200, a build-chain program, arguments
  read later as a garbage triple that the limits would refuse); the busy waves belong to a small direct dispatch
  launched before it (0x90986df00 1 × 1 × 1 or 0x90986e700 11,520 × 1 × 1) — the BVH build chain of F332, and **a
  shader that does not end, not a big grid**. The staircase and the per-dimension limits are not what this class needs;
  a wave-side bound (the loop-bound copy of exp 0137, `loop_bound_copy`, applied to these programs) or a per-dispatch
  timeout is.
- Hang 2: **the title's BVH refit (0x90997a500) issues 435 GFX-form `DISPATCH_INDIRECT`s whose offsets are low dwords of
  0x11-window addresses, with base 1 deliberately 0; the backend runs them unchecked (unbased) and the CP reads the
  arguments at the bare offset — a CPF permission fault, a failed ring reset, the machine down.** The supervisor's
  hypothesis is right in mechanism (an offset read at base 0); the packets are the title's own, not a conversion.
- *Fix (proposal; the bvh session can write it as exp 0345, host + backend, testable offline):* (a) **give these
  dispatches their base**: the host passes the title's window base for GFX buffers — 0x1100000000, from a switch first
  (`BC5_DIRECT_GFX_BASE1=<hex>`), later derived from the title's own `SET_BASE` values and mappings — and the backend,
  for a GFX-form indirect dispatch with no `SET_BASE` earlier in the IB, **emits `SET_BASE` index 1 = that base (with
  the compute shader-type bit, run 64's lesson) before its check** and uses it for the `COND_WRITE`s, so the dispatch
  is checked and reads 0x119bce4d80, a mapped page. Journal each such dispatch once per program (offset, base, the
  resolved address, whether it is mapped). If the resolved address is not mapped, (b) **NOP the dispatch and count it**
  rather than let the CP read at the bare offset: a lost refit costs reflections for a frame; a CPF fault costs the
  machine. (c) Running these buffers elsewhere changes nothing: the packet is the title's and the base is 0 on any
  ring. The first test is the maintainer's post-load spot (85 s) and the S6N route with RT on; hang 1's class (the
  looping build shader at ~106 s) stays and needs its own arm.
