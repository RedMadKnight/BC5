# 0209 — how long the game thread's label waits take, and what a wait limit should be

**Question.** Why 100 ms for `BC5_DIRECT_DCB_WAIT_MS` (F264, F265), and should the limit be a
constant at all? Three parts:
1. How long do the label waits take, per label and for 0x12004b3c38 (F262's machine-downs) on its
   own?
2. What do the long ones coincide with?
3. Which alternative to a fixed limit is safe on this box?

**Answer to "why 100".** It was a round number, chosen to sit well above the 4–8 ms in which most of
these waits are served and below a frame-hitch scale. It was not measured. This experiment
measures.

**Setup.**
- Offline, no GPU. One read pass over six journals on the box (19:09–19:11 under a short BOX-LOCK,
  2 s of reads, page cache warm), then analysis on the laptop.
- Journals: the four tcpW runs of experiments 0206–0208, all the same bench, shared build and
  `BC5_DIRECT_WAIT_TRACE=1`:
  - tcpW1, play-20261022-1652, 8 ms;
  - tcpW1b, -1742, 8 ms;
  - tcpW2, -1712, 100 ms;
  - tcpW2b, -1732, 100 ms.
- Also the water session's B1b (-1811) and B2 (-1825), for give-up times only (part 4).
- `extract0209.sh` keeps the wait-trace, "timing: t … after that wait", "cpu-wait" and frame-profile
  lines. Its wall-clock calibration grep failed (it missed the colon in "timing: t"); calibration was
  done instead from each extract's last frame-profile time against the journal's last-write time.
- `ana0209.py` measures the waits; `giveups0209.py` lists give-ups. Outputs are in `raw/`.

**How a wait is measured, and the limits of it.**
- A "wait trace" line is a graphics-buffer wait the game thread found unsatisfied, at time T1. The
  trace is capped at 20,000 lines a run, which here covers t ≤ 403–433 s of 600.
- The host prints "timing: t T2 s after that wait (dcb N)" whenever its CPU-side wait block ends. It
  does so also for waits satisfied at once, which are never traced.
- The game thread handles one wait at a time. So a traced wait's own line, if any, comes before the
  next traced wait, and the duration is T2 − T1.
- A traced wait without such a line ended inside the 4-ms two-ring window
  (`BC5_DIRECT_TWO_RING_WAIT_MS=4`): it was served, or kept for the GPU.
- T2 − T1 includes the host's own work on the way. When a wait misses the 4 ms, the host splits the
  buffer and submits its head before waiting again. So the longer durations are upper bounds on the
  time to service.
- A first version paired lines by buffer size alone. That matched waits to the next frame's
  same-size buffer and gave frame-period durations (~33 ms) everywhere. Corrected; the numbers
  below are from the corrected pairing.
- No sampler (swap/PSI) ran during these runs. Part 2 can use only the journal's frame profile.

**Result.**

1. **Latency per label** (`raw/tcpW*-ana.txt`). Label 0x12004b3c38:

   | Run | Limit | Waits traced | Under 4 ms | Longer | p50 / p90 / p99 / p99.9 / max of the longer, ms | Given up (in cover) |
   | --- | --- | --- | --- | --- | --- | --- |
   | tcpW1 | 8 ms | 6,697 | 6,633 (99.0 %) | 64 | 23 / 33 / 49 / 54 / 54 | 5 |
   | tcpW1b | 8 ms | 6,759 | 6,682 (98.9 %) | 77 | 24 / 33 / 66 / 101 / 101 | 5 |
   | tcpW2 | 100 ms | 6,201 | 6,078 (98.0 %) | 123 | 24 / 41 / 178 / 393 / 393 | 1 |
   | tcpW2b | 100 ms | 6,048 | 5,966 (98.6 %) | 82 | 26 / 43 / 112 / 201 / 201 | 0 |

   - Every label: 98–99 % of the traced waits end inside 4 ms.
   - Of all waits, traced and longer together: p99 33–34 ms; the largest is 653 ms (0x12004b7838
     in tcpW1b). On 0x12004b3c38 the largest is 393 ms.
   - The other labels with longer waits (0x12004b5438, 0x12004b4838, 0x12004b6038, 0x12004b4c38,
     0x12004b5838) have p50 of 23–34 ms and maxima of 36–653 ms.
   - **What the longer limit changes.** The direct count is the give-ups: 29 in the two 8-ms runs (over
     the whole 600 s) against 1 in the two 100-ms runs. Those 28 waits needed more than 8 ms of
     CPU-side waiting and at most 100 ms, all but one.
   - The count of waits whose T2 − T1 lies between 8 and 100 ms (115 and 79 on the label in the
     100-ms runs, 61 and 72 in the 8-ms runs) is not that number. It includes the host's head
     submission and occurs at both settings.

2. **What the long waits coincide with.** The waits over 50 ms (30 in all four runs, listed with
   their frame in `raw/tcpW*-ana.txt`):
   - About half fall between t ≈ 95 and 195 s. That is the bench's load from "Continue" into gameplay
     and the first play steps, before Photo Mode freezes the view.
   - Five fall in the first 10 s (start-up). The rest are scattered.
   - Their frames show three kinds:
     - the game thread long outside the host, i.e. stalled or busy in its own code (e.g. tcpW2b
       150.7 s: 141 ms outside, a 201-ms wait);
     - long GPU stretches (e.g. tcpW1 95.2 s: GPU busy 271 ms, a 348-ms wait on 0x12004b6038);
     - the wait itself dominating the frame (e.g. tcpW2 165.1 s: 199 ms in label waits).
   - With no swap/PSI sampler in these runs, the link to memory pressure is suggested by the timing
     (loading, when the APR reads and swap peak in exp 0200's samples) but not shown. The tail is a
     property of the host's state, not of the label: a label whose waits take ~1 ms 99 % of the
     time takes 100–400 ms during a stall.

3. **Alternatives to a fixed limit, and which is safe on this box.**
   - **A fixed, larger CPU-side limit** (now `BC5_DIRECT_DCB_WAIT_MS`).
     - Safe: the game thread waits at most L, and nothing changes on the GPU.
     - Cost: at most L per wait that would have been given up (12–17 per 10 min at 8 ms in these
       runs), plus true cycles, if any; the 100-ms runs had 1.
     - The observed tail on the machine-downs' label reaches 393 ms. 100 ms catches all but one wait
       in 20 minutes; ~400 ms would have caught every one seen.
   - **Per-label adaptive** (a multiple of the label's observed latency). Not recommended. The
     distributions are bimodal: ≥ 98 % under 4 ms, and a tail set by host stalls. A limit learned from
     the typical latency is short exactly when it matters, and one learned from the tail is a large
     fixed limit with more machinery.
   - **No give-up when the waiting thread cannot be the writer.** Not safe as it stands. The host
     cannot tell who writes these labels: F263 found it to be the title's CPU code or a shader. If
     the writer is the game thread itself, later in its own program order (the single-ring cycle the
     8-ms limit was introduced for, run 124), waiting without limit deadlocks the title.
   - **Keeping the wait in the GPU stream** (not dropping it after a give-up). This is the console's
     behaviour: the CP waits and the CPU goes on, so no CPU deadlock. Not safe on this box alone,
     for two reasons:
     - A wait longer than the kernel's job timeout makes the rings time out and reset. On this box
       that is ~2 s: today's kernel ring timeouts fire together with the host's 2-s fence timeouts.
       The `lockup_timeout` parameter is the default; TODO(verify) its value on this kernel. A failed
       reset ends in a MODE1 reset the board does not survive (F262, 14:50 and 16:36).
     - A ring blocked in a wait also holds all the work behind it.
     - Made safe only with a watchdog that releases the wait well before the kernel timeout. That
       reintroduces the race after the watchdog fires, and the watchdog thread itself can stall under
       memory pressure (exp 0203 O2: a 1-s stall of all threads).

**Verdict.** Answered with data.
- The 100 ms was a round number. The measurements support a CPU-side limit in the low hundreds of
  milliseconds. 100 ms catches all but ~1 wait in 20 minutes on the machine-downs' label; about
  400 ms would have caught every wait seen.
- The latency is not a property of the label but of the host's state: loading and stalls. A limit
  that follows the label's typical latency would fail exactly then.
- The safest form on this box is a bounded CPU-side wait, either as now, or applied only to labels
  with no pending GPU writer (F263's kind), keeping the short limit for the rest. The second needs a
  build and stays off by default.
- Leaving the wait to the GPU is the console's semantics, but here it exposes the 2-s kernel timeout
  and the reset that takes the box down. Not recommended without a watchdog, and even then marginal.
- The launcher default stays the maintainer's call.

4. **Side result for the water session.** Give-up times in wall-clock time for tcpW1b, B1b and B2
   (`raw/giveups-wall-tcpW1b-B1b-B2.txt`, ±2 s) against its shot series of the water's checkerboard
   flashes:
   - one of four clean→patchy onsets has a give-up 2–7 s before it (B1b 18:15:41, on 0x12004b3c38);
   - B2's first patchy shot coincides with one;
   - none of the three patchy→clean ends has one within 5 s.
   - No consistent link.
