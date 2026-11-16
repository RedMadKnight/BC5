# 0430 — catching the second title's GPU hangs at their source (handover from exp 0428)

**Status: handover, nothing built or run under this number yet.** Written by the exp 0428 session when its context grew
too long (the top session's instruction). A fresh session starts here.

## Question

What makes the second title's GPU hang? Two classes, both seen on 2026-11-16, both also without way 2 (F847):
1. **The GE stall** (F588's class): the ME waits at a partial flush behind draws; GE busy, shaders idle.
2. **The F403 family**: garbage pointers in RT/BVH data. Either a compute dispatch writes through a junk pointer, or
   shader waves hang in memory reads.

The maintainer's order: find the cause and remove it at its source, with way 2 on. No recovery and no timeout counts
as a fix, and there are no ring-count tests (multi-ring is decided).

## Rules for every run (the maintainer, via the top session)

- **Way 2 on.** Shared builds since 2026-11-16 16:55: patch `a8717e53`, normal `dae7bf0b`, lean `819f3b05`. The second
  title's defaults turn on `BC5_DIRECT_ACB_RINGS=4`, `_QUEUE_STATE`, `_MEC_INDIRECT`, `_STATE_NO_WALK` and
  `_SPLIT_LATE=3` (exp 0428).
- **JobArenaFix off** in every run. Use runners that read the shared `~/bc5-work/input.cfg` (it has
  `JobArenaFix.PPSA03671=off`): exp 0428's `run0428f.sh` (normal build, fight route) or `start0428l.sh` (lean, route by
  time). exp 0413's `start0413l.sh` forces it on; do not use it unchanged. An arena crash is data for the arena-fix-v2
  session, not a reason to turn the fix on.
- **No fuse or watchdog that kills the game.** Diagnostics only: `run0428f.sh` with `N_FUSE=0 N_NOWD=1`.
- Box: top GO, BOX-LOCK, never while he plays; arena-fix-v2 also needs slots (BOX-QUEUE).
- Stream to the laptop for every run: the kernel log (`journalctl -k -f`) and `exp 0428`'s `live0428.sh` (a 1-s
  memory/PSI/D-state sampler). A silent freeze (16:59:45) left nothing on the box.

## The records so far (all on the box; devcoredumps hold the title's buffers: private, never committed)

| time | run | class | records |
|---|---|---|---|
| 15:09:18 | his play (lean, way 2, JobArenaFix off) | GE stall, ME at `EVENT_WRITE` 0x410 behind `DRAW_INDEX_AUTO` draws (IB #0 ~1700–1944); `GRBM_STATUS` 0xa0210028 (GE + CP only) | `devcoredump/20261116-150919-devcd4.txt`, `gpu-stall/event-20261116-150918-gfx_0.0.0` (5 samples: every compute ring idle) |
| 15:35 | w428L4 (normal, way 2) | TCP WRITE fault at junk 0x171d720ad000 by compute; `comp_1.0.1` then `gfx_0.0.0` timeout, resets OK | `faults/20261116-153436` (K4), `play-20261116-1527/gc/ib-timeout-00595506-acb-991.bin` (direct dispatches only), `ib-timeout-00595500-dcb-139539.bin` (BVH 0x909974200 indirect dispatches with garbage triples 3.2e9 × 1.1e9 …, arguments at 0x118c62xxxx), devcd2 15:34 |
| 15:47:55 | w428C5 (one ring, normal) | F403 signature on GFX: ME at a partial flush after a checked `DISPATCH_INDIRECT` (IB #0 dword 1845; args 0x11d0571b00 passed the check; program from `LOAD_SH_REG_INDEX` at 1730); SPI/TA/TCP busy, GE idle | `devcoredump/20261116-154755-devcd3.txt`, `gpu-stall/event-20261116-154755-gfx_0.0.0` |
| 16:59:45 | smoke0428b's second title (lean, JobArenaFix ON there) | silent freeze: no kernel line, no sampler event, no pstore; 44 min until his power-cycle | `exp0413/n/play-last.log` to 16:59:38 (normal) |

The exp 0428 tools on the box under `~/bc5-work/exp0428/an/` read these:
- `lst.py <devcd> <from> <to>` lists IB #0's packets;
- `shat.py <devcd> <dword>` gives the SH state (program, user data, `SET_BASE` 1) at a dword;
- `binwalk.py <ib.bin>` walks a dumped IB with its dispatches;
- `ophist.py` gives an opcode census.

Decode registers with Linux v7.3 `gc_10_1_0_sh_mask.h`.

**What the records cannot say:** whether the stuck waves loop or wait, and who wrote the BVH garbage. No record holds
wave state (PC, SGPRs), and the host only sees the arguments at the timeout.

## Plan: one private normal build, each catcher behind its own switch, normal build only

Build exactly as exp 0428 did: `box0428.sh`'s relink pattern with a base unit and edits.
- The base unit is now the swap's tree unit `0cda79b5`. Or start again from 700fd4c2's unit `3e847e03` (saved as
  `~/bc5-work/exp0428/swap/bc5LleAgc.cpp.before-0428`) plus exp 0428's `mk0428.py`, then the catcher edits.
- Mind the shared objects: they are the swapped build's, with the way-2 title rows.

**(a) Wave state at a stall.**
- The stall sampler (`bc5-gpu-stall-sampler`, root, `/sys/kernel/debug/dri/...`, version 0377) already writes register
  samples before the kernel's 2-s timeout.
- Extend it, or a host-side thread, to read the SQ wave state of the busy waves: PC, `HW_ID`, `EXEC`, the first SGPRs,
  through umr (`umr --waves`; the box has umr: `bc250-cu-live-manager` uses it) or the SQ_IND registers.
- TODO(verify): the sudoers list (`/etc/sudoers.d/bc5-claude`) allows only dmesg, drop_caches,
  bc250-cu-live-manager status and amdgpu_firmware_info. umr or debugfs reads need the maintainer to add a rule; ask
  him through the top session first.
- From the PC, find the program: the dispatch journal (b) maps program addresses. Then dump the 16 KiB around the
  addresses in its SGPRs from guest memory, host-side, at the stall.

**(b) The per-ring dispatch journal.** exp 0381's `BC5_DIRECT_DISPATCH_JOURNAL=1` is still in the unit (2 hits in patch
0001). It names program and user data per dispatch. Check its cost and ring field with way 2 on (it predates the compute
rings), and add the ring if missing.

**(c) Who writes the BVH garbage.** At submit, the host reads each 0x9099742xx/0x909939900 indirect dispatch's argument
triple (as the timeout probe does at the timeout) and records the first garbage triple: x, y or z over the check's
limits, or a known garbage pattern. Garbage at submit means a writer before the submit, on the CPU or an earlier GPU
job; clean at submit and garbage at the timeout means a GPU writer in flight. Then narrow down with the jobs in
between: the dispatch journal of each ring between the two reads.

**Runs:** the fight + walk to G+1500 (`run0428f.sh`, `N_WALK_AFTER=1`, `N_FUSE=0 N_NOWD=1`, the normal private
build), repeated until a hang is caught. 15:09 and 15:47 both came about 8.5 min into a route. Rule before the runs:
none to pass; the record of one caught hang is the result.

## What exp 0428 already settled (its README)

- Way 2 works and is deployed: +16.8 % flips/s RT on, the fight route, 4 + 4 runs.
- 99.6 % of the two-ring dcb splits were unneeded and are gone (iteration 6, `SPLIT_LATE=3`).
- A piece's state prefix covers every state-setting packet of the hung IBs. The "split piece" route to the GE stall is
  thin.
- The CP's indirect check works on real MEC dispatches (18/18).
