# 0055 — cross-queue waits served by the ring order, and what stops the second title at 150 s

**Question.** At the second title's first scene change (~150 s) graphics buffers give up
cross-queue waits (8 ms limit of experiment 0026) and, with the indirect draws of 0054, the GPU
stops. Are these waits cycles? How do other projects handle waits between a graphics and a compute
queue, and what of it fits one GFX ring?

**Setup.** Launcher defaults of 0053. `BC5_DIRECT_WATCH_VA` / `BC5_DIRECT_LABEL_TRACE` (exp. 0024)
over the labels at 0x12004b3000–0x12004b7000 (run 244). Survey of other projects (2026-10-12):
local checkouts rpcsx e8ae1481a, KytyPS5 60e53a3, KytyPlus f266548, AnyPS5 f145139, prosper
1c93ab8, ps5rs 5cfb032; shadPS4 main (`src/video_core/amdgpu/liverpool.cpp`); Mesa main
(`src/amd/common/ac_shadowed_regs.c`, `ac_create_shadowing_ib_preamble`, which has a GFX10 branch).
New (all off by default):

- Host `BC5_DIRECT_RING_ORDER_WAITS=1`: the label writes with immediate data (`RELEASE_MEM`,
  `EVENT_WRITE_EOP`, `WRITE_DATA`) of the jobs on the ring that have not completed are registered
  (removed when the job completes; all on a timeout). A wait not yet satisfied whose label the last
  such write sets to a satisfying value is not waited for on the CPU: the `WAIT_REG_MEM` stays in
  the buffer for the GPU (backend `FilterOptions::keep_wait_offsets`; `ctest` 39 of 39). Applies
  to the game thread's buffers and to the compute queue's readiness check (`acb_ready`).
- Host `BC5_DIRECT_DCB_WAIT_UNBLOCKED_MS` (a longer limit while the compute queue is not blocked)
  and `BC5_DIRECT_TRAP_STATS=1` (program RSRC2 `TRAP_PRESENT`, bit 6, and non-zero `*_PGM_HI`
  values; Mesa `gfx10.json` via `tools/bc5-agc/regdb`).

Runs 244–250, 2026-10-12 14:17–14:57. Raw output in `raw/`.

**Result.**

1. **Most given-up waits are latency, not cycles.** Run 244: the graphics buffer's wait at 1042
   on 0x12004b4438 was given up at 8 ms; the label went to 0 6 ms later, written by the
   `RELEASE_MEM` of a compute buffer submitted before the wait — itself waiting behind a 22,000-dword
   graphics buffer on the ring, whose `RELEASE_MEM` sets the label the compute queue waited for.
   A longer limit while the compute queue is "not blocked" (run 245) did not help: it was blocked,
   on a write already on the ring.
2. **Other projects**: none runs PM4 natively on one ring. shadPS4 runs each queue as a coroutine
   that yields at an unsatisfied `WAIT_REG_MEM` (CPU interpretation, Vulkan); rpcsx and Kyty park a
   buffer at its wait and resume it; AnyPS5 treats a wait as held when a write recorded but not
   finished targets its label (`noteHeldAtSubmit`, `Recorder::LookupLabel`); prosper defers only
   memory writes after a wait. Their register state lives on the CPU, so none has to replay it.
   For splitting graphics buffers, Mesa's register shadowing preamble (CP-side save and load of
   context, SH and UCONFIG registers, GFX10 branch) is the candidate; untested on gfx1013.
3. **The ring order serves them** (AnyPS5's idea on one ring): run 247, 300 s: 1 given-up wait
   (245: 90), no deferred compute buffer, over 7,000 waits left to the GPU, no fault, 18.7 fps;
   run 250, 200 s: no fault.
4. **What stops the title at 150 s is a program counter with bit 47 set.** Runs 241, 246 and 248
   (248: ring order and indirect draws, no given-up wait at all) end on an instruction fetch at
   0x8011d0288000 / 0x8011d0375000 / 0x8011d0374000 (kernel: "Faulty UTCL2 client ID: SQC (inst)",
   `raw/dmesg-sqc-faults.txt`) — the pages of the title's compute programs at 0x11d0288000 and
   0x11d0374100–0x11d0375600 with 0x80 above bit 40. No `*_PGM_HI` written or loaded is non-zero,
   and no RSRC2 has `TRAP_PRESENT` (run 250: 1.6 million values), so the address is formed inside
   a shader. Every "junk top byte" fault so far has a valid address in its low 40 bits
   (0x1296844000 under 0x22, 0x1296219000 under 0xfa, 0x1250d7e000 under 0xb0, …): consistent
   with a PS5 GPU that ignores virtual-address bits 40–47, TODO(verify).

**Verdict.** Passed for the waits: the ring order removes the given-up waits of the scene change
without a cycle (runs 247, 250). Not the cause of the 150 s stop, which is a shader-formed address
with a non-zero top byte; the next step is to test whether mapping the memory again under such
addresses (or another way of ignoring bits 40–47) lets the title through, starting with the
pages the faults name.
