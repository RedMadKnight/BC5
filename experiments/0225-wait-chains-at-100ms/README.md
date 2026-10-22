# 0225 — at the 100-ms limit no wait is given up; the long waits are served while the thread is held

**Question.** Exp 0224 (F284) found that in 7 of 13 give-ups at the default 8-ms limit, the waited
label's writer was rung only after the give-up: the waiting thread is held. Such a wait cannot be
served by waiting longer. Yet exps 0207/0208 (F264/F265) at `BC5_DIRECT_DCB_WAIT_MS=100` left about
one give-up per run. What happens to these waits at 100 ms?

**Setup.**
- Exp 0224's binary and traces, unchanged (`~/bc5-work/exp0224/kyty_emulator`), with
  `BC5_DIRECT_DCB_WAIT_MS=100`. That means the flip trace, exp 0221's breakpoints on the four compute
  labels, and the doorbell trace.
- Run tcpW9 by `run0225.sh bench`: the lake bench, 600 s, 2026-10-22 23:07–23:17, attended, on the
  box supervisor's grant. Old launcher values pinned; `AMM_PRT` absent (`raw/tcpW9-environ.txt`).
- Risk: the bench submits to `amdgpu` as every play does (F262); the diagnostic submits nothing.
- The doorbell events are journaled only around give-ups (exp 0224's dump), so served waits have
  none.

**Result.** The full 600 s ran: 0 fault lines, 0 ring timeout or reset lines, 0 fence timeouts, same
boot, no new amdgpu line.
- **No wait was given up**: 0 "GIVEN UP" lines and 0 doorbell dumps. tcpW8, the same binary at
  8 ms, had 13.
- **22 game-thread waits were served after 4 ms or more** (`flip trace: served`, `raw/tcpW9-flip.txt`).
  They took 4.9–68.7 ms, with 7 over 25 ms.
  - They were on the same labels as tcpW8's give-ups: 0x12004b3c38 (11), 0x12004b4838 (6, all at
    t 7–23 s), 0x12004b5438 (4), 0x12004b4c38 (1).
  - At the end of 21 of them a compute job was in flight on cq1 (cq0 empty at 20). So the writer was
    submitted to the compute ring while the game thread was still held in its wait. tcpW8 had 11 such
    served waits, at most 50 ms.
- Frames in the frozen view (t 150–590 s): 29.1 flips/s, 27 seconds with a gap over 100 ms and 6
  over 250 ms. tcpW8 at 8 ms: 28.8 flips/s, 8 and 2. The longer limit trades give-ups for stalls of
  the waiting thread, as exp 0207 saw (frames over 100 ms 44 → 123).

**Verdict.**
- At 100 ms these waits end served, so their writers reached a ring while the waiting thread was
  held. That is not the "rung after the give-up" kind of F284: those cannot be served. So in this
  run, that kind did not form.
- The likely reading is that it is a product of the short limit. An 8-ms give-up lets the graphics
  buffer run ahead of its data (F263), and the title's next frames then arrive in an order where the
  writer's doorbell comes after the waiting submission. With 100 ms the order stays as the title
  meant it, and what remains is F284's other kind: a writer rung earlier and submitted late, which
  the waiting thread sits out (up to 69 ms).
- This is one run. No doorbell timing exists for served waits, so it is shown only by the outcome.
- For ADR 0013:
  - The held tail still removes these stalls: the title's thread would not sit out the 5–69 ms.
  - The consumer side (its point 10) is the one that would shorten them, and it is not in the first
    test build.
  - The A/B should run at the play settings' limit: the 8-ms code default, which the second title's
    launcher does not override. The give-ups and the frame gaps are both measured there.
