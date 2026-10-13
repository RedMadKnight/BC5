# 0062 — where ASTRO BOT's CPU time goes, with the host path at 6 ms

**Question.** Since experiment 0061 the host's direct path costs the submitting thread 5.8–6.3 ms a
frame, and the GPU is busy 15.6–15.8 ms of a 21.7–24 ms frame. What fills the rest? The
maintainer asked whether the next step should be a change to the driver the game uses, or further
work on our code.

**Setup.** Run 283 (2026-10-13), the settings of run 282:
- the ring order and the span filter of 0061;
- driven by the pad script, standing at the start of the first level.

Tools in this directory, both read-only:
- `threadsample.py`: `/proc/<pid>/task/*/stat` every millisecond, giving each thread's CPU share
  and how often it is runnable.
- `ripsample.py`: the PC of one thread at a time, via `PTRACE_SEIZE` + `PTRACE_INTERRUPT`. Only that
  thread stops, for microseconds.

`gdb` snapshots turned out to be biased. gdb stops some 150 threads one after another, and the
game's pool threads fall asleep before their turn: in 130 snapshots they almost never ran. Raw
numbers are in `raw/run283.txt`.

**Result.**

1. **The CPU is nearly full.** The load average is 14.5 on 16 hardware threads.
   - The game's eleven pool threads take 5.8 cores in user mode and 0.8 in the kernel, with 61,000
     voluntary context switches a second.
   - The main thread and the draw thread take 0.6 core each.
   - The background and physics workers take about 1.5.
2. **Much of the pool's time is waiting by spinning.** Half its samples are in a syscall (asleep).
   Of the user-mode samples, 16% sit at one PC: a counted loop of 80 `PAUSE` instructions with a
   doubling count, the job system's spin-wait for work. The main thread's hottest PC is the same
   loop.
3. **The spinning does not slow the main threads.** With the pool threads at nice +10 the frame
   rate is the same to two decimals: 46.18 fps over 30 s before and after.
4. **The two threads that matter wait half the time.**

   | Thread | in a syscall | guest code | host code |
   |---|---|---|---|
   | main thread | 50% | 48% | ~1% |
   | draw thread | 44% | 32% | 21%: our direct path, the "inside 5.8 ms" of the frame profile |

   The waits are on the game's own semaphores and condition variables, which KytyPlus implements
   on host condition variables.
5. **Frame profile here:** 21.7 ms a frame, 46 fps.
   - The draw thread spends 5.8 ms inside the host: prepare 2.9 (filter 1.5, tracker 0.8, copy
     0.4), CS ioctls 1.6, soft CP about 1.1.
   - The GPU is busy 15.8 ms.

**Verdict.** No component is saturated, so the limit is the latency of a chain:
- the main thread's frame work;
- the hand-off to the draw thread;
- our 5.8 ms inside the host on that thread;
- the GPU's 15.8 ms.

In 0061 cutting 4.5 ms of prepare shortened the frame by 2.9 ms, so most of the time on the draw
thread is on that chain.

Against the maintainer's question:
- **The game's own driver** (its `libSceAgc`, LLE) is not where the time is. It is guest code on
  the draw thread, at most the 32% that includes the game's own drawing logic. Patching it would
  also mean patching Sony binaries at run time.
- **The kernel driver** costs the 1.6 ms of CS ioctls. The GPU is busy 15.8 ms, close to the
  16.7 ms of 60 fps. The GPU-side lever, compute beside graphics, needs the kernel's compute rings,
  which take the machine down on this board (F31).

The next lever is our code: take prepare and the CS off the game's draw thread and run them on the
ring thread. This is safe only if the game reuses a command buffer after the GPU (through us)
has finished it, so that the filter may run later; TODO(verify) with a checksum of each buffer at
submission and at filtering. It would remove up to ~5 ms from the chain. At best the GPU's
15.6–15.8 ms then sets the frame, about 60 fps in both levels measured.

Not changed by this experiment: anything in the backend or the host.
