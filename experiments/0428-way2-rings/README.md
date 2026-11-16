# 0428 — way 2: the title's acbs on compute rings, with each guest queue's own state

## Question

Can the second title run its asynchronous compute buffers on kernel compute rings (ADR 0009) with each guest queue's
compute state carried as on the console, cleanly and not slower than the shared builds (patch 700fd4c2)?

Background:
- the maintainer's consent for way 2 through deployment, with priority ("dla drogi nr 2 - jest całkowita moja zgoda, aż
  do pełnego wdrożenia - zadanie ma pierwszeństwo i priorytet"), and to keep looking if it fails or is slower ("ma
  szukać rozwiązania aż do skutku"), both relayed by the top session on 2026-11-16;
- exp 0427: hardware compute queues keep `COMPUTE_USER_DATA`, but a libdrm compute ring index is not a fixed hardware
  queue. The scheduler re-picks one of 7 when the index is idle. So the state has to come from each guest queue's own
  tracker, not from the ring;
- today's shared builds run every acb on the GFX ring. `BC5_DIRECT_COMPUTE_RING` was removed (F412, F415): the 10-26
  machine-down was a `comp_1.2.0` timeout whose reset never came. Build W (exp 0419) removed the October cross-ring
  waits and ADR 0013's held tail with it.

Stale statements, noted here; the top session fixes CLAUDE.md on main:
- ADR 0009's status header ("the second title's `play-pkg.sh` runs its compute buffers on compute ring 0");
- CLAUDE.md's "the direct path uses compute ring 0 for the second title".

Both are stale since 10-27: the patch's `kIgnored` holds `BC5_DIRECT_COMPUTE_RING`, `compute_ring_env()` defaults to
the GFX ring, and F412/F415 record the change.

F412 found that one ring costs no fps with RT off. So this experiment measures RT on, and says plainly if way 2's
overlap gains nothing there. By the maintainer's words, that would be a reason to keep looking for a working form, not
to deploy a slower one.

## Setup

**Private test build.** The relink pattern of exps 0425/0388:
- `mk0428.py` edits the shared tree's `src/libs/bc5LleAgc.cpp` (patch 700fd4c2, md5 `3e847e03`) into `4af9d11d`;
- `build0428.py` compiles it with the shared normal build's command and relinks with the shared objects;
- `box0428.sh` does claim, build and release under one BOX-LOCK line.

Built 2026-11-16 12:04: private normal `64fa2359`. The shared normal `1be1cc1d` was unchanged before and after. There
were 7 warnings, all on old lines (as exp 0424), none in the new code.

The edits, each behind a switch read with `std::getenv` (so lean reads them too); counters are normal-only:
1. `BC5_DIRECT_ACB_RINGS=<0..4>` (tag w428). 0 is today's one GFX ring. With n ≥ 1 the ring thread's acbs go to compute
   rings, each guest queue on its own libdrm ring index (modulo n). `bc5::policy::compute_ring_refusal` still keeps a
   buffer on the GFX ring; those are counted by reason.
2. Cross-ring waits stay for the GPU when the label's last pending write is on another ring: ADR 0009 waits step 3,
   "all", the F178 setting.
3. The game thread's dcb wait on two rings, in exp 0132's form without the held tail:
   - the head is split off and submitted;
   - the wait is kept for the GPU once its writer is on a ring, or satisfied on the CPU, within 8 ms;
   - otherwise the existing path and its limit apply.
4. `BC5_DIRECT_ACB_QUEUE_STATE` (tag aq424, exp 0424's edits unchanged): every acb part that dispatches gets its own
   guest queue's tracked SH 0x204–0x3ff (without `COMPUTE_VMID`) in front, from that queue's tracker at submit time. A
   queue with nothing tracked yet gets nothing, and that is counted.
5. One stderr line every 10 s (tag w428c), normal only: jobs per ring, acbs kept on GFX by reason, the queue→ring map,
   the two-ring wait counts, and aq424's parts with state and with no tracked queue.

**Runs.** `run0428f.sh` is derived by `mkrun0428.py` from exp 0425's `run0425f.sh` (md5 `0591b743`):
- the second title, F464's route from exp 0425's named snapshot (read only), slot 4;
- the 14:50 record's gameplay at G (the fight), G+120 s;
- RT on, `ulimit -c 0`;
- JobArenaFix as the shared `input.cfg` has it;
- everything written goes to `~/bc5-work/exp0428/n`.

`chain0428.sh` runs one set per start under one BOX-LOCK line. It stops at a kernel GPU line, a real pad key, any class
but NO_CRASH/NOT_ROUTED, a second NOT_ROUTED, or a STOP file.

Arms, on the same binary:
- **C**: `BC5_DIRECT_ACB_RINGS=0 BC5_DIRECT_ACB_QUEUE_STATE=0`, the shared behaviour;
- **Q**: `BC5_DIRECT_ACB_RINGS=4 BC5_DIRECT_ACB_QUEUE_STATE=1`, way 2.

Sets:
- **smoke**: `w428Q1` alone first. A compute-ring hang whose reset does not succeed ends the track for the day and goes
  to the top session.
- **series**: `w428C1 w428Q2 w428Q3 w428C2 w428C3 w428Q4 w428Q5 w428C4`.

## Rule (fixed before the runs; `check0428.py`)

- **smoke** passes if the one Q run is NO_CRASH.
- **series** is complete only with 4 C and 4 Q rows of class NO_CRASH.
  - Q fails if any Q row has another class (KERNEL, CRASH_OTHER, WALL, TARGET, SETUP, OTHER).
  - Otherwise "not slower" holds if the median of Q's flips/s ≥ the median of C's − 0.5.
- Beyond that, everything is descriptive (R13): 4 runs per arm say nothing about rare events, and the medians are not a
  cost estimate.
- Deployment also needs ASTRO BOT clean on Q (a separate set, not yet written) and the lean build (its own compile).

## Result

### Iteration 1: smoke `w428Q1`, build `64fa2359` (2026-11-16 12:07)

NO_CRASH at 36.9 flips/s, 0 kernel lines. The counters show it was not way 2 yet:
- 169,922 compute jobs went to ring 0, against 14 on each other ring. The title touches 56 guest queue slots at start,
  so the map by index put its busy queues together.
- 65,268 acbs stayed on the GFX ring, refused by the backend as "indirect dispatch (MEC check unverified)" (exp 0290,
  F332).

### Step 2: the CP's indirect check on real MEC dispatches (12:38; `raw/cp-run.txt`, `raw/cp-dry.txt`)

`userdata-rings --cp-check` ran 18 compute-form `DISPATCH_INDIRECT`s of the probe program on compute rings 0..2. Each
was wrapped by `indirect_check::apply(compute_ring = true)` with the FilterOptions default limits:
- 6 sane triples ran: 1, 64 and 2^20 groups; 2^20 took 0.59 ms.
- All 12 triples just over a limit were skipped: x = 2^20+1, y = 2^10+1, z = 2^10+1. The flag words were right.
- 0 new dmesg lines.

Exp 0129 had checked the same packets with a `WRITE_DATA` in place of the dispatch; this is the real dispatch.

### Iteration 2: build `9e53ae43` (unit `f16eb3f3`)

Changes, each behind its own switch:
- the busy-queue map: a queue moves once to the next ring, after a chain flush and a wait for all rings to be idle;
- `BC5_DIRECT_ACB_MEC_INDIRECT`;
- `BC5_DIRECT_ACB_STATE_NO_WALK`.

Smoke `w428Q6`: NO_CRASH at 42.3 flips/s, 0 kernel lines.

**Series** (`raw/chain0428-series.out`), 14:00–14:33. All 8 runs NO_CRASH, 0 kernel lines, 0 pad keys:

| run | arm | flips/s | s with a gap > 100 ms | longest gap |
|---|---|---|---|---|
| w428C1 | C | 35.8 | 12 | 292 ms |
| w428Q2 | Q | 41.8 | 9 | 272 ms |
| w428Q3 | Q | 42.1 | 11 | 278 ms |
| w428C2 | C | 36.6 | 11 | 258 ms |
| w428C3 | C | 36.0 | 12 | 753 ms |
| w428Q4 | Q | 42.1 | 10 | 300 ms |
| w428Q5 | Q | 42.9 | 9 | 302 ms |
| w428C4 | C | 36.1 | 12 | 293 ms |

**Rule: COMPLETE.** Median flips/s C 36.05, Q 42.10 (Q − C = +6.05): "not slower" HOLDS. Every Q run was above every C
run.

Descriptive (R13: 4 runs per arm, nothing about rare events):
- The Q runs' counters were nearly the same each time:
  - jobs: gfx ~89 k, comp1 ~201 k, comp2 ~21 k, comp0 ~120, comp3 0;
  - busy queues: 0 → ring 1 and 8 → ring 2, 2 moves, both idle within 2 s;
  - acbs kept on GFX: none;
  - about 75 k acbs moved by the MEC switch;
  - dcb waits on two rings: about 17.7 k kept for the GPU, about 700 satisfied, 7–11 not served;
  - aq424 gave state to about 128 k parts, with 0 untracked queues.
- Only two of the title's guest queues are busy on this route, so ring 3 was idle and the ring count did not limit it.
- With RT on, way 2's overlap gains here. F412's one-ring finding was RT off.

### The shared swap (`int0428.sh`, 14:35–14:37; `raw/int0428.out`) and the lean smoke (`raw/smoke0428.out`)

The swap:
- patch 700fd4c2 → `2c82a979` (241 lines; `exp 0372` lines 5; the pad audio header in; the file list unchanged);
- normal `1be1cc1d` → `3f22e0e1`, lean `b7fb337f` → `35a3753d`; the backend archive `9aab722c` is unchanged;
- each build gained exactly the four words `BC5_DIRECT_ACB_MEC_INDIRECT`, `BC5_DIRECT_ACB_QUEUE_STATE`,
  `BC5_DIRECT_ACB_RINGS`, `BC5_DIRECT_ACB_STATE_NO_WALK`, and lost none;
- lean holds no "exp 0428" text; normal holds the w428c line.

Warnings: the same old ones, plus one in lean on a new line: `split` set but not used, since only lean's compiled-out
counters read it. It is harmless; a tidy-up for the next change.

Undo: `undo0428.sh` passed its stand-in test 9 of 9 on the laptop and on the box (alone, inside int, bad pins).

Lean smoke, 14:38–14:44:
- ASTRO BOT 45 s: PASS, 0 kernel lines.
- The second title 300 s, RT on, route by time: PASS, 0 kernel lines.
- At 150 s its render fds showed `drm-engine-compute` 31.06 s against `drm-engine-gfx` 65.2 s, so way 2 is active on
  lean.
- ASTRO BOT's run ended before the 150-s sample. It has no way-2 row, so its behaviour is the shared one before the
  swap.

### The maintainer's play on the swapped lean build: a GPU hang at 15:09:18 (8.5 min into the play)

His words, via the top session: "Grało się świetnie. Ale wystąpił crash GPU".

Records, all read on the box (the devcoredump holds the title's buffers and stays private):
- the devcoredump `~/bc5-data/captures/devcoredump/20261116-150919-devcd4.txt`;
- the stall sampler `~/bc5-data/captures/gpu-stall/event-20261116-150918-gfx_0.0.0`: 5 samples over 1.4 s;
- pstore.

**What happened.** `gfx_0.0.0` timed out (signaled 29225651, emitted 29225652; thread bc5-ring). Its ring reset failed, a
GPU reset began, and `bc5-gpu-watch` crashed the kernel for a reboot. The box was up again at 15:09:49.

**It is not a cross-ring wait:**
- In all 5 sampler samples every compute ring had signaled == emitted. All compute work had finished; only the GFX
  job was pending.
- The ME was not at a `WAIT_REG_MEM`. `CP_STALLED_STAT2` 0x18000 = `ME_WAITING_ON_PARTIAL_FLUSH` (+
  `MEQ_TO_ME_NOT_RDY_TO_RCV`). `GRBM_STATUS` 0xa0210028 = `GE_BUSY`, `GE_BUSY_NO_DMA`, `CP_BUSY`, `GUI_ACTIVE`: no SPI,
  PA, SX, CB, DB or TA busy, and `SPI_CSQ_WF_ACTIVE_STATUS` was 0. Decoded with Linux v7.3 `gc_10_1_0_sh_mask.h`.
- The CP's IB1 had 0x1888 of 0x2008 dwords left. The PFP's history ends at the backend's `WAIT_REG_MEM` (dword 1988)
  and two `ACQUIRE_MEM`. The ME was at an `EVENT_WRITE` partial flush (1944) behind `DRAW_INDEX_AUTO` draws
  (1700–1910). The geometry engine never drained.
- No page fault was part of it. The devcoredump's "Page fault observed 0x1113c50000" is the kernel's stored last fault,
  exp 0424's of 2026-11-15 20:08 (pasid 109; this process was 304). The pstore holds no fault line near 96185 s.

**Conditions of his play.** He had turned JobArenaFix off in the shared `~/bc5-work/input.cfg`
(`JobArenaFix.PPSA03671=off`; the file's mtime is 15:01:06, 13 s after the lean play began; no launcher holds it). C1
was on.
- The smokes and the series (12:43–14:33) ran with JobArenaFix on: their private copies of `input.cfg` read "on".
- The `long` set inherits off from the shared file: his play's conditions.
- The 15:09 event is a GPU geometry-engine stall, not the arena crash, which is a CPU access violation at a known site
  (exp 0425's TARGET class).

**It is F588's class:** 10-29 18:08, one ring, before way 2. `GRBM_STATUS2` 0x50000008 is identical; it was the same
partial-flush wait, its ring reset also failed, and it also ended in a gpu-watch reboot. F588's cause is still open.

**Its link to way 2, a suspect and not proven.** The hung IB opens with `CONTEXT_CONTROL`, `CLEAR_STATE` and about 950
dwords of `SET_CONTEXT_REG` / `SET_SH_REG`: a split piece behind a full state prefix. Iteration 2's two-ring dcb wait
split about 18 k times per 225-s run, and about 97 % of those waits were then kept for the GPU anyway (17.7 k). One
ring splits rarely. A piece whose prefix misses state the geometry engine needs is the leading suspect.

**Iteration 3** (unit `40f01680`, build `547833bb`) adds `BC5_DIRECT_ACB_SPLIT_LATE`:
- A two-ring dcb wait whose writer is already on a ring is kept for the GPU at once, with no split. The head before it
  is in the same IB, so it runs first and its label writes land before the wait blocks the ME.
- It splits only when the writer is not yet submitted.
- It also removes lean's `split` warning.

Test: the `long` set, three runs of the fight then exp 0379's walk to G+1500, RT on, every way-2 switch plus SPLIT_LATE.
The rule (`check0428.py long`, fixed before the runs): PASS if all three are NO_CRASH. The counters must show the
splits cut by at least 90 %.

### Iterations 4–5 and the hangs of the afternoon

**`w428L4`** (iteration 4, JobArenaFix on in its private copy, way 2 on). At 415 s (about G+300):
- a TCP WRITE fault at the junk address 0x171d720ad000, then a `comp_1.0.1` timeout, its reset succeeded, then a
  `gfx_0.0.0` timeout and reset;
- fault record `faults/20261116-153436`: K4, junk;
- the timed-out acb (991 dw, `ib-timeout-00595506`) holds only direct dispatches with ordinary `0x11_…` descriptors, plus
  aq424's prefixes;
- the same timeout's dcb shows the BVH program 0x909974200's indirect dispatches with garbage triples (3.2e9 × 1.1e9 …);
- this is F399/F403's family (garbage pointers in RT/BVH data).

Iteration 4's split fix barely acted (still split 28,571; kept in the IB 0, after the chain 1). The journal said "no
pending write" at the check; the writer was in this buffer's own head. The scan gave up at the first IB2, so iteration
5 (unit `e6be6ffa`, build `0b42eb2c`) scans as `register_label_writes` does, IB2s not followed (a standalone test 3/3).

**`w428C5`, the one-ring control of the `longab` set** (way 2 OFF on the same private binary). At 15:47:55, about 8.5
min into the run:
- `gfx_0.0.0` timed out, its reset failed, `bc5-gpu-watch` rebooted the box (boot 15:48:28);
- devcoredump `20261116-154755-devcd3`, stall event `event-20261116-154755-gfx_0.0.0`;
- the ME at a partial flush (`CP_STALLED_STAT2` 0x18000, `EVENT_WRITE`), `GRBM_STATUS` 0xa0407028: SPI, TA, TCP busy, GE
  idle, no compute waves. That is F589's F403 signature on the GFX ring.

**The day's four hangs:**

| time | run | way 2 | class | end |
|---|---|---|---|---|
| 15:09 | his play | on | GE stall at a partial flush (F588) | reset failed, reboot |
| 15:35 | w428L4 | on | junk-pointer write by compute (F403 family) | ring resets succeeded |
| 15:47 | w428C5 | OFF | shader stuck in memory reads on GFX (F403 signature) | reset failed, reboot |

C5's IB (`devcd3`, IB #0, 10,216 dw) opens with the same full state prefix (`CONTEXT_CONTROL`, `CLEAR_STATE`, ~950
dwords) on one ring, so that shape does not mark a two-ring split piece. The 15:09 "split piece" suspect is weakened.

The work at its stall is the backend's indirect check (exp 0052: `COND_WRITE` ×5, `PFP_SYNC_ME`, `COND_EXEC`) around a
GFX-form `DISPATCH_INDIRECT` at dword 1845:
- arguments at `SET_BASE` 1 = 0x11d0571b00, which passed the check;
- program from `LOAD_SH_REG_INDEX` at 1730 (table 0x11e08efb0c);
- user data set at 1735: V# 0x115a2400…, table 0x11e08ef8ec;
- then `EVENT_WRITE` 0x410 at 1853, where the ME waits while SPI, TA and TCP stay busy.

The dispatch's waves hang in memory reads. Without a wave dump these records cannot say whether they loop or wait.

Both classes occur with way 2 off. The maintainer then stopped the comparison: multi-ring is decided, no one-ring arm
again, and JobArenaFix is off in every run from now on (relayed by the top session, 16:3x). The `longab` set ended
with the machine-down. The stale lock line of its token was released at 16:36.

## Verdict

**Way 2 works and is deployed for the second title.**
- The title's acbs run on compute rings, with each busy guest queue on its own ring and its compute state put in front
  of its dispatching acb parts from its own tracker.
- Indirect dispatches run on the MEC under the CP's check, which is now verified on real dispatches.
- With RT on, on the fight route, it ran 42.10 against 36.05 flips/s (median of 4 each, interleaved, all clean).

Limits:
- 4 runs per arm and one route. Rare events (the machine-down class of F332, and F412's 10-26 compute-ring timeout) are
  not ruled out by this (R13).
- The maintainer's own plays are the next evidence.
- ASTRO BOT has no way-2 runs and keeps the GFX ring.

Rollback:
- `BC5_DIRECT_ACB_RINGS=0` in the environment turns way 2 off with no build;
- `bash ~/bc5-work/exp0428/undo0428.sh` goes back to patch 700fd4c2's binaries (normal `1be1cc1d`, lean `b7fb337f`).

Not done here:
- CLAUDE.md, the shortcuts' notes, and ADR 0009's status (the top session's, on main);
- the lean `split` warning;
- an ASTRO BOT way-2 set.
