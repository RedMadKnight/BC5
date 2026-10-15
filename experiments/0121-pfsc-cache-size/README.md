# 0121 — The PFSC block cache at 1 GiB: 95 % fewer second inflates, 3.7 GB of memory still free

**Question.**
- 0116's reader (back on main since 38e0717, experiment 0120) inflated about 11 % of ASTRO BOT's
  PFSC blocks a second time in the first 30 s with its 256 MiB cache.
- In the maintainer's two play sessions (12:32 and 12:44, ~1000 s on one mount), 61 % of inflates
  were repeats.
- How large should the default cache be on this box, given what the game leaves free?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present.
- ASTRO BOT with its play settings (`bc5-run.env`, pieces as one job), 70 s, no input,
  `BC5_MOUNT_STATS=1`.
- The games' `bc5-mount` from 38e0717 (0116's reader), with `BC5_MOUNT_CACHE_MIB` per run. The
  mount is unmounted (`fusermount3 -uz`) before every run, so that each starts empty with its own
  size.
- `MemAvailable` sampled every second; the table gives the lowest value.
- Runs 466–469 (13:03–13:10), `series-cache.sh 466:256 467:1024 468:2048 469:1024`.
- An earlier attempt (runs 462–465) never started the game: the mount point was left broken after
  a `bc5-mount` process was killed unmounted. No data; the script now unmounts first.
- Raw:
  - `raw/series-466-469.txt`;
  - `raw/long-session-256mib.txt`: the 256 MiB mount of run 461, reused by both play sessions,
    stats every 60 s.

**Result.**

| run | cache | inflated (blocks / MiB) | inflated again | served | lowest MemAvailable | fps (t 40–65 s) | 4000 MiB at |
|---|---|---|---|---|---|---|---|
| 466 | 256 MiB | 88,759 / 5,547 | 9,692 | 4,477 MiB | 4,531 MiB | 59.96 | 28 s |
| 467 | 1024 MiB | 79,573 / 4,973 | 532 | 4,504 MiB | 3,683 MiB | 59.96 | 28 s |
| 469 | 1024 MiB | 79,425 / 4,964 | 384 | 4,501 MiB | 3,689 MiB | 59.96 | 28 s |
| 468 | 2048 MiB | 79,365 / 4,960 | 346 | 4,627 MiB | 2,700 MiB | 59.96 | 29 s |

- **1024 MiB instead of 256 MiB:**
  - second inflates 9,692 → 384–532, about 95 % fewer;
  - inflated data 5,547 → ~4,970 MiB, 10 % less CPU work for the same data;
  - ~850 MiB less free memory at the low point.
- **2048 MiB** saves almost nothing more and leaves 1 GB less free.
- **Long session at 256 MiB:** 31,139 MiB served, 40,799 MiB inflated, 396,288 blocks inflated
  again.
- No GPU fault or timeout in any run. The load ends at 28–29 s either way: the game's own pace
  (0120).

**Verdict.**
- The `.ffpfsc` default goes to 1024 MiB (`tools/bc5-mount/src/pfsc.rs` `CACHE_MIB`, README).
  `BC5_MOUNT_CACHE_MIB` still overrides it.
- The gain is CPU time, not load time: the mount inflates ~10 % less in the first 30 s.
  - The long session suggests far more over a play session at 256 MiB.
  - Measuring that with 1 GiB needs a long play run.
- 3.7 GB free at the low point is enough on this 16 GB box. 2 GiB would cut it to 2.7 GB for no
  measurable gain.
