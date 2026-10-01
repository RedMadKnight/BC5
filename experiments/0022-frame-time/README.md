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

**Verdict.** Open: baseline recorded, no optimisation run yet.
