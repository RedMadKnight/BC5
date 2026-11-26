# 0124 — The second title's start screen: the GPU is idle 27.5 % of the time between ~115 jobs a frame

**Question.**
- After New Game the second title shows its animated start screen at 31 fps (experiment 0123); the
  console's Performance mode targets 60 fps.
- Where does the frame go? Is the GPU busy, or waiting for us?

**Setup.**
- BC-250 dev box, 2026-10-15, maintainer present.
- The second title with its play shortcut's settings, including the reflection traversal skip of
  0123. New Game at 100 s, the start screen from about 105 s.
- **Run 517:** the host's frame profile.
- **Run 518:**
  - render sizes (`BC5_DIRECT_PKT_STATS=1`);
  - the title's own GPU timestamps (`BC5_DIRECT_TS_LOG=170`, which now collects them without a
    timestamp scale too);
  - `tsprof.py` charges the gap before each timestamp to the buffer that wrote it.
- **Runs 519–520:** new opt-in `FilterOptions::job_timestamps` (host `BC5_DIRECT_JOB_TS`). The
  backend puts a GPU-clock timestamp in front of each job and one behind it, and the host reads them
  when the job is done:
  - in front: `COPY_DATA` with `COPY_DATA_TIMESTAMP`;
  - behind: `RELEASE_MEM` `BOTTOM_OF_PIPE_TS` with `DATA_SEL` 3;
  - packet forms from Mesa `src/amd/common/sid.h` at 0866ae7; `radv_query.c` writes its
    timestamps with the same `COPY_DATA`.
- `BC5_DIRECT_JOB_TS=165:180` journals every job's interval in that window. `jtunion.py` sorts them
  and takes the union: time with work and idle holes.
- Raw:
  - `raw/runs-517-518.txt`;
  - `raw/run520-union.txt`.

**Result.**
- **Frame (run 517, t 130–230 s, ~32 ms):**
  - GPU busy 24.0 ms;
  - the title's thread spends 17.0 ms inside the host (prepare 3.3, CS ioctl 2.9, list 0.6,
    label waits 1.7, the rest waiting for jobs in flight) and 11.8 ms in its own code;
  - 47 graphics and 68 compute jobs a frame.
- **Render sizes (run 518).** The title's dynamic resolution renders the scene at 1664×936 and
  composes at 2560×1440: it has already lowered its resolution.
- **The title's own timestamps (run 518)** spread the GPU time over many buffers, 1–3 ms each, with
  no single pass dominating. Async compute is charged about 17 ms a frame, graphics about 9.5. On
  the console async compute overlaps the graphics queue; here everything runs in order on the one
  GFX ring (ADR 0005).
- **The GPU's time line (run 520, 15 s, 53,982 jobs):**

| | |
|---|---|
| GPU had work | 10,850 ms (72.5 %) |
| idle between jobs | 4,120 ms (27.5 %) in 46,037 holes |
| holes under 50 µs | 30,421 (median hole 13.6 µs) |
| holes 50–500 µs | 14,196 |
| holes over 500 µs | 1,420, 1,374 ms (9 % of the time) |

**Verdict.**
- The start screen is limited by feeding the GPU, not by the GPU alone. The GPU waits 27.5 % of
  the time; the same work without the holes would be about 43 fps.
- Nearly every job boundary has a hole: the kernel's and the CP's per-job overhead, plus the host's
  per-submission work, about 115 times a frame.
- Next, in order:
  1. fewer submissions: merge small consecutive jobs into one CS submission;
  2. a cheaper prepare;
  3. the holes over 500 µs, probably CPU-served waits between pieces.
- Running async compute on a compute queue would be the larger change. It stays out (ADR 0005)
  until the cheaper steps are measured.
