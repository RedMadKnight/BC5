# Exp 0401 series e4: survey items 7 and 10 (PRT zero pages, VideoOut output status) — notes, 2026-11-03

These are items 7 and 10 of exp 0402's Top 10 (`bc5-0402/experiments/0402-related-projects-survey/README.md`, §3
"Sparse/PRT"). The work was read-only on the laptop: no box access, no compiler, no tree edited.

**Result: neither item is missing and reachable.** So no `mkprt0401.py` or `mkvo0401.py` was written, and the switches
`KYTY_BC5_PRT_ZERO_PAGES` and `KYTY_BC5_VIDEOOUT_STATUS_UHD` do not exist. This file is the only output.

## Inputs read

Our effective code is KytyPlus f266548 + patch 0001, the series e4 tree
(`…/19eb012d-…/scratchpad/e4/full/src`).

| File | md5 | Used for |
|---|---|---|
| `src/libs/libAmpr.cpp` | a0e2ff6e6fcbcae83847107243b35319 | item 7 |
| `src/kernel/memory.cpp` (tree) | f61546925dcf96ee9bbc1278b0f8ae6c | item 7 |
| `src/kernel/memory.cpp` (the private next build, `memout`) | 43713ef677ec887a8ca273f7ab5cee90 | item 7: its diff against the tree has no PRT line; not needed |
| `src/libs/libKernel.cpp` | 3bf94a6168d176d591730bac33dff5b1 | item 7 |
| `src/libs/bc5LleAgc.cpp` (read only) | d18b448299a335aadac75bbd202155fd | item 7 |
| `backend/src/direct.cpp`, `backend/include/bc5/direct.hpp` (bc5-0401 checkout `ca552261`) | 51279eaeb0df4225d69ce0a60587cdb9, a9fcb26bc48efa2dc19cb0523bfd7a60 | item 7 |
| `src/libs/libVideoOut.cpp` | 572eada279bbc10cffcba51d4b4bdeb5 | item 10 |
| `src/graphics/presentation/videoOut.cpp` | f848f5c6b81196e9722f3c7caf3984ec | item 10 |
| `src/libs/agc.cpp` | 78b3fd7194f7ce013f907ce391f86011 | item 10 |
| `src/common/emulatorConfig.h` | cca91191d6ef76d230247beecf64ba1f | item 10 |
| `src/main.cpp` | ce505124c2ff0a62c6d2e423960af2c7 | item 10 |

Other sources:

- **AnyPS5** (GPL-2.0-only) at `4f41f4c37`, plus commits `e3b5192cb`, `79fc99774` and `37881a5da`. Files:
  `core/libs/prx/libkernel/Apr/src/Apr.cpp`, `core/libs/prx/libkernel/DirectMemory/DirectMemory.cpp` and
  `core/libs/prx/libSceAmpr/Export.cpp`.
- **sharpemu** (GPL-2.0-or-later) at `b1ec286`: `src/SharpEmu.Libs/VideoOut/VideoOutExports.cs`.
- **Stub lists:** exp 0327 `raw/S1-stub-list.txt` and `S1-stub-list-resolved.txt` (197 imports), and exp 0329
  `raw/S2-stub-list.txt` (the last 10).
- **Our experiments:** exp 0291 (README and `raw/A-videoout.txt`, `raw/B-videoout.txt`); HANDOFF F161, F162, F255,
  F257, F258, F260, F261, F277 and F354.

NIDs were computed with the exp 0327 / `nid0401.py` calculator (SHA-1 of name + salt). It was self-checked on
`strcmp` and on `sceAmprAmmCommandBufferMap` = `JEVYGhDc97M`. It also hashed all 131 `sceAmpr*` names in AnyPS5's
`libSceAmpr/Export.cpp`, and each of the 92 NIDs in our `libAmpr.cpp` matched one of them.

## Item 7: PRT zero-page model. Verdict: not applicable (the title cannot reach the path)

**What AnyPS5 does.**
- Zero pages exist only for ranges the title itself declares PRT through AMM commands:
  - `_ammMapAsPrt` and `_ammUnmapToPrt` map the range with `_zeroPrt`, a zero mapping with GPU-read protection 0x10
    (`Apr.cpp:417-447`, `DirectMemory.cpp:1284-1293` `DoMapZero`).
  - `_ammAllocatePrt` (`Apr.cpp:450-478`) needs a PRT range (`_requirePrt`). It backs only the unbacked runs through
    `AmmPool::MapScattered` and restores `_zeroPrt` on failure (`e3b5192cb`, `79fc99774`).
- An AMM page that is never mapped, or that `_ammUnmap` releases, goes back to the reservation (`_reserve`,
  `Apr.cpp:387-390`, `423-430`). It is not a zero page.
- On Windows the zero pages are views of one read-only section (`37881a5da`).
- Their stated semantics (debt note `docs/dev/debt/libkernel.md:61`): reads return 0 and GPU writes fault. The effects
  are "inferred from the names, not confirmed on a title".

**Our host registers no AMM PRT command.**
- `libAmpr.cpp:3648-3741` registers 92 Ampr NIDs. Hashed against AnyPS5's names, every one is a non-PRT function.
  The AMM encoders are `Map`, `MapWithGpuMaskId`, `MapDirect`, `MapDirectWithGpuMaskId` and `Unmap` (`3730-3740`).
- The host-side command record has only three AMM kinds, `MapAuto`, `MapDirect` and `Unmap` (`libAmpr.cpp:943-947`).
  A PRT command cannot be recorded or executed at all.
- These NIDs appear nowhere in the tree:

  | Name | NID |
  |---|---|
  | `sceAmprAmmCommandBufferMapAsPrt` | `ZJCgt+aPHAU` |
  | `…AllocatePaForPrt` | `d3lKWPM6odc` |
  | `…RemapIntoPrt` | `0Xo9g4goDXU` |
  | `…UnmapToPrt` | `3A2X6OCHtnA` |
  | `sceAmprAmmMeasureAmmCommandSizeMapAsPrt` | `4SSJ+cn+Pvg` |
  | `…AllocatePaForPrt` | `2yYv9QWB3hU` |
  | libkernel `sceKernelWriteMapAsPrtCommand` | `b2kyWqWFno0` |
  | libkernel `sceKernelWriteUnmapToPrtCommand` | `vnKYv2NuO5U` |
  | libkernel `sceKernelWriteRemapIntoPrtCommand` | `RPAHEYSOt1s` |

**The title imports none of them.**
- The link-time stub list names every import the host does not register (exp 0327 README, the `runtimeLinker.cpp`
  line).
- None of the NIDs above is on it.
- It has no `Ampr_v1` line at all, so every Ampr import of the title binds to one of the 92 non-PRT functions. This
  holds whatever the console's names are.
- Its four `libkernel_v1` lines are `rmdir`, `sceKernelInternalMemoryGetModuleSegmentInfo`, `sceKernelMlock` and
  `signal`. Its only unresolved NIDs are NpCppWebApi.
- The programs on the list are `eboot.bin` and `sce_module/libc.prx`. `libSceAmpr.sprx` left the second title's
  module pack in exp 0035 (HANDOFF Q14).

**Our model already covers more than theirs.**
- `BC5_DIRECT_AMM_PRT` (`bc5LleAgc.cpp:1259-1263`, and again at the reopen, `:5401`) maps the whole 64 GiB AMM window
  0x8000000000 as `AMDGPU_VM_PAGE_PRT` without a BO (`direct.cpp:886-895`).
- Mappings inside the window replace the PRT pages, and unmaps restore them (`direct.cpp:90-105`, the RADV sparse
  pattern).
- It has been the launcher default since 2026-10-22 (F277).
- Every unbacked AMM page therefore reads 0 and drops writes (exp 0102, F162), whether or not the title ever declared
  it PRT.
- F161's sparse UI layer is exactly that case: pages never mapped, with no PRT command. AnyPS5's model would leave
  those pages reserved, so a port would not even reach F161.
- `sceKernelSetPrtAperture` and `sceKernelGetPrtAperture` are a different, registered API (`libKernel.cpp:3472-3473`,
  `memory.cpp:1130-1150`, `2532-2600`, `3698`) and not part of this item.

**The write side (ours drops, theirs faults) cannot be decided by testing this path, because it is unreachable.**
- The only evidence on this title points to "not a fault".
- Its own first-use clears write 64 KiB blocks of UI surfaces it never backs (F257). On our stack a fault there
  meant ring timeouts and a freeze (F257). Under PRT the same writes were absorbed in two fault-free sessions (F260).
- This is weak: F257 is only medium that those blocks are unbacked by design rather than refused.

**One idea from `37881a5da` does apply to our code. It is described here, not done, because it is a
`bc5LleAgc.cpp` change.**
- `scratch_fill` (`bc5LleAgc.cpp:2229-2324`) maps one shared, writable 2 MiB scratch buffer over the holes of each
  learned window (`:2353`) and of the heap guards (`:2357-2370`). It does not leave out the device's PRT windows.
- `map_shared` inside a PRT window replaces the PRT pages. So with `BC5_DIRECT_AMM_PRT` on, any hole of a learned
  window inside 0x8000000000-0x9000000000 reads whatever last landed in the shared buffer, not 0.
- AnyPS5's `37881a5da` made its zero pages one read-only section precisely so that "no view of it can be made
  writable".
- **Change:** in `scratch_fill`, after the guest-range `cut`, also call `cut(0x8000000000ull, 0x9000000000ull)`
  while the AMM window is PRT. Add one journal line with the bytes left to PRT. Put it behind its own switch in the
  series' style.
- **Gate:** a read-only check that the box's `~/bc5-work/direct-learned.txt` still holds windows in that range. F257
  counted 9 of 102 there, and F260's run X1 used a file without them.
- **Expected effect:** small. F261 found the frozen lake as patchy with PRT and no shared buffer in the AMM window as
  with the defaults. The change would only make "reads 0" hold for the whole window.

## Item 10: `sceVideoOutGetOutputStatus` before buffer registration. Verdict: not applicable (already measured, exp 0291 / F354)

**What our host answers, before and after registration.**
- `VideoOutGetOutputStatus` is at `videoOut.cpp:1837-1863` and is registered at `libVideoOut.cpp:38` (NID
  `utPrVdxio-8`).
- `resolution` is `ctx->width >= 3840 || ctx->height >= 2160 ? 2 : 1` (`:1850`). `dynamicRange` is 1. `refreshRate`
  is 59.94 Hz, or 119.88 Hz in the 0xF mode or with `--vblank-frequency` ≥ 119.
- `ctx->width` and `ctx->height` are written only in `Impl::Init` (`:666-670`). The value comes from
  `VideoOutInit(width, height)` (`:646-650`), called from `agc.cpp:57-61` with `Config::GetScreenWidth/Height()`.
  Those are set by `--screen-width` / `--screen-height` (`main.cpp:246-249`) and default to 1280×720
  (`emulatorConfig.h:62-63`).
- `VideoOutRegisterBuffers2` (`:1418`) does not change the size.
- The launcher passes no `--screen-width` (exp 0291 setup). So the host answers **1, the HD class**, before and after
  registration.
- This is the same placeholder-size behaviour sharpemu had before `b1ec286`. With `b1ec286`, sharpemu answers 2 on a
  Gen5 port while no buffer group is registered.

**The title calls it before registering, and the answer does not matter.**
- Exp 0291's test binary journaled both arms, one 300 s run each.
- In `raw/A-videoout.txt` the first line is
  `GetOutputStatus call 1 (handle 1) -> resolution 1 … VideoOut size 1280x720`. The second is
  `RegisterBuffers2 set 0, 2 buffers from index 0: 3840x2160`.
- Arm B told the title 2 at that same single call, which is exactly sharpemu's answer. It registered the same two
  3840×2160 buffers, with the same GPU time (14.3 against 14.4 ms per frame) and frame rate (39.4 against 40.0
  flips/s) (F354).
- sharpemu's symptom, a viewport laid out for 4K over 1080p buffers, cannot occur here, because this title always
  registers 3840×2160.
- A `KYTY_BC5_VIDEOOUT_STATUS_UHD` switch would only repeat arm B.

**What a journal would show.**
- Today's shared build: nothing. The launcher runs with logging silent. With logging on, the `PRINT_NAME` line for
  `VideoOutGetOutputStatus` comes before `VideoOutRegisterBuffers2`, once at start.
- With the sharpemu change the status call would read `resolution 2`. The `RegisterBuffers2` line would be
  unchanged, as in exp 0291's `raw/B-videoout.txt`.

## Doubts

- **Item 7, the stub lists are dated.** They were taken on 2026-10-25 (exp 0327 S1) and after exp 0329. The title on
  the box has not changed since: the maintainer keeps his game update to himself.
- **Item 7, dynamic resolution.** A PRT export resolved at run time through `sceKernelDlsym` would not appear on the
  list. Nothing suggests one.
- **Item 7, pack modules.** The list names only `eboot.bin` and `libc.prx`. This assumes the 0327 linker line is
  written for pack modules too (`libSceAgc`, `libSceAgcDriver`, `libScePsml`). Even if they imported a PRT command,
  our host has no PRT command to bind it to.
- **Item 7, the write side.** Drop against fault is unproven both ways, as the survey says. Our "drop" is the
  hardware's PRT behaviour on gfx1013 (exp 0102), not a console fact.
- **Item 10, scope of exp 0291.** It ran with RT off (before the 2026-10-28 RT-on rule), one run per arm, on one
  route. The title asked once in 300 s; a later query, for example from a display-settings screen, was not seen.
- **Item 10, the meaning of 1 and 2.** It is still TODO(verify) (exp 0291). sharpemu's "a PS5 reports what the
  display chain can take" comes from one title's behaviour, not a console measurement. A console on the maintainer's
  1080p display might answer the HD class too.
