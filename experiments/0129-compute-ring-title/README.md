# 0129 — The second title's compute buffers on a compute ring: start screen 32–34 → 41–42 fps once the GFX ring waits on the GPU

**Question.** ADR 0009 steps 2 and 3:
- Does `Device::submit`'s compute-ring path work on the BC-250?
- Do the title's asynchronous compute buffers run correctly on compute ring 0?
- Does the start screen get faster when compute and graphics overlap?

**Setup.**
- BC-250 dev box, 2026-10-15 22:15–23:05, maintainer present, hang watcher on.
  - Kernel 7.2.8-ogc5.1.
  - GPU clock up to 2150 MHz (experiment 0126).
- Code:
  - backend c45e123 and a45f25a;
  - KytyPlus patch 7070a90 and a45f25a.
- **Ladder** (`direct-selftest --submit --compute-ring 0`, commit 963e125): seven steps on
  `Device::submit`'s own path, no shader.
- **Start screen** (`exp0129.sh`):
  - the settings of run 525 (play shortcut, New Game at 100 s);
  - job timestamps from 165 to 180 s, analysed with `jtrings.py`: busy time per ring and the time
    both are busy.
- **Menu** (`exp0129m.sh`): Settings > Visuals scrolled as in run 513 (experiment 0122), with
  screenshots at 8 moments.
- Knobs, all off by default:
  - `BC5_DIRECT_COMPUTE_RING=0`;
  - `BC5_DIRECT_CROSS_RING_WAITS=compute|all`: a wait counts the last pending label write on
    the other ring;
  - `BC5_DIRECT_RING_DEPS=acb|dcb`: a CS dependency on the other ring's last job.
- The maintainer pressed ✕ on the start screen during runs 527 and 528. Their 130–200 s windows
  are the game proper, not the start screen. Runs 529–535 were left alone.
- Raw: `raw/runs-527-535.txt`.

**Result.**

Ladder, compute ring 0: all seven steps passed, no kernel message.

| step | result |
|---|---|
| 1 | `0xffff1000` NOP pad: OK |
| 2 | job timestamps (`COPY_DATA`, `RELEASE_MEM` `DATA_SEL` 3): OK |
| 3 | `RELEASE_MEM` BOTTOM_OF_PIPE_TS/5 and CS_DONE/6 with data: both written |
| 4 | MEC-form indirect-count check (`COND_WRITE`, `COND_EXEC`): the five cases as expected |
| 5 | a 64 MiB CP DMA fill on the GFX ring took 1.18 ms; a compute job submitted after it started 0.39 ms into it. The rings run side by side, with no implicit sync between our own jobs. |
| 6 | a GPU-side wait on the compute ring for a label a later GFX job writes: held, then released; a userptr range mapped during the wait, a later compute job wrote into it |
| 7 | GDS fill and GDS → memory on the compute ring, the GDS BO listed: read back |

Start screen (fps from the frame profile, 130–165 / 165–200 s; the GPU time line over 165–180 s):

| run | setting | fps | both rings busy | game thread in host | label waits / frame |
|---|---|---|---|---|---|
| 530 | one ring (baseline) | 33.6 / 31.6 | — | 13.0 ms | 0.1 ms |
| 528 | compute ring (✕ pressed: game proper) | 27.0 / 25.5 | 19.6 % | 23.9 ms | 23.6 ms |
| 529 | compute ring, cross-ring waits `compute` | 27.5 / 26.1 | 23.3 % | 20.8 ms | 12.8 ms |
| 535 | compute ring, cross-ring waits `all` | **41.8 / 41.4** | 48.9 % | 10.3 ms | 0.6 ms |

- Every run: 0 host timeouts, 0 page faults, 0 ring resets.
- Every compute buffer went to the compute ring (262,145+ jobs a run, none kept back).
- **528 and 529 were slower than the baseline.** On one ring, a graphics buffer's wait for a
  label that a queued compute job writes stayed in the buffer, since ring order covered it. With two
  rings the game thread served those waits on the CPU until `all` let the GFX ring wait on the GPU.
- **535's picture** at 190 s is the start screen, complete.

Menu (fps 120–135 s; screenshots with menu text broken and the scene inside the highlight bar,
out of 8):

| run | setting | fps | both rings busy | broken screenshots |
|---|---|---|---|---|
| 534 | one ring | 49.9 | — | 0 |
| 531 | compute ring, waits `compute` | 34.6 | 10.8 % | 1 (185 s) |
| 532 | + `RING_DEPS=acb` | 33.3 | 7.8 % | 0 |
| 533 | + `RING_DEPS=dcb` | 33.8 | 6.8 % | 0 |

- The maintainer saw the same breakage live in run 529 (Initial Setup).
- The flip brightness detector of experiment 0122 does not tell the cases apart: 19–23 jumps
  in all four runs, including the baseline. Menu transitions count as jumps.

**Verdict.**
- **The compute ring works for this title.** Hundreds of thousands of jobs ran with no fault
  or reset, and the GDS, the indirect-count check and the timestamps behave on the MEC.
- **The gain needs the GFX ring to wait on the GPU** (`CROSS_RING_WAITS=all`). Then the rings
  overlap half the time and the start screen runs +24–31 % (41–42 fps).
- No wait can deadlock:
  - only the label writes of jobs already submitted count, so each job waits on earlier ones;
  - what remains is the case of a compute job that hangs, which would now stop the GFX ring too
    (F110 risk).
- **Open, before any play setting:**
  1. **The menu race.** One broken screenshot out of eight in 531, and one seen live in 529.
     - The DMA snapshots did not overflow.
     - The ring dependencies are the instrument for finding it, but eight screenshots a run are
       too few to tell which direction it is.
     - Also needed: the menu's frame rate with `all` (531–533 ran with `compute`).
  2. **ASTRO BOT** with the compute ring and `all`, above all the water cycles (ADR 0008).
  3. **A longer start-screen run, and the game proper after ✕.**
