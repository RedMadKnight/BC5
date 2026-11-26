# 0199 — the TCP write faults are the title's clears over AMM pages it never backs

**Question.** The second title sometimes hits a GPU fault from client TCP with `PERMISSION_FAULTS 0x5`
and `RW 0x1`, followed by compute and graphics ring timeouts, after which the game freezes (F255, last
paragraph). Which mapping is "read-only" at those addresses, and which program writes them?

**Setup.**
- Analysis only. No GPU run, no build.
- Box: kernel 7.2.9-ogc3.1 (CLAUDE.md still lists 7.2.4); libdrm 2.4.131 in the `ubuntu` container.
- Launcher settings: `~/bc5-work/play-pkg.sh` as of 2026-10-22.
  - `BC5_DIRECT_AMM_PRT` is not set, so unbacked AMM pages have no GPU PTE (experiment 0102).
  - The eager names include `AMM`.
  - Learned faults go to `~/bc5-work/direct-learned-pkg.txt`.
- Sources, all on the box:
  - the kernel journal (persistent; boots of 2026-10-20 and 2026-10-22);
  - the direct-path journals `~/bc5-data/captures/play-<date>/gc/direct.log`;
  - the buffers the timeout probe dumped (`ib-timeout-*.bin`; title data, they stay on the box);
  - the host source: `backend/src/direct.cpp` and patch 0001.
- Scripts in this directory:
  - `collect0199.sh` writes `raw/` (run as `bash ~/bc5-work/exp0199/collect0199.sh`);
  - `ibscan.py` finds 64-bit pointers, V# and T# bases near a fault address in a raw PM4 dump;
  - `ibwalk.py` lists the packets of a dump range. Its "CS pgm" follows `SET_SH_REG` only; the
    program in force comes from the probe's `cs` field, because the clears load theirs with
    `LOAD_SH_REG_INDEX`;
  - `markers.py` lists the title's debug-marker push/pop pairs (`SET_UCONFIG_REG` 0x342 plus
    `WRITE_DATA` to 0xc343) around draws and dispatches.
- The cases. The kernel journal has one more case than F255 (2026-10-20 15:08). The "10:28 session"
  is the one started at 10:26: its fault is at 10:28:15, and `play-20261022-1028` was only created at
  10:28:42.

| Case | Journal | Binary and settings | Fault pages (kernel) |
| --- | --- | --- | --- |
| A | play-20261020-1503 | the launcher's journal (binary not checked) | 0x8518598000–0x851859f000 |
| B | play-20261022-1026 | shared, normal shortcut | 0x84a6880000–0x84a68a9000 |
| C (run W2) | play-20261022-1049 | exp 0194 diagnostic, plus draw journal and unmapped trace | 0x820c37c000–0x820c37f000, 0x820c3a6000 |
| D (maintainer 12:00) | play-20261022-1200 | exp 0194 diagnostic ("woda 0194"), plus draw journal and RT dumps | 0x83fdaa0000–0x83fdaa1000 |
| E (run L7) | play-20261022-1244 | exp 0194 diagnostic, `BC5_DIRECT_DMA_SNAPSHOT=0` | 0x1765833000 |

**Result.**

1. **It is a write to a page with no valid PTE, not to a read-only page.** The kernel prints `ring:40`,
   the IV entry's ring_id 0x28. KFD decodes that field as `prot_valid = ring_id & 0x08` and
   `prot_write = ring_id & 0x20`, and reports them as `NotPresent` and `ReadOnly` (Linux v6.12,
   `drivers/gpu/drm/amd/amdkfd/kfd_int_process_v10.c`, `event_interrupt_wq_v10`). 0x28 sets both: the
   valid check and the write check failed. `PERMISSION_FAULTS 0x5` is the same pair of bits in the
   status register (TODO(verify): that field's bit order against a register reference; the IV bits
   agree). `MAPPING_ERROR` is 0, the client is TCP (CID 8) and `RW` is 1. A write to a present
   read-only PTE would set only the write bit.

2. **The host has no read-only GPU mapping at these addresses.**
   - Read-only userptrs exist only for the r--/r-x anonymous VMAs, i.e. module images.
   - Direct-memory, AMM and heap mappings, the zero buffer and the aliases of writable sources are all
     mapped R|W|X (`direct.cpp`: `map_shared`, `map_alias`).
   - The AMM pages the title maps GPU-only (F87, prot 0x30/0x90) get CPU read/write on the host, and
     the GPU's view of them is R|W|X like every shared mapping.
   - The code aliases lie under a non-zero address byte 47:40, away from these addresses.
   - So the pages are either unmapped for the GPU, or not guest memory at all.

3. **Cases A–D: the address lies inside a buffer that a clear dispatch writes in full.** Each
   timed-out graphics buffer holds the dispatch. Its first four user-data dwords are a V# whose extent
   contains the fault (`raw/clears.txt`). The probe found the dispatch executed ("ran") and gives its
   program (`raw/journal-lines.txt`).

   | Case | V# base | Stride × records = extent | Groups × 64 | Fault offset | Markers around it | Program |
   | --- | --- | --- | --- | --- | --- | --- |
   | A | 0x8518580000 | 4 × 0x1c0000 = 7 MiB | 0x7000 × 64 = 0x1c0000 | +0x18000…+0x1f000 | ClearUnorderedAccessView | 0x11d0288800 |
   | B | 0x84a6860000 | 16 × 0x6000 = 0x60000 | 0x180 × 64 = 0x6000 | +0x20000…+0x49000 | RTV First-Use Init Clear › ClearRenderTargetView | 0x11d0288a00 |
   | C | 0x820c240000 | 16 × 0x2c000 = 0x2c0000 | 0xb00 × 64 = 0x2c000 | +0x13c000…+0x166000 | RTV First-Use Init Clear › ClearRenderTargetView | 0x11d0288a00 |
   | D | 0x83fda50000 | 16 × 0x6000 = 0x60000 | 0x180 × 64 = 0x6000 | +0x50000 | RTV First-Use Init Clear › ClearRenderTargetView | 0x11d0288a00 |

   - The dispatch has exactly one thread per record. Each thread writes one record, so the clear
     writes the whole extent.
   - In C and D the same buffer binds the surface as colour target 0 a little later:
     - `CB_COLOR0_INFO` format 10 (8_8_8_8);
     - `CB_COLOR0_ATTRIB2` gives 340×150 (D) and 1364×434 (C);
     - `CB_COLOR0_ATTRIB3` swizzle mode 27 (SW_64KB_R_X).
     - Field positions as the host's `size_tally` reads them; TODO(verify) the ATTRIB3 swizzle
       field against `tools/bc5-agc/regdb/gfx10.json`.
   - In 64 KiB blocks of 128×128 pixels those sizes are 3×2 blocks (0x60000) and 11×4 blocks
     (0x2c0000): the V# extents. The clear covers the surface's whole block allocation.
   - In C, the next pass after the clear is the title's UI middleware ("CoherentManager"). These are
     UI render targets in the AMM window.

4. **The faulting blocks have no guest memory at all.** After the timeout the host saves a learned
   window: 96 MiB, starting 32 MiB below the fault's 64 MiB boundary (`learned_add`). At the device
   reopen it maps the guest memory found there and gives every hole the 2 MiB zero buffer (`scratch_fill`, holes per
   `Bc5GuestRangesIn`).
   - Holes found: 0.2 MiB in A, 0.3 MiB in B (5 of the surface's 6 blocks) and 0.5 MiB in C (8 of 44
     blocks). D's journal ends inside the probe, but its window 0x83fa000000 is in the learned file.
   - No guest range means that no AMM map took effect on those blocks, so there was nothing for the
     direct mapper to drop.
   - This matches experiment 0101: the title's UI surfaces in the AMM window are sparse, and only the
     64 KiB tiles drawn into are backed.
   - The console must therefore drop writes to unbacked AMM pages (F161, AnyPS5's PRT model). The
     title's first-use clear relies on that.
   - The AMM pool refusals of F206 are journaled only with the AMM trace, which these runs did not
     have. So these journals cannot tell blocks the title never asked for from blocks the pool refused;
     experiment 0101's trace and the UI middleware's pass favour the first.

5. **Why only sometimes: the learned windows.**
   - Each such fault adds a 96 MiB learned window.
   - Its holes get the zero buffer, mapped R|W|X, so a later clear there writes into that buffer and
     does not fault.
   - 9 of the 102 learned windows lie in the AMM window: 0x8002…, 0x81b6…, 0x81c2…, 0x81c6…, 0x820a…,
     0x83fa…, 0x842e…, 0x84a2… and 0x8516…. Four of them (0x8516…, 0x84a2…, 0x820a…, 0x83fa…) come from
     cases A–D.
   - A UI target the title places elsewhere in the 64 GiB window faults once more. Where it lands
     depends on the run's AMM allocations, so new menus and new routes find new ones.
   - The zero buffer does not stay zero. It is one 2 MiB BO (`scratch_bo`), and every hole piece maps
     it from offset 0 with R|W|X (patch 0001, `scratch_fill`). A clear's writes into one hole therefore
     show up in every hole at the same offset modulo 2 MiB. The comment "its writes go nowhere" does
     not hold. This is a lead for F255 (passed to the water session), not tested.

6. **The freeze.**
   - In A–D the fault is followed after about 2 s by the timeouts of `comp_1.1.0` and `gfx_0.0.0`.
   - Of the timed-out jobs, one is the graphics buffer holding the clear.
   - Then the jobs in flight fail with -125 after the reset (C, E), and the game stops presenting.
   - Why a dropped TCP write stalls the ring here instead of being absorbed is not examined
     (TODO(verify)). F74 and F88 saw the same: a TCP fault, then a ring timeout.

7. **Case E (run L7) is a different fault.**
   - 0x1765833000 is outside the AMM window and in no guest range: after the reopen its whole 96 MiB
     window was holes (`raw/journal-lines.txt`).
   - Neither timed-out buffer has a pointer, V# or T# within 64 MiB of it, nor a first-use clear
     (`raw/l7.txt`).
   - The compute buffer is a "Lighting Prep" pass: a small UAV clear (0x11d0288800) and image passes
     over 0x114b200000 (1024×576) and 0x114b580000 / 0x113f190000 (256×144). The graphics buffer holds
     GBuffer Landscape, Landscape Mesh and Ray Tracing Update passes.
   - Their remaining descriptors come from tables in memory that the dumps do not contain.
   - The run had DMA snapshots off, an exp 0194 arm and not the launcher's setting.
   - A wild address computed from memory. Not identified.

Seen on the way, separately: the machine-down at 13:41 during experiment 0198's arm A
(`play-20261022-1337`) had a graphics-buffer timeout, no kernel fault line and a parity-error reset
(F256). It is not one of these.

**Verdict.** Answered for four of the five faults; the fifth is open.
- No read-only mapping is involved. The pages belong to the title's sparse UI render targets in its
  AMM window, and the title never backs them. Without PRT the GPU has no PTE there; with
  `BC5_DIRECT_AMM_PRT=1`, or inside a learned window's zero buffer, it would.
- The writer is the title's own clear: "RTV First-Use Init Clear" › ClearRenderTargetView (program
  0x11d0288a00, 16 bytes a thread) and ClearUnorderedAccessView (0x11d0288800, 4 bytes a thread). It
  writes every 64 KiB block of the surface's allocation; the console drops what lands on the
  unbacked blocks.
- The host already has the fitting switch, off by default: `BC5_DIRECT_AMM_PRT=1` (experiment 0102:
  accepted by the kernel, no fault in run 371, re-applied at every device reopen). It is in both the
  shared and the diagnostic build, so no build is needed.
- Next, on the GPU and only with the maintainer present (D16: one short run): the normal shortcut with
  the switch, `play-prt-0199.sh`, through menus and the outpost/lake route. Expected: no TCP write
  fault at first-use clears.
  - To make the test sharper, add a copy of the learned file without the nine AMM windows
    (`BC5_DIRECT_LEARNED`), so the clears meet unbacked blocks.
  - To separate "never mapped" from "refused by the pool", add `KYTY_BC5_AMM_TRACE=1`.
- With PRT on, `scratch_fill` still maps the shared zero buffer over the holes of the nine learned
  windows inside the AMM window, so those holes would keep the writable shared buffer instead of
  PRT. A complete fix would skip `scratch_fill` inside the PRT window (not implemented; behind the
  same switch).
- The PRT window is fixed at 0x8000000000 + 64 GiB. Every AMM fault so far was at 0x82–0x85…, but the
  guest's AMM reservation should be checked in that run's log.
- Case E stays open. The next capture of it needs the dispatch journal's user data and the memory
  tables those dispatches read.
