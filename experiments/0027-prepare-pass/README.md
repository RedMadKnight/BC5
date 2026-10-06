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

**Result, run 126** (the same scene as run 125, the maintainer at the controller, 424 s until the
controller's USB link failed): `prepare` 2.9–4.1 ms a frame in the second level against 4.0–4.6
in run 125, the frame 20.7–23.7 ms against 21.4–24.1 — a gain of about a millisecond, not the four.
The walk is cheap offline and the scratch reads are gone, so the rest is in what the benchmark
cannot run: the tracker following `LOAD_CONTEXT_REG` tables and expanding pops, and the nested
buffers' survey and filters. The device now times those parts separately (`SubmitResult::prep_*`,
in the frame profile line); the next run says which.

**Result, run 127** (the parts timed inside the device, per frame, the second level): filter
2.4–3.1 ms, tracker 0.5–0.6, copy 0.3, nested 0.1, CU tables 0. Offline the same filter takes
0.07 ms per 10,000 dwords with `mapped()` answering yes (`--filter-only`), 0.06 answering no. A
frame's nine game-thread submissions are about 130,000 dwords (a 25,000–34,000-dword main buffer,
an 85,000–90,000-dword second one, a few small ones), so 0.9 ms is what the bench predicts and
2.4–3.1 is what the game pays: three times, not forty — the buffers the game has just written are
not in the host's cache the way a benchmark's are, and every operand goes through a `std::function`.

**Verdict (2026-10-06).** The pass is where it should be, give or take a factor of three, and that
factor is the remaining lever here: a cheaper `mapped()` (a bitmap over the guest address space
instead of a callback and a bisection), and a filter that does not re-walk the 90,000-dword buffer
when it is the same one as last frame. Both are small against a frame that is 17–18 ms of GPU
time. Not touched, as ADR 0005 (vii) and F25 require: the scratch's memory type and its VA
allocation.
