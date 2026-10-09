# 0035 — AMM and AMPR in the host: what stopped the second title, and the fixes

**Question.** Experiment 0034 ended the second title (started from its PS5 package) 20 s in, at
a read in a range reserved as `AMM`. What does the host's AMM/AMPR emulation get wrong, and how
far does the title get once it is right?

**Setup.** BC-250, the track-B host (KytyPlus f266548 + patch 0001 at this commit), the package
mounted by `bc5-mount`, the launcher of experiment 0034 with the system module pack minus the
game's own `libSceAmpr.sprx` (`PACK_DIR=~/bc5-data/sysmodules-pack-hle-ampr`; with it the result
is the same, the host's HLE serves the calls either way). Unattended runs of 60–300 s,
2026-10-09. Diagnostics added for this (all behind `KYTY_BC5_AMM_TRACE=1`): every AMPR library
entry, every AMM map/unmap with its result, every APR file read, every submission with its
command counts, `SetBuffer`, `WaitOnAddress`/`WriteAddress` arguments, and for a fault in a
reserved range the faulting instruction (guest module + offset, or host module, symbol and
backtrace). gdb (`gdb-sigill.sh`, passing the host's own signals) was used to read the title's
code at its trap. Public references read as documentation only: prosper's notes
(`docs/PORTING.md`, `KHAZAN_STATUS.md`, `UE4_APR_IOSTORE_BRINGUP.md`, comments in
`hle_kernel_mem.cpp`; the project has no licence, no code taken).

**Result.** Each fix moved the stop further; in order:

| # | What the trace showed | Cause | Fix in patch 0001 |
|---|---|---|---|
| 1 | The title reads 0x1112642b68, inside its own `FileSystem` mapping (0x1110000000, 52 MiB), whose host pages are an inaccessible placeholder (`---p`) | `AmmGetVirtualAddressRanges` reserved the 64 GiB AMM window **at a fixed 0x1000000000 with MAP_FIXED**, after the title had already mapped twenty heaps there (`InitAllocator`, `DynamicHeap`, `FileSystem`, `RenderGpu*` …, placed there by the host's own address allocator): the reservation replaced them all | the window is reserved once, where the host has room, and its real address is returned (`AmmWindowStart`) |
| 2 | With the window elsewhere, the title runs 180 s; the APR engine's file reads copy into AMM pages and fault in host `memcpy` | the title maps AMM pages with protection 0x30/0x90 (GPU and AMPR only, no CPU bits), so the host mapped them without CPU access, and the host is the one emulating the DMA | AMM pages without CPU bits get host read/write (`ExecuteAmmMapCommand`) |
| 3 | A read into the AMM window before anything mapped it; 174 `AmmCommandBufferMap` calls, 155 executed | the APR buffer carries `WaitOnAddress(counter, value, op 4)` until the title's sequence counter reaches the value it bumps once its AMM maps are submitted; the host recorded waits as no-ops and ran every buffer at submit time | `WaitOnAddress` is a real command: a submission stops at an unmet wait, later APR submissions queue behind it in order, AMM-only submissions run at once, and a `bc5-apr-wait` thread re-checks every 0.5 ms (op 4 as ≥, op 3 as =) |
| — | (earlier, on the way) | APR `MapBegin`/`MapDirectBegin` were recorded as no-ops | they map their range when the buffer runs (not exercised by this title) |
| — | | `SetBuffer`'s map flavour (prosper's notes: `a3 != va`, `a4 = -1`) unhandled | implemented; this title only uses the buffer flavour |
| — | | a fault in the AMM window ended the run | optional lazy commit of 64 KiB pages (`KYTY_BC5_AMM_LAZY_COMMIT=1`, off by default: it hid cause 1 by replacing a live page and was the wrong fix), and never over a page the host already maps |

After fix 3 the title runs its loading with 9 submissions parked at waits, 88 resumed and 79
queued in order, through 144,000 lines of guest output, calling `sceNpEntitlementAccess*`
(stubs) in its loop, and stops at a null read in its own code (`eboot` +0x5e6e303, `rax` = 0,
`rbx` = 0x1200002220 in its `RenderGpuRwSmall` heap). That stop is not an AMM fault.

**Verdict.** Passed for AMM/AMPR as this title uses it: the window placement, the protection
of DMA-written pages and the in-order waits were the three gaps; with them closed the title
loads for minutes instead of 20 s. Not yet known: what the null read at +0x5e6e303 depends on
(next step), the meaning of the wait ops other than 3 and 4, and whether the AMM window's
"multimap" half (returned as the upper 32 GiB) matters for any title.
