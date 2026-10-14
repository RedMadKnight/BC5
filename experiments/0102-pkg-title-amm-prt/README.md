# 0102 — the AMM window as PRT pages: no fault, but the menu background stays black

**Question.** Experiment 0101 found the second title's UI layer sparse: only 8 tiles are backed.
If the GPU reads the unbacked rest of the AMM window as zero (PRT semantics, as the console
evidently does), is the menu's background scene shown?

**Setup.**
- Backend (commit f9d392b): `Device::map_prt_window` maps a VA window as PRT pages (amdgpu
  `AMDGPU_VM_PAGE_PRT` without a BO: reads 0, writes dropped).
  - Userptr and shared mappings inside the window use `AMDGPU_VA_OP_REPLACE`.
  - Their unmapping replaces them with PRT pages again.
  - This is how RADV binds and unbinds sparse memory (Mesa
    `src/amd/vulkan/winsys/amdgpu/radv_amdgpu_bo.c`, 0866ae7).
- Host: `BC5_DIRECT_AMM_PRT=1` maps 0x8000000000 + 64 GiB that way at device open.
- Run 371 (2026-10-14 23:04, `run371.sh`), with the maintainer present and the hang watcher on.
  The play shortcut's settings (undeferred flips, `multi`, aliases), a fresh save, one cross,
  then menu navigation.

**Result.**
- "bc5-direct: PRT window 0x8000000000+0x1000000000: 0": the kernel accepted the PRT mapping.
- No GPU fault, timeout or ring stall.
- The menu is drawn and its text is clean. The background is still black.
- The emulator ended at about 105 s with exit code 0, before the 130 s limit. The window was
  closed: by the maintainer, or by the title. TODO(verify).
- The direct path's zero-buffer fill of holes (experiment 0037) puts nothing in the UI layer's
  range, so it does not explain the black either.

**Verdict.** Failed: reading the unbacked AMM pages as zero does not bring the background back.
The opaque black is therefore in data the layers actually hold, not in their holes. Two places
are left:
- UI layer 1 (0x80d36d0000, fully backed), or the 8 backed tiles of layer 0, may hold opaque
  black;
- the blend's destination (0x114c6c0000) may not hold the scene when the pass runs.

The knob stays, off by default. The PRT window is harmless with this title and still matches the
console for its sparse surfaces.
