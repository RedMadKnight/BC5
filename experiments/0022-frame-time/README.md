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

**Verdict.** Open: steps 1 and 2 confirmed on the GPU (2.4 times the frame rate at the title
screen); the cutscene comparison and steps 3 and 4 are still to do.
