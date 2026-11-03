# Exp 0381, re-reads: what the second title reads again, and why

**Date.** 2026-11-01, laptop only. No box access, no run. **Branch.** `exp/0381-mount-reread` from main 5b22f700.

**Question.** In the maintainer's 2026-10-31 play the frame rate falls as `bc5-mount` reads more. What is read again and why
(page cache, decode-ahead, the mount's workers, swap, pinned memory), and what is an ordinary load?

**State.** Candidates and counters are built and tested on the laptop. No arm has run: on the slot of 2026-11-01 01:00 two
read-only box reads passed, and the third was refused by the session's classifier (`[Production Reads]`) before any claim, so
the series waits for the morning (`series0381r.sh`). Every effect below is a hypothesis. No verdict.

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
- Read on the box, 2026-11-01: `vm.swappiness` 60, `vfs_cache_pressure` 100, `min_free_kbytes` 67,584, zram zstd 7.4 GiB, MGLRU
  on (`lru_gen` 0x0007), FUSE `max_background` 12. The disk cache holds 8.1 GiB, its limit, with files dated 10-25, for a title of
  750 k blocks (196 GiB decoded): no block past that limit is kept, so most reads must go to the image and Kraken.
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
| 6b | Bigger disk cache | a private directory and `BC5_MOUNT_DISK_CACHE_MIB` | exists, 157 GB free | The cache filled on 10-25 and has no eviction, so it holds old blocks; never touch the shared one for this | Writes go through the page cache while filling |
| 7 | Workers | `BC5_MOUNT_THREADS=4` / `16` | exists | Tests the ceiling | May starve game threads |
| 8 | Fewer pinned pages | exp 0379's zero skip and exp 0388's arena work | other sessions | ~0.7 GB more cache in free play (F632) | Theirs |
| 9 | `vm.swappiness` (60 now), zram algorithm (zstd), `vm.page-cluster` | sysctl, the maintainer's root | his decision | Prefer zram to the NVMe | System setting |
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
   `~/bc5-work/exp0381/reread/`, inside the `ubuntu` container, and its tests (`setup0381r.sh`): the FUSE code has only been
   type-checked with a stubbed `fuser` build script and never executed.
2. **Launcher.** A copy of `play-pkg-0381tb2s.sh` with `BM=` on the private mount, `BC5_MOUNT_STATS=5`, a cap of 900 s, the
   sampler started beside it (`card1` on the box). Binary 86318679, switches all off, and a private copy
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

## Scripts

`series0381r.sh <id> <out>` runs it all from the laptop: claim and build, A0, the streaming gate, A C A C, release, copies. `arm0381r.sh`
is one arm and takes only this test's switches. The lock line is test build 2's format, because the launcher checks it.
Not yet run; `test_arm.sh` drives the gate on stand-ins. The launcher's check of `TB2_SERIES_LINE` was not read: the refused read
was for that, so if the launcher refuses, this is the first place to look.

## F687 and F688 catchers

`mkcatch0381r.py` puts them into a copy of test build 2's `bc5LleAgc.cpp`; `setup0381r.sh` builds that into `reread/bin/kyty_emulator`,
linked as tb2 was. Read-only, off unless set, and written to their own files in the capture directory, so logging off and the
journal's buffer do not hide them. Neither touches GPU submission.

- `BC5_0381_PAGE_CHECK=1112eae000` (`page-check.txt`). For each address: the host's GPU mapping and the rights it recorded, zero
  page, learned window, guest ranges, guest VMA, `/proc/self/maps` rights, and resident and swapped from pagemap. Written at each
  change, and for any fault address at a timeout. It decides F687's open point at the next start: is the page in a real mapping, with
  read rights? The rights are the host's record, not a read of the PTE.
- `BC5_0381_REOPEN_TRACE=1` (`reopen-trace.txt`). For 240 s after a device reopen, each second: flips, mapped bytes, GTT, fence wait,
  how many of the killed jobs' labels have not reached their value, and the threads asleep on an unusual kernel wait. Pinning would
  show GTT climbing with a thread in the driver; labels would show flat GTT with open labels and the title asleep. It only acts on a
  reopen, so the arms may never exercise it: nothing here forces a hang. To learn from the next one, these two switches must be
  in his play launcher, and the emulator must be this binary. That launcher change is the maintainer's decision.

## Local checks

- `cargo test -p bc5-mount`: 81 + 15 + 10 passed, 1 ignored (Windows host).
- `cargo clippy -p bc5-mount --target x86_64-unknown-linux-gnu --all-targets -- -D warnings`: clean, with a scratch copy of
  `fuser` whose build script accepts a Windows host (not committed). `cargo fmt --check` clean.
- `bash test_reread.sh`: 10 of 10, stand-in `/proc`, lines in the mount's format. `bash test_arm.sh`: 8 of 8, with `bash -n` of all
  scripts.
- `test_stream.sh`: 13 of 13. `test_catch0381r.cpp` (MSVC 19, pure parts): all passed. `mkcatch0381r.py` applied to main's unit,
  extracted from patch 0001: 8 edits, every anchor once.
- Not run: any FUSE read, `fadvise`, the switches, the sampler on the box. `catch0381r_host.inc` has never been compiled: the laptop
  has no Linux C++ toolchain. Its first compile is `setup0381r.sh`, on the box, and an anchor that does not fit tb2's unit stops there.

## Proposed F rows

F689–F691, free on `docs/HANDOFF.md` of all 30 refs on 2026-11-01. Check again before writing them there. F686–F688 are the
20:39 hang.

- **F689.** In the 2026-10-31 play, flips/s fall with mount reads, r = −0.93, 33 minutes, with the cost concentrated above
  ~6 GiB a minute (38 flips/s at 2–4 GiB, 16 at 8 or more), and reads never pass ~9.8 GiB a minute. Slow minutes follow PSI io
  (−0.89) more than PSI mem (−0.42). Heavy minutes come with GTT flat. Medium: one session, per-minute.
- **F690.** `bc5-mount` gains counters for repeated reads and read waits and three switches, off by default (5249deee). Laptop
  tests only.
- **F691.** The re-read plan: this file. Nothing measured yet.

## First measured arm (RR3, 2026-11-01)

The series stopped in A0 on its first kernel line, as set: A1, C1, A2 and C2 did not run, so no lever is compared. Setup passed and
both catchers compiled. RT on, no pad, snapshot saves-sample, mount c39cac9f, emulator be846ba2. Gameplay at 140 s; the kernel line at
839 s.

- **What is repeated.** Of 33.1 GiB served, 22.1 GiB (67 %) reached the mount a second time or more; 11.0 GiB were new. From minute 5 to minute 14 repeats are
  80–99.7 % of what the mount serves (1.2–1.9 GiB a minute), and new data is 5–389 MiB a minute.
- **How soon.** 16,154 MiB of the 22,633 MiB of repeats came back within a second, and 16,118 MiB within 64 MiB of other reads. Only
  244 MiB were older than 256 s. So this is not the title walking old areas: it is mostly the same pages asked for again at once.
- **What it costs.** 164,756 of 221,526 Kraken decodes (74 %, 41 of 55 GiB) were of blocks decoded before. From minute 5 the mount
  decodes 2.6–4.1 GiB a minute against 0.2–0.4 GiB taken from the disk cache, while serving 1.3–2.0 GiB. Whether those decodes cost the
  frame rate is not measured here.
- **Pressure.** `workingset_refault_file` runs 84–325k pages a minute (0.3–1.3 GiB), the same order as the repeats, with `pgsteal_direct`
  near 0 from minute 9. Swap-in is small but comes in bursts (5–11k pages a minute in minutes 7–9), with 2.4–5.3k emulator major
  faults in those minutes.
- **Reading, not a result.** A page evicted within a second of being read fits read-ahead pages thrown away before use. Nothing here
  shows that; C1 and C2, with read-ahead at 32 KiB, are the test.
- **The stop.** At 839 s, gfxhub permission faults, SQC data, `bc5-ring`, ten lines at six addresses with a zero high dword (first 0x16382000), then a gfx ring
  timeout, a ring reset that succeeded and a devcoredump. Not the page of F687: the three reads of 0x1112eae000 say read-write in a
  shared range, resident or not, and that page did not fault, so F687 stays open. No reopen, so F688 got nothing.
- **Script bug found.** RR2 ended silently: `distrobox` read the setup script from stdin (f5ae3a1c).

**Rest of the series (RR4).** `series0381r.sh <id> <out> rest` runs A1 C1 A2 C2 without A0. The maintainer set vm.swappiness 150 and
vm.page-cluster 0 at about 08:00 (until reboot), so A0 was under other VM settings: compare A with C inside RR4, and read A0 against
it only with that said. Each arm's start file records the settings.

## RR4: A1 C1 A2 C2 (2026-11-01)

All four arms ran to the 900 s cap with no amdgpu kernel line. RT on, no pad, mount c39cac9f, emulator be846ba2, vm.swappiness 150, vm.page-cluster 0. C is
`BC5_MOUNT_DROP_BACKING=1 BC5_MOUNT_MAX_READAHEAD_KIB=32 BC5_MOUNT_PREFETCH_KIB=512`, all three together, so nothing below separates them. Mount and sampler
figures are the window 200–830 s; flips are the whole run.

| | A1 | C1 | A2 | C2 |
|---|---:|---:|---:|---:|
| title's reads (`emu_rchar`), GiB | 36.7 | 51.5 | 19.0 | 17.4 |
| served by the mount, GiB | 35.3 | 47.5 | 16.3 | 11.0 |
| new, GiB | 6.7 | 7.1 | 2.0 | 1.5 |
| repeats, % of served | 81.0 | 85.0 | 87.7 | 86.4 |
| repeats within 1 s, % of repeats | 71.3 | 71.8 | 71.1 | 71.0 |
| backing read per MiB served | 1.25 | 0.79 | 1.32 | 0.95 |
| decoded per MiB served | 1.88 | 1.19 | 1.86 | 1.47 |
| decode-ahead blocks used, % | 46 | 76 | 50 | 72 |
| service mean, µs (whole run) | 1,292 | 1,409 | 1,172 | 1,493 |
| flips | 21,896 | 21,022 | 27,368 | 25,774 |
| frames of 100 ms or more | 795 | 885 | 349 | 447 |
| kswapd steals, M pages | 21.7 | 13.2 | 10.6 | 3.2 |
| direct steals, k pages | 670 | 165 | 197 | 53 |
| swap-in, k pages | 246 | 152 | 103 | 21 |
| emulator major faults, k | 66.6 | 36.7 | 31.5 | 10.8 |

- **What is repeated.** Archive data: `movie` and `movie_inst` (over 90 % of what these files serve is repeats in A1), then textures. It is not refilled from a kept cache: in the A arms the title asks for only
  1.04–1.16 times what the mount serves, so the page cache spares it at most 4–14 %, even though 71 % of repeats came back within a second. Pages read under a second ago are
  gone, or the read never looks at them. Why is open.
- **Read-ahead refuted as the cause.** At 32 KiB the shares do not move. The reading in the A0 section does not hold.
- **The levers.** C does not cut the repeats. It cuts the mount's own waste: backing read per MiB served by 28–37 %, decoding by 21–37 %, unused decode-ahead by about half.
  Memory churn falls in both pairs, even in C1 where the load rose by 34 %.
- **Frame rate.** No gain. C loses 4 % and 6 % of flips, and has 11 % and 28 % more frames of 100 ms or more; service time rises. Two pairs, with very different load, so this is a direction, not a size.
- **The storm.** Minutes under 1,400 flips (6 in A1, 7 in C1, none elsewhere) serve 5.8–6.2 GiB a minute against 1.1–1.7 GiB in the others, at 15–23 flips/s; r = −0.91 over 54 minutes
  of all five arms. C does not stop it: it came in C1 as in A1. What sets it off is not known, it may be where the route walks to.
- **A0.** A0 ran at swappiness 60 and the old page-cluster, so its swap and fault counts do not compare: with page-cluster 0 each swap-in is one page. Repeat shares match.
- **Fault.** No amdgpu line in 60 minutes of these arms, so the 07:22 fault did not repeat. F687's page again read read-write in a shared range and did not fault. No reopen: F688 got nothing.

**Verdict.** The bundle is not a frame-rate fix and stays off. Its memory saving is real in both pairs, but needs its own test, one switch at a time, against the storm. The next question is why a
page read under a second ago reaches the mount again.

**Cache test (RR5).** `series0381r.sh <id> <out> cache`: a fill arm W0, then A1 W1 A2 W2, about 76 minutes. W uses the private `reread/dc` with a 64 GiB limit, through one more changed line in the private launcher. A arms keep the shared cache, and `arm0381r.sh` refuses
a bigger limit without the private directory, so the shared cache is never written. Each arm's start file records the private cache's size.

## RR5: the private 64 GiB disk cache (2026-11-01)

W0 (fill), A1, W1, A2, W2, all to the 900 s cap with no amdgpu kernel line. RT on, no pad, mount c39cac9f, emulator be846ba2, swappiness 60, page-cluster 3. VGT_HS_OFFCHIP_PARAM was latched at 0x1ff since exp 0392's T1 (top
session's note), so RR5 is not the same GPU state as RR4. The private cache ended at 18.0 GiB of its 64: 15.6 GiB after the fill, so it was never at its limit. The shared cache was not written. Mount figures are the window
200–830 s; flips are minutes 3–14. The counter "decoded" also counts raw blocks, which the cache does not hold, so decode time is the measure of Kraken here, not the block count.

| | A1 | W1 | A2 | W2 | W0 |
|---:|---:|---:|---:|---:|---:|
| served, GiB | 14.2 | 17.4 | 18.7 | 11.6 | 14.3 |
| Kraken and raw decode time, s | 61 | 7 | 101 | 4 | 10 |
| mount CPU, s | 105 | 66 | 157 | 54 | 60 |
| from the disk cache, GiB | 2.2 | 21.0 | 3.1 | 18.7 | 11.9 |
| disk read mean, µs | 1,351 | 9,057 | 666 | 6,739 | 8,621 |
| service mean, µs | 2,466 | 3,723 | 1,412 | 3,661 | 3,408 |
| backing read per MiB served | 1.38 | 1.89 | 1.41 | 2.26 | 1.67 |
| repeats, % of served | 89.2 | 87.1 | 88.9 | 80.3 | 90.7 |
| repeats within 1 s, % | 70.0 | 70.4 | 68.9 | 71.2 | 70.3 |
| flips/s | 34.4 | 29.9 | 31.3 | 31.8 | 32.3 |
| frames of 100 ms or more, whole run | 301 | 353 | 352 | 316 | 267 |

- **Decoding.** The cache takes out 91–96 % of decode time, and flips do not follow: A 34.4 and 31.3, W 29.9 and 31.8. Kraken is not what limits the frame rate in these calm minutes.
- **Price.** A read from the new cache takes 6.7–9.1 ms, against 0.7–1.4 ms in the A arms, and service time rises by 51–159 %. Why was not measured; the fresh file was written block by block.
- **Memory.** No change that holds across the pairs: file LRU 750–920 MiB in all.
- **Repeats.** Unchanged, again at about 70 % within a second, so they do not depend on the decode path.
- **Not tested.** No arm had a storm (no minute under 1,400 flips after minute 3), so this says nothing about storms. They came in 2 of the 4 RR4 arms, and in none of the 6 at swappiness 60; too few to say why.

**Verdict.** The bigger cache is no frame-rate fix and stays off. Together with RR4 this also takes the case out of the pre-decoded image: removing Kraken brought no frames. The open questions stay why a page read under a
second ago comes back, and what sets off a storm.

## Correction: the "within a second" figure (2026-11-01)

**Every "within a second" and "within 64 MiB" above, in A0, RR4, RR5 and the design note, is an artefact, as is the question "why does a page read under a second ago come back".** `reuse.rs` kept age and distance per 256 KiB chunk, and a request
reset them for the whole chunk. A chunk comes back in about three requests (mean 61–95 KiB), so the second and third saw the first one's time. That predicts 1.7–2.2 of bytes under a second for each byte older (3.2 in C2); the logs show 2.2–2.5, in all
ten arms, whatever the switches.

Read from the buckets of 1 s or older only, 76–85 % of repeats are 16–256 s old in the calm arms (52–55 % in A1 and C1 of RR4, with the storms). The file LRU, about 900 MiB at 19–30 MiB/s served, lasts 30–50 s. So plain eviction from a small page
cache fits, with the title cycling over more than the cache holds. That is a reading: per-page ages are not measured yet.

What stands: repeats are 80–91 % of serving, the cache spares little, neither the bundle nor the big cache gave frames. What falls: "read-ahead refuted" loses its age argument and keeps only the unchanged repeat share.

**Fix and tool, laptop only.** Age is now per 32 KiB slot (about 64 bytes a chunk). `BC5_MOUNT_READ_TRACE=<file>` writes every read, open and forget with its caller, off by default; `ana-trace.py` replays it per page. `series0381r.sh <id> <out> trace` runs two default arms with it.
Windows `cargo test -p bc5-mount` 85+15+10, clippy for Windows and for Linux (with the stub fuser) clean, `cargo fmt`, test_arm, test_stream 18, ana-trace on a made-up trace. Nothing of this has run on the box.

## Correction: the RR5 verdict (2026-11-03, Codex review)

The RR5 verdict above says too much. The cache removed decode time, but its own reads slowed to 6.7–9.1 ms against 0.7–1.4 ms and service time rose by 51–159 %, so the new cost may have
cancelled the saving. RR5 shows only that this implementation gave no frames in calm arms. It does not show that Kraken costs no frames, or that every pre-decoded image would fail. The cache stays off and
nothing new is run for this. Storms are untested and the age of repeated pages is still open: the 32 KiB slot is not a per-page measurement.
