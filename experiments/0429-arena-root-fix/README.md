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
does not keep the workers ahead of the owner. The stressor works: the control crashed again (now M 3 crashes, 1 clean,
across builds 3, 4 and 6). R13: counts only. The guest mutex's inner `std::mutex` is not the cause, or not the whole of
it. No candidate of this experiment survives. The removal is unaffected; it needs no candidate to be swapped.
