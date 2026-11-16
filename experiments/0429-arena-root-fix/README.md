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
