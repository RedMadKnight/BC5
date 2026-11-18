# 0429 — The job-arena crash at its root, so that JobArenaFix can leave the code

**Date.** 2026-11-16. **Branch.** `exp/0429-arena-root-fix`, base main `0f335e5b` (shared patch `2c82a979`, way 2 on).
**Status.** Open: the build is made; the smoke (all candidates on) crashed at the site; the affinity model is being redone.

## Question

The maintainer, 2026-11-16, through the top session: "Masz również znaleźć rozwiązanie Job arena fix - ta opcja ma
zniknąć, więc wszelkie testy i moje gry mają być bez tego." Why does the owner (main) thread take a crash-type job
at all, what does the console do differently, and which host change ends the crash at eboot+0x3d7eca0 with
`JobArenaFix` off, so exp 0359's eboot patch and its option can be removed? Every test of this experiment runs with
`JobArenaFix` off.

## Starting point

- Exp 0425 C1 (the 200 µs wake slice, shared since 2026-11-16 11:04) held 0 of 10 inside G..G+120 of the fight
  route, but exp 0428's w428L1 crashed at the site at 228 s (G+120) with C1 active. Exposure read from its log
  (`~/bc5-work/exp0428/n/raw/w428L1-play.log`, 2026-11-16 16:40): "C1 wake slice ON (200 us)", and 68 slice lines
  reading back 200000 ns on MainThread, Job Hi 0–4, Job Lo 0–4 and the other title threads; job-arena fix OFF; way 2
  on; 43.0 flips/s. So C1 lowers the crash but does not end it.
- Exp 0388 J (a title-aware wait) also crashed once in 8 (F811). Timing changes have lowered the rate; none has
  removed it.

## The title's code, read on the box (exp 0318's rule: offsets and meaning only, no bytes kept)

- **The crash site** (+0x3d7eca0) is inside a per-item loop of the crash job's work: an item that passes a set of
  float comparisons is given a buffer from the per-thread frame arena (arena+0xc read, then the allocator at
  +0x3a04b50). With a null arena that read faults. So a crash needs both the owner taking a crash-type job and that
  job instance reaching an item that allocates. This fits exp 0425's catcher: the owner took crash-type jobs in 5
  clean runs.
- **The owner's help** (+0x3cca600): it runs only on the owner (the thread id at tcb−0x90 equals image+0x9b75c3c).
  It scans entry 2 (Hi), then 1 and 0 depending on the awaited job's flags (+0x8c bits 0 and 1). It returns at once
  if the awaited job has flag bit 3 set or is done and inactive. Otherwise it takes the first pending job with
  started < total whose class meets the owner mask (image+0xb064038). It takes the 1 MiB block from the owner arena
  (image+0xb09bf10) and calls the job's function at +0x3cca87b. It never sets the special index, so the job's own
  arena lookup (+0x466212d–+0x4662171) still sees index −1 and gives null. This path is the title's own, the same on
  the console: the bug is latent in the title, and the host's timing decides how often it fires.
- **The owner's wait** (+0x3cca900): a non-owner spins on `pause` until the job is done. The owner goes to
  +0x3ccb180, which loops: call the help (+0x3cca600), then 20 `pause`, until the awaited job is done. There is no
  OS call in this path (no semaphore, sleep or yield), so no host primitive's speed decides when the owner arrives.
- **The push** (+0x4662f00–+0x46630c0): a loop over items. Each item creates a partner job (+0x3faf5c0) and pushes a
  crash-type job (+0x4661e50) through +0x3cca270, with class "any thread" (image+0xb064040) and the partner's handle
  in its descriptor.
- **The crash job's own arena lookup** (+0x466212d–+0x4662171) has exactly three cases: index == N → the override
  arena (image+0xb064018); entry (tcb−0x108) == −1 → null; else the worker slot. It has no case for the owner, while
  the help path (+0x3cca7f0) gives the owner the owner arena. **The title's code is inconsistent with itself: an owner
  that helps with this job class always runs it with a null arena.** The code is the same on the console, so there
  the crash can be avoided only by the workers taking every crash-type job before the spinning owner sees it with a
  block left (TODO(verify): no console measurement).

## What this means for a fix

- No host change can make the crash impossible without touching the title's code or data. The owner is allowed by
  the title's own rules to take the job, and it spins on the job list with no OS call in between. A host change can
  only make it rarer, by letting the workers reach each pushed job before the owner does.
- The console's advantage is its scheduling: the job workers run on dedicated cores at fixed priority, and nothing of
  lower priority holds their core (TODO(verify): the PS5 scheduler is FreeBSD-derived; no console measurement). On
  this host guest priorities 300–732 all map to nice 0 (`Bc5GuestNice`), so the Hi workers (500) share the CPU equally
  with the Lo workers (600), Havok (550, 700), Bink (500–700) and the audio and IO threads. Exp 0360 F471 measured the
  Hi workers 156–205 ms a second in the run queue at the fight, against 4–12 ms for the owner.
- Exp 0425 C1 attacks the same wait with a shorter slice. It lowered the rate (0 of 10 in G..G+120) but w428L1 shows
  it does not remove it.

## The maintainer's decision (2026-11-16, through the top session)

"JobArenaFix ma zniknąć z menu, z przełączników i wszystkich miejsc - miałeś zbudować rozwiązanie problemu." No
title-code patch. The workaround leaves the code entirely, and the host's scheduling must keep the Hi workers ahead.

## The private build (fixes first, then test)

`mk0429.py` on copies of nine units of the shared tree at patch `a8717e53` (pins in `units.sha256`), six of them
compiled, linked with the shared builds' other objects (`build0429.py`, `box0429.sh build`), normal and lean.
Built 2026-11-16 21:11–21:20 under BOX-LOCK, CPU only: **normal `5af774e4dce1a337893d67e981e3f314`, lean
`8c81bb1ca965ad72b40e72f6c9fc0ef3`**, 0 errors, 8 warnings each, all of them in the unchanged code (the same
`wstring_convert`, `sec_to_timeval`, lambda-return and format warnings). The shared binaries stayed `dae7bf0b` and
`819f3b05`.

**1. The removal, in both builds, with no switch.** The hook and its patcher (`loader/gamePatch.cpp` and `.h` are
back to f266548's text), the call at load and its helper (`loader/runtimeLinker.cpp`), the "Game fixes" menu
(`hostMenu.cpp`, it held only this item), the input.cfg key, its member, accessors and `KYTY_BC5_JOB_ARENA_FIX`
(`hostInput.cpp` and `.h`), and `src/bc5/job_arena_fix.hpp`. An old `JobArenaFix.<TITLE_ID>=...` line in input.cfg is
accepted silently and not written back. The build checks that neither binary holds `KYTY_BC5_JOB_ARENA_FIX`,
"job-arena fix", "Game fixes" or the hook's name.

**2. The candidates, each behind its own switch, default off.**

| switch | does |
|---|---|
| `KYTY_BC5_0429_PRIO_ORDER=1` | guest priorities keep their order as nice levels below the job workers: 550–599 +1, 600–649 +2, 650–699 +3, 700–732 +4; up to 299 −15, 300–549 0, from 733 +5 as before |
| `KYTY_BC5_0429_AFFINITY=1` or `2` | the guest's CPU mask on the host thread at start and at Setaffinity: guest CPU i → host core i with its SMT sibling (`/sys` topology). 1 every mask (the default 0x7f then keeps the title on cores 0–6, core 7 for the host), 2 only masks narrower than 0x7f |
| `KYTY_BC5_0425_HANDOFF_US=300` | exp 0425 C2, unchanged (`patch0425.py`'s semaphore edits; C3 `KYTY_BC5_0425_DIRECT_WAKE` is in the build too) |

**3. The catcher, normal build only.** `KYTY_BC5_0429_TRACE=1` logs each guest thread's mask, priority and nice at
start, Setaffinity and Setprio (the first 400 lines), so the title's requests are on record.

**Fixed-priority behaviour without root.** The console's rule is "a lower number always wins". Linux offers that only
in SCHED_FIFO/RR, which needs RLIMIT_RTPRIO or rtkit; rtkit grants a bounded RR level per thread with RLIMIT_RTTIME,
and the title's threads spin on `pause` (the owner's wait above), so a spinning RR thread would starve the host's own
threads until the kernel's RT throttling or rtkit's canary demotes it. Not used. Without privilege, nice (down to −15
through the path the build already uses) and SCHED_BATCH/IDLE are possible; PRIO_ORDER uses nice. TODO(verify): the
box's `ulimit -e`/`-r` and rtkit's limits were not read (the box was busy).

## Test, fixed before the runs

- `chain0429.sh` (from exp 0428's chain by `mkrun0429.py`), one BOX-LOCK line per set, the private normal binary.
  Each run: `run0429f.sh` (exp 0428's runner with exp0429 paths, and no JobArenaFix line in its private input.cfg),
  slot 4, the named snapshot, RT on, the 14:50 record's gameplay at G, then exp 0379's walk, to G+600 s.
- Arms, every run with `KYTY_BC5_0429_TRACE=1`: C none, P `PRIO_ORDER=1`, A `AFFINITY=1`, H `HANDOFF_US=300`, X all
  three.
- Sets: `smoke` h429X1; `screen` h429C1 h429X2 h429P1 h429A1 h429H1 h429C2 h429X3 h429P2 h429A2 h429H2; `rep<k>` the
  survivors with controls between.
- A crash at the site (TARGET) or a GPU line (KERNEL) does not stop the chain. Stops: a real pad key, a STOP file
  (`~/bc5-work/exp0429/STOP`), any other class, a second NOT_ROUTED.
- **Rule** (`check0429.py`): an arm is OUT at its first TARGET; it survives a set when every counted run (NO_CRASH to
  G+600) is clean. KERNEL and NOT_ROUTED runs are not counted and are listed. A form goes to the shared swap only after
  repeated sets with no TARGET while the control keeps crashing; the counts are reported as counts (R13). Since the bug
  is the title's, a clean form lowers the rate; it cannot prove the crash gone.

## Shared files that name the workaround (read 2026-11-16 21:20)

Only `~/bc5-work/input.cfg` line 3, `JobArenaFix.PPSA03671=off`. The three launchers (`play-pkg.sh`, `play-astro.sh`,
`play-any.sh`) and the words files under `exp0413/n` do not name it. The experiment runners' directories were not read
(an emulator started). With the new build the line is ignored and dropped at the next save of input.cfg.

## Smoke h429X1 (2026-11-16 21:55–21:57, the top's GO, BOX-LOCK, no person at the pad)

Arm X (PRIO_ORDER, AFFINITY=1, C2 300 µs, trace), private normal `5af774e4`, way 2 on, RT on, no JobArenaFix
anywhere. **CLASS TARGET at 118 s = G+10**: the access violation at eboot+0x3d7eca0 with the owner's help call on the
stack (frames +0x46621ba, +0x3cca882), 39.9 flips/s, no kernel line, no pad key. Exposure: "affinity ON (1)", "prio
order ON", "C2 handoff ON (300 us)", C1 on, and 96 trace lines. Raw: `raw/chain0429-smoke.out`, `raw/n/` (start, end,
summary, route, dmesg, pad, the trace lines, the crash excerpt without code bytes). The laptop's kernel stream
recorded nothing (0 lines); the box's dmesg-after has no amdgpu line.

**What the title asks for (the trace, descriptive).** The masks use bits 0–12, a 13-CPU model, while the host's
default mask is 0x7f (7 CPUs, so the title makes 5 workers per entry, F790):

| thread | priority | mask |
|---|---|---|
| Job Hi 0–4 | 500 | 0xff (CPUs 0–7) |
| Job Lo 0–4, Job Bk 0–4 | 600, 750 | 0x1ff (CPUs 0–8) |
| MainThread | 300 | Setaffinity 0x100 (CPU 8) ×5, 0x3f ×4, 0x800 (CPU 11) ×2 |
| Render Thread | 300 | 0x400 (CPU 10) |
| Havok Solve / Queries | 700 → 450 / 550 | 0xab |
| Bink | 700 | 0x1, 0x3, 0x7f |
| IO, save, UDS, trophy, Coherent, AK | 256–700 | 0x800, 0xa00, 0x1000, 0x1a00 |

So on the console the owner (MainThread, mostly CPU 8 or 11) never shares a CPU with the Hi workers (CPUs 0–7), and
the render thread has its own CPU 10. That is the console's scheduling difference in the title's own words.

**AFFINITY=1 modelled it wrongly.** It took the bits as cores 0–7 with both SMT threads and ignored bits from 8 up, so
MainThread, the Render Thread and the IO threads stayed unpinned while the workers were spread over all 16 host CPUs
and shared them with Havok and Bink. This smoke therefore says nothing for or against the title's own affinity.

**Next (not built).** A 13-CPU model: the default mask 0x1fff (the title then reads 13 CPUs and makes 8 workers per
entry, as exp 0388 arm A did without pinning, F791), and each guest CPU i mapped to one host logical CPU, SMT siblings
paired as the console pairs them (TODO(verify): the console's CPU numbering; the box's sibling list must be read).
That puts the owner on its own host CPU apart from the Hi workers, and leaves host CPUs for the emulator's own threads.

## Second build, prepared on the laptop (2026-11-16 22:2x)

`mk0429.py` now carries `KYTY_BC5_0429_CPU13=1` in place of AFFINITY: the default thread mask 0x1fff (PthreadAttrInit,
so the title reads 13 CPUs and makes 8 workers per entry), and every guest mask applied at start and at Setaffinity
with guest CPU i (0–12) as one host logical CPU, guest 2k and 2k+1 the two SMT threads of host core k (siblings from
`/sys`). With the title's masks that puts MainThread (guest 8) on host core 4, the Render Thread (guest 10) on core 5,
the Hi workers (guest 0–7) on cores 0–3, and leaves the second thread of core 6 and all of core 7 without a title
thread unless one asks. The trace prints the map once. Exp 0388 arm A (0x1fff without pinning) crashed 3 of 3 (F791),
so the new element is the pinning. Arms of `screen2`: C, M (CPU13), Y (M + PRIO_ORDER), X (Y + C2 300 µs); `smoke2`
is h429M1. Not built yet; the box is exp 0430's.

## Build 2 and smoke h429M1 (2026-11-16 22:29–22:34, the top's slot between exp 0430's runs)

Build 2 under BOX-LOCK (22:29:44–22:31): **normal `10cd55a2c564a20261d84d1a18ff91e6`, lean
`70983f923903e94fb4bf623e8b02f6e4`**, 0 errors, the same 8 warnings; the shared binaries unchanged. Smoke h429M1
(arm M, CPU13 on, trace): **CLASS KERNEL**: a GPU page fault at 119 s (G+5), TCP write, address 0x1551d16000, ring reset
succeeded, record `~/bc5-data/captures/faults/20261116-223404`; 30.7 flips/s, no arena crash before it. **Not a test of
the arena crash**, and not a clean run either: the chain saw 3 real pad keys at 22:33:56–22:34:03 (BTN_TR2,
BTN_NORTH) and stopped (R51).

**The map was wrong.** The trace printed `0:0 1:1 2:0 3:1 4:2 5:3 6:2 7:3 8:4 9:5 10:4 11:5 12:6`: the box numbers SMT
siblings next to each other (cpu0's list is 0-1), and the code took host CPU k as core k, so the 13 guest CPUs were
folded onto host CPUs 0–6 and the five Hi workers onto CPUs 0–3. The masks themselves were applied as asked
(MainThread 0x100, Render Thread 0x400, Job Hi 0xff, Job Lo 0x1ff, AK 0x1000; no FAILED). Whether the squeeze caused
the GPU fault is not known; F847's F403-family faults also come without it.

**Fixed in `mk0429.py` (build 3, not built):** host core k is the k-th distinct sibling group in CPU order. Checked on
two layouts by a Python copy of the loop: adjacent siblings give guest i → host i (0–12), the "i, i+8" layout gives
0:0 1:8 2:1 3:9 … 12:6. On this box the title then has host CPUs 0–12, MainThread on CPU 8 apart from the Hi workers
on 0–7, and CPUs 13–15 carry no title thread.

**The top session's reading of h429M1's hang (2026-11-16, from exp 0430's laptop stream):** a compute write fault at
0x1551d16000 (thread bc5-ring), then comp_1.3.0 and gfx_0.0.0 timeouts, both resets succeeded: exp 0430's class (a
cross-ring wait passed on a stale label), not the arena crash. It counts neither for nor against the scheduling
candidates. Its records stay on the box for exp 0430, untouched by this experiment: the fault record
`~/bc5-data/captures/faults/20261116-223404`, the run's devcoredump and gc directory, and
`~/bc5-work/exp0429/n/play-last.log` (the next run of this chain overwrites that log; copy it first if 0430 needs it).

## Handover (2026-11-16 22:5x, for this session after a context reset or for another session)

- **Task (the top session, the maintainer's word):** JobArenaFix removed from everything; a host fix by console-like
  scheduling; long routes (fight, then walk to G+600) until a form survives repeated runs; no shared swap tonight
  (the top brings the result and the removal to the maintainer in the morning). Unattended box work is allowed tonight
  until 07:30; exp 0430 (local_0f8d7c32-5a0d-4c82-a91b-680e4487bdaf) has priority and gives slots between its runs
  (its STOP file `~/bc5-work/exp0430/STOP`); exp 0431 (local_228b97d5-fa31-4190-b766-2473b7d010b6) also needs slots.
  A GPU hang in a run of this experiment is exp 0430's data, not a result here. Report each stage to the top
  (local_60d88c3d-6710-42fe-a07e-1ecae2f445a3) in a few lines; never mention turning JobArenaFix on.
- **Kit (this directory, copied to `~/bc5-work/exp0429`):** `mk0429.py` (the edits, needs `patch0425.py` beside it),
  `units.sha256` (9 shared units at a8717e53), `build0429.py`, `box0429.sh claim|build|release` (normal + lean into
  `~/bc5-work/exp0429/{normal,lean}`, the words checks), `mkrun0429.py` → `run0429f.sh` + `chain0429.sh`
  (`CHAIN_SET=smoke2|screen2|rep<k>`, `REP_TAGS=` for rep), `check0429.py`. Start a chain detached:
  `cd ~/bc5-work/exp0429 && CHAIN_SET=… setsid nohup bash chain0429.sh > chain0429-<set>.out 2>&1 < /dev/null &`.
  The chain takes its own lock line and releases it; a TARGET or KERNEL run does not stop it.
- **State:** build 3 (the fixed CPU map) is in `mk0429.py` and not built. Next: (1) exp 0430's newest fix build as the
  base, if its units do not overlap ours (asked 22:5x); (2) build 3 + smoke2 (h429M1 is used: rename to h429M4 or
  higher, the chain refuses a used tag); (3) screen2; (4) rep sets of the survivors.
- **Tags used so far:** h429X1 (TARGET, first build), h429M1 (KERNEL, build 2).

## Build 3 changed again before it was built: no fixed CPU count (the maintainer, 2026-11-16 ~23:00)

"13 procesorów => a jak w innej grze będzie 14? musisz ustalić to dynamicznie dla dowolnej gry." CPU13 is gone.
`KYTY_BC5_0429_GUEST_CPUS=1` (`affinity0429.cpp`, inserted by `mk0429.py`) derives everything at run time, for any
title:

- the host CPU list: every CPU whose topology `/sys` shows, in SMT sibling-group order (0,1,2,3,… on this box, where
  siblings are numbered next to each other; 0,8,1,9,… on a machine that numbers them apart);
- the default mask of a new thread: one guest CPU per host CPU in that list (16 here). The title's own masks then
  narrow it as it asks;
- every guest mask, at thread start and at Setaffinity: guest CPU i → the i-th host CPU of the list (modulo its
  length), so the title's split of its threads (its owner on a CPU of its own, its workers on others) is kept;
- logged in the normal build only: the list and the default mask once, each growth of the union of CPUs the title has
  asked for (with the thread that asked), and with `KYTY_BC5_0429_TRACE=1` each thread's mask, priority and nice.

`KYTY_BC5_0429_PRIO_ORDER` stays as it was: one rule over the console's priority range (lower number → lower nice,
the job-worker band at nice 0), no title rows. The arms of `screen2` use `GUEST_CPUS` where they used CPU13.

## Build 3 and smoke h429M4 (2026-11-16 23:48–23:59, the slot after exp 0430's X1)

Build 3 under BOX-LOCK: exp 0430's build-5 object copied and pinned (`~/bc5-work/exp0429/base0430`, object
`f92257718c821cabce9ba4c6fcd11482`, source `96920f82`), linked into normal only. **Normal
`0d7ab42723fed584d4ecdce97cc03f8a`, lean `576c13dd778adacac98257dce36d3d59`**, 0 errors, the same 8 warnings,
the shared binaries unchanged.

Smoke h429M4, arm M (`GUEST_CPUS=1`, trace, `BC5_0430_G=0`, exp 0430's F2/F3 on as built), long route: **CLASS TARGET
at 502 s = G+393**, in the walk after the fight; 47.0 flips/s, no kernel line, no pad key. Exposure: "guest CPU mapping
ON"; the host list 0–15 in order (siblings adjacent); default mask 0xffff; the union of what the title asked grew
0x1ff → 0x9ff → 0xdff → 0xfff → 0x1fff by its own masks, then 0xffff by Bink Snd, which takes the default mask;
MainThread 0x100 and the Render Thread 0x400 applied, Job Hi 0xff applied, no FAILED. One run: the crash came far later
than in the runs of the first builds and exp 0425 (G+10 to G+120), but it came, so the title's own CPU split alone
does not remove it. Not yet read (the box went to exp 0431): the crash's frames and the job-thread count at 0xffff.

## Build 4 (2026-11-17 00:15–00:17, the first gap of exp 0430's chain Y)

Exp 0430's build-6 object (object `58c76fcccd51c3c54299d19b69994273`, source `42f9f976`) copied, pinned and linked into
normal. **Normal `2aa1e673945ae5b23f88d5973357c262`, lean `dc5d3c637b4a53a47b131b4cf0cbb1d2`**, 0 errors, the same 8
warnings, the shared binaries unchanged (`dae7bf0b`, `819f3b05`); `KYTY_BC5_0429_WAITS` in normal and not in lean; no
workaround word. `box0429.sh` stopped at its last check, which looked for `BC5_0430_F3` as a string: exp 0430's switch
names are not plain strings in its own binary either. Checked instead: a symbol only exp 0430's object defines
(`__cxx_global_array_dtor.1047`) is in build 4's normal and not in the shared normal. The check is now that symbol test.

Exp 0430's h430Y1 (its build 6 `b2770458` = the shared unit + its fix, way 2, no JobArenaFix, the fight route) ended in
this experiment's crash at 294 s (G+187), 0 kernel lines: the crash comes on 0430's fix build without any candidate of
this experiment, as expected.

## h429Z1 (2026-11-17 00:52–00:54, a gap of exp 0430's chain Y): arm Z out, and the catcher's first picture

Build 4, arm Z (`GUEST_CPUS=1`, `PRIO_ORDER=2`, catcher on, `BC5_0430_G=0`): **CLASS TARGET at 119 s = G+10**, 39.0
flips/s, no kernel line. Exposure: "guest CPU mapping ON", "prio order ON (2)", "wait catcher ON". Arm Z is OUT by the
rule. Raw: `raw/n/h429Z1-waits.txt` (the band lines and the 113 per-thread lines at the fault).

What the catcher shows (one crash, descriptive):

- **At the fault every Hi worker was asleep on `JobLoaderSema`, but each had gone to sleep only 7–146 µs before** (two
  entered their wait during the dump itself). So they were busy until just before the fault and found nothing left: the
  owner had the crash job. The fault comes some time after the owner took the job (the job's own loop runs first), so
  this is after the push, not at it; it fits F454 (workers busy at the push), not sleeping workers.
- **The semaphore's wake is not slow.** Over 1.35 million wakes of `JobLoaderSema`: 461k under 20 µs, 421k 20–100 µs,
  218k 0.1–0.5 ms, 21k 0.5–2 ms, 38 over 2 ms, none over 8 ms. Other semaphores alike.
- **Run time and run-queue time per group** (/proc schedstat at the fault, about 119 s of process life): the 8 Hi workers
  ran 65.6 s and waited 40.9 s for a CPU over 393k slices each, about 13 µs per wake. The Lo workers ran 28.7 s, waited
  57.3 s. MainThread (host name game-main) ran 37.7 s on its own CPU 8 and was the only thread running at the fault. The
  CPUs 0–7 the Hi workers may use were far from full. So the workers lose by microseconds per wake-up, not by
  starvation, and a nice level cannot buy that back.

Next (to be checked in the title's code at the next gap): whether the title's worker spins before it sleeps on its
semaphore, and how it bounds that spin (a time read through an import, or a count). A spin bounded by a host time
source that runs at the wrong rate would end the spin too soon on this host and send the worker to sleep where the
console's worker would still be spinning when the owner pushes. That would be a host fix for every title.

## The title's worker loop, the host's guest mutex, and candidate F (2026-11-17 01:2x–01:41)

**Read on the box** (offsets and meaning only). The Hi worker's loop (+0x3ccbfe0–+0x3ccc2b0) keeps its own cursor into its
entry's pending list and scans it **while holding a per-entry guest mutex**. It releases the mutex (import stub
+0x5f1f8b0) before it runs a job and takes it again after (+0x3978ba0). When its cursor reaches the end it sets an
8000 µs timeout and waits on the entry's semaphore (import +0x5f202a0). A worker that claims a multi-block job may
signal the semaphore for more workers (import +0x5f20260). The title's lock wrapper +0x3978ba0 spins up to a count kept
in the mutex object, each round 16 `pause` and a trylock (import +0x5f1f890), then takes the blocking lock (import
+0x5f1f8a0). The owner's help (+0x3cca600) scans the same list with no mutex. Exp 0358's import resolver does not read
this SELF's layout (no PT_DYNAMIC entry), so the imports are named by their use (trylock, lock, unlock, wait, signal).
TODO(verify): their NIDs.

**The host's guest mutex** (`pthread.cpp`, NativeMutexLock/Trylock/Unlock): a `std::mutex` and a condition variable
inside each guest mutex. Every trylock, lock and unlock takes that inner `std::mutex` first, so the eight workers'
spinning trylocks can block in the kernel behind the holder's unlock, and a blocked locker is woken through the
condition variable. On a FreeBSD-derived kernel (TODO(verify): the console's libkernel) a trylock is one atomic
operation in user space.

**Candidate F, `KYTY_BC5_0429_FAST_MUTEX=1`** (`fastmutex0429.cpp`; read once per process, so all mutexes use one
scheme): the guest mutex as a word in user space (0 free, 1 locked, 2 locked with sleepers; Drepper's futex mutex);
trylock and an uncontended lock or unlock are one atomic operation; a contended lock spins 64 `pause`, then sleeps on
the word through the futex with the old signal poll; unlock wakes one sleeper only when there is one. Owner and count
are written only by the holder. The normal build with `KYTY_BC5_0429_WAITS=1` counts contended locks and their sleeps.
For every title, not just this one.

**Stand-in test** (`test_fm0429.cpp`, the block with minimal stand-in types, g++ -O2 -Werror in the box's ubuntu
container, under BOX-LOCK): 13 of 13: 8 threads × 200,000 rounds (half as the title's wrapper, half by lock) end with an
exact counter and a free word; recursive takes, EPERM for a non-owner, the timed lock's bound, a zero timeout, and a
hand-over to a timed waiter. It does not cover the condition-variable waits that unlock and relock through
NativeMutexUnlock(recurse) and NativeMutexLockRecurse; those are in build 5 only.

**h429C1** (build 4, control arm, 01:25–01:37): **NO_CRASH to G+600** (711 s), 40.4 flips/s, no kernel line. The
control does not always crash on the long route; the counts must be read with that.

**Build 5** (01:38–01:41, BOX-LOCK, CPU only, exp 0430's build-6 object as in build 4): **normal
`41669d9aed6454baee3cdbea95cf23ce`, lean `4bf6c7e90f94a0cb4803991b43666a32`**, 0 errors, the same 8 warnings, the
shared binaries unchanged. Arm F (`FAST_MUTEX=1`, catcher on) runs next.

## h429F1 (2026-11-17 02:10–02:19, build 5, arm F)

`FAST_MUTEX=1`, catcher on: **CLASS KERNEL**, a GPU page fault at 526 s = G+418 (thread bc5-ring, address
0x18f22df4b000, status 0x006C1071, ring reset succeeded, 120 kernel lines, record
`~/bc5-data/captures/faults/20261117-021855`), exp 0430's data; 42.3 flips/s. No arena crash before it, but by the rule a
KERNEL run is not counted. Exposure: "fast guest mutex ON"; the mutex counter at 100,000 contended locks: 49,340 slept,
mean sleep 100.8 µs, max 25.6 ms. Half of the contended locks still sleep, about 0.1 ms each.

## Build 6 and h429S1 (2026-11-17 02:50–03:05)

Exp 0430's build 7 copied and pinned to `~/bc5-work/exp0429/base0430b` (source `b8afba59`, object `a823c32e`, its private
backend archive `1423af83`, which the object needs); `BASE0430=2` links both into normal only (`build0429.py`
`ARCHIVE=`). Stand-in test with `FM_MODE=2`: 0 failed. **Build 6: normal `0fc7f2516bc367e5bc407b40035e79f7`, lean
`3153793dc446b8c138361561cd4b86ac`**, 0 errors, the same 8 warnings, the shared binaries unchanged.

**h429S1** (arm S, `FAST_MUTEX=2`, catcher on): **NO_CRASH to G+600** (712 s), 42.4 flips/s, no kernel line. The mutex
counter at 140,000 contended locks: 43,959 slept (31 %, against 49 % with mode 1 in h429F1), mean sleep 120.6 µs, max
41 ms. One clean run; the control was clean once too (h429C1), so this says nothing yet.

Tally on the long route so far (counted runs only; R13: counts, not rates): C 1 clean (h429C1); Z 1 crash (h429Z1, G+10);
M 1 crash (h429M4, G+393, build 3); X 1 crash (h429X1, G+10, build 1); S 1 clean (h429S1); F 0 counted (h429F1 KERNEL).

## h429C3 and h429S2 (2026-11-17 03:40–04:04, build 6)

**h429C3** (control): NO_CRASH to G+600, 47.1 flips/s, no kernel line. **h429S2** (`FAST_MUTEX=2`): NO_CRASH to
G+600, 40.1 flips/s, one 3.4 s gap, no kernel line; mutex counter at 140,000 contended locks: 48,720 slept, mean 127 µs.

Tally on build 6 (exp 0430's build 7 underneath): C 1 clean, S 2 clean. With build 4 (exp 0430's build 6): C 1 clean,
Z 1 crash. **The controls of builds 4 and 6 are 2 of 2 clean on the long route**, so these runs cannot show an effect
of S or F: the crash on this route has become rare on these builds (exp 0430's own build 6 still crashed once, h430Y1,
G+187). R13: two and three runs are no rate. A test of S needs either many more runs or a route on which the control
crashes reliably (the earlier 180 s fight route crashed 7 of 9 in exp 0388 on older builds; not re-measured on these).

## h429S3 and h429C4 (2026-11-17 05:16–05:40, build 6)

**h429S3** (`FAST_MUTEX=2`): NO_CRASH to G+600, 46.1 flips/s, longest gap 267 ms, no kernel line. **h429C4**
(control): NO_CRASH to G+600, 39.9 flips/s, longest gap 472 ms, no kernel line. Real pad keys 0 in both.

Tally on build 6: C 2 clean (h429C3, h429C4), S 3 clean (h429S1, S2, S3). With build 4, the controls on the long route
are 3 of 3 clean. R13: the crash does not show on this route on these builds, so S cannot be told from C here.

## Morning note (2026-11-17 05:5x)

See `MORNING-NOTE.md`: every crash of this experiment ran with an arm that changed the guest CPU mask; proposed A/B arm M (stressed control) against new arm T (M + FAST_MUTEX=2).

## Morning A/B: stressed control M against T (2026-11-17 07:40–08:33, build 6, the top's GO)

Both arms ran with `GUEST_CPUS=1` (the guest CPU mask widened and pinned) as a stressor. T adds `FAST_MUTEX=2`. The
setup was the long route, slot 4, the named snapshot, RT on, the catcher on, no pad key in any run, no kernel line. The
box had rebooted before the set (boot 735f9153). The chain paused after h429M5 for exp 0431's smoke of the swapped
shared builds (07:52–08:09); `rep8` ran the rest.

| run | arm | result | flips/s |
|---|---|---|---|
| h429M5 | M | NO_CRASH to G+600 | 44.5 |
| h429T1 | T | **TARGET at 341 s = G+232** | 43.9 |
| h429M6 | M | **TARGET at 118 s = G+10** | 39.1 |
| h429T2 | T | **TARGET at 119 s = G+10** | 39.5 |

All three crashes were at eboot+0x3d7eca0. In the T runs the fast mutex was on: 47,061 of 80,000 contended locks slept
(T1) and 22,973 of 40,000 (T2), with a mean sleep of about 220 µs.

**Verdict: candidate S/T is OUT.** Under the stressor the fast guest mutex crashed 2 of 2, the control 1 of 2, so it
does not keep the workers ahead of the owner. The stressor works: the control crashed again (with `GUEST_CPUS=1` and no
mutex change: M4, Z1 and M6 crashed, M5 was clean, on builds 3, 4 and 6). R13: counts only. The guest mutex's inner `std::mutex` is not the cause, or not the whole of
it. No candidate of this experiment survives. The removal is unaffected; it needs no candidate to be swapped.

## The removal swap kit (2026-11-17 08:4x, held: the maintainer plays from about 09:00)

`mkswap0429.py`: the removal only, none of the candidates or catchers. It edits seven units and deletes
`src/bc5/job_arena_fix.hpp`, and each unit is first checked against its pin in `pins-swap0429.txt`, taken at patch
9e7c4514. All eight units are byte-identical in patches a8717e53 and 9e7c4514, so these exact removal edits already
compiled in builds 1–6. On a laptop tree of f266548 + 9e7c4514 (the diff reproduces 9e7c4514) the new patch is
**fcedb6cd**:
- exp 0372 lines 5;
- gamePatch.cpp and .h back to f266548;
- 8 files changed, 4 insertions, 256 deletions;
- JOB_ARENA, job-arena, "Game fixes" and ApplyJobArenaFix: 0 lines;
- `JobArenaFix` appears once, on the silent-accept line for old input.cfg lines.

`int0429.sh` adapts exp 0431's int0431.sh. It checks the patch and the words in both builds; the only word allowed to
go is `KYTY_BC5_JOB_ARENA_FIX`, and no word may be added. It also removes the JobArenaFix line from
`~/bc5-work/input.cfg` after keeping a copy. `undo0429.sh` puts back the units, the header, both binaries and
input.cfg. If the menu has rewritten input.cfg since the swap, it only adds the removed line back. Its stand-in test
`test_undo0429.sh` passes 17 of 17 on the laptop (6 worlds). Not yet run on the box: the stand-in test, the builds and
the swap. They wait for the top's go after his play.

## Offline: the worker's spin before its sleep, against the console's scheduler (2026-11-17 09:xx, no box)

From the code already read (above) and the catcher of h429Z1:
- **The Hi worker has no spin before its sleep.** When its cursor reaches the end of the pending list it waits on the
  entry's semaphore straight away, with an 8000 µs timeout. The only bounded spin is in the lock wrapper (a count kept
  in the mutex object, rounds of 16 `pause` and a trylock), and the fast mutex has just shown that the lock is not where
  the race is lost. The idea of a spin cut short by a host clock has nothing to act on.
  TODO(verify), at the next box read: the exact instructions between the cursor's end and the wait call (a yield, a
  short spin or a re-check).
- **The race is the owner's help against the worker's wake.**
  - The owner pushes, signals, and enters its `pause` loop that calls the help, which takes any job.
  - A worker that was just asleep (7–146 µs in h429Z1) has to be woken and get a CPU first.
  - On the host 18 % of `JobLoaderSema` wakes took 0.1–2 ms (h429Z1: 218k + 21k of 1.35M). The Hi workers waited about
    13 µs per wake for a CPU on average.
- **What the console does differently** (from the title's own requests; the console's kernel is TODO(verify)):
  - The owner (priority 300) runs on its own CPU (8 or 11); the Hi workers (500) are on CPUs 0–7.
  - "A lower number wins" means a woken Hi worker takes its CPU at once from the Lo workers (600), Havok (550/700),
    Bink and the background (750) that share those CPUs.
  - The host has no such preemption: equal nice, or nice steps (PRIO_ORDER), only change shares.
  - This also fits the stressor: GUEST_CPUS pins the Hi workers onto CPUs 0–7 together with the Lo workers (0x1ff)
    without the console's priority, so a woken worker waits behind them, and those runs crash more (M4, Z1, M6, T1, T2).
- **Candidate R (next build, for any title, derived at run time; not built):** strict preemption for the guest's top
  worker band on the host.
  - Guest threads get SCHED_RR in the order of their guest priority, through RLIMIT_RTPRIO or rtkit (RealtimeKit1,
    which the host already falls back to for nice).
  - Pure spinners must not get it. The owner's wait is a `pause` loop, and an RR spinner would starve its CPU until the
    kernel's RT throttling stops it. One rule: a thread that has just slept on a guest semaphore or wait counts as a
    sleeper; RR goes only to sleepers, and is taken back from a thread that ran a whole slice without sleeping.
  - Combined with GUEST_CPUS, it is the console's model: the title's own CPU split plus "a lower number wins".
  - It needs one read on the box first: `ulimit -r` and `ulimit -e` for his user, and rtkit's limits (MaxRealtimePriority,
    RTTimeUSecMax, the per-user thread cap). A simpler, weaker fallback without privilege: SCHED_IDLE for guest
    threads of the background band (priority above the Lo workers' band), so that any woken normal thread preempts them.

## The shared swap (2026-11-17 09:46–09:50, the top's GO after his play at 09:45)

- **Before the swap:** the stand-in test of undo0429.sh on the box passed 17 of 17. BOX-LOCK still held exp 0430's
  line, which itself said "released" (08:54, written when it stopped D2 for his play), so it was emptied with a
  BOX-QUEUE note.
- **Try 1 (09:46):** int0429 stopped by itself after mkswap and undid everything (patch 9e7c4514, normal 6044be08,
  lean d239d4bf back, input.cfg untouched). The patch check had found "job-arena" in this experiment's own comment on
  the silent-accept line. The comment now reads "the workaround of exp 0359 is gone".
- **Try 2 (09:48–09:49):** passed every check.
  - **Patch 9e7c4514 → bc39a035:** exp 0372 lines 5, the pad_audio_route header in, the file list less gamePatch.cpp/.h
    and job_arena_fix.hpp. JOB_ARENA, job-arena, Game fixes and ApplyJobArenaFix: 0 lines; JobArenaFix 1 line (the
    silent accept).
  - **Builds:** normal 6044be08 → **0de9349b**, lean d239d4bf → **63fda02d**, 9 warnings each, the archive 1423af83
    unchanged.
  - **Words:** normal lost only `KYTY_BC5_JOB_ARENA_FIX`, lean none, neither gained one. Neither binary holds any
    JobArenaFix, job-arena fix, Game fixes or hook string; the silent accept's literal is not a plain string in either.
  - **`~/bc5-work/input.cfg`:** 28d3366a → 6b966137, its line `JobArenaFix.PPSA03671=off` removed; the copy is in
    `~/bc5-work/exp0429/swap/input.cfg.before-0429`.
  - **Undo:** `bash ~/bc5-work/exp0429/undo0429.sh` (then exp 0431's undo further back). Raw: `raw/int0429.out`,
    `raw/int0429-try1.out`.
- `backend/kytyplus-patches/0001-bc5-lle-agc.patch` on this branch is the new shared patch bc39a035 (main's 9e7c4514
  plus the removal; at a merge, this branch's version of that file is the right one).

## Candidate R on the box (2026-11-17 10:39–11:07)

- **Build 7** (normal 6ba312b8): R's sleep hook was missing, because the edit that adds it to semaphore.cpp failed
  unnoticed. R switched on but promoted nothing. Runs h429G1 (TARGET G+76) and h429G2 (TARGET G+56) therefore did
  not test R. The control in between, **h429M7** (arm M, valid), crashed at G+95.
- **Build 8** (normal e564f440, with the hook): every rtkit call failed with "no system bus". The normal build runs in
  the distrobox, which has no `/run/dbus`; the host's socket is at `/run/host/run/dbus/system_bus_socket`, and the
  container shares the host's PID namespace (checked with busctl and /proc/self/ns/pid). Run h429G3 (TARGET G+313) did
  not test R either. mk0429.py now stops if the hook did not land.
- **Build 9** (normal 5b082c6a, lean 6095973a, the host-bus fallback). The top's rule: a check run of at most 3 minutes
  before any set. **Check h429K1, FAIL** (raw `raw/n/h429K1-r.txt`):
  - rtkit granted RR 17 times. MainThread was promoted and was back to SCHED_OTHER by G+25 (SIGXCPU, so the spinner's
    demotion works). The watchdog dropped two Havok Solve threads.
  - 7 of 8 Job Hi workers were RR. Job Hi 5 arrived when the cap of 14 was reached (the Lo workers arrived first).
  - 16 threads were held at once: the cap check raced.
  - After 17 grants rtkit refused (its per-user limit with the desktop's own RT threads, TODO(verify) its value).
- **Fixed offline, for build 10:**
  - the cap is reserved atomically;
  - when the cap is full, the holder with the numerically highest guest priority above the newcomer's is dropped for
    good to make room (the console's "a lower number wins");
  - after the first rtkit refusal, rtkit is asked again only to replace an evicted thread;
  - SIGXCPU drops are logged through the watchdog.
- **Build 10** (normal c8ea1061, lean 13c3ac84; 11:35, in a gap of exp 0430's A/B): the fixes above, plus the top's
  remark: the runtime's main thread (`PthreadInitSelfForMainThread`, which runs the owner's help) is never promoted,
  for any title.
- **Check h429K2, PASS** (11:37–11:40, raw `raw/n/h429K2-r.txt`):
  - all 8 Job Hi workers were RR (priority 6) at G+25, and the main thread was not (one "not promoted" line);
  - 21 promotions, 0 rtkit refusals;
  - 7 Lo workers (600) were evicted for the Hi workers;
  - the watchdog dropped 5 threads that ran 100 ms in one slice (Havok, AK);
  - 9 RR threads at G+25 (the 8 Hi workers and AK::AudioOutThread);
  - NO_CRASH to G+40, 40.3 flips/s.

  The set (G against M, the long route) waits for the end of exp 0430's A/B (about 13:50).

## The R set (2026-11-17 12:03–12:42, build 10, the top's order after exp 0430's hang and reboot at 11:59)

The long route, slot 4, the named snapshot, RT on, the catcher on, no pad key, no kernel line. Arm G
(`GUEST_CPUS=1` + `RR=1`) against arm M (`GUEST_CPUS=1`, the stressed control).

| run | arm | result | flips/s | R |
|---|---|---|---|---|
| h429G5 | G | NO_CRASH to G+600 | 48.1 | 22 promoted, 8 of them Job Hi; 0 refused; 7 Lo evicted; 4 dropped |
| h429M10 | M | NO_CRASH to G+600 | 47.9 | – |
| h429G6 | G | NO_CRASH to G+600 | 44.4 | 20 promoted, 8 Job Hi; 0 refused; 5 evicted; 5 dropped |
| h429M11 | M | **TARGET at 117 s = G+10** (eboot+0x3d7eca0) | 39.5 | – |

**Tally with the stressor (R13: counts, not rates):**
- Without R, M and Z: M4, Z1, M6, M7 and M11 crashed, M5 and M10 were clean.
- G1–G3 also crashed. Their R was inactive (builds 7 and 8), so they ran as M.
- With R active: G5 and G6 clean, 2 of 2.

R has not crashed yet, and the stressed control crashes in most runs. Two runs are not enough to call it a fix: more G runs are needed, then R alone against C, and an fps check.

## R offline (2026-11-17 13:xx): lean, the host shortcut, ASTRO BOT

- **Lean carries R.**
  - In lean, `BC5_LEAN` removes only R's log lines and the catcher.
  - The sleep hook in semaphore.cpp sits after the catcher's `#endif`, under `#ifdef __linux__` only.
  - The promotion, the bounds and the rtkit call all compile in.
  - Build 10's check found `KYTY_BC5_0429_RR` in both binaries.
  - Lean has not run with R yet: a lean check (h429K-) belongs in the next slot.
- **The host-lean shortcut (no distrobox).**
  - On the host the system bus is at its usual `/run/dbus/system_bus_socket` (read 09:59: `busctl` reached rtkit
    there), so `dbus_bus_get_private` takes the first path; the `/run/host` fallback is for the container only.
  - TODO(verify) at the next slot: `libdbus-1.so.3` on the host, normally `/usr/lib64` from Fedora's dbus-libs.
    If it is missing, R refuses every promotion with rc −1000 and logs it; the title runs on as without R.
- **ASTRO BOT.**
  - R is for every title, with no title rows. For ASTRO BOT it promotes, at their first sleep on a guest semaphore,
    the threads below 700 except the runtime's main thread. The highest priorities win when more than the cap (online
    CPUs − 2 = 14) want RR or rtkit's limit is reached.
  - Its threads and priorities have not been read. The trace (`KYTY_BC5_0429_TRACE=1`) lists them, and so does R's own
    log.
  - The risks are the same as here:
    - a thread that runs long under RR is dropped (20 ms without blocking by SIGXCPU, 100 ms in one slice by the
      watchdog);
    - its audio thread may become RR (here AK::AudioOutThread, 256, stayed RR at rtkit priority 13), and so may its
      render-side guest threads, which then preempt the host's own GPU threads on their CPU.
  - Before any swap: an ASTRO BOT smoke with R on (normal and lean, `astro0431.sh` with `XWORDS=KYTY_BC5_0429_RR=1`),
    the flips/s against the same run without R, and the screen shots. R stays off by default until the maintainer
    decides.

## Is the crash host blocking? (the top's question, 2026-11-17 13:xx, offline, from h429Z1's dump at the fault)

h429Z1 is the one crash whose per-thread state at the fault is on the laptop (`raw/n/h429Z1-waits.txt`). The dumps of
M4, M6, M7 and M11, also with the catcher on, are in their play logs on the box, not read yet. At Z1's fault (G+10):
- **No job thread and not the owner is inside a host call.**
  - All 8 Job Hi and 8 Job Lo workers are in `futex` (202), asleep on `JobLoaderSema`. The Hi workers went to sleep
    7–146 µs before, and their last wakes waited 0.01–1.34 ms for a CPU (Hi 6 1.34 ms, Hi 4 1.12 ms).
  - The owner (`game-main`) is running the fault handler on CPU 8.
  - No guest thread is in mmap, munmap or ioctl. Neither submit thread is blocked: one `bc5-ring` is running on CPU 13,
    the other is in `nanosleep`.
- **What is running instead: all 8 `Job Bk` workers** (guest priority 750, the background band), state R on CPUs 0, 1,
  1, 2, 3, 6, 7 and 8. Those are the Hi workers' CPUs 0–7 and the owner's CPU 8. The file readers are busy too:
  `bc5-apr-q3`, two of them in D state in `pread64` (17), so the title is loading.
- **So the slow wakes line up with CPU contention from the title's own background workers at a load, not with host
  blocking.** The wake bands have no timestamps, so a single slow wake cannot be matched to a host event offline, and
  no maps or drain line is in this record.
- **What this means:**
  - 0432's D (the drain before an unmap) would not change this picture.
  - It fits R exactly: on the console a woken Hi worker (500) preempts a Bk worker (750) on its CPU at once.
  - It also explains why the crashes cluster at G+10: the load wakes all the Bk workers at once.
- **To confirm across crashes** (one read-only minute on the box): the "thread at fault" lines of M4, M6, M7 and M11.
  Are the Bk workers running there too, and is any job thread in a host call?

## Slot 16:17–16:55 (2026-11-17): the dumps at the fault, the set G M G M, the lean check

Box: boot 66e113e1, a fresh boot after the 16:15 reboot (0432's hang), no GPU reset on it. Build 10 (normal c8ea1061,
lean 13c3ac84), all runs with the stressor and RT on.

**The dumps at the fault** (`faultread0429.sh`, read-only; `raw/n/faultread-1655.txt`):

| run | Job Bk running | job thread or owner in a host call | D state |
|---|---|---|---|
| M4 | no dump (build 3, no catcher) | – | – |
| M6 | 8, CPUs 0–7 | none | none |
| M7 | 8, CPUs 0–7 (Hi 6 shares CPU 5 with Bk 6) | none | bc5-apr pread |
| M11 | 8, CPUs 0–7 (Hi 0, 4, 6 and Bk 4 all on CPU 7) | none | none |
| G1 (R inactive) | **0**; all Hi asleep | none | none |
| G2 (R inactive) | 8, CPUs 0–7 | none | 2 bc5-apr pread |
| G3 (R inactive) | 8, CPUs 0–7 | none | none |

The owner (`game-main`) runs the fault on CPU 8 in every one. 5 of 6 dumps match Z1, and no dump shows a host call:
the top's D (host blocking) is out for this crash. G1 is the exception that Bk contention does not explain.

**The set rep12** (chain0429.sh; `raw/n/h429*-summary.txt`):

| run | arm | end | flips/s |
|---|---|---|---|
| G7 | G (R on) | G+600, no crash | 45.9 |
| M12 | M | the target crash at 108 s | 40.2 |
| G8 | G (R on) | G+600, no crash | 44.0 |
| M13 | M | the target crash at 117 s | 39.9 |

Totals, counts only: G with R active 4 clean of 4 (G5–G8). M and Z without R 7 crashes of 9 (M4, Z1, M6, M7, M11,
M12, M13; M5 and M10 clean). R in G7/G8 (`raw/n/h429G7-r.txt`, `h429G8-r.txt`): 22 and 20 promotions, cap 14, no
SIGXCPU drop. The watchdog dropped 4 and 5 threads, all `Havok Solve`. No Job Hi worker was dropped.

**The lean check: FAIL.**
- h429K3 (`check0429r.sh` with `CHECK_LEAN=1`) ended as CLASS SETUP. `run0429f.sh` gates on the journal's frame
  profiles (`direct.log`), which lean compiles out, so that harness cannot drive lean.
- New `check0429l.sh`: the private lean build through exp 0428's `start0428l.sh` with lean0428's key route, 200 s,
  arm G's words, ps at 150 s.
- h429K4 (`raw/n/check-h429K4.ps`, `.run`): the run passed (200 s, no crash), and the main thread is not RR.
- But **only 6 of the 8 Job Hi threads are RR**: Hi 0 and Hi 6 are TS. Also RR: AK::AudioMgr (rtkit priority 7) and
  AK::AudioOutThread (13). No Lo and no Havok thread is RR.
- Lean logs nothing, so the cause is open. Two suspects:
  - the watchdog dropped them (100 ms in one slice; a dropped thread stays TS for good);
  - the 24-call rtkit budget ran out before they slept.
- By the check-first rule, no lean set runs until this is understood offline.

**libdbus on the host:** `/usr/lib64/libdbus-1.so.3 -> libdbus-1.so.3.38.3` (364832 bytes), so R's dlopen has a
library on the Bazzite host.

## Build 11 (offline, 2026-11-17 evening): lean counters, the pool rule, the R/C pairs and the ASTRO smoke

The top's three points after the 16:17 slot. Not built or run yet (the next slot builds it).
1. **The lean Hi 0/6 cause.** `rr0429.cpp` now counts in both builds:
   - the counts: promotions (P), rtkit refusals (R), cap denials (C), budget denials (B), evictions (E), drops by
     SIGXCPU (X), by the watchdog (W), by a priority of 700 or above (H), and of a gone thread (G);
   - the last 16 losses as kind and guest priority (e.g. `W500` is a Job Hi worker dropped by the watchdog);
   - one stderr line a minute from the watchdog thread, `exp 0429 R count: ...`.
   - This line is in lean too, for this experiment only: it must leave lean before any swap (lean has no diagnostics).
   - `check0429l.sh` also records the policy of the Job Hi and AK threads every 10 s, so a Hi worker that leaves RR
     (a drop) shows apart from one that never got it (budget or cap).
2. **The AK audio threads.** Their guest priorities, from the R logs of K2, G7 and G8:
   - AK::AudioOutThread 256 (rtkit RR 13, above the Hi workers' 6);
   - AK::AudioMgr 450 (RR 7).
   - Both are below 700, so rule 1 promotes them: an RR audio thread preempts the host's own GPU threads (bc5-ring,
     kyty-present, SCHED_OTHER) on its CPU.
   - New mode `KYTY_BC5_0429_RR=2`, still no title rows: only a sleeper on a **pool** semaphore, one that two or more
     distinct threads have slept on (by address, a table of 512). A thread that slept there first is marked at its next
     sleep.
   - The job workers share their semaphore (JobLoaderSema in Z1's dump); a lone audio thread's semaphore has one
     sleeper. Whether the AK threads sleep alone is what the check with RRMODE=2 shows.
   - `RR=1` is unchanged.
3. **Prepared runs:**
   - `chain0429.sh` arms:
     - H: G with RR=2;
     - P: the plain control, `KYTY_BC5_0429_RR=0` only, no stressor, no trace, no catcher;
     - Q: `KYTY_BC5_0429_RR=${RRMODE:-1}` only.
   - P and Q are the fps pairs on the long route.
   - `astro0429.sh <prefix>`: ASTRO BOT through exp 0431's `astro0431.sh` on the private build, 4 runs of 200 s:
     normal RR=0, normal RR=$RRMODE, lean RR=0, lean RR=$RRMODE. Screen shots stay on the box.
   - `check0429r.sh` and `check0429l.sh` take `RRMODE`.

Next slot, in order:
1. `box0429.sh build` (build 11).
2. The checks:
   - `check0429r.sh h429K5` (normal, RR=1);
   - `RRMODE=2 check0429r.sh h429K6` (do the AK threads stay TS? are all 8 Hi RR?);
   - `check0429l.sh h429K7` (lean, RR=1, with the counts);
   - `RRMODE=2 check0429l.sh h429K8`.
3. The R/C pairs `CHAIN_SET=rep13 REP_TAGS="h429Q1 h429P1 h429Q2 h429P2"`, with RRMODE as the checks decide.
4. `astro0429.sh a429B`.

## Slot 17:44 (2026-11-17): build 11, check K5 FAIL; build 12 (offline)

Box: rebooted by the maintainer at about 17:42 after a GPU reset at 17:06. Up 1 min at the start. The only amdgpu
dmesg line was bc5-gpu-watch's own start line.
- **Build 11:** normal 47bc95e1, lean 2f9d01e5. No new warnings; the shared binaries are unchanged.
- **h429K5** (normal, RR=1, arm G 40 s; `raw/n/check-h429K5.out`):
  - The run was clean (42.2 flips/s).
  - **7 of 8 Job Hi RR: FAIL**, and the slot stopped there (K6–K8, the pairs and ASTRO did not run).
  - The count line: `P 21 R 0 C 11 B 0 E 7 X 0 W 5 | last E600 ×6 E500 W450 ×5`.
- **The log:** once the cap of 14 was full, **AK::AudioMgr (450) evicted Job Hi 2 (500)**.
  - An eviction used Drop, which marks the thread a spinner, so Hi 2 never came back.
  - Then the watchdog dropped all five Havok Solve (450). The freed places went unused, while 600s and 550s were
    refused.
  - The same is very likely lean's Hi 0/6 at h429K4.
- **Build 12** (rr0429.cpp, offline, not built):
  - An eviction is no longer a spin drop. An evicted sleeper is promoted again at a later sleep once a place is free.
  - rtkit's budget is 15 calls per 20 s window, not 24 per lifetime. A refusal blocks new promotions until the window
    turns, but not the replacement of an evicted thread.

## Slot 22:39–23:53 (2026-11-17): build 12 with RR=2; checks K10 and K12 PASS, pairs and ASTRO clean

Box: up about 5 h, no amdgpu reset since boot (only bc5-gpu-watch's start line), BOX-LOCK empty. Build 12 (c1090952):
private normal `40051afd`, lean `91081355`, 0 errors, the same 8 warnings; shared builds unchanged (md5 before = after).

**rtkit's limits (read only, the box).** `rtkit-daemon` runs with no arguments, so its defaults hold (rtkit-0.14-2.fc45,
`--help`): actions-burst-sec 20, actions-per-burst-max 25, max-realtime-priority 20, min-nice -15, and RLIMIT_RTTIME
required (`--rttime-usec-max`). Build 12's own budget, 15 calls per 20 s, is under rtkit's 25 (which is per user, so
other users of rtkit, e.g. PipeWire, share it). This replaces the TODO(verify) in rr0429.cpp's head comment.

| run | build | R | result | R count at the end |
|---|---|---|---|---|
| h429K10 check | normal | 2 | PASS: Job Hi 8 of 8 RR, main thread TS, NO_CRASH, 39.5 flips/s | held 14, P 21, R 0, C 4, E 7 (Lo 600 evicted) |
| h429K12 check | lean | 2 | PASS: Job Hi 8 of 8 RR at every 10 s sample, 10–190 s; main TS | held 14, P 21, R 0, C 5, E 7 |
| h429Q1 (G+600) | normal | 2 | NO_CRASH, 42.6 flips/s, longest gap 260 ms | held 12, P 12, R 2 (550, 450), B 3 |
| h429P1 | normal | 0 | NO_CRASH, 41.3 flips/s, longest gap 316 ms | — |
| h429Q2 | normal | 2 | NO_CRASH, 39.2 flips/s, longest gap 278 ms | held 12, P 12, R 2, B 2 |
| h429P2 | normal | 0 | NO_CRASH, 41.4 flips/s, longest gap 277 ms | — |
| a429BA1 ASTRO | normal | 0 | PASS, 60–61 fps, longest gap ~17 ms | — |
| a429BA2 ASTRO | normal | 2 | PASS, 60–61 fps, longest gap ~17 ms | held 2, P 2, R 7 (478), B 7 |
| a429BA3 ASTRO | lean | 0 | PASS (lean has no fps line) | — |
| a429BA4 ASTRO | lean | 2 | PASS | held 2, P 2, R 4 (478), B 10 |

0 kernel lines, 0 crash lines, 0 GPU hangs in all ten runs; no reboot was needed.

**The RR threads with R on (K10, K12 ps):** Job Hi 0–7 (rtprio 6), five "Havok Queries" (5), AK::AudioMgr (7);
game-main stayed TS. AK::AudioOutThread was not promoted.

**Notes, counts only:**
- The build-11 K4/K5 failure is gone: no Hi worker left RR in K10 or K12 (lean K4 had 0 of 6).
- The pool rule does not keep all audio out: AK::AudioMgr (450) sleeps on a semaphore shared by two or more threads and
  became RR (rtprio 7) in both checks (in lean at about 50 s). Bounded like every RR thread (RLIMIT_RTTIME, watchdog;
  W 0 in all runs).
- fps: R on 42.6 and 39.2 flips/s, R off 41.3 and 41.4 on the long route (two runs each: no difference shown beyond
  run-to-run spread); ASTRO 60–61 with R on and off.
- rtkit refused calls in the Q runs (2 each) and in ASTRO (7 and 4, all for guest priority 478). The refusal reason is
  not logged; ASTRO held 2 RR threads. Open: why rtkit refuses there (per-user burst shared with other clients, or a
  per-thread rule).
- Not shown: anything about the crash rate on the job-arena route. Q and P were 2 clean runs each; earlier, without R,
  7 of 9 runs crashed under the stressor (arm M/Z), which these pairs do not use.

Files: raw/n/check-h429K10.out, check-h429K12.out, check-h429K12.series, chain-rep13.out, astro-a429B.out (ASTRO
screenshots stay on the box).

## Build 13 (offline, 2026-11-18 night): the worker-family rule (RR=3) and rtkit's room

**rtkit's refusals, read in its journal (read-only, 00:25 in a slot gap).** All 23 refusals since 22:40 are
"Reached maximum concurrent threads limit for user '1000'", none is the burst limit. rtkit serves at most 25 threads per
user at a time (`--threads-per-user-max`, default 25, `--help`; rtkit runs with no arguments). From rtkit's public source
(rtkit-daemon.c, GitHub mirror heftig/rtkit, read through a fetch; TODO(verify) against the box's 0.14): the count is
every thread of the user rtkit made RT or high priority that still is (RR/FIFO, or nice < 0), swept at every D-Bus call;
a known thread asking again reuses its place. Besides PipeWire (4 threads), the emulator itself asks rtkit for high
priority (nice -10/-15) for many of its threads: 3 at h429K10's start, 16 at a429BA2's (from a library it links, not
from our code: no tracked file asks rtkit apart from R; which one is TODO(verify), the checks now list the nice < 0
threads). So:
- in K10 R's 14 RR threads came first and rtkit refused 4 of the emulator's own later requests (22:42:44, 3 at 22:43:13;
  R's own count shows 0 refusals): R took places other parts of the emulator wanted;
- in ASTRO the emulator's 16 requests came first and left R room for 2 (R 7 and 4 refusals).

**Build 13 (commits e1982999, 1fdb382b), offline, not yet built:**
- `KYTY_BC5_0429_RR=3`: a sleeper is promoted only on a semaphore where two or more distinct threads of its own name
  family slept (the guest name without its trailing index: "Job Hi 0".."Job Hi 7" are one family). A lone name such as
  AK::AudioMgr, which got RR under RR=2 in K10 and K12 because it shares a semaphore with other threads, is out. No title
  rows. RR=2 stays as it was for comparison.
- rtkit's room: the watchdog counts the user's RR/FIFO and nice < 0 threads once a second (/proc, what rtkit counts), reads
  rtkit's limit from its command line (default 25), and R promotes only while count + 1 + 4 (a reserve for the emulator's
  own and others' requests) fits. A thread denied for room or budget now waits and is promoted at a later sleep (before,
  a budget denial lost it for good: ASTRO B 7 and 10). New count `N` (room denials) and `user U of M` in the count line.
- The normal build logs rtkit's D-Bus error text on a refusal.
- check0429r.sh / check0429l.sh: with RRMODE=3 a check also fails if an AK thread is RR; both print the nice < 0 threads.

Next slot (after exp 0432's): build 13, checks K13 (normal) and K14 (lean) with RRMODE=3, then 2 pairs Q/P with RRMODE=3.

## Slot 04:23–04:29 (2026-11-18): build 13, check K13 FAIL; build 14 (offline)

Box up 10:41 h, 0 amdgpu reset lines since boot, BOX-LOCK empty. Build 13: private normal `4abfec5e`, lean `1a85bf66`,
0 errors, the same 8 warnings, shared builds unchanged.

**h429K13 (normal, RR=3): FAIL**, Job Hi 6 of 8 RR (Hi 2 and Hi 7 not), NO_CRASH, 40.4 flips/s, 0 kernel lines. The
slot stopped there (the check rule). What worked: the family rule, AK threads RR 0 (AudioMgr out), main thread TS, rtkit
refusals 0. RR threads: Job Hi 0, 1, 3–6 (rtprio 6), Job Lo 1, 3, 4, 5, 7 (3). Count line:
`held 11 P 11 R 0 N 13 user 27 of 25`. The emulator's own rtkit high-priority threads at the snapshot:
AK::AudioOutThread, AK::JobWrkr-Acm, HIDAPI Rumble, SDLAudioP0, SDLAudioP53 x2 (nice -15/-10; the audio engine and SDL).

Cause (read after the run, read-only): the user's RT or nice < 0 threads with no emulator were kwin_wayland 3,
pipewire 2, wireplumber 3, pipewire-pulse 2. kwin_wayland has CAP_SYS_NICE (CapEff bit 23) and sets its own RT threads
without rtkit, so rtkit does not count them, and R's scan did: it saw 27 where rtkit had 24 (PipeWire's stack 7, the
emulator's own 6, R's 11). So R's room ran out after 11 promotions. Room-short promotions evicted no one, so the Job Lo
workers, which slept first, kept places the Hi workers needed. With rtkit's 25 and these neighbours, R has about 12
places, or 8 with the reserve of 4.

**Build 14 (offline, not yet built):**
- the scan leaves out processes with CAP_SYS_NICE;
- a short room evicts like a full cap: the holder with the numerically highest guest priority above the newcomer's
  goes back and waits;
- a waiting thread comes back at a later sleep also when such a holder exists.

Expected in the next check: R holds about 8, all of them Job Hi.

## Slot 06:13–06:19 (2026-11-18): build 14, check K15 FAIL on the audio condition

Box up 12:31 h, 0 amdgpu reset lines since boot. Build 14 (d6ac3656): private normal `d8a4ce2c`, lean `31dcc2c5`,
0 errors, the same 8 warnings, shared builds unchanged.

**h429K15 (normal, RR=3, RESERVE=2): FAIL.** The workers' part passed: Job Hi 8 of 8 RR (rtprio 6), six Havok Queries
(5), main thread TS, AK threads RR 0, R refusals 0, NO_CRASH, 40.3 flips/s, 0 kernel lines. Count line:
`held 14 P 21 R 0 C 4 E 7 N 2 user 25 of 25`. The audio condition failed (the top session's rule, 2026-11-18): rtkit
refused 4 requests that were not R's, and SDLAudioP53 x2 and SDLAudioHotplug stayed at nice 0. rtkit's journal:
the emulator's own high-priority requests at 06:15:43–45 (4 granted), 1 refused at 06:15:45.97, in the same second as
R's promotions; 3 more came together at 06:16:14 and all were refused. When R began, the user had 8 such threads, so R
filled to its cap of 14; the audio requests that came later found rtkit full. A reserve checked only when R promotes
does not protect requests that come after. The slot stopped there (K16 and the pairs were not run).

**What this means (desk numbers):** PipeWire's stack 7 + the emulator's own about 8 (AudioOutThread, JobWrkr-Acm, HIDAPI
Rumble, SDLAudioP0, SDLAudioP53 x2, SDLAudioHotplug, and one more seen in K10) = 15 of rtkit's 25, leaving 10. A design
where R yields (drops its lowest holders whenever fewer than 3 places are free, since the burst seen was 3) would hold
about 7, i.e. 7 of 8 Hi. Under rtkit's default limit and these neighbours, R cannot have all 8 Hi workers and leave
every audio request room. The clean way out is raising rtkit's `--threads-per-user-max`, a box system configuration
change: the maintainer's decision only, not done.

## rtkit's limits raised: the maintainer's decision, 2026-11-18 08:17

He chose option (a). Since 08:17:22 rtkit-daemon runs with `--threads-per-user-max=64 --actions-per-burst-max=100`
(the top session verified it: the unit is active and its argv shows both). The change is a systemd override,
`/etc/systemd/system/rtkit-daemon.service.d/bc5-limits.conf`. It is a box system configuration change, done on his word.
R reads the limit from rtkit-daemon's cmdline, so its room count follows the new limit with no build.

Undo (on the box):
`sudo rm /etc/systemd/system/rtkit-daemon.service.d/bc5-limits.conf && sudo systemctl daemon-reload && sudo systemctl restart rtkit-daemon`

The plan for the next slot:
- build 14 with the default reserve of 4 (no build 15);
- K15 normal, then K16 lean, with RR=3;
- if both pass, 2 fps pairs and an ASTRO run.

Pass condition: Job Hi 8 of 8 on RR, 0 rtkit refusals of any kind (R's included), NO_CRASH. Both checks now require
the run's total count of rtkit refusals in the journal to be 0. R stays off by default.

## Slot 08:19–10:13 (2026-11-18): build 14 under rtkit's new limits, all clean

Box up since 06:56 (exp 0430's h430H4 GPU hang at 06:55 and the box's own reboot), 0 amdgpu reset lines; rtkit-daemon
argv `--threads-per-user-max=64 --actions-per-burst-max=100`. Build 14 pins: normal `d8a4ce2c`, lean `31dcc2c5`.
RR=3 and the default reserve of 4 throughout. The tags K15 and K16 were taken earlier, so the checks are K17 and K18.

| Run | Build | R | Result | R's count line |
|---|---|---|---|---|
| h429K17 check | normal | on | PASS: Job Hi 8 of 8 RR, game-main TS, AK RR 0, rtkit refusals 0, NO_CRASH, 41.1 flips/s | held 14, P 20, N 0, user 27 of 64 |
| h429K18 check | lean | on | PASS: Job Hi 8 of 8 RR at every 10 s mark to 190 s, main RR 0, AK RR 0, refusals 0, 200 s | held 14, P 21, N 0, user 27 of 64 |
| h429Q3 (G+600) | normal | on | NO_CRASH, 40.9 flips/s, longest gap 584 ms | held 14, P 15, R 0 |
| h429P3 | normal | off | NO_CRASH, 41.4 flips/s, longest gap 2533 ms | — |
| h429Q4 | normal | on | NO_CRASH, 39.2 flips/s, longest gap 1145 ms | held 14, P 14, R 0 |
| h429P4 | normal | off | NO_CRASH, 41.2 flips/s, longest gap 249 ms | — |
| a429CA1–A4 ASTRO | normal/lean | off/on | 4 of 4 PASS, 0 kernel/crash lines, 0 pad keys; normal fps mean 59.3 (off), 59.1 (on) | lean A4: user 37 of 64, W 7 (prio 478) |

- rtkit refused 0 requests in the whole slot.
- In both checks the emulator's own 7 high-priority requests were all granted. SDLAudioHotplug never asks rtkit.
- K17's ssh link dropped at the end of the run. Its verdict was recomputed from the saved ps, log and journal with the
  check's own conditions.
- fps with R on and off differ by no more than the run-to-run spread, with 2 runs per arm here and 2 more in the 22:39 slot.
- 0 GPU faults or resets.

Raw: `raw/n/check-h429K17.{ps,run}`, `raw/n/check-h429K18.{ps,run,series,out}`, `raw/n/chain-rep15.out`,
`raw/n/astro-a429C.out`.
Still open before any swap: the R count line leaves lean; whether R goes into the shared builds, and on by default, is
the maintainer's decision.
