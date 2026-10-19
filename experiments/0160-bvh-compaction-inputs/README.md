# 0160 — What the BVH compaction (0x909974400) feeds that makes the geometry engine fetch from address 0

**Question.** F207 skips compute program 0x909974400 (the second title's BVH neighbour-link
compaction) because with it running one graphics buffer of the night scene faults the GPU: the
geometry engine reads pages 0x0–0x2f000. Which of the program's inputs is wrong on the host, what
does it write that the engine then reads, and can the emulator be fixed so the skip goes?

**Setup.**
- BC-250 dev box, 2026-10-18 17:30–20:25, runs 740–770 (opening started by script, killed at
  +165 s; the fault runs reproduce the kernel's `[gfxhub] page fault` at journal t ≈ 144.9 s, the
  box survived every one). Kernel 7.2.8, the KytyPlus build of the committed patch plus the
  diagnostics below. `experiments/0159-opening-hang-amm-pool` is the starting point.
- Host diagnostics added to `src/libs/bc5LleAgc.cpp` (all opt-in, in the patch):
  `BC5_DIRECT_DISPATCH_JOURNAL=1` now prints user data 0–15 and the indirect base/offset of every
  dispatch, and every draw, `INDEX_BASE`, `INDEX_BUFFER_SIZE`, `SET_BASE` packet of a graphics buffer;
  with `BC5_DIRECT_GE_PROBE=<min>:<max>` (title dwords) also the register tables a buffer loads
  (`LOAD_*_REG_INDEX` pairs) and the `COND_EXEC` flag value. `BC5_DIRECT_TIMEOUT_PROBE=1` dumps the
  buffer whose fence timed out as the GPU ran it (`ib-timeout-<submission>.bin`) and journals its draws
  with the index base in force, whether the filter let each packet through, the indirect arguments
  and the first index dwords as the GPU left them (`BC5_DIRECT_PROBE_VA=<addr>:<n>` adds memory).
  `BC5_DIRECT_DROP_AT=<dwords>:<offset,...>` drops packets by offset in buffers of one size;
  `BC5_DIRECT_UCONFIG_FORCE=<reg>:<value>`, `BC5_DIRECT_INDEX_TYPE_MASK=<hex>`,
  `BC5_DIRECT_INDEX_BASE_DUP=1`, `BC5_DIRECT_GE_PROBE` with `BC5_DIRECT_GDS_SHADOW=1` (COPY_DATA
  register captures in front of each draw), and `BC5_DIRECT_TF_RING=<base>:<size>` /
  `GraphicsDriverSetTFRing` → prefix (the tessellation-factor ring registers) are the knobs of the
  runs below. The dmesg-triggered root hang dump (`~/bc5-work/exp0160/faultdump.sh`) came too late
  (the CP was already idle); the kernel's device coredump of each reset was read instead.
- Offline: `~/bc5-work/exp0160/pm4off.py` (packets with offsets), `blocks.py`, `restore_diff.py`
  (register-table diff between runs), the disassembly of the buffer's programs
  (`~/bc5-work/dis-0159/`, llvm-mc gfx1013). No game data is committed; the dumps stay in
  `~/bc5-data/captures/play-20261018-17*..20*/gc/` and `~/bc5-work/exp0160/`.

**Result.**
- *The compaction's inputs are not the problem.* With the journal extended (run 740) the dispatches
  of 0x909974400 carry: s0/s1 = 0x11/0x12 (the high dwords of the two bases), s2 = 0 (mode),
  s3 = BASE_A lo (0x8c5f1200, 0x8c5f8100, … one per object), s[4:5] = the constant block
  (0x118c5f0000, 0x118c5f1f00, …), s6 = BASE_B lo (0x52a0b100 …, a per-frame ring in the 0x12 heap),
  ud12 = 0xa; the `DISPATCH_INDIRECT` arguments sit at BASE_A + 0x40 (the same block the clear
  0x909974200 and the four 0x9099739xx/f00 programs use at +0x0/+0x20/+0x60/+0x80). Nothing is zero
  or unmapped, and the program already runs from journal t ≈ 47 s (the menu scene) without any
  fault: only the night scene faults. The `DISPATCH_INDIRECT` drops the host journals as "args not
  mapped" belong to other programs (0x909974200 at offset 881 with no `SET_BASE` in its buffer,
  0x909973b00 at 18918/20048) — the host's per-buffer `SET_BASE`/user-data tracking starts at zero
  in continuation buffers, a separate, smaller defect.
- *The reader is the geometry engine's index/work-distributor path, at any draw of one frame.* The
  kernel's coredumps name `WD_UTCL1_STATUS` 0x101 with `IA_UTCL1_STATUS` 0 and client 3 (GE2); the
  faulted pages are 0x0–0x2f000 in two interleaved rising streams (the two shader engines). The
  buffer whose fence times out varies (2893, 3805, 9374 dwords in different runs); in the 2893-dword
  one (title part 1633 dwords, dumped as the GPU ran it) every packet executed, the title's
  `INDEX_BASE 0x121a600000` / `SET_UCONFIG_REG_INDEX VGT_INDEX_TYPE 0x401` precede its single
  `DRAW_INDEX_INDIRECT_MULTI` (args {0x36xx, 1, 0, 0, 0}, indices 0,1,2,2,1,3 …), the CP's
  `CP_INDEX_BASE_ADDR` reads back 0x1a600000 after that draw, and the ME's last packet (coredump
  header dump) is the `DISPATCH_DIRECT` after the draws with the ME stalled on the pipeline.
  Dropping that indexed draw (run 745), the three `DRAW_INDEX_AUTO` (747), two of them (760), all
  but the first auto draw (765), re-emitting `INDEX_BASE`/`INDEX_BUFFER_SIZE`/`VGT_INDEX_TYPE` with a
  `PFP_SYNC_ME` before the indexed draw (761), masking the unknown bits of `VGT_INDEX_TYPE`
  (0x400/0x480 → 0, 748, 762), forcing the unknown uconfig 0xc383 (0x40000040) to 0 (752),
  skipping the buffer's fill kernels (753), its ray-tracing dispatch 0x11d040e200 (766) or the
  32-byte copy kernel 0x11d0287900 (754, black screen) all leave the fault. Dropping both draw kinds
  (750) removes it: a 3-vertex `DRAW_INDEX_AUTO` with the NGG pass-through shader 0x11d00be800
  (vertex fetch, `GS_ALLOC_REQ`, `exp pos/prim/param`, no memory write) and a pixel shader that only
  exports is enough to make the engine read ~200 KiB from address 0.
- *The state is the same as in a run that does not fault.* The per-submission restore tables the
  title loads (`LOAD_CONTEXT/SH/UCONFIG_REG_INDEX` from 0xfe0040068/0xfe0042068/0xfe00425d8: 921, 174
  and 57 pairs) are identical in the faulting run and in a run with the compaction skipped at the same
  clock (`restore_diff.py`), the per-draw tables name the same programs, and the title's uconfig
  writes outside AMD's gfx10 register database (0xc248, 0xc2bb–0xc2bf, 0xc2c4–0xc2d3, 0xc2e4–0xc2eb,
  0xc383 = 0x40000040, 0xc41d) are all constant. The guest has no memory below 0x40000 (gdb `info proc
  mappings`), so the engine is reading through a base register that is 0 on the host and not written
  by the command stream: the geometry engine's own buffers (`WD_INDEX_BUF_BASE`, `WD_POS_BUF_BASE`,
  `WD_CNTL_SB_BUF_BASE`, the tessellation-factor ring `VGT_TF_MEMORY_BASE`, all privileged or
  system-programmed; `COPY_DATA` reads of them return 0). The title never calls
  `GraphicsDriverSetTFRing` (the host stores its arguments and programmed nothing). Programming
  `VGT_TF_RING_SIZE`/`VGT_HS_OFFCHIP_PARAM`/`VGT_TF_MEMORY_BASE(_HI)` to the backend's 64 KiB shadow
  buffer in every prefix (run 770) moved the same address-0 fault from the night scene to the first
  frame that runs the compaction (t ≈ 45 s, the menu): the engine's tessellation state takes part,
  but the ring base is not the register it reads from.
- The data dependence stands: with 0x909974400 skipped the same buffers (same layout, same tables)
  draw without a fault. What the compaction's consumers write for the engine is still unknown; the
  candidates are the eleven indirect programs of F207 (0x909977100 and 0x90997a500 run on the
  compacted list with function pointers at 0x11d039d400/0x11d039d800) and whatever system-programmed
  ring they fill.

**Verdict.** Inconclusive for the fix. The compaction's inputs are correct and it runs for a minute
before the fault; the fault is the geometry engine reading, at the first draws of the night scene,
through a base register the console's system programs and the host leaves at 0, as soon as the
compaction's output exists. The skip stays in the launchers as a diagnostic. Next: find the
system-programmed geometry-engine buffer (the AGC driver's initialisation that the host stubs, or a
privileged register the kernel driver sets on the console: WD index/position/sideband buffers,
GS/NGG rings), and read the consumers 0x909977100 / 0x90997a500 for what they emit per element.

## Continued (2026-10-18 20:30–20:40, runs 780–781, the maintainer's directions)

- **The compacted list's consumers write nothing for the geometry engine** (three agent readings of
  the llvm-mc disassembly, every store and descriptor accounted for). 0x909977e00 is the BVH
  leaf builder: from a {triangle, 3 neighbours} table at BASE_A+0x80+cb[0x9c]·32 it fetches vertex
  indices and positions through the two function pointers (s[8:9], s[12:13]) and writes one 64-byte
  triangle node per leaf at BASE_B+cb[0xa8]·64 (five float3 positions, NaN → FLT_MAX, and a packed
  triangle-id dword of per-triangle vertex-rotation nibbles — the RT IP 1.1 node layout), plus in mode
  0 a 20-byte record of the five vertex indices at BASE_B+cb[0x48]. 0x909977100 does the same
  adjacency/position build with the other pointer pair (0x11d039d400/d800). 0x90997a500 is the
  bottom-up refit: four lanes per node, child AABBs into the node, the back-pointer table's
  outstanding-child counters decremented with `buffer_atomic_sub`, the merged box climbing to the root
  (node 4) whose AABB goes to BASE_B+0x98; it has twelve user SGPRs (s12 is the group id, the journaled
  ud12–15 are stale), and its s[8:11] V# has one record, so an instance index above 0 yields a zero
  descriptor and compute loads from address 0 — a TCP-side read, not the GE's. No program writes draw
  or dispatch arguments, 16/32-bit index data, a ring pointer, a GDS word, an `s_sendmsg` or a base;
  the only CP-consumed datum is the producer's byte counter at BASE_B+0x80, which is the
  `DISPATCH_INDIRECT` argument block of 0x90997a500 (x = 4·N; y and z from the ring header).
- **The prefix is not the base.** The full-state prefix in front of the faulting buffer carries only
  CB/DB bases, `IA_MULTI_VGT_PARAM` 0xff and `SPI_TMPRING_SIZE` 0x1500 among base/ring/size registers;
  the title's own writes in that buffer are user data and thread-trace markers. With the prefix off
  (`BC5_DIRECT_PREFIX_ALL=0`, run 780) the kernel still logs the address-0 faults at the night scene,
  but **no fence times out and the title plays on** (journal t 169.8 s, the screenshots keep
  changing): the GE's read of address 0 is survivable by itself; the hang needs the full-state prefix.
  With the SX-only prefix (`=sx`, run 781) the box stopped answering about three minutes in (no ping,
  no SSH): the machine-down the maintainer has seen, now reproduced once without the full prefix.
- Next, in the maintainer's order: step 3 — read the WD/GE base registers at the hang through the
  root hang-dump helper (its `umr -r` list needs `mmWD_INDEX_BUF_BASE(_HI)`, `mmWD_POS_BUF_BASE(_HI)`,
  `mmWD_CNTL_SB_BUF_BASE(_HI)`, `mmVGT_TF_MEMORY_BASE(_HI)`, `mmVGT_ESGS_RING_SIZE`,
  `mmVGT_GSVS_RING_SIZE`, `mmGE_CNTL`, `mmVGT_GS_MODE`; root is the maintainer's), in a faulting and in
  a clean run, with `faultdump.sh` firing on the kernel's fault line. Run 780 also suggests testing
  whether the hang is the prefix's `CLEAR_STATE` + state reload colliding with the GE's pending work
  (a run with the prefix only in front of buffers after a fault, or `BC5_DIRECT_PIECES_NO_CLEAR=1`).
- *Run 782* (`BC5_DIRECT_PIECES_NO_CLEAR=1`: the full-state prefix without its `CONTEXT_CONTROL` and
  `CLEAR_STATE`): the fault and the fence timeout as before (kernel ring reset at 390 s uptime). The
  hang that run 780 avoided is not the prefix's `CLEAR_STATE`; it needs the prefix's register reload.
  Step 3 (the WD/GE base registers at the hang) waits for the root hang-dump helper to read them:
  `/usr/local/bin/bc5-gpu-hang-dump` on the box is still the 2026-10-12 version. The host now takes
  `BC5_DIRECT_FENCE_TIMEOUT_MS` (the completion thread's fence wait, default 2000) so a dump has a
  wider window before the kernel's own reset.
- *Runs 783–784* (the root hang-dump helper now reads `mmWD_INDEX_BUF_BASE(_HI)`,
  `mmWD_POS_BUF_BASE(_HI)`, `mmWD_CNTL_SB_BUF_BASE(_HI)`, `mmVGT_TF_MEMORY_BASE(_HI)`,
  `mmVGT_ESGS/GSVS_RING_SIZE`, `mmGE_CNTL`, `mmVGT_GS_MODE`; `faultdump.sh` fires it on the kernel's
  fault line; `BC5_DIRECT_FENCE_TIMEOUT_MS=8000`): the kernel resets the ring 2.0 s after the fault
  whatever the host's fence timeout (run 784: fault at 1270.37 s, "ring gfx_0.0.0 timeout" and reset at
  1272.38 s), and the helper runs `umr -O halt_waves` first, so its register reads land after the reset
  (CP idle, `GRBM_STATUS` 0x3028): every WD/TF base reads 0, `GE_CNTL` 0xf680, `VGT_GS_MODE` 0 — the
  post-reset values, not the stalled state. With the longer host timeout the night scene arrives later
  (journal t 164 and 199 s instead of 145: a job the 2-s timeout used to cut short now waits out),
  so a run needs the kill at +200 s or later. To read the stalled state the helper must read the
  registers before halting waves, and the kernel's 2-s gfx timeout (this kernel's default; the module
  parameter is unset) would have to be raised on the kernel command line — both root's.
- *Run 785* (helper reads the registers before `halt_waves`, kernel `amdgpu.lockup_timeout=10000`,
  host fence timeout 12 s, kill at +210 s): the previous boot's kernel log shows two GE2 fault bursts.
  The first (23:00:17, pages 0x0 and 0x18000) fired the dump within a second: `GRBM_STATUS` 0x3028 and
  `CP_STAT` 0 (idle), every WD/TF/ESGS/GSVS base 0, `GE_CNTL` 0x8040, `VGT_GS_MODE` 0 — **the GPU had
  already recovered**; the title played on for 25 s (the journal reaches t 197 s). The second burst
  (23:00:42, pages 0xa000–0x25000) was followed by "Dumping IP State" three seconds later and then
  nothing: the machine reset itself ("Previous system reset reason: a parity error"). So the address-0
  read is survivable once (the GE takes the NACK and finishes the draw), and what kills the box is a
  later job's hang after a repeat of it; the 2-s timeout and reopen of the earlier runs were what kept
  the machine alive. The registers at the fault cannot name the base: the WD index, position and
  sideband buffers and the TF ring all read 0 on this host at every moment, idle or not.
- *What is left:* program the candidates one at a time to a GPU-mapped buffer (root's `umr -w` of
  `mmWD_INDEX_BUF_BASE(_HI)`, `mmWD_POS_BUF_BASE(_HI)`, `mmWD_CNTL_SB_BUF_BASE(_HI)` to e.g. the backend's
  GDS shadow at 0x100004000000, encoding unknown — TODO(verify)) before the night scene and see which
  one moves the fault address; each such run risks the machine. Until then the skip of 0x909974400 and
  the 2-s kernel/host timeouts are the safe configuration: `amdgpu.lockup_timeout=10000` should be
  removed again.

## Continued (2026-10-19 08:00–08:25, runs 786–787): the window at address 0 and the zero pages

- The lead (the main session): the host's learned-window file holds a window `0x0 0x6000000` (learned
  from the faults), and `scratch_fill` tries to back its holes with 2 MiB zero buffers; the first piece
  at GPU VA 0 is refused by amdgpu (`shared map at 0x0+0x200000: -22`, the VA below the driver's
  reserved bottom), and the loop gave up on the whole piece, so none of the 96 MiB was zero-backed.
  Now a refused piece below 2 MiB is retried from the next 64 KiB boundary: run 786 (skips on) maps
  from 0x10000 (`scratch: zero page at 0x0 refused, trying from 0x10000`); only `0x0+0x10000` stays
  refused — this kernel's (7.2.8) reserved bottom is 64 KiB (TODO(verify) against amdgpu_vm.h).
- Run 787 (no skip of 0x909974400): the geometry engine's faults now cover **only pages 0x0–0xe000**
  (15 pages, two per page at most), nothing above 0x10000 — the zero pages serve the rest of its
  ~200 KiB read. The fence still times out (one 2-s timeout, the kernel's ring reset succeeded, the box
  stayed up), and the dump fired on the fault caught the stalled state this time: `CP_STAT` 0x94038600,
  `CP_IB1_BUFSZ` 0xd8 (the same position as the kernel's coredump), `CP_PFP_HEADER_DUMP` ACQUIRE_MEM,
  `CP_ME_HEADER_DUMP` EVENT_WRITE — and `WD_INDEX_BUF_BASE(_HI)`, `WD_POS_BUF_BASE(_HI)`,
  `WD_CNTL_SB_BUF_BASE(_HI)`, `VGT_TF_MEMORY_BASE(_HI)`, `VGT_ESGS/GSVS_RING_SIZE` all 0 while the job
  is in flight, `GE_CNTL` 0x8040. So the CP does not program any of these per draw either; the base
  the engine reads through is 0 for the whole run and is none of the registers that can be read.
- What hangs is the retried fault, not the data: the kernel logs each page up to twice (retry faults;
  `amdgpu.noretry` is at its default -1), and a translation that never succeeds stalls the engine until
  the ring reset. With the first 64 KiB unmappable from user space, the remaining mitigation on the
  kernel side is `amdgpu.noretry=1` (the engine gets a NACK and reads zeros, as it does above 0x10000)
  — to be tested next (run 788 without the skip), together with `amdgpu.lockup_timeout` back at its
  default, since 10 s let a repeated fault take the box down (run 785).
- *Run 788* (`amdgpu.noretry=1`, `lockup_timeout` back at default, zero pages above 64 KiB, the
  compaction running, seven minutes like run 735): 17 fence timeouts with reopens and 26 failed
  submissions, the kernel's ring resets succeeded every time (the box stayed up), the faults still at
  pages 0x0–0x5000 (the first 64 KiB), the opening a crawl as in runs 638–639. The no-retry mode does
  not make the engine's read of the unmappable first 64 KiB survivable; the skip stays. `amdgpu.noretry=1`
  has no further use and should go back to the default (it changes how shader faults behave in every
  other experiment).

**Verdict (continued).** The program's inputs are correct; the fault is the geometry engine reading the
first 64 KiB of GPU address space (and, before the zero-page fix, ~200 KiB) at any draw of the night
scene's first frames once the compaction's output exists, through a base that is 0 here and none of the
readable registers (WD index/position/sideband buffers, TF ring, ES/GS rings all read 0 while the job is
in flight). User space cannot map those 64 KiB (amdgpu's reserved bottom), retry-less faults still stall
the engine, and a longer kernel timeout lets a repeat take the machine down. Left for the host: the
zero pages above 64 KiB (kept, generic) and the skip (diagnostic). Left to find: which GE base register
the console's system programs — only writable as root (`umr -w` of the WD buffer bases to a mapped
buffer, one per run) or by reading the console driver's initialisation, neither of which this
experiment could do.
