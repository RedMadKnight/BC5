# 0406 — Which safeguards can go to win back frame rate

**Status: laptop audit done; the test build and the arms are proposed, not built, not run.** Written 2026-11-05 on the
top session's order. The only box access was the number claim (`~/bc5-work/exp0406`, 21:24, on the top session's GO, no
emulator running).

## Question

Since BC5 began we have added many safeguards against GPU hangs, corruption, audio faults and memory faults. Some of them
cost frame rate. The measured trend at his slot-4 save: e6 41.3 flips/s, e7 with the memory fixes 38.4 (−7 %, r6c/r7m,
exp 0401), and F2 (`BC5_DIRECT_FL_SERIAL`) about −3 %. Which safeguards can be dropped because another one overlaps
them, a later fix covers the same cause, or their question is already answered? What does one test build look like
that turns each drop into a switch, and how should it be A/B-tested?

## Setup

Laptop only. Code: the `exp/0401-mesa-preamble-switches` tree (24fccd38), whose units make his new shortcut's binary
(e8, dc7fb4e0); `P:` below means a line of that tree's `backend/kytyplus-patches/0001-bc5-lle-agc.patch`. Effective env:
the e8 shortcut's words (`shortcut0401.sh cpacb`, 24fccd38) plus the launcher and `bc5-run.env` as recorded in exp 0396's
`W1.manifest.txt` and exp 0399's `Z1.manifest.txt`. Today's box files were not read.

Four laptop agents each audited one area: GPU sync, logging, memory, and host (audio, pad, FS, APR). Each table is in
`raw/audit0406-*.md` with file:line and F-row citations. The claims this ranking rests on were checked again by hand:
- the probe's copy at submit (P:34536);
- the AMM ports' per-page map (`mkamm0401.py:158, 357-360, 510-520`);
- `learned_apply`'s cost (exp 0288 README:62).

## Result

### Four facts that bound the gain

1. **On the render thread, host CPU does not set the frame rate** (F482, F483, F470). About 80 % less `emit_prefix`
   gave 33.8 against 33.6 flips/s, and exp 0360's two host cuts moved nothing; the time freed goes into the title's own
   job-wait spin. So CPU-only removals on that thread should be expected to give about 0 fps. What does pay off:
   - GPU time;
   - stalls on the game thread, which make the gaps over 100 ms;
   - free memory: page-cache re-reads are the largest known cost, 41.2 against 24.9 flips/s (F620, F621).
2. **On one ring (`COMPUTE_RING=-1`), the two-ring safeguards never run.** That covers `TWO_RING_WAIT_MS`,
   `CROSS_RING_WAITS=all`, `RING_DEPS=dcb` and the hold tail (P:31587, P:31621, P:31324; direct.cpp:1579-1589). They cost
   nothing now, and removing them gains nothing. Ten launcher words do nothing at all since F812 folded them into code:
   `RINGS`, `REOPEN`, `GDS_ALL`, `GDS_SHADOW`, `ASYNC`, `RING_ASYNC`, `MAX_IN_FLIGHT`, `PIECES_DRY`, `PIECES_FULL` and
   `RING_ORDER_WAITS`. The same is true of `HOLD_TAIL`.
3. **The −7 % from e6 to e7 is most likely not a safeguard** (medium confidence; `raw/audit0406-memory.md`).
   - r6c ran first and r7m right after it, in one boot, once each. Both rates include the load.
   - The e8 "c" arms, with one binary and one set of words at the same save, spread over 31.9–35.0 flips/s. That spread
     covers the 2.9 flips/s gap.
   - r7m was smoother on everything else: 181 against 219 seconds with a gap over 100 ms, a longest gap of 1.2 s against
     3.3 s, and 5 s against 63 s stalled under PSI full.
   - The zero skip has no write protection and no fault takeback. It finds CPU writes with `SEEK_DATA`, and its canary
     scans one 2 MiB slice every 50 ms on a nice-10 thread.
   - No e7 code on a hot path costs anything near 7 % with its switch off. The only mechanism with a precedent is the BO
     list growing (F172), and F542 measured it at no cost.
4. **Two of the biggest wins are already in the new shortcut.**
   - `JOURNAL_QUIET` cut `direct.log` from 385 MB to 24 MB in 1,042 s. That removes most of the journal's page-cache
     load (F353).
   - `FL_CRUMBS` is off. It was the one switch present in every slower all-on arm of 0401 (sall 22.8 against s0 23.4; tall
     22.9 against t0 23.6; t6all 22.0 against t6 22.8).
   - The lazy release's dry pass and F2 are not in it either.

### Ranked drop candidates (likely gain × low risk, best first)

"Off" is the value that gives the old (today's) behaviour back where a new switch is proposed, and the true disable value
where the item is an env word. Several older parsers treat `=0` as on (lesson R41; switch-history REPORT). F767 fixed seven
of them. The ones still checked as on at `=0` are `SHADOW_LABELS`, `GPU_CHECK`, `DMA_SYNC`, `REMEMBER_UNMAPPED`,
`MEC_INDIRECT`, `TIMING`, `FRAME_PROFILE`, `TIMEOUT_PROBE`, `AUDIO_TRACE`, `MEASURE` and `FPS_COUNTER`: only **unset** turns
these off.

| # | Item | Added by | Guards against / why it exists | Evidence now | Overlap or later fix | Cost | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | `BC5_DIRECT_ACB_INHERIT=journal` (+ ring census) | exp 0403, 0401 e2/e3 | catcher: acb parts that dispatch on an inherited program | 0 lines in every play and night arm; census empty (hang1954-0401.md:248) | `ACB_STATE_RESTORE` and the full-state prefix carry the compute state | a full tracker apply + scan of every acb part on bc5-ring under a mutex (mkunit0401.py:766-800); `apply_level` is 10.4 % of render samples for dcbs (exp 0367) | **drop**, high. Unset. |
| 2 | `BC5_R3_REWIND_CATCH`, `BC5_R3_DROP_CATCH` | exp 0405 G4, G8 (0401 e5) | catchers | answered: drop catcher saw only opcode 0x4a (112,152), never 0x20 (0401 README:327) | — | one lookup per packet | **drop**, high. Unset. |
| 3 | `KYTY_BC5_AMM_PRT_CMDS=1`, `KYTY_BC5_AMM_EXTRA_CMDS=1` | 0401 e4, item 7 (AnyPS5 ports) | behaviour for titles that use AMM PRT/remap commands | the second title imports none of the 26 NIDs | — | with either on, **every** AMM map/unmap takes one recursive mutex and adds a `std::map` node per 16 KiB page (`mkamm0401.py:357-360, 516`): ~16 MiB for the 3.1 GiB pool, malloc churn at ~4k maps/min | **drop for the second title**, high. Ports are not title-gated, so the port stays and only the word goes for this title. Unset. |
| 4 | Probe copy at submit (`BC5_DIRECT_TIMEOUT_PROBE`) | exp 0160, F317, F334 | the hang record: the stuck IB and its executed offsets | every hang read used it; keep the probe | the devcoredump overlaps IB #0 only | with the probe on, **every** async job copies its whole submitted IB and offset list into heap vectors (P:34536), plus an uncached `getenv` per submit, at ~965 submissions/s; IBs up to 1.67 M dwords (F768) | **merge**, medium-high: new switch `BC5_0406_PROBE_LAZY`, below. Not measured. |
| 5 | Learned windows / `learned_apply` (`BC5_DIRECT_LEARNED`) | exp 0103-era learned faults, D15 | GPU faults outside the eager heaps | 107 windows of 96 MiB, 46 at junk addresses (bits above 40, or 0) that import nothing (exp 0288) | eager heaps cover most of the real ones | exp 0288: 10,028 calls over 5 ms, 83 s of a 1,742-s session, max 633 ms, **on the game thread** → gaps. It copies and sorts the whole mapping list at every layout change, and the zero skip's ~1,000 canary mappings lengthen that list | **merge**, medium: `BC5_0406_LEARNED_PRUNE`, below. Not re-measured since exp 0288. |
| 6 | `BC5_DIRECT_GPU_CHECK_PRODUCT=1` (the staircase) | exp 0342, F414/F415 | runaway grid products in the CP check | never seen to refuse a dispatch; as built it cannot catch F403 (F416); F403 recurred with it on | the base `GPU_CHECK` keeps the absurd-count check (F106) | 44 of the check's 88 dwords and one of its two PFP_SYNC_MEs (exp 0352): ~0.4 of F439's 0.8 ms GPU a frame, ~1–1.3 % flips (reasoned) | **drop candidate**, medium, **only after an RT-on A/B**: it was one of F415's two RT-on guards and was never tested alone. Off: `=0` (F767; verify on the archive used). |
| 7 | `BC5_DIRECT_TABLE_CATCHER=1` | 0401 e (exp 0402 item 4) | catcher for F403 sub-class B | one reading: 24 of 256 slots changed at the e8 F403 timeouts (hang1954-0401.md:816) | — | hashes up to 256 argument/LOAD tables (≤ 64 KiB each) at submit and again at completion; ~578k changes counted in a 155-s play | **keep while F403-B is chased**; drop when the top says it is answered. Unset. |
| 8 | `BC5_DIRECT_FRAME_PROFILE=1`, `KYTY_BC5_AUDIO_TRACE=1` | exp 0177-era profiling; audio trace exp 0180s | diagnostics | the scripted routes gate on frame-profile lines; the replug check reads `pad route:` lines | — | ~1.4 MB/min of journal and ~5 mutex sections per submit (FRAME_PROFILE); ~1 line/s per port + `fflush(stderr)` (AUDIO_TRACE) | **drop in his plain play only**, medium, small gain. Keep in the test arms, so not measured by this plan. Unset. |
| 9 | `KYTY_BC5_MEASURE=1`, `BC5_DIRECT_PIECES_DRY=1` | old | — | `MEASURE` does nothing while logging is on (P:27266-27270); `PIECES_DRY` is read nowhere | — | 0 | **cleanup**, high. Unset. |

### Kept, with the reason (detail in `raw/`)

- **GPU path** (`raw/audit0406-gpu-sync.md`):
  - the base `GPU_CHECK` (F106; ~0.4 ms; its batched form saved only 0.27 %, F438);
  - `SHADOW_LABELS` (an RT-on guard, F414/F415, R41);
  - `HOST_INDIRECT` (F419), `DMA_SYNC` (F107), `DMA_SNAPSHOT` (F172, no measured cost on one ring);
  - `ACB_STATE_RESTORE` (F685: 3 of 3 faulted without it, 3 of 3 clean with it);
  - the full-state prefix (F204; 45.0 → 43.9 fps). Exp 0367's byte-identical C1 rewrite is CPU-only, so it is a later
    fold, not a test item;
  - the F41 CP DMA wait;
  - the soft-CP R3 items (`WAIT_IDLE` costs 0 here, F144);
  - `COMPUTE_RING=-1`. This is the largest possible gain (F178: two rings, 41–42 fps against 32–34 at the start screen)
    and also the largest risk (F332 machine-down), so it is not a safeguard to drop here.
  - `CS_PREFIX` is a superset case of `ACB_STATE_RESTORE` (33 actions in 140 s, F321). Merging them gains about 0.
  - `CP_COHER_START_DELAY` is **unknown**: there is no A/B, and the register latches. See arm C below.
- **Memory** (`raw/audit0406-memory.md`):
  - `EAGER_NAMES` (F88, F207);
  - the zero skip (GTT −440 MiB, swap −739 MiB in r7m);
  - `LAZY_NAMES` (−242 MiB, F394);
  - `REMEMBER_UNMAPPED` (a 9-ms walk saved per frame);
  - `AMM_PRT` (F161; its page-table cost is unknown);
  - `ALL_RW` and `DMABUF` (ADR 0006);
  - `CACHE_MIB`, `VMA_BLOCK_MIB`, `GUEST_MEMORY_MB=13824`, and `MEMORY_FROM_PARAM=0` (on, it gave the AMM fatal on e2);
  - `AMPR_WAITS` (a behaviour change), `JIT_SHM`, and the R3 mem group (edge paths only).
  - Later memory gains, not safeguards: a fresher and larger zero list including AMM and RenderGpuRwLarge, a 32 MiB
    snapshot ring, 48 MiB staging, and a `DONTNEED` on the mount's disk-cache reads (a second page-cache copy beside
    FUSE's).
- **Host** (`raw/audit0406-host.md`): every port stays (the port rule). On a hot path each costs one switch read or bit
  test. Small code merges, none on the render thread, are left for later:
  - the AudioOut blocking wait polls every 500 µs (P:27011): about 2,000 wake-ups a second on the nice −15 audio thread,
    which takes SDL's lock. It is an audio change, so it needs exp 0372's replug check;
  - an APR thread pool instead of up to 7 threads created and joined per run;
  - per-queue APR condition variables;
  - the mount-table stat outside its lock.
  - Optional storm arms, env only: `BC5_MOUNT_DISK_CACHE` unset, `KYTY_BC5_APR_READAHEAD=0`, `KYTY_BC5_APR_PARALLEL=4`.
    Gains are unlikely (F814, RR4, RR5).
- **Hang-record kit that stays** (`raw/audit0406-logging.md`):
  - the devcoredump rule;
  - `BC5_GC_DUMP_DIR` with `BC5_DIRECT_JOURNAL=min`. `JOURNAL` must stay `min`: anything else brings back an fsync per
    submission and turns async jobs off (P:28562);
  - `TIMEOUT_PROBE`, with item 4's fix;
  - `TIMING` with `JOURNAL_QUIET`: its 8,192-line ring is the "last submits" record;
  - the memory line, `FPS_COUNTER`, and `TABLE_CATCHER` while F403-B is open.
  - With the FL catchers off, a draw-class hang is still classed and probed, but the stuck draw is not named. That is the
    e8 shortcut's accepted trade.

### Proposed test build: 0406 = e8 + three code switches

Base: e8's units (dc7fb4e0), built the way 0401's `box0401.sh` builds a series. Each new switch defaults **off**, which is
today's behaviour, so the binary with no 0406 word set must behave as dc7fb4e0. Each takes only unset, empty or `0` as
off, and has a CPU test with the switch on, off and unset.

- `BC5_0406_PROBE_LAZY=1`: read `BC5_DIRECT_TIMEOUT_PROBE` once (a static). Stop copying `ib_copy` and `ran_copy` at
  every async submit. At a fence timeout, copy them from the job's submitted buffer, which the job still owns because its
  fence has not signalled (TODO(verify): the slot's lifetime in `direct.cpp` up to the completion thread's timeout). Keep
  a ring of the last 32 jobs' copies as the fallback when the slot cannot be read. CPU test: a timed-out stand-in job must
  give the same `ib-timeout` bytes as today.
- `BC5_0406_LEARNED_PRUNE=1`: when the learned file is loaded, drop windows with bits above 40 set or a base of 0. In
  `learned_apply`, skip windows that lie entirely inside an eager heap, where they import nothing. One journal line gives
  the counts kept and dropped. With the switch on or off, count calls over 5 ms and their total, and journal them every
  60 s, so both arms measure it. CPU test: the exp 0288 window list against a stand-in heap layout.
- `BC5_0406_AUDIO_SLEEP=1` (optional; skip it to keep the build free of audio changes): in the main AudioOut blocking
  wait, sleep for the computed drain time (capped at 2 ms) instead of 500 µs polls. It needs exp 0372's software replug
  check (P1, P2) before any play, then his physical replug. It is not in the frame-rate arms.

Not built (env only): items 1–3, 6–9. Not built (later code folds): C1, the APR pool, the mount `DONTNEED`.

### Test plan: route A/B at his slot-4 save

As 0401's r6c/r7m and e8 arms: `run0401t.sh`/`night0401.sh`, private input.cfg with **RT on** and JobArenaFix on, a
private snapshot of the live saves (checksum pinned first, LC_ALL=C), the freeze watcher, the memory sampler, and the
kernel stream to the laptop. Route: slot 4's Continue, then stand still to G+600. Box slots come from the top session,
and nothing runs while he plays.

Arms. Every arm uses the 0406 binary. Base words = the new shortcut's (e8 `cpacb`).

| Arm | Words beyond the base | What it answers |
|---|---|---|
| B | none (all 0406 switches off) | control; also shows the 0406 binary = dc7fb4e0 in behaviour |
| D1 | unset items 1, 2, 3, 9 (`ACB_INHERIT`, `R3_REWIND_CATCH`, `R3_DROP_CATCH`, `AMM_PRT_CMDS`, `AMM_EXTRA_CMDS`, `MEASURE`, `PIECES_DRY`) | the env-only drops, no GPU change |
| D2 | D1 + `BC5_0406_PROBE_LAZY=1` + `BC5_0406_LEARNED_PRUNE=1` | the two code drops |
| D3 | D2 + `BC5_DIRECT_GPU_CHECK_PRODUCT=0` | the one GPU-side drop, RT on |
| D4 (after the top's word on F403-B) | D3 + `BC5_DIRECT_TABLE_CATCHER` unset | the last catcher |

- **Order:** three rounds of B, D1, D2, D3 in a rotated order (B D1 D2 D3 / D2 D3 B D1 / D3 B D1 D2), then D4 and B
  twice each. That is 16 arms of about 13–14 min (G at 150–230 s + 600 s), about 3.7 h, in one boot where possible. A
  ring reset does not stop the series, the top's e8 rule.
- **Measures:**
  - flips/s from G+120 to G+600, not over the whole run, because the load differs by 80 s between arms;
  - seconds with a gap over 100 ms, and the longest gap;
  - the count and total of `learned_apply` calls over 5 ms (the 0406 line);
  - hangs by class: F403 (acb, TA busy) and the draw class (19:54/06:40);
  - memory floor, GTT max, swap max and PSI full from the memory line.
- **Reading:** single-arm noise is about ±5 % (e8: 31.9–35.0), so three arms an arm resolve about 4 % at best. A ~1 %
  item (D3) will not show alone. A drop is accepted when:
  - its arms are not slower than B's beyond the noise;
  - the gaps are not worse;
  - no new hang class appears;
  - and the cost is shown in a counter where the plan has one (learned stalls, probe copies, memory).
  - Clean arms are not evidence of a fix (R18). F403's rate, 2 in 18 e8 arms, is too low for 16 arms to show a change in
    either direction.
- **Before the arms (one box read, GO needed):** r6c's and r7m's `direct.log` lines `pinned … in N BOs`, `timing split`
  and `learned apply:`. These say whether the 7 % had a code cause at all.
- **Arm C, separate (needs reboots):** `CP_COHER_START_DELAY` latches until a reboot, so B against `=0` needs a reboot
  before each arm: B, reboot, C, reboot, B. It runs only if the top judges a reboot cycle worth about 1 % at most.
- **Audio arm, separate:** `BC5_0406_AUDIO_SLEEP=1` under `aud0401t.sh`/`replug0401t.sh` (pulls and late), then his
  physical replug and a DS4 before it reaches his shortcut.

### Expected gain (an estimate, not a measurement)

- **From the drops:** a few percent at most in flips/s.
- **In gaps:** possibly more, from the learned stalls if exp 0288's 633-ms peaks still occur.
- **In memory:** 20–40 MiB from item 3 and from the probe copies' heap.
- **The levers that would move frame rate a lot are not safeguards:** two rings (F178), memory headroom and re-reads
  (F620), and the mount.
- **The 7 % between e6 and e7** most likely was not a cost of the memory fixes. The ABBA arms above will show it once B
  is measured three times.

## Verdict

Pending the arms. The laptop part answers the question as far as code and records can:
- **High confidence:** items 1, 2, 3 and 9 can go, the catchers already answered and the unused AMM commands for this
  title.
- **Medium:** items 4 and 5 are code merges whose costs are real but not re-measured.
- **Gated on an RT-on A/B:** item 6.
- **Kept while F403-B is open:** item 7.
- Every other safeguard stays, each with a shown need or no cost on one ring.
