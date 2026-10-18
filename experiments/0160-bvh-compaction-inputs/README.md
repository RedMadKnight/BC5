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
