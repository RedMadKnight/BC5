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

## Setup (this session, 2026-11-16 evening)

**Build.** `box0430.sh build`: the shared tree's unit at patch `a8717e53` (md5 `0cda79b5`, the same file as exp 0428's swap
unit; it is also what the `src/libs/bc5LleAgc.cpp` hunk of main's patch holds) edited by `mk0430.py` (8 anchored edits,
md5 `20c0e644`), compiled with the shared normal build's command and relinked with the shared objects (`build0430.py`,
a copy of `build0428.py`). Private binary `~/bc5-work/exp0430/kyty_emulator`, md5 `9b0a5317`; the shared binary stayed
`dae7bf0b`. Built 19:48–19:50 under its own BOX-LOCK line; 7 warnings, all at lines the base already had.

**The catchers (tag dj430), normal build only (`BC5_DIAG_ENV`), each off unless set:**
- (a) `BC5_0430_WAVES_MS=<ms>` (≥ 500): when a completion queue has waited that long for one job (from its submission),
  one `sudo -n /usr/bin/umr -O halt_waves -wa none` (every wave on the GPU, no ring named; the exact NOPASSWD line of the
  box's sudoers, per the top session) into `<capture dir>/waves0430-<k>.txt`, synced; at most 2 per run. The halt runs
  directly, not through `bc5-gpu-hang-dump`: exp 0370 K2 found that path's 27 register reads before the halt landed
  after the reset (F112). Dedicated runs only: F229 (a halt at a 0.6-s stall that would have recovered was followed by a
  ring reset). The runs use 1100 ms. Per completion queue (2), not exp 0058's single `g_fence_wait_since`, which the
  other queue's thread overwrites.
- (b) `BC5_0430_DJ=1`: per hardware ring (GFX + 4 compute), an in-memory journal of the last 4096 dispatches the host
  submitted (submission, kind, offset, op, program, COMPUTE_USER_DATA_0..15, an indirect dispatch's argument address and
  the triple read at submit), written to `<capture dir>/dj0430-<k>.txt` (fsync; at most 8) at the same stall and at
  every host timeout. Nothing is written while the GPU runs well (exp 0381's journal grew to 38 GB).
- (c) `BC5_0430_ARGS=1`: an indirect dispatch whose triple at submit is over the host check's limit (65536 × 64 per axis
  or as a product) is journaled as `args0430:` (ring, program, address, triple), the first 256, then every 4096th.
  Separate reads (R13): the triple at submit (here and in (b)) and the timeout probe's read at the timeout.

**Runs.** `chain0430.sh` (MAX=6): `run0430f.sh` (= `run0428f.sh` with exp 0430's private directory and lock lines; 9 lines
differ), slot 4, the 14:50 record's gameplay at G, then exp 0379's walk to G+1500 s. Way 2's words named explicitly
(`BC5_DIRECT_ACB_RINGS=4`, `_QUEUE_STATE=1`, `_MEC_INDIRECT=1`, `_STATE_NO_WALK=1`, `_SPLIT_LATE=3`), JobArenaFix off in
each run's private input.cfg (`N_ARENA=off`), RT on, `N_FUSE=0 N_NOWD=1`, catchers `BC5_0430_DJ=1 BC5_0430_ARGS=1
BC5_0430_WAVES_MS=1100 BC5_DIRECT_TIMEOUT_PROBE=1`. The chain stops at any class but NO_CRASH (R55; its STOP file was
tested dry before the first run), at a second NOT_ROUTED, or at an emulator that is not its own. The kernel log
(`journalctl -k -f`) and `live0428.sh` (1-s memory/PSI/D-state) stream to the laptop (`raw/`). Chain started 19:51:34.

## Result 1: h430R2, the hang of 20:25:47 (build 1, `9b0a5317`)

Chain 1 (`h430R*`): h430R1 NO_CRASH (19:51–20:18); h430R2 started 20:18:42 and hung at 20:25:47, 7 min in. Records:
`~/bc5-data/captures/play-20261116-2018/gc/` (`dj0430-0.txt`, `dj0430-1.txt`, `ib-timeout-00587477-dcb-175614.bin`,
`ib-timeout-00587478-acb-14667.bin`, `direct.log`), devcoredump `20261116-202549-devcd1.txt`, pstore
`dmesg-efi_pstore-179485715004001`, the laptop streams `raw/kernel-stream-h430R.txt` and `raw/live-stream-h430R.txt`.
The box went down: `comp_1.0.1` timed out, its ring reset failed, and `bc5-gpu-watch` crashed the kernel (SysRq s, c)
at 20:25:49.63.

- **The kernel:** TCP page faults from 20:25:47.405 (ring 24, vmid 7, thread bc5-chainwd): READs at address 0
  (`GCVM_L2_PROTECTION_FAULT_STATUS` 0x00701031), many (96 callbacks suppressed). The host's last fault: 0x11cc847000,
  status 0x00741051, a TCP WRITE (client and RW fields as in Linux v7.3 `gc_10_1_0_sh_mask.h`).
- **Where the compute queue stood** (devcoredump): MEC queue 2, IB base 0x1041_00000000, `CP_HQD_IB_RPTR` 0x9f3b
  (dword 40,763). The ring's INDIRECT_BUFFER for that base is 0xa448 = 42,056 dwords. The host's buffer was acb
  #587478, 14,667 dwords with 652 checked indirect dispatches (14,667 + 652 × 42 + 5 = 42,056). The read pointer maps
  exactly onto the end of the indirect dispatch at original dword 14047, before an EVENT_WRITE at 14051. The MEC's
  header dump holds the check pattern and the dispatch (37, 45 ×3, 37, 22, 16, 46): a partial flush waits for the
  waves of a checked dispatch, the F403 signature.
- **The dispatch:** program 0x90985c800, arguments at 0x11871ed440, user data 0-1 a table at 0x11872d9920. Its triple at
  submit (journal (b)): −15580, −3940, 2300, stale. At the timeout (the probe): 12220 × 1 × 1. In between it was written
  by GPU work in the same buffer: the direct dispatch 0x909875600 at dword 14002 (13,440 groups, user data 12-13 =
  0x11871ed400). So the CP check passed a legal count, and the dispatch's waves faulted and did not end.
- **Ruled out by this record:** (1) the per-axis-only check on the compute ring (`backend/src/indirect_check.cpp:145`:
  no product staircase when `compute_ring`). 241 of the acb's 652 indirect dispatches pass the per-axis limits at the
  timeout, and none has more than 2^22 groups. (2) A host drop in this buffer: the only drop was a label wait already met
  at submit. (3) "Garbage at submit" as a sign by itself: 981 of 985 indirect dispatches of 0x909936c00 have garbage
  triples at submit in every buffer of the window, healthy ones included (GPU-written later; R13).
- **Open candidates:** (A) the table at 0x11872d9920, or the lists the 12,220 counts, hold null or stale entries when the
  dispatch runs; (B) the scratch page 0x11871ed400 is shared by several passes (acbs #587469 and #587470 use it through
  0x11d04f2500, 0x11d04f2f00 and 0x11d04f3400, on the same ring). No dispatch on another ring used the page in the
  window, so this record does not implicate way 2's ordering.
- **Catcher (a) failed, and why:** the watchdog fired, but `std::system`'s forked child (pid 654388, named after the
  thread, `bc5-dj430`) stood in D state in `drm_sched_entity_flush` at 20:25:48.9 (live sampler). At exec, closing the
  close-on-exec DRM fd runs amdgpu's flush, which waits for the context's jobs, which were the hung ones. So no umr ran.
  This is likely also why exp 0058's dumps landed after the reset (F112). Build 2 spawns the helper while the GPU is healthy.

## Build 2 (`104cbf66`, unit `51f7e7b5`) and chain S

(a) The wave reader is a helper shell started by `popen` when the watchdog thread starts (at the first job wait). At the
stall the watchdog writes one line to its pipe, and the helper, which holds no DRM fd, runs the halt. (d)
`BC5_0430_SNAP=1`: with each dump, 512 bytes at every 64-bit user-data pointer of the last 16 dispatches per ring
(`snap0430-<k>.txt`), read with `process_vm_readv`. That is the memory at the dump, not at the run (R13). Chain S
(`h430S*`) started 20:39:22 with `BC5_0430_WAVES_MS=900 BC5_0430_SNAP=1` and the rest as before.

### Lesson (for LESSONS.md, the top session's call)

**A diagnostic that forks at a GPU hang never runs.** `std::system`, `popen` and `fork + exec` at a stall create a child
that inherits the emulator's close-on-exec DRM fd. At `exec` the kernel closes it, and amdgpu's flush on close
(`drm_sched_entity_flush`) waits for the context's jobs, which are the hung ones. The child stands in D state until the
reset, and the tool it was to start (umr) never runs. Seen in h430R2 (20:25:48.9, the live sampler), and it likely
explains exp 0058's dumps that came after the reset (F112). **Rule:** start the helper process before any stall, while
the GPU is healthy, and only signal it at the stall (a pipe line). Never fork from the stalled process.

## Result 2: h430S1, the hang of 20:47:54 (build 2, `104cbf66`)

Chain S started 20:39:22. h430S1 hung at 20:47:54, 8.5 min in: `comp_1.0.1` and `gfx_0.0.0` timed out, and both ring
resets succeeded (the box stayed up). Fault record `~/bc5-data/captures/faults/20261116-204756` (exit 86); captures
`play-20261116-2039/gc/` (`waves0430-0/1.txt`, `dj0430-0..3.txt`, `snap0430-0..3.txt`, two ib-timeout bins); the
laptop streams `raw/*-h430S.txt`. The chain stopped (class KERNEL).

- **Catcher (a) worked.** The helper's halt ran at the 901-ms stall (`waves0430.log`: 0.32 s), before the reset. Two
  waves, both on ME 0 (the GFX ring; `SQ_WAVE_HW_ID2` 0x071f0006), vmid 7, at PC 0x90997395c and 0x909973d68,
  `SQ_WAVE_TRAPSTS` 0x50000100 (the memory-violation bit set, TODO(verify) the field layout against the gfx10 header),
  `INST_DW0` 0xbf810000. They are halted by a memory violation, not looping (as F249).
- **What they wrote.** One wave's s[8:11] is a buffer descriptor with base 0x11_de0bf180, stride 16, 0x11548 records.
  The kernel's first fault: page 0x11de0bf000, a TCP WRITE, status 0x00741050 (permission 5, no mapping error: no PTE,
  as F257 decodes ring:40). The descriptor was loaded through s[4:5] = 0x118c68c900, a per-object table in
  RenderGpuWcLarge.
- **The pass.** The BVH passes over the per-object "PSR_BVHL" trees (that ASCII is in their user data; the F234 family):
  per object, 0x909973900/b00/d00/f00, then 0x909974400 (the compaction), 0x909977100 and 0x90997a500, all on one
  user-data block (ud3: the arguments at 0x118c68cd00; ud4: the table at 0x118c68c900).
- **The addresses.** Neither h430R2's write (0x11cc847000) nor h430S1's (0x11de0bf000) has a guest range, a view or a
  GPU mapping (the fault record's layout files; R2's catcher line: "K3 no guest range (a hole)"). Both lie past the
  end of an eager GPU heap: R2's is 2.3 MB past RenderGpuWcLarge's end (0x11cc600000), just past exp 0037's 2 MiB zero
  guard; S1's is about 115 MB past RenderGpuWcSmall's end (0x11d6e00000). S1's host-side last fault is K4
  (0xce0871333000).
- **So** both hangs are the title's BVH shaders writing through descriptors into true holes. The console drops such
  writes and reads zero there (F257; `experiments/0412-memory-guardian/DESIGN-learned-windows.md` §7, the K3/K4
  rule). Here they fault, halt the waves and hang the ring. Open: whether those descriptors point into holes on the
  console too (writes silently dropped there) or only here (stale or uninitialised table contents).
- **Catcher (d) missed:** it took the newest 16 dispatches per ring, which belonged to later submissions, not the
  stalled one.

**Proposed build 3** (sent to the top session, waiting for its decision): F1 `BC5_0430_HOLES=1`, the §7 K3/K4 rule
alone (one PRT mapping under the guest's span, unimported parts of views cleared so that a missed import still
faults),
and catcher (e): the snapshot keyed to the stalled submission's dispatches, with 4 KiB at each of their table
pointers. `BC5_GUARD_PRT_BG` is banned from launchers (CLAUDE.md; exp 0412 §53–54), so F1 needs the decision first.

## Build 3a (`394d1d89`, unit `d811b666`) and chain T

The top session (20:5x): F1 waits for the maintainer's word; catcher (e) alone goes ahead. (e) replaces (d): at each dump,
every dispatch of the stalled submission itself (any ring), with 4 KiB at each user-data pointer and at an indirect
dispatch's argument page (`snap0430-<k>.txt` the index, `snap0430-<k>.bin` the bytes; each address once). Chain T
(`h430T*`) started 20:59:31, otherwise as chain S.

## His play: the test shortcut (2026-11-16 21:10)

The maintainer wanted to play and trigger the hang himself (his plays hit it at about 8.5 min). Chain T was ended at
once: h430T1 stopped at 424 s by a TERM to its own emulator (no hang in it; class OTHER), STOP left in place. Build 3b
(`bfde29b6`, unit `69ff539a`: catchers (a), (b), (c), (e) and (f)) went behind one private shortcut,
"BC5 test 0430 (hang catcher)": `~/bc5-work/exp0430/play-0430.sh` (`06081a80`), made by `mkplay0430.py` from
`play-pkg.sh` `47426d8e` (shared launchers untouched). It keeps his saves, his input.cfg (RT on), the empty learned
file and `ulimit -c 0`, with `BC5_GUARD_MAP_RULE` and `BC5_GUARD_PRT_BG` unset, no fuse or kill, and way 2 as the build's
title defaults. It sets `BC5_0430_DJ=1 BC5_0430_ARGS=1 BC5_0430_WAVES_MS=900 BC5_0430_SNAP=1 BC5_0430_TABLES=1` and the
table program list. Checks: `desktop-file-validate`, `bash -n`, and a dry run of the launcher's environment in the
distrobox, cut before the pad watcher and the emulator (all words present, nothing banned). Laptop streams:
`raw/*-play.txt`.

## Result 3: the maintainer's play, the hang of 21:38:40 (build 3b, `bfde29b6`)

He played from 21:12 (the emulator in the live stream) and hit the hang at 21:38:40. `comp_1.1.0` timed out and its
reset succeeded; `gfx_0.0.0` timed out, its reset failed, and `bc5-gpu-watch` rebooted the box (SysRq s, c, 21:38:42.9).
The fault record was written in time (`faults/20261116-213843`, exit 86 at 1584.1 s). Records:
`~/bc5-data/captures/play-20261116-2112/gc/` (`waves0430-0/1.txt`, `dj0430-0..3.txt`, `snap0430-*`, `tab0430-*`,
two ib-timeout bins), devcoredump `20261116-213842-devcd2.txt`; laptop streams `raw/*-play.txt`.

**His question: was the faulting descriptor already wrong in the title's table?** No. It is not stored in a table: the
shader builds it from per-object BVH data. That data was correct at submit and was overwritten, while the BVH pass was
still using it, by another GPU job.

- **The fault:** two waves halted by a memory violation (`TRAPSTS` 0x50000100) at PC 0x909977ae4, program 0x909977100
  (the BVH chain's third pass), on the GFX ring (`HW_ID2` 0x06000006, vmid 6), dcb #1980428. Their s[80:83] is the
  descriptor they wrote through: base 0x5ab6_9e48e5a4 (the other wave 0x5b26_9e48f814), stride 20, 30 records. The low
  word is a plausible heap address; the high word should be 0x0011. The kernel's first fault (0x5ab69e48e000, TCP WRITE)
  is that address.
- **The bad high word:** each wave's s[4:5] points at its object's BVH block (0x118c64ab00, 0x118c64b200); s[106:107]
  holds 0x5aa4 (0x5b14), and the high word is that plus 0x12 in both waves.
- **The block at submit** (catcher (f): 8 copies within #1980428, one per BVH pass, identical): a BVH node (child
  indices, float bounds, 0xffffffff and ±inf sentinels). **At the stall:** 16-byte records {key_lo, 0x283b3xxx, i, i}
  with i counting up. All 91 blocks the submission named differ between submit and stall. Record i lies at
  0x118c5f0100 + 16·i in both faulting blocks: one array laid over the whole block area 0x118c5f0000–0x118c64b2xx. The
  wave read record 0x5aa4 as node data.
- **The writer:** the only dispatches in the journal window that name 0x118c5f0100 are a sort pipeline in every frame's
  acb on compute ring 1 (#1980369, #1980398, #1980431): 0x90996d700, 0x90996e500, 0x90996ec00 and 0x909970800 eight
  times (radix passes, by shape), ud2-3 = 0x118c5f0100, ud4-5 = 0x118c66e100. The title uses that memory in turns:
  BVH object blocks for the graphics queue, a key/index array for the compute queue's sort.
- **When:** acb #1980431, submitted three submissions after dcb #1980428, while the dcb's BVH passes ran (both timed
  out together). Its cross-queue wait at dword 62 (WAIT_REG_MEM64, label 0x12004b4fc8 == 0) was dropped by the host
  as met at submit ("now 0x0 (met) DROPPED"; "2 waits (0 kept for the GPU)"). Through the rest of the play the host
  kept that wait for the GPU ("ring order: acb ... keeps its wait at 0 on 0x12004b4fc8 for the GPU", 837,633 times).
- **Not proven (R13):** the moment of the overwrite is inferred from the copies at submit and at the stall. Who writes
  the label 0x12004b4fc8 is not in this record.

Reported to the top session for his decision; no fix proposed (his order: the descriptor question first).

### The label behind the dropped wait (after his "Tak, zleć poprawkę")

`labscan.py` over the two hung buffers: the label the sort waited on (0x12004b4fc8, `== 0`, 64-bit) is written by the
graphics buffer itself: dcb #1980428, dword 19839, RELEASE_MEM with 64-bit data 0, after its BVH passes (dwords
~12,460–18,390). The protocol: the dcb releases the shared memory by writing 0 when its BVH work is done, and the
compute sort waits for 0. In normal frames the label is non-zero when the acb is submitted, and the host keeps the
wait for the GPU because the dcb's pending write of 0 satisfies it (837,633 "ring order ... keeps its wait at 0 on
0x12004b4fc8" in the play). In the hang frame it was already 0 at the acb's submit, a stale 0 from the previous
frame's release, so the host dropped the wait as met. Neither hung buffer writes a non-zero value to that label.

So keeping a satisfied wait for the GPU would not have prevented this hang: the GPU reads the same stale 0 and passes
too. The waits are value-based on the console as well. The missing piece is the per-frame step that makes the label
non-zero (the title's CPU, an earlier submission, or a packet the host dropped or delayed). Every drop path in
`submit_split` and the acb head and hold-tail paths share the rule "satisfied when the host looks, then dropped"; the
GIVEN UP and CYCLE paths drop unsatisfied waits. Proposed to the top session: F2 (a wait on a label with a pending
write from a not-yet-completed job on another ring is ordered after that job through a submit dependency) and catcher
G (per-wait value, pending writes and decision at submit), waiting for the decision.

## Build 4 (`85a77956`, unit `540d9d3d`): F2 and G, chain V

`ho430.cpp` (tag ho430), applied by `mk0430.py` with four hooks: the wait in `submit_split`, the job's submit
(`register_label_writes`), its completion (`forget_label_writes`) and the GIVEN UP / CYCLE line. **F2** (`BC5_0430_F2`,
on unless "0"): a wait satisfied when the host looks, while a not-yet-completed job on another ring has a registered
pending write to that label, waits on its own submitting thread until that job completes (at most 250 ms); refused when
the writer job holds a kept GPU wait on a label this buffer writes (a cycle). **G** (`BC5_0430_G`, on unless "0"): a
32k ring of label events (waits seen with value and pending writes, writes registered, writes the filter dropped, F2
events, given-up and cycle drops), dumped as `g0430-<k>.txt` with each stall dump, and a count line every 30 s.

**h430V1** (22:01:56, F2 + G + every catcher): NO_CRASH to G+1500, 0 kernel lines. At t 391 s: F2 waited 13,315 times
(10.6 s in all, 0.8 ms on average, all acb waits for a GFX-ring job), cycles refused 0, bound reached 0. So "satisfied
at submit with a pending GFX-ring write" is the normal case, about 34 a second (mostly label 0x12004b37c8). G: 16,049
label writes dropped by the host's filter in 391 s; 2 given-up unsatisfied waits.

**Cost (one run each, not separated):** 35.7 flips/s against 43.8 in h430R1 (build 1, the same route, without F2, G,
the table copies and the snapshot), 118 s with a frame gap over 100 ms against 13. F2 as built holds the acb until the
whole writer job completes; the console's wait ends at the release write inside it (dcb #1980428's RELEASE_MEM sits
at dword 19839 of 33286). Proposed to the top session: an A/B of F2 alone, then F3, a precise form with a host shadow
slot written right after the writer's release and the waiter's wait redirected to it on the GPU (like exp 0341's
`bc5/shadow_labels.hpp`, but across jobs; a backend change).
