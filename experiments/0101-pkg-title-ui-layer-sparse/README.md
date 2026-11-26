# 0101 — the second title's UI layer is a sparse surface: it maps only the tiles it draws on

**Question.** UI layer 0 is only about 1.5 % mapped when the final pass uses it (experiment
0100). Does the title map the rest at some point, perhaps through AMM commands we execute late or
not at all?

**Setup.**
- Run 370 (2026-10-14 22:46): the play shortcut's settings, a fresh save, one cross.
- KytyPlus's AMM trace was on (`KYTY_BC5_AMM_TRACE=1`, experiments 0035 and 0043): every map,
  unmap, pool operation and AMPR command with the monotonic clock. 47,995 trace lines.
- The maps and unmaps overlapping layer 0 (0x81dacf0000 + 33,423,360 bytes) were filtered out.
  Raw: `raw/run370-amm.txt`.
- Our KytyPlus implements only Map, MapDirect and Unmap of the AMM command set. The title imports
  no other AMM function: none appears among its unresolved stubs. The remaining stubs are
  `sceKernelGetOperationMode` and `fsync` (names from the local ps5rs NID list).

**Result.**
- Over the whole run, the title maps exactly 8 pieces inside layer 0, all at about the same
  moment (when the menu is built), with protection 0x90 and no unmap:
  - 0x81db094000 +0xc000, 0x81db348000 +0x18000, 0x81db8a4000 +0xc000, 0x81dbb54000 +0xc000;
  - 0x81dbe08000 +0x8000, 0x81dc364000 +0xc000, 0x81dc618000 +0x18000, 0x81dcb74000 +0xc000.

  Experiment 0100's coverage listed 9 pieces because two neighbours were counted separately.
- Nothing else is ever mapped there.
- Whole run: 4,805 automatic maps, 725 unmaps, 137 fixed maps, 207 waits on address, 6,736
  write-address commands.

**Verdict.** Answered:
- The UI layer is a sparse (partially resident) surface. The title backs only the 64 KiB tiles it
  draws menu elements into, and leaves the rest of the 3840×2160 layer without memory, on the
  console too.
- That only works if unbacked pages read as zero (transparent) and writes to them are dropped.
  This is AnyPS5's model for such pages (its PRT path), and evidently what the console's GPU does
  in the AMM window.
- On our GPU, the unbacked part reads as something that composes as opaque black. That is the
  black menu background.

Fix to build:
- give the GPU's view of the AMM window PRT semantics: amdgpu's `AMDGPU_VM_PAGE_PRT` mappings read
  0 and drop writes;
- lay the title's real AMM mappings over that.

It changes how the direct path maps memory for the GPU, so it is tested only with the maintainer
present.
