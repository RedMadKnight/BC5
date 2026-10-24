# 0266 — The night lake: the depth in the patch cells, clean against patched reads of one run

**Question.** Within a run, every lake draw compared so far is issued identically in clean and
patched frames (F313, F320, F323), so the patch state comes from memory those draws read. Exp 0248
(F307) saw, in reads of one run, the patch cells hold depth unlike the lake around them; but its
clean reads caught the G-buffer before the lake surface and it never compared clean and patched
reads at the same frame size. Within one run with both states, at one frame size, what depth do the
patch cells hold in clean reads and in patched reads?

**Setup.**
- Granted by the top session after exp 0262: 1–2 runs, same data rules (reads in
  `~/bc5-data/priv/exp0266`, summarised, then deleted). After the maintainer's afternoon play and
  the top session's exp 0267 integration, GO at 17:06 for W266a and, after the fault below, an
  explicit GO at 17:09 for W266b. Boot 9f3e0da8; `/var/home` at 71–72 %.
- **Binary:** exp 0251's private `kyty_emulator` (`~/bc5-work/exp0251`, built 2026-10-23 22:06), through
  the bench's own launcher copy; not today's shared builds.
- **Run:** `ab0266.sh` / `bench0266.sh` (exp 0262's, renamed; the full-screen draw journalled with
  `_EVERY=10` for the frame sizes over time) and, started by hand, `capl0266.sh`: every STEP s, the
  whole depth memory (0x1129ec0000 + 0x2940000, exp 0251) and the G-buffer target (0x113f230000 +
  0x1860000, exp 0240) through `/proc/<pid>/mem`. The render size changes every few frames, so many
  reads are taken and only reads of the same size are compared.
- **`ana0266.py`:** the frame size of each read by block-row shear, completeness (both images
  coherent), the cell mask from the run's patched shots, and inside the cells against the rest of
  the lake window: depth median, depth-0 share, G-buffer cleared share and the depth step at the
  cell edges; grouped by (size, state). No image is written.

**Run W266a (stopped on a GPU fault).**
- **When:** started 17:03:57 after the top session's GO (17:06 on its clock, after the maintainer's
  play). The live saves' checksum was 2f5d956c8f1b6ebd before and after; the change from earlier
  values is the maintainer's play.
- **The fault:** at t ≈ 95 s, while the lake save was still loading and before the frozen view or
  any journal window, the GPU raised six write page faults (`raw/W266a.kern.txt`):
  - gfxhub, vmid 7, pasid 165, client TCP through UTCL2;
  - `GCVM_L2_PROTECTION_FAULT_STATUS` 0x00741051, PERMISSION_FAULTS 0x5, RW 1;
  - pages 0x145e628000–0x145e62d000, from the emulator's Render Thread.
- **What followed:** compute ring comp_1.1.0 and gfx ring timeouts from the bc5-ring thread, with
  resets that succeeded ("device wedged, but no recovery needed"), and two devcoredumps.
- **What the driver did:** `ab0266.sh` stopped the run on the new kernel lines, as designed. The
  emulator ended at 17:05:34, and the bench removed its lock. The reader (`capl0266.sh`) had not
  reached a frozen-view shot, so no reads were taken; it was stopped.
- **Afterwards:** the box stayed up, with the amdgpu dmesg count at 170 (from 120). This is the TCP
  write-permission fault class another session investigates, on exp 0251's private binary. The
  details went to the top session for that session.
- The devcoredump is root-only. The top session reports it expired unread at about 17:10; the
  kernel stream holds the fault lines. W266a's run directory and journal were left on the box
  for that session.

**Run W266b: clean throughout.**
- **Box state.** 17:09–17:16 on the same binary. No kernel fault, timeout or reset: the amdgpu
  dmesg count stayed at 170, and the stream (`raw/W266b.kern.txt`) has only routine lines. The
  live saves' checksum was the same before and after (2f5d956c8f1b6ebd).
- **Shots.** All 26 frozen-view shots were clean (0.8–1.0 %).
- **Reads.** `capl0266.sh` took 20 reads, from ts00 to ts25, 1.3 GB, deleted after the summary.
  `ana0266.py` (`raw/W266b.ana.txt`) found 13 of them complete: 3072×1728 ×5, 3328×1872 ×4,
  2816×1584 ×3 and 2304×1296 ×1. The other 7 caught a frame mid-update (G-buffer shear 3.5–12.7).
- **No cell mask.** With no patched shot there is none, so the clean/patched comparison has no
  data.

**Verdict.**
- **No answer to the question.** Neither run gave both states: W266a stopped on a GPU write fault
  during load, and W266b stayed clean. That used the grant's two runs.
- **The method works.**
  - 20 reads at 7-s steps give about 4–5 complete reads at each of the two common sizes
    (3072, 3328).
  - `ana0266.py` finds each read's size and completeness from the data.
  - A run with both states would allow the comparison.
- **W266a's fault is the other result.** It is a TCP write-permission fault with compute and gfx
  ring resets, during load, on exp 0251's private binary (built 2026-10-23 from the shared tree
  of that day). The fault details went to the session that investigates that fault class.
- **Next:** the same run again, possibly more than once, until one run shows both states (as
  exps 0253, 0257, 0261 and 0262 needed one to three tries).
