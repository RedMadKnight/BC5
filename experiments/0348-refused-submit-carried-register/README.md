# 0348 — a refused submit and the carried base register

Analysis of the maintainer's RT-on plays of 2026-10-27 (12:52 machine-down on the shared build ddfb9456; 18:55 ring
reset and 19:22 machine-down on the test build ecbb95ce, 0343 + 0346 v3), ordered by the top session; reads and copies
on the box only, no emulator run. Findings F421–F426. The title's dumps stay on the box and in a private folder outside
every checkout; only counts, offsets and addresses are quoted here.

**Question.** Which packet read page 0 at 19:22, why did 0346's third version leave the chain alone, and what fix does the
offline harness gate?

**Setup.**
- Box captures (read-only): `~/bc5-data/captures/play-20261027-1919/gc/` (`direct.log`, `ib-timeout-00168772-dcb-9779.bin`,
  `ib-timeout-00168773-acb-1853.bin`), `play-20261027-1854/gc/` (`ib-timeout-00054518-dcb-28288.bin`,
  `ib-timeout-00054515-acb-4641.bin`), `play-20261027-1251/gc/` (12:52), the devcoredumps
  `~/bc5-data/captures/devcoredump/20261027-192209-devcd1.txt` (the final IB of #168772 as the kernel saw it, 10,983 dwords
  listed) and `20261027-185531-devcd1.txt`, the play log `~/bc5-work/exp0343/play/play-20261027-191917.log`.
- Packet listings of the dumps and of the devcd's IB listing with a 30-line perl walker (type-3 header, opcode, shader-type
  bit, length, the first dwords); the kernel's `amdgpu_cs.c` (torvalds/linux master, read 2026-10-27) for the IB size limit.
- Offline harness: `experiments/0346-host-resolved-indirect/raw/harness0346.cpp` built on the laptop as before (0346's
  `build-harness.cmd`: `harness_main.exe` = main d0c2668's passes, `harness_0346.exe` = the third version a98c8b2), run over
  the new dumps copied to the private folder: `harness_X --window 1100000000 [--zeroed] <dcb> <acb>`. Summary lines in
  `raw/harness-1919.txt` and `raw/harness-1854.txt`.
- The fix (this branch, `backend/src/direct.cpp`, experiment-marked): the register `host_indirect` carries across GFX-ring
  jobs is committed to the device only after `amdgpu_cs_submit` returned 0; a refused submit also prints one stderr line
  with the job's final IB size. Not built or run on the box yet (a build needs a GO; the box is the top session's).

**Result.**

- **F421 — root cause of all three failures: one ~1 MB dcb the kernel refused.** Each failing play has exactly one submit
  with `FAILED rc -22` in 0.02 ms (the ioctl itself, no fence wait), and it is the largest dcb of the play: 12:52 #48052
  252,101 dwords at t 61.407 s; 18:55 #51832 257,041 dwords at t 64.635 s; 19:22 #168770 264,505 dwords at t 166.670 s.
  The clean 15:34 play (largest dcb 10,171 dwords), the 13:27 and 14:23 plays and every bench run (R1/R2 v3, v3b, 0343 R1)
  have no `rc -22`; a 177,126-dword dcb (#122368, 19:22's play) went through. `amdgpu_cs.c` (`amdgpu_cs_p2_ib`) returns
  -EINVAL when `ib_bytes / 4` exceeds `AMDGPU_GFX_SDMA_IB_PACKET_SIZE_MAX_DW` = 0xfffff (1,048,575 dwords, the 20-bit size
  field of the INDIRECT_BUFFER packet). The host's passes grow a dcb (the CP check adds 88 dwords per checked dispatch:
  52,360 for 595; a 30,221-dword dcb became 77,241), so a 250,000-dword title dcb plausibly ends above the limit.
  `TODO(verify)`: the host never journals the final size, and the box's kernel 7.2.9-ogc3.1 was not read for the same check;
  the new stderr line will show the size. The refused dcb is the frame's big one; nothing of it reached the GPU, and what
  followed read what it should have written or set:
  - 12:52: the next dcb (#48055, 38 ms later) carried the 435-dispatch unbased chain → fault at page 0x9bce4000 (= base 0
    + offset 0x9bce4d80), ring reset failed, machine down (exp 0342/0344/0346).
  - 19:22: the next dcb (#168772, 110 ms later) carried a 595-dispatch chain of the same form → fault at page 0x0, ring
    reset failed, machine down (this experiment).
  - 18:55: 3.1 s and 44 submits later a compute-ring acb (#54515, 127 compute-type `SET_BASE` + GFX-form
    `DISPATCH_INDIRECT` pairs, offsets 0x20 … 0x860) read garbage arguments (the probe: a grid of
    17,996,103,389,943,308,224 groups at 3849) and the dcb #54518 next to it took a TCP fault at 0x1315516000; the ring
    reset succeeded. The same lost frame, a different symptom.
- **F422 (question 1) — the page-0 read is the chain dispatch with offset 0x60, not the LOAD_SH_REG_INDEX.** In the dump
  the chain is 595 GFX-form `DISPATCH_INDIRECT` (op 0x16, dword 2 = 0x61) from dword 77 to 6674 in five groups separated
  by `LOAD_SH_REG_INDEX` (op 0x63, 5 dwords: address 0x909842440 … with the index bits 0 = a direct address, format
  bit 31 set, 10 dwords), the groups' offsets restarting at 0x60: dump 811 / final IB 982 is `offset 0x60`. The devcd's
  final IB has only a `PFP_SYNC_ME` (0xc0004200) before each chain dispatch — the unbased path, no `COND_WRITE`/`COND_EXEC`
  — and `CP_IB1_BUFSZ` 0x2500 of 0x2ae0 puts the fetch at dword 1,504; the PFP header ring (… 0xc0004200, 0xc0036300,
  0xc0047600, 0xc0011600, 0xc0004200) holds the only 0x63 within those 1,504 dwords (final 975) followed by the 982 dispatch.
  With the base register 0, that dispatch reads its three dwords at 0x60: page 0, exactly the fault (CPF, read,
  permission). The 0x63 reads 0x909842440 (program memory next to 0x909973b00) and had executed. The 81 chain dispatches
  before it (offsets 0x9a920 … 0x4adf20) raised no fault; `TODO(verify)` whether the GPUVM maps those low VAs (the host's
  own `shared map at 0x0+0x10000: -22` lines show that only page 0 is refused by the kernel).
- **F423 (question 2) — 0346 left the chain because its carried register came from the refused dcb.** The pass runs at
  prepare time and stored `register_out` into the device before the submit; #168770's `SET_BASE`s (the frame's base for the
  chain, never executed) left the host's copy non-zero, so every one of the 595 dispatches was "left: the register is
  non-zero" (the play's periodic line: 3,228,178 left, 0 never set, 0 rewritten). The hardware's register was 0 and zeroed:
  the previous small dcb of each frame ends with the pair `SET_BASE(compute) 1 = 0`, `SET_BASE(gfx) 1 = 0` (this dcb: 8091
  and 8095, after its own `SET_BASE 1 = 0x118c8fdb00` at 8013). Not an acb (#168773 has no `SET_BASE`), not the
  `LOAD_SH_REG_INDEX` path. Offline (`raw/harness-1919.txt`): main and 0346 with nothing carried → 595 unbased / "never
  set", left alone, 10,969 dwords; 0346 with `--zeroed` (the hardware's state) → 595 rewritten to verified pages
  (0x110009a000 … 0x11cd5c9000 under the learned window 0x1100000000), 0 dropped, 0 overflow NOPs, 595 checked, 66,899
  dwords. 18:55's dcb #54518: 209 checked, 0 unbased, nothing for 0346 to do (`raw/harness-1854.txt`).
- **F424 — the fix (this branch).** `direct.cpp`: the pass's `register_out` goes to a local; the device's register is
  updated right after `amdgpu_cs_submit` returned 0, so a refused or otherwise failed job leaves the host's copy as the GPU's
  own. With it, 19:22's and 12:52's chains are the `--zeroed` case: rewritten to pages the host verified, or NOP-ed. Also a
  stderr line on any refused submit: rc, the final IB dwords, the title's dwords, the BO count. Gate: the harness outputs of
  0346's gate set are unchanged (the pass itself is not touched; only the glue), plus the two `--zeroed` runs above.
  Not built on the box; the box's Catch2 set does not reach `Device::submit`.
- **F425 — what the fix does not do.** The refused frame is still lost: the title's descriptors, indirect arguments and
  labels of that frame never get written, so the next frames run on stale data (18:55's garbage grid, and whatever the
  chain's verified pages hold). The 0290 compute-ring refusal and the host's sanity limits bound the damage; a hang 1 of
  exp 0344 remains possible.
- **F426 — the proposal for the cause: keep every job under 0xfffff dwords.** Options, in order: (a) submit the final IB as
  up to four IBs in one `amdgpu_cs_submit` (the box's libdrm `amdgpu.h`: `AMDGPU_CS_MAX_IBS_PER_SUBMIT 4`), split at a
  packet boundary outside any `COND_EXEC` range, each piece ≤ 0xfffff dwords, the prologue in the first and the epilogue in
  the last — the kernel emits each IB from the ring at IB1 level, so the title's own nested `INDIRECT_BUFFER`s stay IB2;
  (b) RADV-style chaining with a trailing `INDIRECT_BUFFER` that has the chain bit (Mesa 0866ae7,
  `src/amd/vulkan/winsys/amdgpu/radv_amdgpu_cs.c` lines 293 and 435), one IB per submit; (c) first, with the new stderr
  line, measure how far above the limit those dcbs land and whether the CP check's 88 dwords per dispatch is the bulk
  (a cheaper check form for long chains would shrink them).

**Verdict.** Answered: the page-0 read was the chain's `offset 0x60` dispatch under a zero base; 0346 left it because its
carried register came from a dcb the kernel had refused; all three failures of the day start at a ~1 MB dcb refused with
-EINVAL (the kernel's 0xfffff-dword IB limit, final size still to be journaled). The fix on this branch commits the carried
register only for jobs that reached the ring; the cause needs the IB split (F426), a new experiment after a GO.
