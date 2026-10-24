# 0279 — the 19:57 stray write with RT off: where the GFX CP stood

**Question.** At 19:47 on 2026-10-24 the maintainer played the second title on exp 0278's binary cd17ab79 with ray
tracing off. "Off" drops the "Ray Tracing Update" build chain (0x909939400, 0x909936c00, 0x909939700, 0x909939900),
and BC5_DIRECT_SKIP_PGM drops the compaction 0x909974400.

After about 10 clean minutes at ~48 flips/s (F338), at 19:57:27 the box logged a TCP **write** permission fault:
- page 0x1474260000;
- RW 1, PERMISSION_FAULTS 0x5, status 0x00741051, vmid 7, pasid 113, MORE_FAULTS (W266a's signature).

Then dcb #841748 and acb #841756 timed out, and the devcoredump devcd3 was saved.

This experiment asks three things:
- Is it F322's pair again?
- Where did the GFX CP stand?
- What can the dumps say about the writer?

**Setup.** One read-only copy at 19:59–20:00 on the box supervisor's GO, scp only, with no emulator running. The files
went to the tcp session's scratchpad and are **not committed**, because they hold the title's command buffers:
- `~/bc5-data/captures/play-20261024-1947/gc/direct.log`: lines 2,180,000 to its end (2,212,840) of the 217 MB
  journal, plus a grep of its key lines (gpu check, ray tracing, learned, fault, TIMEOUT, scratch window);
- `ib-timeout-00841748-dcb-37814.bin` and `ib-timeout-00841756-acb-865.bin`, each with its `.tfring.bin`;
- `~/bc5-data/captures/devcoredump/20261024-195730-devcd3.txt`.

Analysed offline. Committed, derived text only:
- `raw/journal-lines.txt`: the TIMEOUT, probe count, wait, fault, learned and scratch lines;
- `raw/coredump-cp-state.txt`: registers only;
- `raw/dcb-dispatch-runs.txt`: the dcb as runs of dispatches per program, with barriers and draws;
- `raw/cp-fetch-window.txt` and `raw/model-output.txt`: the fetch position;
- `model0279.py`: the model that gives the fetch position.

**Result.**

1. **F322's pair, the third time, now with RT off** (`raw/journal-lines.txt`, `raw/coredump-cp-state.txt`).
   - **dcb #841748**: 37,814 dwords, 2,615 dispatches (1,645 indirect), TIMEOUT 2,009.6 ms. Both its waits were kept
     and both are **met**: 0x12004b3c38 == 0 at offset 1269 (pfp) and 0x11e04f06c8 == 1 at offset 1330. So it stopped
     in its own work.
   - **acb #841756**: 865 dwords, TIMEOUT 2,005.7 ms. Its only wait, the first packet (WAIT_REG_MEM64 on 0x12004b53c8
     == 0), was kept and is **not met**: "now 0x9076d6d8c", the very value of exp 0275's acb.
   - The coredump was written at the **comp_1.2.0** timeout. That queue is mec 0 pipe 2 queue 0: IB_BASE
     0x1026_00000000, IB_RPTR 0x1c, and its pipe's header dump repeats 0xc0079300 (WAIT_REG_MEM64). So the compute
     ring is parked on the acb's first wait, as in 0275.
2. **The fault.** The status decodes, with the field layout of `tools/bc5-agc/regdb/gfx10.json` (Mesa fe554882), to
   MORE_FAULTS 1, PERMISSION_FAULTS 0x5, CID 8, RW 1 (write), VMID 7.
   - The host's fault query gave "timeout: fault 0x1474260000 status 0x00741051", then "learned … region
     0x1472000000+0x6000000 (saved)". So the page lay in a hole.
   - After the device reopen, the host put zero buffers over its saved fault windows: 0x14852000000, 0x1452000000,
     0x145a000000 and now 0x1472000000. Stray accesses in the 0x145…–0x148… GiB range are a recurring pattern.
   - No probe line names an address in 0x1472000000–0x1478000000.
   - The dump's `mmTCP_UTCL0_STATUS` is 0x1. Its fields are not in the vendored regdb: TODO(verify).
3. **New: the coredump's GFX state is the hung dcb's, and it locates the fetcher.**
   - **The IB matches.** CP_IB1_BASE is 0x1004_00000000 and CP_IB1_CMD_BUFSZ is 102,512 dwords. `model0279.py` takes
     the dcb as dumped, adds exp 0052's GPU check as the backend inserts it (44 dwords in front of each checked
     DISPATCH_INDIRECT, 35 in front of each indirect draw, none for dropped packets) and gets **102,498**, 14 dwords
     apart.
   - **The fetch position.** CP_IB1_BUFSZ is 47,376 dwords left, so the fetcher had read 55,136, which is **title
     offset 26,143**. That is inside a run of DISPATCH_INDIRECT of **0x909973d00** (`raw/cp-fetch-window.txt`).
   - **The ME is at or before it.** The fetcher was stalled with its queue full (CP_CPF_STALLED_STAT1:
     RING_FETCHING_DATA, INDR1_FETCHING_DATA), so the ME was not consuming. GRBM_STATUS shows CP_BUSY, SPI_BUSY and
     GUI_ACTIVE and no other pipeline block busy; GRBM_STATUS_SE0 shows SPI_BUSY. So waves are still resident (field
     names from the regdb).
   - **Caveat.** Whether this GFX state predates the GFX ring's reset depends on the kernel's order of the two
     timeouts. That is TODO: the kernel log lines of 19:57:27–19:57:31. The busy state and the matching IB1 suggest it
     does; exp 0275's dump, written 2 s after the GFX reset, did not.
4. **The window holding the dispatch that does not end** (`raw/dcb-dispatch-runs.txt`).
   - The last CS_PARTIAL_FLUSH (EVENT_WRITE event 7) before the fetch position is at offset 20274. Between it and
     26143 there are only two ACQUIRE_MEMs (23480, 23554), and no flush.
   - So the dispatch that does not end is one issued after 20274:
     - 0x909974200 ×194;
     - 0x909973900 ×194;
     - 0x909973b00 ×194;
     - the first ≤57 of 0x909973d00.
   - In each of these programs, 30 dispatches have counts that read as floats, and the GPU check skips them. It is
     the same 30 objects in every program: each object's block holds one argument slot per program (+0x00 0x909973900,
     +0x20 0x909973b00/f00, +0x40 0x909974200/4400, +0x60 0x909973d00, +0x80 0x909977100), and the last 30 blocks hold
     float data.
   - The rest have sane counts: up to 524 groups for 0x909974200, and up to 69×69×69 = 328,509 for 0x909973d00.
5. **The same eight programs, in the same order and numbers, form exp 0275's dcb #68401** (RT on, 18:52): 0x909974200,
   0x909973900/3b00/3d00/3f00, 0x909974400 (dropped), 0x909977100, 0x90997a500. So both GFX hangs of the day stopped
   in this family. It is the second tree family's builders (the BVH session's reading), and 0278's "off" does not drop
   it.

**Verdict.**
- **The 19:57 stop is F322's pair**, with the graphics ring stopping first in its own work and the "Lighting Prep"
  compute buffer waiting on it, now with RT off.
- **The dump located the GFX fetcher for the first time**: inside the second tree family's builders. The dispatch that
  does not end is one of about 600 issued since the last CS_PARTIAL_FLUSH, all from 0x909974200, 0x909973900,
  0x909973b00 and 0x909973d00. The first family's build chain was dropped, so it is neither the writer of 0x1474260000
  nor the work the ring stopped in (F338).
- **Open: whether the faulting write and the endless dispatch are the same wave.** If the GPU retries a faulting
  write, the wave never ends; that is TODO(verify) via the box's `amdgpu` `noretry` setting.
- **Next.**
  - Read-only, on a GO: the kernel's lines for the two timeouts and the fault, and `noretry`.
  - A catch run with exp 0277's breadcrumbs. They would name the dispatch, among those ~600, that was reached and is
    not done. With RT off that needs 0277 and 0278 in one binary. Their edits to `bc5LleAgc.cpp` commute: applied to
    a2a2c2df in either order they give md5 55fa73a4. That is the box supervisor's decision.
  - For the BVH session: 0x909973d00 and its inputs (its 68³–69³ grids), and the 30 float-filled object blocks.
