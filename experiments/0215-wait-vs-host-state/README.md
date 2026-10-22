# 0215 — the slow label waits are not host stalls: the title keeps running while they last

**Question.** The maintainer wants the game-thread wait limit to be dynamic, and asked what the long
waits depend on. The candidate rule was to count the limit in the title's CPU progress instead of
wall time: give up only after the title's threads have together run ~8 ms of CPU since the wait
began. A swap or loading stall, where they do not run, would then not cause a give-up. Does the
data support that rule, or one gated on memory pressure or major faults?

**Setup.**
- One scripted run, tcpW4, 20:14–20:24 on 2026-10-22, attended, on the box supervisor's Go.
- The run:
  - the water session's bench `bench0201.sh tcpW4 600`, from the private lake save copy;
  - the shared build as rebuilt at ~20:10, with APR read-ahead v2 on by default (the maintainer's
    policy since that evening). Frame times are therefore not like-for-like with tcpW1–W3; that
    does not matter for this question;
  - `BC5_DIRECT_WAIT_TRACE=1` and the default 8-ms limit, so give-ups occur;
  - no timeout, no fault, no new amdgpu line.
- Alongside: `hoststate.py`, a /proc-only sampler reduced from exp 0200's `sample0200.py`. It does not
  read the emulator's memory. Run at nice 5. Every 0.1 s it writes:
  - the CPU time of all the emulator's threads from `schedstat` (ns precision), split by thread name
    into the title's threads (52 of them) and host threads (bc5-*, kyty*, SDL*…, 32), with the title
    threads' R/S/D counts;
  - PSI memory/io/cpu as deltas of the cumulative `total=` counters (ms stalled per period);
  - vmstat deltas (major faults, swap-ins, compaction and allocation stalls), and available memory.
- Time base: the emulator log's line "bc5 clock: journal t 0 = monotonic 13000.833 s" maps journal
  t to the sampler's CLOCK_MONOTONIC.
- `state0215.py` takes every traced game-thread wait (from exp 0209's extraction; durations as in
  exp 0209: upper bounds for waits over 4 ms). It integrates the sampler's periods over the wait,
  and over the 500 ms before it, weighted by overlap.
- The sampler counts the title's threads only from its first thread-list refresh (journal t 7.8 s),
  so 282 earlier waits are left out.
- Committed: `raw/tcpW4-waits-vs-host-state.txt` (the analysis output), plus every 10th sampler line
  of each kind (`raw/tcpW4-title-cpu-1s.txt`, `raw/tcpW4-host-pressure-every-10th.txt`). The full
  2.5-MB sampler file stays on the box: `~/bc5-work/exp0215/hoststate-tcpW4.txt`.

**Result.** 19,366 waits ended within 4 ms ("short"), 344 took longer than 8 ms and were served
("long"), and 5 were given up (14 in the whole run).

| p10 / p50 / p90 | short (19,366) | long (344) | given up (5) |
| --- | --- | --- | --- |
| The title's CPU per wall ms during the wait (cores busy) | 0.00 / 2.51 / 4.92 | 0.77 / 1.85 / 4.10 | 2.05 / 2.83 / 4.04 |
| … in the 500 ms before | 1.94 / 2.32 / 5.00 | 0.98 / 2.21 / 3.70 | 1.92 / 2.25 / 3.48 |
| PSI memory full, ms in the 500 ms before | 0 / 68 / 143 | 0 / 0.3 / 114 | 2.9 / 30 / 125 |
| PSI io full, ms in the 500 ms before | 0.2 / 50 / 274 | 0 / 13 / 279 | 2.6 / 56 / 365 |
| Major faults in the 500 ms before | 0 / 89 / 541 | 0 / 1 / 186 | 0 / 1 / 215 |

- During the long waits the title's threads averaged 2.2 cores of CPU. Only 12 of 344 (3.5 %) were
  below 0.5 cores, and 63 below 1.0.
- During the give-ups they averaged 3.0 cores, none below 1.0.
- The longest served waits (46–139 ms) all fall in the load into gameplay (t ≈ 101–143 s), with the
  title at 1.5–3.2 cores. Some follow heavy IO stalls (186–333 ms io full in the prior 500 ms),
  others none.
- The title's threads were never seen in D state at the 0.1-s samples.

**Verdict.** The candidate rules are not supported by this run.
- **The CPU-progress rule** would cut these waits shorter, not longer. While they last, the title
  runs at ~2–3 cores, so 8 ms of its CPU passes in 3–4 ms of wall time. That would make more
  give-ups than now. It would extend only a wait during which the title stops, and such waits are
  rare here (12 of 344).
- **Gating on memory pressure or major faults** would not separate them either. The long waits and
  the give-ups come at lower memory pressure and fewer major faults than the median short wait.
- So the tail is not a host stall: the label's writer simply takes longer while the rest of the
  title keeps running, mostly during the load into gameplay. Exp 0209's link to loading stands; its
  "stalls" reading does not, in this run.
- A dynamic rule therefore needs to know the writer, which the host does not (F263: the title's CPU
  code or a shader store).
  - If it is a shader, the natural rule is "keep waiting while GPU work is in flight, give up after a
    few ms with the GPU idle and the label unwritten".
  - If it is a title thread, "keep waiting while that thread runs".
- Next: a journal-only host diagnostic, behind a switch and off by default (a build, so D16 and the
  maintainer). After each give-up it watches the label at sub-ms resolution and records when it
  flips to 0, against the GPU jobs completing and in flight at that moment. That says which writer
  it is, and so which rule.
- Until then the safest setting stays a bounded wall-clock limit. Exp 0213 shows it costs no frame
  time at 100 or 400 ms.
- One run with the read-ahead build. The 2-cores-running finding is consistent across all 349 slow
  waits, but the distribution of *when* waits are slow may differ with other builds or routes.
