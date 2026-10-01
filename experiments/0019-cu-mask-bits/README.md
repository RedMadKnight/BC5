# 0019 — Which CU-mask bits carry execution units on the BC-250 (Q8, F39)

**Question.** Experiment 0016 (runs 82–88) found that the game's frame gets faster with every
CU-mask bit up to 16 per shader array, although the kernel counts 10 CUs per array. Which bits of
`COMPUTE_STATIC_THREAD_MGMT_SEn` are backed by something that executes?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`; `bc250-cu-live-manager status`:
10/10 CUs routed in each of the four shader arrays. `dispatch-min --submit --console --bytes
268435456 --repeat 12 --cu-mask <hex>` (new options: the mask goes into all four
`COMPUTE_STATIC_THREAD_MGMT_SE` registers; each run is timed from the submit to its fence): the
ADR 0004 buffer-clear program over 256 MiB, 262,144 thread groups. Masks: bit 0 of both 16-bit
halves alone, bit 0 plus one further bit k (never a mask without bit 0, so that some unit always
runs), then cumulative masks. Raw output: `raw/cu-bit-probe.txt`.

**Result.** Medians, submit to fence:

| mask (both halves) | time |
|---|---|
| bit 0 | 1.313 ms |
| bit 0 + bit 1 / 2 / 3 | 0.733 / 0.720 / 0.699 ms |
| bit 0 + bit k, k = 4 … 15 | 0.802 – 0.813 ms, every one of them |
| 0x0003 | 0.702 ms |
| 0x000f | 0.652 ms |
| 0x003f, 0x00ff, 0x03ff, 0x0fff, 0xffff | 0.642 – 0.644 ms |
| low half only (0x0000ffff) | 0.642 ms |
| high half only (0xffff0000) | 0.713 ms |

- **No bit is dead.** Each of bits 1–15 added to bit 0 shortens the run by 39–47 %; a bit
  without a unit behind it would leave it at 1.31 ms.
- Bits 1–3 add more than bits 4–15 (0.70–0.73 ms against 0.80–0.81 ms).
- The program is bound by memory, not by CUs, beyond four bits per half (256 MiB in 0.64 ms),
  so the cumulative masks say nothing about how much each further bit is worth; the two halves
  of the register are not equivalent either.
- All values verified: 0 of 67,108,864 dwords wrong in every run.

**Verdict.** Partly answered: all sixteen bits per half are live on this board, so a "36 of 40"
mask cannot be read off the bit positions (F39 stands). How much each bit is worth needs a
CU-bound program; one is assembled (`alu-probe.s` next to this file: the same program with a
4,096-iteration integer loop per thread, built with `llvm-mc -arch=amdgcn -mcpu=gfx1013`, whose
encodings of the shared instructions match the IGT program's dwords) and waits for the
maintainer's go-ahead, being new code on the GPU.
