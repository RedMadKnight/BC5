# 0027 — `prepare`: the host's pass over the main command buffer

**Question.** The game's thread spends 4.0–4.6 ms of a second-level frame in `prepare` (HANDOFF
F65): the policy filter over a 25,000–34,000-dword main buffer, the state-stack tracker, the
CU-mask tables, the nested-buffer survey and filters, the copy into the scratch, and the second
pass that re-points `INDIRECT_BUFFER` packets. Which of these is the time, and what can go without
changing a dword the GPU executes?

**Setup, step 1 (offline, no GPU).** `backend/experiments/prepare-bench`: the steps of
`Device::submit` before the CS ioctl, timed one by one over raw command buffers dumped by the host
(`BC5_GC_DUMP_DIR` with the full journal, map-only run `kytyplus-20261006-1911`: 1,099 main
buffers of the title screen, up to 9,891 dwords — the second level's buffers are three times
longer and were not dumped; a dump there needs a GPU run with the full journal). Nested targets
and tables are not available offline, so `mapped()` answers "no" (`--no-mapped`); with "yes" the
tracker would read guest memory that is not there.

| Buffer | dwords | filter | offsets | tracker | cu | copy (cached) | re-point | total |
|---|---|---|---|---|---|---|---|---|
| 000148-dcb | 9,891 | 0.061 ms | 0.006 | 0.016 | 0.001 | 0.001 | 0.019 | 0.104 |
| 000174-dcb | 9,774 | 0.060 | 0.005 | 0.016 | 0.001 | 0.001 | 0.018 | 0.101 |

0.1 ms for 10,000 dwords, 0.3 ms scaled to a second-level buffer: **the walk is not the 4 ms.**
What the benchmark cannot reproduce is where the rest is, and the code says where to look:

1. every scan after the filter read the **uncached scratch** (`MTYPE_UC`, F25): `executed_offsets_of`
   compares source and destination packet by packet, the re-point pass walks every destination
   header, `has_draw_or_dispatch` walks it again — thousands of uncached reads per submission;
2. the filter asks `mapped()` for every memory operand, and the host answered with a **linear walk
   over ~340 mappings** per operand;
3. the nested buffers (the compute rings' targets) are filtered straight into the scratch and
   scanned there the same way.

**Change (2026-10-06, before any GPU run).** (a) `Device::submit` assembles and scans the whole
image — prologue, filtered IB, nested copies, re-pointed packets — in a cached buffer kept in the
device and copies it into the scratch once, sequentially; nothing reads the scratch back. (b) The
host's per-submission mapping list is sorted by address and `mapped()` is a binary search. Neither
changes the bytes the GPU executes: (a) moves the same stores, (b) answers the same question.

**Result.** Pending: a GPU run of run 125's scene with `BC5_DIRECT_FRAME_PROFILE=1`, `prepare`
against run 125's 4.0–4.6 ms. Map-only, the build runs as before (28 flips in 60 s).

**Verdict.** Open until the GPU run. Not touched, as ADR 0005 (vii) and F25 require: the scratch's
memory type and its VA allocation.
