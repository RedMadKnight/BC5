# Exp 0381, re-reads: what the second title reads again, and why

**Date.** 2026-11-01, laptop only. No box access, no run. **Branch.** `exp/0381-mount-reread` from main 5b22f700.

**Question.** In the maintainer's 2026-10-31 play the frame rate falls as `bc5-mount` reads more. What is read again and why
(page cache, decode-ahead, the mount's workers, swap, pinned memory), and what is an ordinary load?

**State.** Candidates and counters are built and tested on the laptop. Nothing here has run on the box, so every effect below
is a hypothesis until the arms have run. No verdict.

## What the data shows

Source: the top session's copies of `play-20261031-200140.log` and `mem-20261031-200140.txt` (not committed), tb2 binary
86318679, all switches off, RT on. `permin-play.py` makes `raw/perminute-20261031.txt`. Reads are the mem sampler's
`mount_read_1min`, minutes 240–2220 s, 33 minutes, 155.7 GiB.

| Reads a minute | Minutes | Flips/s | Frame | PSI io full | PSI mem full |
|---|---:|---:|---:|---:|---:|
| under 2 GiB | 5 | 40.8 | 24.5 ms | 3.5 | 0.7 |
| 2–4 GiB | 12 | 38.3 | 26.1 ms | 5.0 | 1.1 |
| 4–6 GiB | 4 | 33.0 | 30.3 ms | 6.4 | 1.0 |
| 6–8 GiB | 5 | 22.2 | 45.0 ms | 10.8 | 1.5 |
| 8 GiB or more | 7 | 16.4 | 61.1 ms | 12.4 | 3.4 |

Facts:

- r(flips, reads) = −0.93 over these minutes (the top session's −0.89 used another window). r(flips, PSI io full) = −0.89,
  r(flips, PSI mem full) = −0.42, r(reads, PSI io full) = 0.92. So this play's slow minutes go with I/O stall more than
  with reclaim stall, unlike F620's −0.77. Correlation only; scenes drive reads too.
- The cost is not linear: little below 4 GiB a minute, then +20–35 ms a frame. A linear fit (12.2 ms + 5.3 ms per GiB/min)
  hides that.
- Reads have a ceiling: from t 60 s on, no minute passes 9,754 MiB (163 MiB/s), and the heavy minutes sit at 8.1–9.8 GiB.
  Load and play reach the same level. Whether the limit is the title's demand, the mount, or the drive is not known.
- Heavy stretches come after the load, with GTT flat: t 420–720 s (12,325–12,372 MiB) and t 1990–2232 s (12,624–12,639 MiB).
  So those reads do not feed the eager import.
- MemAvailable stays at 206–480 MiB after t 300 s and does not follow reads (r = −0.44 with flips): as in F620, it shows that
  the box is full, not how badly.
- The mount's path from code: kernel page cache (`FOPEN_KEEP_CACHE`) → 32 MiB block cache → disk cache of decoded blocks
  (launcher: on, 8 GiB limit) → image plus Kraken. Each block is 256 KiB. `POSIX_FADV_RANDOM` is on, so kernel readahead on
  the backing files is off (F398). The kernel's own readahead on the mounted files is at its default.

Inference, not measured: 5 minutes at 8 GiB is ~40 GiB of NVMe reads. F396's ratio (served ≈ 0.6 of what the mount asked) gives
~25 GiB served, twice what the title can hold, so a large part must be read and thrown away or read twice. That would make
the title's own streaming a real load on any cache, and no page-cache lever would remove it all.

Inference, not measured: with ~400 MiB of page cache to work in and 140 MiB/s coming through it, a page stays ~3 s unless it
is reused. Each block adds a backing copy and, for the part served, a copy of the mounted file. Those backing pages are the
least useful ones: a read that reaches them already missed two caches.

What the data cannot show: nothing recorded separates first reads from repeats, or says where a read waits. The counters
below exist for that. F396–F398 and F505 measured totals, never repeats.

## Levers

Ranked by expected gain against risk. All gains are hypotheses.

| # | Lever | Switch | Needs | Why it might help | Risk |
|---|---|---|---|---|---|
| 1 | Drop backing pages after a read | `BC5_MOUNT_DROP_BACKING=1` | this build | Roughly halves what enters the page cache, so hot pages live longer | A syscall per block; a re-read that the backing copy would have caught now hits the NVMe |
| 2 | Less kernel readahead on the mounted files | `BC5_MOUNT_MAX_READAHEAD_KIB=32` | this build | Same over-read as F396, one layer up | More FUSE round trips on sequential reads |
| 3 | Less decode-ahead | `BC5_MOUNT_PREFETCH_KIB=512` or `0` | exists | Waste is unmeasured; F287 only tested more | Sequential loads slower |
| 4 | Pass the page cache by | `BC5_MOUNT_DIRECT_IO=1` with `BC5_MOUNT_CACHE_MIB=512` | this build | If most reads are one-shot, the page cache only churns; the mount's cache becomes the one bounded copy | Repeats all reach the mount; 512 MiB of anon on a full box; a shared mmap of a mounted file would fail (none seen in patch 0001's mmap calls, not proven) |
| 5 | Bigger block cache | `BC5_MOUNT_CACHE_MIB=256` | exists | Keeps decoded blocks out of the kernel's LRU | Goes to zram under pressure |
| 6 | No disk cache | unset `BC5_MOUNT_DISK_CACHE` | exists | If compressed reads are smaller than decoded ones, fewer NVMe bytes | Costs Kraken CPU, and the start-up gain of exp 0113 |
| 7 | Workers | `BC5_MOUNT_THREADS=4` / `16` | exists | Tests the ceiling | May starve game threads |
| 8 | Fewer pinned pages | exp 0379's zero skip and exp 0388's arena work | other sessions | ~0.7 GB more cache in free play (F632) | Theirs |
| 9 | `vm.swappiness`, zram algorithm, `vm.page-cluster` | sysctl, the maintainer's root | his decision | Prefer zram to the NVMe | System setting; current values not read |
| 10 | `/sys/fs/fuse/connections/*/max_background` | root | his decision | Tests whether the kernel's queue of 12 caps async reads | `fuser`'s setter needs a newer ABI feature, so it is not in this build |

Not built: the setter of lever 10, on purpose: `abi-7-13` changes the mount's INIT for every title.

## The test build

Commit 5249deee, `tools/bc5-mount` only. No emulator, backend or launcher change, and no shared file. Everything is off
unless named:

- `BC5_MOUNT_STATS=<s>` keeps its old `stats` line and adds three:
  - `reread`: first and repeated bytes, repeats by age and by bytes served since, per 4 KiB page. With the page cache on, a
    repeat is a page the kernel dropped and the title asked for again. With `DIRECT_IO` it means the title read it again,
    so the two are not the same number.
  - `spans`: pool peak, image and disk-cache bytes, decode-ahead's use, and mean and peak of queue, service, disk, image and
    decode time. `reread` costs ~20 MB of RSS at most (hypothesis: 400 k chunks).
  - `again`: the 12 files with most repeats, once a minute. Holds file names, so the log stays on the box.
- `sample-reread.sh`: one line a second beside a run: refaults, swap, direct reclaim, PSI, mount and emulator I/O and CPU,
  and every 10 s the emulator's threads with most major faults. Read-only.
- `ana-reread.py`: per-minute table from both.

## Run plan

No pad, RT on, one job, atomic lock, private paths, stop on the first kernel line, as `tb2run0381.sh`.

1. **Build.** On a slot: private checkout of 5249deee, `cargo build --release -p bc5-mount --target-dir` under
   `~/bc5-work/exp0381/reread/`, inside the `ubuntu` container. Run the mount's tests there: the FUSE code has only been
   type-checked with a stubbed `fuser` build script and never executed.
2. **Launcher.** A copy of `play-pkg-0381tb2s.sh` with `BM=` on the private mount, `BC5_MOUNT_STATS=5`, a cap of 900 s, the
   sampler started beside it. Check `DRM`'s path for `mem_info_gtt_used`. Binary 86318679, switches all off, and a private copy
   of the learned file, so line 110 (F687) is in every arm alike.
3. **Route.** Start from sample f93851b7b0e0dc7a, gated keys as `s6n0382.sh` (slot from the list, gameplay by ~140 s). Page cache
   dropped before each arm (`drop_caches` is allowed).
4. **Calibrate once.** Baseline, walking script adapted from `walk0379s4.cmd`. F634 and F635 warn that a route can fail to
   stream: the gate is 4 GiB a minute or more in at least 3 minutes after gameplay starts. If it fails, say so, keep only the load
   window (menu to gameplay, 5–6 minutes, 7–10 GiB a minute here) as the measure, and do not call it play.
5. **Arms, all candidates first** (the standing rule): A baseline, C = levers 1 + 2 + 3 (512), A, C. Then F = lever 4 alone if the
   counters show mostly one-shot reads. If C wins, take levers out one at a time; if C loses, read the counters before
   anything else.
6. **Measures.** Flips/s and frames over 70 ms in the same window, reads a minute, repeats share and age, queue and service
   time, refaults. A win needs both C runs above both A runs.
7. **Fallback.** His next play on the counters alone costs him nothing and is the only real streaming data: `BC5_MOUNT_STATS=5`
   and the private mount, no switch.

Limits: two runs an arm is weak; a bench route differs from his play (F543); DROP_BACKING's benefit depends on how full the box
is, so a run without pressure shows nothing either way; the arms do not test hangs.

## Local checks

- `cargo test -p bc5-mount`: 81 + 15 + 10 passed, 1 ignored (Windows host).
- `cargo clippy -p bc5-mount --target x86_64-unknown-linux-gnu --all-targets -- -D warnings`: clean, with a scratch copy of
  `fuser` whose build script accepts a Windows host (not committed). `cargo fmt --check` clean.
- `bash test_reread.sh`: 10 of 10, stand-in `/proc`, lines in the mount's format.
- Not run: any FUSE read, `fadvise`, the switches, the sampler on the box.

## Proposed F rows

F689–F691, free on main and on the branches checked (rows stop at F685, then F700). F686–F688 are the 20:39 hang.

- **F689.** In the 2026-10-31 play, flips/s fall with mount reads, r = −0.93, 33 minutes, with the cost concentrated above
  ~6 GiB a minute (38 flips/s at 2–4 GiB, 16 at 8 or more), and reads never pass ~9.8 GiB a minute. Slow minutes follow PSI io
  (−0.89) more than PSI mem (−0.42). Heavy minutes come with GTT flat. Medium: one session, per-minute.
- **F690.** `bc5-mount` gains counters for repeated reads and read waits and three switches, off by default (5249deee). Laptop
  tests only.
- **F691.** The re-read plan: this file. Nothing measured yet.
