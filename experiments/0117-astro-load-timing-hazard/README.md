# 0117 — ASTRO BOT hangs the GPU when its second load phase is served differently: 0116 reverted

**Question.** Experiment 0116 replaced the readers' duplicate-decode handling with per-block
in-flight slots and gave PFSC a 256 MiB cache. Offline it was faster. Does it hold in ASTRO BOT,
where 0114's striped version caused GPU timeouts?

**Setup.**
- `bc5-mount` built from d28b47f (0116) into the games' binary. The previous binary was kept as
  `~/bc5-work/bc5-mount.before-0116`.
- ASTRO BOT with its play settings, 60 s, no input, `BC5_MOUNT_STATS=1`; 2026-10-15, maintainer
  present:
  - 439 (10:01);
  - 440 (10:03);
  - 441 (the second title's intro) was queued after 440 and never ran.

**Result.**

| run | `bc5-mount` | GPU job timeouts | outcome |
|---|---|---|---|
| 426, 429, and 0052, 0113, 0116, 0135 | as before 0114 (39ad030) | 0 | clean |
| 427 (0114) | striped locks | 4 | machine down |
| 428 (0114) | striped locks | 2 | ran on |
| 439 | in-flight slots (0116) | 0 | clean; second phase 26–30 s, as before |
| 440 | in-flight slots (0116) | 2 | machine down at ~10:03:05 |

- **Run 440.** At 30.4 s of game time, just as the second load phase began (the mount had served
  +50 MiB in its last second), a 27,778-dword graphics buffer and the compute state that follows
  it both failed with 2 s timeouts. The ring reset took the machine down; the kernel journal ends
  at 10:03:05. The maintainer restarted it.
- **Run 427 (0114)** failed the same way, at the same point in the load.
- The second title showed no timeouts with any of the mount versions (0112, 0113).

**Verdict.**
- The fault is ours, but not in the mount. When ASTRO's second load phase is served in a
  different rhythm (faster, or with a different order of completions), its GPU work hangs: three
  of four runs with a changed PFSC reader, against none of six without.
- So there is a latent race in the direct path (or the host's APR/AMPR completion order) that
  depends on when loaded data arrives. It is open, and is the next thing to find for ASTRO.
- Until then:
  - 0116's code is reverted on main (d0e173e);
  - the games' `bc5-mount` is the previous binary again;
  - mount changes are tested on ASTRO with the maintainer present.
- 0112's package-reader change (striped locks) stays: the second title has had no timeouts with it.
