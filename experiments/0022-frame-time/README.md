# 0022 — Frame time on the direct path: where 167 ms go

**Question.** The game reaches its opening cutscene on the BC-250 (run 100 below) at 6 frames
per second, and its first level takes four minutes to load. The GPU needs about 15 ms for the
frame's main command buffer. Where does the rest go, and how much of it is the host's own?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44` with `ttm.pages_limit` at
13 GiB (HANDOFF D12: 13,312 MiB of GTT). Track-B host with patch 0001 as of experiment 0021,
run command of experiment 0017 plus `BC5_DIRECT_LAZY_NAMES=orbis_user_malloc
KYTY_BC5_CACHE_MIB=96,16,16,16 KYTY_BC5_VMA_BLOCK_MIB=16`. Times come from the journal's
`timing:` lines (`BC5_DIRECT_TIMING=1`).

**Result.**

*Run 100* (18:02, GPU, 900 s, the maintainer at the controller; capture
`kytyplus-20261001-1802`, `raw/run100-summary.txt`): **96,484 submissions, one failed, 6,399
flips; the first level loads and the game plays its opening cutscene in real time.** Title
screen left at 159 s; loading tunnel until about 400 s; then the cutscene — a planet and
asteroids, the mothership full of bots, an alien in a saucer — rendered by the game's own draws
(main command buffer up to 42,906 dwords, median 14.9 ms on the GPU) at 6 fps. Imported memory
ends at 7,672 MiB, the GTT counter at 7,940 of 13,312 MiB when 7,296 were imported: past the
old ceiling of 7,597, so the raised limit was needed. The one failure is a fence timeout 889 s
in, on a write fault at 0x52afd9000 (learned), eleven seconds before the run's end.

A cutscene frame, averaged over 120 s (717 frames, 16 submissions per frame, 167 ms):

| Part | ms per frame |
|---|---|
| mapping sync before the submissions | 17.4 |
| render-target hints | 6.8 |
| device: filter, state stack, copies (`prepare`) | 7.5 |
| device: BO list creation | 4.5 |
| device: submission ioctl (1,592 BOs in a draw's list) | 28.9 |
| device: waiting for the fence (the GPU's work) | 17.0 |
| host around the device call: crash journal, IB dumps, a second filter pass | 80.9 |
| everything else: the game, the soft CP, presentation | 4.4 |

So the GPU works 17 ms of a 167 ms frame, the game itself is not the limit, and **half of the
frame is the crash journal**: for every submission the host writes the raw and the filtered IB
and its tables to files (842,600 files, 5.6 GB in this run), filters the IB a second time for
the journal line, and syncs the journal (620 MB) to disk. That was the price of finding the
reset classes of experiment 0016; it is not needed to run.

The plan, in order of size:

1. a journal mode without per-submission dumps and syncs (about 80 ms);
2. fewer, larger BOs — 1,475 imports averaging 5 MiB exist because memory is imported as it
   fills; merged they would be a fifth of that — and one BO list kept between submissions
   instead of one built per submission (most of 33 ms);
3. the mapping sync and the hints, which rescan what has not changed (most of 24 ms);
4. the state-stack emulation restoring 7,368 registers per pop where few differ, and waiting
   for every fence synchronously (part of 24 ms).

*Steps 1 and 2, written and checked without the GPU* (map-only run, 75 s):

- `BC5_DIRECT_JOURNAL=min` (host): no per-submission dumps, no second filter pass, no sync; one
  buffered journal line per submission, flushed twice a second and at once on a failure. The
  dump directory of the check run holds one file and a 1,623-line journal. For chasing a hang
  the variable stays unset.
- merged imports (host, `Device::free_shared`): neighbouring imports that have existed for 3 s
  are replaced by one import of up to the udmabuf module's limit (64 MiB), at most 256 MiB per
  pass and a pass every 250 ms, the old BOs freed after the remap. 97 BOs for 3,966 MiB in the
  check run. `BC5_DIRECT_NO_MERGE=1` turns it off, `BC5_DIRECT_MAX_BO_MIB` sets the size.
- kept BO list (backend): the list of a submission with draws is reused while the set of mapped
  BOs and the scratch BO stay the same.

*Run 101* (18:30, GPU, `BC5_DIRECT_JOURNAL=min`, merged imports, kept BO list; capture
`kytyplus-20261001-1830`, `raw/run101-summary.txt`): **99,794 submissions in 356 s, none
failed, no fault; the title-screen scene runs at 19.8 fps instead of 7.4–8.2** (runs 97 and
99), the picture unchanged. The intro before it now takes its own 45 s instead of 85. 128
imports for 6,124 MiB (61 merge passes); a draw's list has 246 BOs. The dump directory is 56 MB.

A title-screen frame, averaged over 180 s (3,565 frames, 14 submissions per frame):

| Part | run 97, ms | run 101, ms |
|---|---|---|
| mapping sync | 15 | 12.5 |
| render-target hints | 3.5 | 4.6 |
| device: `prepare` | 4 | 1.1 |
| device: BO list | 3 | 0.1 |
| device: submission ioctl | 21 | 14.5 |
| device: waiting for the fence | 15 | 14.3 |
| around the device call, the game, the rest | 60 | 3.4 |
| **frame** | **122** | **50.5** |

The cutscene was not reached: the controller dropped off the USB bus 75 s into the run (kernel
log: eight disconnect–reconnect cycles of the DualSense within 70 s, one more later), and the
emulator, inside its container, does not see a controller that comes back. That is the dev
box's cabling or port and the container's missing hot-plug, not the GPU path; the maintainer
ended the run.

What is left of the frame is now mostly three things of similar size: the mapping sync and
hints (17 ms), the submission ioctl (14.5 ms over 14 submissions), and the GPU's own time
(14.3 ms, waited for synchronously).

*Step 3* (host, patch 0001), from a split of the sync and hint time measured map-only:

- the direct-memory sync returns at once while nothing can have changed: the memfd's allocated
  size (`st_blocks`, which grows with every page the game first writes), the views and the
  forced set are the same as at the last full scan (`BC5_DIRECT_NO_FAST_SYNC=1` turns it off);
- the walk over the anonymous VMAs (`/proc/self/maps` and `mincore`, 0.9 ms a call) runs at most
  every 100 ms for the forced call before a draw (`BC5_DIRECT_ANON_SYNC_MS`); an unmapped
  operand or an `-EFAULT` from a submission still walks at once;
- learned regions are re-applied only when views, VMAs or the list changed;
- the hint mapper tracks only the render-target base registers and skips unchanged addresses.

*Run 102* (19:00, GPU, steps 1–3, 598 s; capture `kytyplus-20261001-1900`,
`raw/run102-summary.txt`): **228,876 submissions, none failed, 16,266 flips; the title-screen
scene at 27.1 fps** (36.8 ms a frame), the loading tunnel behind it at 27–29 fps. Two `-EFAULT`
resyncs early in the run, both recovered by the retry that exists for them.

| Part of a title-screen frame | run 97 | run 101 | run 102 |
|---|---|---|---|
| mapping sync | 15 | 12.5 | 1.2 |
| render-target hints, learned regions | 3.5 | 4.6 | 0.1 |
| device: `prepare` | 4 | 1.1 | 1.1 |
| device: BO list | 3 | 0.1 | 0.1 |
| device: submission ioctl | 21 | 14.5 | 15.0 |
| device: waiting for the fence | 15 | 14.3 | 16.3 |
| the rest | 60 | 3.4 | 3.0 |
| **frame, ms** | **122** | **50.5** | **36.8** |

What is left is the submission ioctl (14 submissions a frame at about 1 ms) and the GPU's own
time, waited for after every submission: 31 of 37 ms. Both are properties of submitting each of
the game's buffers as its own job and waiting for it.

The level load does not get shorter with the frame rate: the maintainer picked the save slot
407 s in, and 191 s later the run ended with the load still going (imports at 6,928 MiB; in run
100 the load took about 240 s at 7 fps). The game made about as many file lookups in that time
as in run 99. What paces the load is not known yet.

*Run 103* (19:17, GPU, the code of run 102, 718 s, the maintainer at the controller, with a
probe of the load; capture `kytyplus-20261001-1917`, `raw/run103-summary.txt`): **258,551
submissions, 17,191 flips; the game loads its level, plays the cutscene at 24.3 fps (6 in run
100) and reaches its first interactive scene** — the crash site in the desert, with the
controller prompt on screen — at 23.5 fps. Three submissions timed out on page faults in
memory no register had named; each was learned and the device reopened, as designed.

| Window | fps | submissions per frame | sync + hints | ioctl | fence (GPU) | frame, ms |
|---|---|---|---|---|---|---|
| cutscene, 390–480 s | 24.3 | 16.0 | 1.9 | 17.6 | 17.0 | 41.1 |
| desert, 560–620 s | 25.5 | 16.0 | 1.7 | 16.7 | 16.9 | 39.2 |
| first interactive scene, 640–690 s | 23.5 | 17.2 | 2.0 | 16.8 | 17.7 | 42.6 |

*The level load.* Slot picked 61 s in, imports at their loaded size about 240 s later, as in
run 100. The probe (two minutes of the load: per-thread CPU time, I/O counters of the emulator
and of `bc5-mount`, a backtrace of every thread):

- storage is idle: `bc5-mount` reads 16 MiB/s from the disk (the disk does 700–780 MB/s, the
  mount 400–770 MB/s on a large file) but uses 76 % of a core;
- no thread of the emulator is busy for more than 43 % of a core;
- the thread caught in the file system is in `KernelStat` → `ResolvePathIgnoringCase`. That
  function of KytyPlus, for a file that does not exist, lists the whole directory to look for a
  name differing only in case — under the mount table's lock, through FUSE, in directories of
  up to 12,133 entries — and the game asks for about 17,000 files that do not exist while this
  level loads (it searches eight directories for every asset). That is the 52 lookups a second
  of experiment 0021, and the pace of the load.

Patch 0001 now keeps each directory's names, folded to lower case, while the directory's
modification time is unchanged. The same lookups and results in a map-only run; the effect on
the load is for the next GPU run.

The probe also shows the host's own remaining cost during a load: the anonymous-VMA walk reads
`/proc/self/maps` at 32 MiB/s (ten walks a second over a 3 MiB file), 17 % of a core.

*Motion input.* The first interactive scene asks for the controller to be shaken, and nothing
happened: KytyPlus reports zero acceleration and angular velocity to the game. Patch 0001 now
enables the pad's accelerometer and gyroscope through SDL and puts the latest sample into every
pad state the game reads (acceleration in G, angular velocity in rad/s, SDL's axes; no
orientation is derived yet — `TODO(verify)` the console's axis convention). SDL reports both
sensors enabled for the DualSense on the dev box; whether the game accepts the data is for the
next run.

*Run 104* (19:44, GPU, the directory cache and the motion sensors, 598 s, the maintainer at
the controller; capture `kytyplus-20261001-1944`, `raw/run104-summary.txt`): **227,311
submissions, none failed, no fault, 14,758 flips — and the game reaches gameplay.** The whole opening
cutscene renders; in the desert the maintainer shakes the controller, the game's controller
wakes up, the character climbs out, and from about 570 s it stands in the level, the game waiting
for the player (stick events are not logged, so whether it was moved is not recorded), at 23.9 fps (16 submissions and 41.8 ms a frame: ioctl 17.6, GPU 17.5).

- *Motion input works*: SDL's accelerometer and gyroscope samples in the pad state are what the
  game wanted. Axes and the missing orientation remain `TODO(verify)`.
- *The level load takes 135 s instead of 240* (slot picked at 60 s, imports at their loaded size
  at about 195 s). The directory cache removed the scan, not the questions: the game still
  makes 28,246 path lookups, 21,061 of them for files that do not exist. What paces the
  remaining 135 s has not been probed.

**Verdict (2026-10-01, 20:00).** Passed for its question, with one step left open. Where the
167 ms went is answered and most of it is gone: 6 to 24 fps in the cutscene, 8 to 27 at the
title screen, the first level's gameplay at 24. Steps 1–3 were all host overhead;
step 4 — the submission path, 35 of the remaining 42 ms split evenly between the kernel's job
handling and the GPU's own work that is waited for — is the next experiment, and the load time
with it.

**Addendum, runs 105 and 106** (20:03 and 20:06, GPU, `BC5_DIRECT_EAGER_NAMES=GpuGarlicMemory,GpuOnionMemory`;
captures `kytyplus-20261001-2003`, `-2006`). Run 105 was ended by the maintainer after 141 s:
the controller had dropped off the USB bus again (six disconnects in 80 s, on the other port
too — the cable or the pad, not the port). Run 106, the full 598 s with the controller staying
connected: **226,913 submissions, no page fault, no fence timeout, 14,834 flips**; the level is
reached, and the Options button, which froze run 103 for 14 s, opens the pause screen at once
(31–32 fps there); the maintainer reports that walking the character works. With both GPU heaps imported in full the imports end at 8,314 MiB.

One submission was lost: a compute buffer answered `-EFAULT` twice (the retry after the resync
too), 596 s in — a userptr BO whose pages the guest had unmapped; eight such resyncs in the run
against two to four before the anonymous walk was rate-limited. One retry is not always enough.
`SDL_JOYSTICK_DISABLE_UDEV=1` was set so that SDL would notice a controller coming back inside
the container; the controller never left, so that is untested.
