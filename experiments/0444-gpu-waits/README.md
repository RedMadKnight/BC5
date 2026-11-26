# Experiment 0444: the GPU decides every cross-queue wait

Started 2026-11-22 on the top session's order, with the maintainer's word (get to work). Based on exp 0439's branch
`exp/0439-third-title` (5ab8a128), so the third title can run the build. The kernel facts and the step plan come from
exp 0443 (`exp/0443-gpu-decides-waits`, the design session "Way 3: amdkfd user queues on BC-250"); this experiment
references that document and does not copy it.

## Question

Can the host stop deciding cross-queue waits (dropping waits judged met at submit, filtering piece waits, holding
acbs, presetting labels, registering writers early, serving waits on the CPU), so that every WAIT_REG_MEM reaches
the GPU unchanged and each guest queue has its own hardware queue for the life of the run, as on the console?

Why (main's HANDOFF F898, F899, F901, F902): the third title's frame is one dcb chain of 73 to 98 pieces plus compute
buffers on at least seven guest queues. Our substitute for the console's order reads only a buffer's top level, and a
kept GPU wait deadlocked against a host hold.

## Setup (planned)

1. Inventory: every place where the host decides, drops, rewrites, serves or holds on behalf of a wait or a label
   (file:line, unit and backend), with what it stands in for and what the queue mapping must give before it can go.
2. One master switch, `BC5_DIRECT_GPU_WAITS=1` (default off), so both worlds stay testable: a fixed guest-queue to
   hardware-queue binding, every WAIT_REG_MEM passed unchanged (top level and chained pieces), none of the inventory's
   mechanisms active, and host-written labels in memory before or while a queue waits for them.
3. A title-free test first (dispatch-min over two and three rings: wait before and after the writer, a job queued
   behind a waiter on the same ring and on another, GFX waiting on compute and the reverse), each case its own unit
   behind the R60 gate, run only in the top session's slot.
4. Then the first title with the switch on (pass, lean numbers), then the third title.

## Result

(open)

## Verdict

(open)

## Test program: wait-rings (step 3)

`backend/experiments/wait-rings/main.cpp` (target `wait-rings`), modelled on `userdata-rings`: dry run by default
(builds and checks every IB with placeholder VAs, prints the plan), `--info` and `--submit` only with
`BC5_WITH_AMDGPU`. `--submit` is never run by tests, CI or scripts, and only in the top session's slot (hard rule 5).
Options: `--case NAME|ALIAS|all`, `--contexts one|separate` (default one).

Each job is one CS with one IB of blocks W (WAIT_REG_MEM "equal" on the case's label), P (the HW_ID2 probe dispatch
into the job's slot), L (WRITE_DATA of the label value) and D (WRITE_DATA of the job id to its done word); a waiter is
W P D, a writer P L D, a plain job P D; GFX jobs start with CONTEXT_CONTROL. Safety: all BOs mapped before the first
submit; fences polled with timeout 0 every 1 ms; 3000 ms after a case's last submit the CPU stores the final label
value (rescue); 6000 ms after it a job still open is STUCK: no further case, drain to 12000 ms, exit 3.

| Id | Name | Jobs | Expected on a console-like engine |
|----|------|------|-----------------------------------|
| T1 | two-b-first | writer c1, waiter c0 | waiter passes at once |
| T2 | two-a-first | waiter c0, writer c1 | waiter done after the writer |
| T3 | three-same | waiter c0, C c0, writer c2 | C done only after the writer |
| T4 | three-other | waiter c0, C c1, writer c2 after C's fence (2000 ms bound) | C done before the writer's submit |
| T5 | cpu-writes | waiter c0; the CPU writes the label 500 ms after the submit | waiter done at about 500 ms |
| T6 | writer-late | waiter c0, writer c1 submitted at 2000 ms | waiter done right after the writer |
| T7 | race | plain c0 and c1, two contexts, two threads at a latch, 1000 rounds | 0 rounds on a shared queue |
| T7b | race-locked | as T7, one mutex around each submit | 0 rounds on a shared queue |
| T8 | high-prio | 20 plain runs on c0 in an `amdgpu_cs_ctx_create2` HIGH context | one queue, never moving (SKIPPED if refused) |
| X1 | gfx-waits-compute | waiter gfx, writer c1 | waiter done after the writer |
| X2 | compute-waits-gfx | waiter c0, writer gfx | waiter done after the writer |
| X3 | same-entity | waiter c0, writer c0 | blocked, ended by the rescue |
| X4 | three-rings-pipe | waiter c0 (needs 2), writers c1 (1) and c2 (2) | waiter done after the c2 writer; HW_ID2 shows the pipes |

`--case all` runs T5 first and stops with exit 4 if it is not AS EXPECTED (every other case relies on the rescue),
then every ring case with one context, then every ring case with separate contexts, then T7, T7b and T8 once. Output
lines start with `plan`, `case`, `verdict` or `STUCK`; a verdict carries `AS EXPECTED` or `UNEXPECTED` and, when they
apply, `COLLISION` (two jobs the case expects on different hardware queues on one ME.PIPE.QUEUE) and `RESCUED`.
Exit 0 when no case is STUCK (UNEXPECTED is data), 3 on STUCK, 4 on T5's failure, 1 on a setup or submit failure.

## Box kit (prepared, not run)

`kit/` runs `wait-rings` on the box. Only in the top session's slot, on a clean boot after bake 1, one case per unit.
- **Stand-in.** `kit/standin-run444.sh` passes on the laptop (ALL PASS) in four cases:
  - clean read: the case runs and the lock is released;
  - failed read: refused (R43, exit 3);
  - a GPU line on the boot: refused (R60, exit 2);
  - a foreign lock line: refused, and the line is left untouched.
- **Ship.** From the laptop, send `git archive <commit> backend` to `~/bc5-work/exp0444/src/`, write the commit to `src/COMMIT`, and copy `kit/` to `~/bc5-work/exp0444/kit/`.
- **Build, no GPU.** `kit/build444.sh` as the unit `bc5-b444`. It builds `wait-rings` and `bc5_backend_tests` in the ubuntu distrobox (GCC, warnings as errors, BC5_WITH_AMDGPU=ON), runs the tests and the dry run, and prints the binary's md5. That md5 goes into `kit/PIN`.
- **Run.** `kit/run444.sh <case> [one|separate]` as the unit `bc5-w444-<case>` (RuntimeMaxSec=120):
  1. the R60/R43 gate;
  2. the binary checked against PIN;
  3. no emulator running;
  4. BOX-LOCK claimed by hard link;
  5. `wait-rings --submit --case <case> --contexts <x>`;
  6. the gate again, which reports any new kernel line and closes the boot (R60).

  Logs go to `~/bc5-work/exp0444/runs/<time>-<case>-<x>.txt`.
- **Order.** T5 alone first; nothing else runs in the slot unless T5 is AS EXPECTED (exp 0443's caveat: every other case relies on the CPU rescue). Then:
  1. T1, T2, T3 and T4, each with one context and then with separate contexts;
  2. T6;
  3. gfx-waits-compute and compute-waits-gfx;
  4. three-rings-pipe;
  5. T7 and T7b;
  6. T8;
  7. same-entity, last, because its block is by design: the rescue ends it at 3 s, under the 10-s job timeout.

  A STUCK case or a new kernel line ends the slot.
