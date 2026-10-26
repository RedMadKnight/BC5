# 0334 — F399's freeze: the BVH compaction, the ring split, or the build's own work?

*Number claimed by the cloud supervisor, 2026-10-26 16:54, in the maintainer's autonomous window. A design written offline
from the repo and the host source (exp 0330's 29664e3c); not built, not run. Every arm needs his yes.*

**Question.** *(Design, 2026-10-26: not built, not run; no arm needs a build.)* With RT on, the second title freezes
at one spot in the maintainer's play (F399): a GFX-ring timeout on an acb/dcb pair, recovered by a ring reset. With RT
off, 35 minutes ran with no freeze (F400). Which RT-only work causes it: the BVH compaction (on with RT since exp
0323), the BVH build split between the compute and GFX rings, or the stuck acb's own work? Which single switch removes
the freeze at the spot?

**Known before this experiment.**
- **The freezes.** Four `gfx_0.0.0` timeouts (10:08:45, 12:20:11, 12:21:44, 12:21:46), each with two jobs unsignaled
  and a successful reset. No compute-ring timeout and no fault line (exps 0330/0331 `raw/maintainer-test/kernel.txt`).
  The host timed out the acb and the dcb behind it after ~2 s (F399).
- **The spot comes right after a load.** At 12:21:44 the emulator had run 66 s and GTT was still rising (exp 0331
  `raw/maintainer-test/mem-20261026-122037.txt`). TODO(verify): the journal's load lines.
- **Ring choice.** `job_ring()` puts every kind except "acb" on the GFX ring, so dcbs always go there (bc5LleAgc.cpp
  (exp 0330's 29664e3c) :3155–3157). `acb_ring()` (:3145–3154, called at :5849, :3206 and :3280) first reads
  `BC5_DIRECT_COMPUTE_RING` (unset = GFX, :3104–3110; the launchers set 0). It then asks
  `bc5::policy::compute_ring_refusal()`. A refused acb gets the GFX ring, and every 1,024th is journaled (:3151–3152).
- **The refusal (exp 0290).** `kMecIndirectCheckVerified = false` makes any DISPATCH_INDIRECT refuse the whole buffer
  (backend/src/policy.cpp:214, :241), as do graphics-only packets and PARTIAL_TG_EN (:229–234). The host passes no
  `mapped` callback (:3149), so IB targets are not followed (policy.cpp:242). The refused acb is neither moved elsewhere
  nor split: it runs whole as its own GFX-ring job, in submission order with the dcbs (a chain closes on a change of ring
  or kind, :3748). Its compute-form indirect dispatches are rebuilt into GFX form (`MEC_INDIRECT=1`, F334; :8015–8030)
  and get the CP's argument check there (F106, :7694–7701). It moves ~29 % of compute jobs (F356); shared since F388.
- **Ring deps.** `BC5_DIRECT_RING_DEPS`: acb → 1, dcb → 2, any other value (even "0") → 3, both (:1246–1256, set at
  :1318 and :5964). Bit 0: a compute-ring job waits for the GFX ring's last job; bit 1: a GFX-ring job waits for every
  compute ring's last job; a kernel CS dependency, no CPU wait (backend/src/direct.cpp:1193–1205). So the launchers'
  `=dcb` (F388) puts the refused acb and every dcb after the compute jobs submitted before them, but holds back no
  compute job submitted after the refused acb (`=both` does). The dcb waits for the acb in ring order.
- **The stuck acb** is F332's "Ray Tracing Update" chain. Its first half is the count pass 0x909939400, the leaf
  builder 0x909936c00 (its argument triples read as floats, as in F371/F373), 0x909939700 and the refit 0x909939900.
  Then a "PSR_BVHL" header write lands, and ~20 programs follow, 0x90985f200 … 0x9098eb200 (exp 0138 names three of
  them as instance-table writers). The acb's end write to 0x12004b5038 never landed. The dcb waits for that label at
  dword 1781 (exp 0331 `raw/maintainer-test/probe-1220.txt`). The probe's ran/DROPPED marks are void for a rebuilt acb
  (F334), so the stuck dispatch has no name.
- **The dcb's wait at dword 1640** follows its own WRITE_DATA 0 and end-of-pipe release of 1 (F360's sync). Two
  freezes read 0 there, so the dcb's head may have run, its release waiting for the acb's waves (12:20:11 read
  0xffffffff). TODO(verify) with the devcoredump.
- **The CP check limits each dimension** (2^20, 2^10, 2^10; backend/include/bc5/policy.hpp:110), not the product
  (indirect_check.hpp). The second half's triples read at the timeout would pass it, such as 818 × 820 × 819
  (0x90992af00). TODO(verify): what the CP read when it dispatched.
- **RT off drops only the ten-program list** (:7945–7997, F343): the compaction 0x909974400, the chain's first half,
  and the second tree family. The host's switch does nothing else (:304, :7955). So the acb's second half still runs
  with RT off (TODO(verify) in the 14:31 journal), and `SKIP_PGM` with RT on equals `RT_BUILD_PGM` with RT off.
- **The compaction** runs with RT on again since exp 0323 (F388). It is a load-time burst (F304). With it on and no
  ordering, S6N's route hung the F332 way, with the leaf builder's float arguments (F371, F373) written by the title's
  load-time memcpy (F377, F381). The ordering cleared S6N 9 × 600 s (F388), a route that never reached this spot.
- **Switches.** None acts on this pair alone. The narrowest for this acb is `BC5_DIRECT_MEC_SKIP_PGM` (compute-form
  indirect dispatches in acbs, :8015). `SKIP_PGM` covers every buffer (:7931–7943); `DROP_AT` one dcb size (:7905–7927);
  `COMPUTE_RING=-1` puts all on one ring (F384); `LOOP_BOUND` and `BVH_MISS` act on traversals only.

**Setup (proposed).**
- **R0.** Read-only on the box behind the guard, while he is not playing; nothing copied off, register values quoted.
- **GPU arms** use the binary that froze, behind the test-0330 shortcut (exp 0330's, tree 29664e3c, the shared mount
  since F398). Each runs a derived copy of its launcher with only the arm's lines changed, since that launcher sets
  `RING_DEPS=dcb` itself (exp 0323; TODO(verify) which lines inherit). Private working directory and input configuration,
  its RayTracing line on (off for B), which overrides `KYTY_BC5_RT` (:298–302). The live saves are compared only.
- **The route.** Preferred: a private copy of the slot he loaded at 12:20, driven by `KYTY_BC5_INPUT_CMD` (start
  screen, slot list, Continue; keys at ~90 s). Stop 120 s after Continue, or 10 s after the first TIMEOUT so the probe
  can write. If A does not freeze in two runs, the route misses the spot and the arms move to his play on a test
  shortcut. His 14:31 RT-off session may have saved past the spot (F400), so he names the copy that still stands there.
- **The runs.** Two per arm unless one freezes; ~3–4 min each, ~40 min of box time. The kernel stream goes to a
  session file and ends itself. Wait a minute after a freeze; after each run check that the launcher and bc5-mount are
  gone. Order: R0, A, B, C, D, then E or F.

**Arms.**

| arm | where | switches (on top of the shortcut's) | GPU risk |
|---|---|---|---|
| R0 | box, read-only | none: devcd1–4, the six `ib-timeout-*.bin` (bc5-agc), the 0958/1216/1220/14:31 journals, the launcher | none |
| A | private copy, or his play | none, RT on | the freeze: a GFX timeout, recovered 4/4 here; one failed reset in eight (MODE1) under the refusal (F358) |
| B | same | RT off in the private configuration | low: RT off ran 35 min (F400) and 63 min (F351) clean |
| C | same | RT on, `BC5_DIRECT_SKIP_PGM=909974400` (the default before exp 0323) | low–medium: the play setting until 10-25; the lab's reflections go white (F370) |
| D | same | RT on, `BC5_DIRECT_COMPUTE_RING=-1` | medium: may freeze; no compute ring is used, so no compute reset (F384); ~11 % fewer flips |
| E | same, only if D passes | RT on, `BC5_DIRECT_RING_DEPS=both` | medium: may freeze; compute jobs queue behind a hung GFX job, TODO(verify) at the reset |
| F | same, only if C and D freeze | RT on; F1 `BC5_DIRECT_MEC_SKIP_PGM=909936c00,909939900`, F2 the second family by `SKIP_PGM` | medium–high: part-built trees; F338 (four chain programs dropped) stopped on a stray write; a skip once took the machine down (exp 0059 run 273) |

**Rules.**
- A freezes and B passes: the route reaches the spot, and the spot needs RT.
- C passes twice: the compaction is the condition (why its load burst still breaks the chain is F373's open writer).
  The interim for his RT-on play would be the skip, a yes of its own.
- C freezes, D passes: a gap between the rings remains; E shows whether it is the one `=dcb` leaves.
- C and D freeze: the cause is in the GFX-ring work itself (the chain's order or data); F1 tests the leaf builder's
  output. A fix then needs a build (a product limit in the CP check, or a flush before the leaf builder's argument
  fetch; F364's per-dispatch flush failed on S6N without the ordering), a new ask.

**Readings.**
- **Kernel.** `ring gfx_0.0.0 timeout, signaled seq … emitted seq …` and its thread; `reset succeeded|failed` and
  MODE1; any `[gfxhub]` fault or `comp_1.x.0` timeout; the `bc5-devcoredump` line and the new file.
- **Journal.** `TIMEOUT` lines (kinds and sizes against F399's pair); the probe's header and end-label writes; the
  refusal counter (0 in D) and the `compute ring:` lines; the `skip pgm` and RT-off drop lines; the `gpu check` counter.
- **Each run.** fdinfo ~30 s after Continue (drm-engine-compute absent in D only); the seconds from Continue to the
  freeze; flips per 10 s; the live-save checksum at the start and at the end.
- **R0, the devcoredumps.** Precedents: exp 0290's devcd4, F339, F360. TODO(verify) every field's meaning and this
  kernel's gfx10 register list.
  - `CP_IB1_BASE` with `CP_IB1_CMD_BUFSZ` − `CP_IB1_BUFSZ` (and `CP_IB2_*`): the host IB the CP stood in, the acb's
    or the dcb's, and how far it had fetched. The gfx ring's rptr/wptr and INDIRECT_BUFFER entries against the two seqs.
  - `CP_PFP_HEADER_DUMP` and `CP_ME_HEADER_DUMP`: each parser's last packet. `CP_STALLED_STAT1–3`, `CP_CPF_STATUS`,
    `CP_CPF_BUSY_STAT`: what the CP waited for. The VM_L2 and UTCL1 status words: a silent retry.
  - `GRBM_STATUS` and `_SE0–3`: busy means waves alive in a dispatch that does not end; idle means a CP wait.
  - One position in all four dumps means a deterministic stop; devcd4 shows what ran after the first reset. Not
    expected in the dump: wave PCs, IB contents, `COMPUTE_PGM_LO/HI`.
- **R0, the other files.** In the `ib-timeout-*.bin`: any CS_PARTIAL_FLUSH or ACQUIRE_MEM between the count pass and
  the leaf builder's first indirect dispatch, whether the filter kept it, and the acb's 4–5 drops. In the journals:
  whether 0x909974400 ran just before each TIMEOUT (cs-prefix lines, F371). In the 14:31 journal: whether the second
  half ran. In the launcher: the `GPU_CHECK` and `RT_BUILD_PGM` lines.

**Needs the maintainer's yes:**
1. R0: a read-only look at his devcoredumps, probe dumps and journals on the box, while he is not playing.
2. A private copy of the slot he loaded at 12:20, if it still stands at the spot; otherwise his play on a test shortcut.
3. Arms A and B together (A can freeze the GPU; B is the RT-off control).
4. Arm C: the compaction skipped, with RT on.
5. Arm D: every compute buffer on the GFX ring, with RT on.
6. Arm E or arm F, chosen by C and D (one yes each).
7. Any follow-up that needs a build (a product limit in the CP check, or a flush before the leaf builder).

**Result (arm R0, 2026-10-26 17:00–17:09).** The arm ran in the maintainer's autonomous window. His words were
"samodzielnie działaj i podejmuj decyzję przez ok. 1,5h", then "Jeszcze 30 minut beze mnie - może być dłużej jak ci
się przedłuży" (BOX-QUEUE 180).
- **What was read:** the five devcoredumps of 10-26, read on the box with awk and grep. Only register values and the
  IB header lines (address and size) left it (`raw/r0-registers.txt`); no IB or ring contents.
- **How it was decoded:** register fields with Mesa's `gfx10.json` and packet opcodes with `pm4-opcodes.tsv`. Both
  are vendored in `tools/bc5-agc/regdb/`, from Mesa `fe554882`.

| dump | time | ring timed out | host IB (CP_IB1) | IB1 left to fetch | VM fault |
|---|---|---|---|---|---|
| devcd1 | 10:08:46 | gfx_0.0.0 | 0x1015_00000000, 28,760 dw | 0 | none (address 0, status 0) |
| devcd2 | 12:20:11 | gfx_0.0.0 | 0x100c_00000000, 27,592 dw | 1,544 | none |
| devcd3 | 12:21:44 | gfx_0.0.0 | 0x1012_00000000, 5,736 dw | 680 | none |
| devcd4 | 12:21:46 | gfx_0.0.0 | 0x1015_00000000, 3,008 dw | 608 | none |
| devcd5 | 00:01:52 (the night) | comp_1.2.0 | 0x1020_00000000, 872 dw | 0 | write, 0xa8256950000, status 0x00541051 |

- **The three first timeouts (devcd1–3) stop the CP in the same state.**
  - The same PFP and ME microcode positions: `CP_PFP_INSTR_PNTR` 0xea0–0xea1 and `CP_ME_INSTR_PNTR` 0x77a–0x77b.
  - The same eight-entry history in `CP_PFP_HEADER_DUMP`: `ACQUIRE_MEM`, `EVENT_WRITE`, `COND_WRITE` (twice),
    `COND_EXEC`, `PFP_SYNC_ME`, `WRITE_DATA` and `DISPATCH_INDIRECT`. That is the host's GFX-form indirect dispatch with
    its CP argument check (F106, F334).
  - `CP_ME_HEADER_DUMP` ends in the same packets, `DISPATCH_INDIRECT` among them.
  - The same busy units:
    - `GRBM_STATUS` 0xa0407028: SPI_BUSY, TA_BUSY, CP_BUSY and GUI_ACTIVE, with CB and DB clean;
    - `GRBM_STATUS_SE0` and `SE1` 0x0a000036 (devcd1) or 0x0a000016: SPI, TA, TCP and GL1CC busy;
    - `GRBM_STATUS3`: GL2CC busy;
    - `CP_CPF_STALLED_STAT1`: RING and INDR1 fetching data.
  - **So shader waves were still running a compute dispatch the CP had issued through `DISPATCH_INDIRECT`,** and no
    page fault was recorded. This is a dispatch that does not end within the 2-s fence wait. It is neither a CP wait
    on a label nor a missing page.
  - The IB1 counters (`IB1_BUFSZ` of `IB1_CMD_REQSZ`) put the CP's fetch in the last 0–12% of the host IB. That fits
    the probe's reading of the BVH build's second half. TODO(verify): that `CP_IB1_BUFSZ` counts the dwords still to
    fetch, and that fetch runs ahead of execution.
- **The second timeout of the 12:21 freeze (devcd4, 2 s after the first reset) is a different state.**
  - SPI and TA are idle, and SE0 shows only CB/DB clean. The CP and EA are busy.
  - The PFP history holds `RELEASE_MEM`, the unknown opcode 0x93 and a type-3 `NOP` header 0xffff1000.
  - So no waves ran: the CP waited. That fits a GFX-ring job waiting for a label the reset-killed acb never wrote
    (F399's 0x12004b5038). TODO(verify) against that session's journal.
- **This supports the design's dimension-product lead.**
  - The CP check bounds each dimension (2^20, 2^10, 2^10; policy.hpp:110), not their product.
  - A triple such as 818 × 820 × 819 (549 M workgroups) passes the check and can run far longer than the 2-s wait.
    TODO(verify) for this program.
  - The dumps cannot name the program or read its arguments: they hold no wave PCs or `COMPUTE_PGM_*`.
- **New, about the night's machine-down (devcd5, RT off, the lean build):** the compute ring 1.2.0
  timed out with a recorded gfxhub fault.
  - The access was a write (RW = 1) at 0xa8256950000.
  - The fault status was PERMISSION_FAULTS 0x5, MAPPING_ERROR 0, VMID 5 and CID 0x8, with MORE_FAULTS set.
  - The address lies far above the direct-memory views (up to ~0x859b8a0000, exp 0330's breakdown). TODO(verify) what
    is mapped there.
  - The lean build wrote no journal, so the job is unknown. This is a GPU write fault, not only the memory shortage
    the maintainer named.

**Verdict (R0 only).**
- F399's freeze is a compute dispatch that does not end, issued by a GFX-form `DISPATCH_INDIRECT` in the refused acb.
  It is the same state in all three freezes, with no page fault.
- The next arms stand as designed:
  - C, skipping the compaction, tests the load-time cause;
  - a product limit in the CP check (a build) tests the runaway grid directly.
- Each still needs the maintainer's yes, with RT on.
- devcd5 is a separate lead: a GPU write fault on a compute ring in the night's machine-down.

**Correction (2026-10-26 17:12, the kernel log of the night's boot).** The devcoredump's "Page fault observed" section
is the driver's last recorded fault, not the fault of the timeout it dumps. The kernel log of boot −2 (10-25 16:07 to
10-26 00:01:52) shows where devcd5's fault came from:
- the fault at 0xa8256950000 (status 0x00541051, `Faulty UTCL2 client ID: TCP (0x8)`, vmid 5, pasid 77) was logged at
  **10-25 20:56:06**, among eleven TCP faults of that evening's hang (10-25's devcd4);
- the night's `ring comp_1.2.0 timeout` at 00:01:52 has no fault line.

So the night's machine-down has **no recorded GPU fault**, and the R0 bullet "New, about the night's machine-down" and
the last Verdict bullet are withdrawn. devcd1–4 stand as read: the kernel log of the current boot (from 10-26 00:03:16)
has no page-fault line at all, so their empty fault record (address 0, status 0) means no fault in this boot.

