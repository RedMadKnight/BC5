# 0429 — The job-arena crash at its root, so that JobArenaFix can leave the code

**Date.** 2026-11-16. **Branch.** `exp/0429-arena-root-fix`, base main `0f335e5b` (shared patch `2c82a979`, way 2 on).
**Status.** Open: reading the title's code; no build, no run yet.

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

## Proposed private build (fixes first, then test; not built)

On the shared tree at patch `2c82a979` (C1 on, way 2 on), `JobArenaFix` off in every run, no title code patched by
any arm (no pass-through hook, unlike exp 0425's catcher runs):

| switch | does |
|---|---|
| `KYTY_BC5_0429_PRIO_ORDER=1` | guest priorities 300–732 keep their order as nice levels below the job workers: 300–549 → 0, 550–599 → +1, 600–649 → +2, 650–699 → +3, 700–732 → +4 (≤299 −15 and ≥733 +5 as now). The Hi workers then win the CPU against every lower-priority title thread, as by fixed priority |
| `KYTY_BC5_0425_HANDOFF_US=<us>` | exp 0425 C2, unchanged: after a semaphore signal wakes a waiter, the signaller yields its CPU for up to this long |

Test: the long route, the fight record from G and exp 0379's walk after it, to G+600 s, RT on, the named snapshot.
Arms control (the shared state), PRIO_ORDER, C2 and both, three runs each, interleaved. A crash at the site in any arm
is reported against the control's count. Since the bug is the title's, a clean arm lowers the rate; it cannot prove
the crash gone.
