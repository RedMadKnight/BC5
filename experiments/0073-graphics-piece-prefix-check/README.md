# 0073 — the full-state prefix checked in the running game (ADR 0008, step 1 continued)

**Question.** Experiment 0072 showed that a graphics piece needs the state that the frame's
earlier buffers set. Can a tracker that follows every graphics buffer, reading the indexed
tables from guest memory, build a prefix after which each later draw of a piece sees the same
tracked registers as in the unsplit buffer? And do the buffers set registers in ways the tracker
does not follow?

**Setup.**
- `bc5::full_state` (backend, commits 33c6e7e and 03f3112) follows:
  - the context, SH, UCONFIG and config registers;
  - `LOAD_*_REG[_INDEX]` tables and nested `INDIRECT_BUFFER`s, read through a reader;
  - the `CLEAR_STATE` push/pop stack;
  - `SET_BASE` and the `INDEX_*` and `NUM_INSTANCES` packets.
- `emit_prefix()` writes `CONTEXT_CONTROL`, `CLEAR_STATE` cmd 0, the registers in runs and the
  packet state.
- `check_split()` runs, from a split point on, the unsplit tracker and a fresh tracker that
  starts from the prefix side by side, and compares them before every draw and dispatch. The
  fresh tracker takes over the open pushes' saved contexts, as the device's state-stack
  emulation keeps its stack across submissions.
- Unit tests: `bc5_backend_tests`, 48 cases, all pass (`[full_state]`: round trip, prefix over
  foreign state, prefix through the policy filter, register runs longer than one packet, tables,
  nested buffers, push/pop across a split).
- Host: `BC5_DIRECT_PIECE_CHECK=30` (KytyPlus patch, `piece_check()` in `bc5LleAgc.cpp`) follows
  every cc/hib/dcb buffer. For every 30th graphics buffer with memory waits, it checks each
  memory `WAIT_REG_MEM[64]` as a split point. It runs on the CPU only, and what is submitted does
  not change.
- Run 316 (`run316.sh`, otherwise the same as run 315): Sky Garden from the save, 150 s, the box's
  kernel now 7.2.8-ogc5.1.
- `blindspots.py` lists the opcodes in the dumped graphics buffers that the tracker does not
  model, and register writes through `WRITE_DATA`, `COPY_DATA`, `DMA_DATA` and
  `SET_SH_REG_OFFSET`. Inputs: the 60 later-level buffers of experiment 0061 (`ibdump-262`) and 3
  of `ibdump-256`, private.

**Result.** Run 316 produced 14 reports, one every 10 s (`raw/run316-piece-check.txt`):

| | |
|---|---|
| graphics buffers followed | 62,973 |
| buffers checked | 1,174 |
| split points checked | 13,874 |
| later draws and dispatches compared | 885,445 |
| draws with a different tracked state | **0** |
| tables read / unreadable | 5.5 million / **0** |
| nested buffers | 0 |
| pushes = pops; pushes open at a split point | yes; 0 |
| tracked registers | context 921, SH 178, UCONFIG 60, config 0 |
| prefix | 1,260–1,261 dwords |
| CPU time of the check | 2.7–5.9 s per 10 s |

Blind spots (`raw/blindspots.txt`):
- The only other register write is `WRITE_DATA` to UCONFIG `0xc343`, which is
  `SQ_THREAD_TRACE_USERDATA_3` (Mesa gfx10 register JSON, vendored in `tools/bc5-agc/regdb`).
  It is a thread-trace marker, not draw state.
- There is no `COPY_DATA` or `DMA_DATA` to registers, and no `SET_SH_REG_OFFSET`.
- The remaining untracked packets do not set registers: `EVENT_WRITE`, `ACQUIRE_MEM`,
  `RELEASE_MEM`, `WRITE_DATA` to memory, `PFP_SYNC_ME`, the dispatches and draws, `COND_EXEC`,
  `ATOMIC_MEM`, `NOP`, and the waits.
- The `DMA_DATA` register-destination test is `DST_SEL` 0 with bit 27 of the command dword
  (DAS). TODO(verify) that bit against PAL's pm4 headers.

**Verdict.** Passed for its question. The state the pieces need is all set by packets the
tracker follows. With guest memory available, every table could be read. A prefix of about
1,260 dwords reproduces the tracked state at every later draw. This was outside the water (Sky
Garden start); the water's buffers are the same kind, but they were not reached in this run.

What this cannot show: the tracker compares with itself. Whether the GPU, after the prefix and
someone else's work on the ring, behaves as without the split is ADR 0008 steps 2–3. Next is
step 2: the host builds the pieces with this prefix and counts them, still without submitting
them.
