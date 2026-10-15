# 0120 — 0116's PFSC reader on ASTRO BOT again, with pieces fixed: no fault, about 1 s earlier in the first load phase

**Question.**
- Experiment 0117 reverted 0116's PFSC reader (per-block in-flight slots, 256 MiB cache) after ASTRO
  BOT GPU hangs.
- 0118 and 0119 showed those hangs came from the graphics pieces' two-job submission, not from the
  mount.
- With pieces fixed, does 0116's reader run ASTRO BOT cleanly? What does it gain?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present (the maintainer asked for the PFSC work to continue), `nproc`
  16 before every run.
- ASTRO BOT with its play settings: `bc5-run.env`, with `BC5_DIRECT_PIECES_FULL=1` back on and
  pieces sent as one job (0119). 70 s, no input, `BC5_MOUNT_STATS=1`.
- **Runs 457–460 (12:05–12:12).** The games' `bc5-mount` swapped for 0116's build
  (`bc5-mount.0116`, md5 7368a3d7…, from d28b47f) by `series-pfsc.sh 457 460`. The script puts the
  previous binary (`bc5-mount.before-0116`, md5 fd749db9…, 39ad030) back at the end, as it did.
- **Baseline: runs 451–456 (0119)**, same settings with the previous binary.
- Raw:
  - `raw/series-457-460.txt`;
  - `raw/load-timing.txt`: when the mount had served 2000 and 4000 MiB, from its 1-s stats lines.

**Result.**

| `bc5-mount` | runs | GPU faults | fps (t 40–65 s) | 2000 MiB served at | 4000 MiB at | total |
|---|---|---|---|---|---|---|
| previous (39ad030) | 451–456 | 0 | 59.8–60.0 | 9.0 s (6 of 6) | 28–29 s | 4481–4519 MiB |
| 0116 (d28b47f) | 457–460 | 0 | 59.9–60.0 | 8.0 s (3 of 4), 9.0 s | 28.0–28.1 s | 4484–4494 MiB |

- 0116's reader decoded 5540–5582 MiB of PFSC blocks to serve ~4490 MiB. 9578–10089 blocks
  (~11 %) were decoded a second time, after leaving the 256 MiB cache.
- No timeouts and no page faults in any run.

**Verdict.**
- 0116's reader is safe on ASTRO BOT once pieces go as one job: 4 of 4 runs clean. 0117's reason
  for reverting it no longer holds.
- The gain is small on this machine. The first load phase reaches 2000 MiB about 1 s earlier. The
  second phase ends at the same 28 s, which is the game's own pace (as 0113 found for the second
  title).
- Re-applying 0116 on main (revert of d0e173e) and keeping it in the games' binary is the
  maintainer's call. The games' binary is still the previous one.
- A larger cache would cut the ~11 % decoded twice; the box has the memory for it.
