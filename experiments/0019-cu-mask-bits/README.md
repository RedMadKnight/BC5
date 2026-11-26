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

*The CU-bound program* (`alu-probe.s`, 15:23–15:27, with the maintainer's go-ahead;
`raw/alu-probe.txt`): 4 MiB, 4,096 thread groups of 64 threads, 4,096 loop iterations each, all
1,048,576 dwords right in every run. Times are stable to the microsecond within a run of 8–16
(a drift of 5–10 % between batches, one transient outlier re-measured). With "unit" = the rate of
one bit set in every register (53.54 ms):

| mask (all four registers) | time | units |
|---|---|---|
| 0x00000001 / 0x00010000 | 53.54 / 53.53 ms | 1 / 1 |
| 0x00010001 | 26.82 ms | 2 |
| bit 0 + bit k of the low half, k = 1…15 (0x00000401: 26.81 ms) | | 2 |
| 0x00080001 (bit 19) | 26.81 ms | 2 |
| 0x00100001, 0x80000001, 0xfff00001 (bits 20–31) | 53.55, 53.54, 53.53 ms | **1 — nothing added** |
| 0x000f0000 (bits 16–19) | 13.44 ms | 4 |
| 0xffff0000 (bits 16–31) | 13.45 ms | 4 |
| 0x000003ff (bits 0–9) | 5.45 ms | 9.8 |
| 0x0000ffff (bits 0–15) | 3.42 ms | 15.7 |
| 0x0003ffff (bits 0–17) | 3.10 ms | 17.3 |
| 0x000fffff (bits 0–19) | 2.79 ms | 19.2 |
| 0xffffffff | 2.80 ms | 19.2 |

- **Bits 0–19 of each `COMPUTE_STATIC_THREAD_MGMT_SEn` are live, one execution unit per bit;
  bits 20–31 do nothing**, alone or on top of the others (0x000fffff = 0xffffffff).
- A unit is one bit in both shader engines' registers, i.e. two CUs: 20 bits × 2 engines = the
  40 CUs the board routes (F14). The register is not two 16-bit fields of ten CUs each, as the
  generic layout (and experiment 0016's "36 = 0x01ff01ff") assumed; whether the two arrays of
  an engine sit at bits 0–9 and 10–19 or elsewhere cannot be told from throughput and does not
  matter for a mask.
- Throughput is linear in the bit count within the measurement's drift (10 bits 9.8 units, 16
  bits 15.7, 18 bits 17.3, 20 bits 19.2).
- The memory-bound program's "bits 4–15 add less than bits 1–3" was its own artefact: with both
  16-bit halves given the same bit, bits 4–15 of the upper half are bits 20–31 — dead.

**Verdict (2026-10-01, 15:30).** Answered for compute: 40 CUs = bits 0–19 of the two
shader-engine registers; **a 36-CU compute mask is 0x0003ffff** (or any 18 of the 20 bits), and
it costs what it should (3.10 ms against 2.79 ms, 11 %). For the graphics stages the mask is
`SPI_SHADER_PGM_RSRC3_*.CU_EN`, a 16-bit field: experiment 0016's frame series showed its bits
10–15 live as well, so it reaches at most 16 of an engine's 20 CUs if it maps onto the same
bits — which CUs a 16-bit `CU_EN` selects is the remaining question, and it needs a CU-bound
draw. The 0x01ff01ff / 0x03ff03ff rows of experiment 0016 were not 36 and 40 CUs but 26 and 28.
