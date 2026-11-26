# 0071 — the display buffer's wait left to the GPU: two machine resets

**Question.** Since 0070 the game's thread waits 6–7.5 ms a frame on the CPU for a display
buffer:
- the frame whose flip frees it has to finish on the GPU;
- KytyPlus has to read it.

Meanwhile the GPU is busy only ~15.5 ms of a ~26 ms frame. Can the wait stay in the graphics
buffer for the GPU, like the ring order's waits (0055), so that the game's thread goes on?

**Setup.** `BC5_DIRECT_FLIP_GPU_WAIT=1` (patch 0001, off by default):
- when a deferred flip of the buffer is queued, the flip-label wait is added to the waits the
  filter keeps for the GPU;
- the label is cleared once KytyPlus has read the buffer (0070);
- a watchdog thread clears a label whose flip has been queued for more than 150 ms.

Run 312 (2026-10-13 20:26) as that. Run 314 (20:55) with:
- the labels moved from the emulator's data to an anonymous page of their own;
- that page mapped for the GPU (`map_userptr`) and checked before each wait is left to the GPU;
- the CPU wait kept otherwise.

The maintainer was at the machine. Journal lines are in `raw/`.

**Result.**
- **Run 312:**
  - the first wait left to the GPU (t = 1.3 s) never ended: a 2 s fence timeout and a kernel
    ring reset, and the machine went down;
  - the buffer also had its 3 usual "unmapped" drops, the label writes: the labels were not in
    the GPU's address space.
- **Run 314:**
  - the page was mapped ("mapped for the GPU now") and the waits went to the GPU for 29 s;
  - the watchdog cleared a label 5 times (flips queued 150–162 ms);
  - the mapping had to be redone 4 times, so the host's anonymous-memory revalidation removed it
    in between;
  - at 31 s a graphics buffer timed out and the machine went down again.

**Verdict.** Failed, and kept off. A wait the GPU holds on host memory needs two guarantees this
host does not give:
- the page must stay mapped for as long as any job may wait on it;
- the flip's read must happen in bounded time (KytyPlus's presentation thread sometimes takes
  more than 150 ms).

Without them every attempt risks the machine. Not to be retried without both, and never
unattended.

The hard reboots also dropped the staged `rpm-ostree` deployment that carried
`udmabuf.size_limit_mb=1024` (0066). Staged deployments are written at an orderly shutdown.
