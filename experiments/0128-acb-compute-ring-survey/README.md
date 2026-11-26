# 0128 — The second title's compute buffers hold nothing a compute ring would refuse

**Question.** ADR 0009 sends the title's asynchronous compute buffers to a kernel compute ring
and keeps a buffer on the GFX ring when it holds:
- a graphics-only packet;
- a GFX-form `DISPATCH_INDIRECT`;
- a dispatch with `PARTIAL_TG_EN` set and `USE_THREAD_DIMENSIONS` clear (mesa#16054).

How many of the title's buffers would that keep back, and what else do they use?

**Setup.**
- Offline, no GPU.
- `acbscan.py` reads the dumped compute buffers (`ib-*-acb-*.bin`, top level only). It applies
  the rules of `bc5::policy::compute_ring_refusal` (commit c45e123).
- Inputs (private):
  - `~/bc5-data/captures/ibdump-372`: the intro, experiment 0103;
  - `ibdump-377`: the menu, experiment 0104.
- The start screen after New Game has no dump yet.
- A second pass counted three more things: the `SET_UCONFIG_REG` registers, the `EVENT_WRITE`
  and `RELEASE_MEM` events, and the `DMA_DATA` selects.
- Raw: `raw/acbscan.txt`.

**Result.**
- 440 buffers, 0 refused.
- **Dispatches:** 10,974 `DISPATCH_DIRECT` and 8,817 `DISPATCH_INDIRECT`, all of them in the
  4-dword MEC form.
- **Initiators** (`COMPUTE_DISPATCH_INITIATOR` bit layout from Mesa
  `src/amd/registers/gfx10.json`, commit 0866ae7):

  | initiator | count |
  |---|---|
  | 0x61 (`COMPUTE_SHADER_EN`, `USE_THREAD_DIMENSIONS`, `ORDER_MODE`) | 16,328 |
  | 0x41 | 2,850 |
  | 0x8041 | 421 |
  | 0x8061 | 192 |

  None sets `PARTIAL_TG_EN`.
- **Opcodes:** `SET_SH_REG`, `SET_UCONFIG_REG`, `DISPATCH_*`, `ACQUIRE_MEM`, `RELEASE_MEM`,
  `EVENT_WRITE`, `DMA_DATA`, `WRITE_DATA` and `WAIT_REG_MEM64`. There are no `SET_BASE`,
  `CONTEXT_CONTROL` or context registers.
- **The details:**
  - `SET_UCONFIG_REG`: only `SQ_THREAD_TRACE_USERDATA_2/3`. These are markers, which the policy
    drops anyway.
  - `EVENT_WRITE`: only type 7 / index 4 (`CS_PARTIAL_FLUSH`).
  - `RELEASE_MEM`: only `BOTTOM_OF_PIPE_TS` / index 5, with `DATA_SEL` 2 or 3. CS_DONE does not
    occur.
  - `DMA_DATA`, all 329 without `CP_SYNC`:
    - 47 fills of GDS;
    - 203 GDS-to-memory copies;
    - 79 memory-to-memory copies.

**Verdict.**
- On these dumps the compute-ring policy keeps every compute buffer on the compute ring. The
  buffers are MEC streams as they are, which is what the console runs them as.
- The GFX-ring rewrites that go away on a compute ring are the MEC_INDIRECT rebuild and the
  `PFP_SYNC_ME`.
- What the ladder (ADR 0009 step 2) still has to show on the BC-250's MEC:
  - **GDS through the CP**, since 250 of the copies touch GDS. TODO(verify): does the kernel
    program a GDS partition for compute-ring jobs?
  - `COND_WRITE` / `COND_EXEC`, used by the indirect-count check.
  - `RELEASE_MEM` `BOTTOM_OF_PIPE_TS` with `DATA_SEL` 3, as in the job timestamps.
  - A wait on a label written from the GFX ring.
  - Overlap with a GFX job.
- The start screen's buffers are worth the same count once they are dumped.
