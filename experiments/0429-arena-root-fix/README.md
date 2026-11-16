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
