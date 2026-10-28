# 0368 — F403's class: which program is resident and not ending?

**Date.** 2026-10-28 (18:5x–19:xx). **Branch.** `exp/0300-rt-dispatch-sync`. **Box.** Offline so far; no run.

**Question.** F403's class — a GFX ring timeout with no fault, waves busy, the CP inside the host's GFX-form
indirect-dispatch check — is the one machine-down risk left with RT on (F476: one in ~25 S6N RT-on runs since the
cut). Across F403's three freezes (2026-10-26 10:08, 12:20, 12:21), F416's R2 (2026-10-27 12:39) and exp 0364's R4
(2026-10-28 18:15): which program is resident and not ending? Always the same family (the BVH build or traversal)?
A loop whose exit depends on data a lost or late job should have written (F360-like), or a compute shader waiting on
a label? Then the arm: B, a bisection with `BC5_DIRECT_SKIP_PGM` on the bench, or A, exp 0137's wave-side loop bound.

**Setup.** Read-only: the five devcoredumps (`~/bc5-data/captures/devcoredump/20261026-100846-devcd1`,
`-122011-devcd2`, `-122144-devcd3`, `20261027-123919-devcd1`, `20261028-181505-devcd2`), the timeout probe's dispatch
lists in the journals of the captures that timed out (`play-20261026-1216`, `-1220`, `play-20261027-1237`,
`play-20261028-1813`; 10:08's capture has no journal), the host's code for `BC5_DIRECT_UMR_ON_TIMEOUT` (exp 0058)
and the box's sudo rules. Nothing of the title leaves the box.

## Result

- **F490 — the five devcoredumps are one CP state; the CP's place in the IB is not the stuck dispatch's.** Every dump
  has `CP_PFP_INSTR_PNTR` 0xe9f–0xea1 and `CP_ME_INSTR_PNTR` 0x77a–0x77b, `GRBM_STATUS` 0xa0407028, SE0/SE1
  0x0a000016 (0x0a000036 on 10-26 10:08; exp 0334 read these as SPI, TA, TCP and GL1/GL2 busy: waves alive), and the
  PFP's and ME's header dumps hold the host's check sequence around `DISPATCH_INDIRECT` (`ACQUIRE_MEM`, `EVENT_WRITE`,
  `DISPATCH_INDIRECT`, `COND_EXEC`, `PFP_SYNC_ME`, `WRITE_DATA`, `COND_EXEC`, `PFP_SYNC_ME` on the PFP; `… COND_WRITE`,
  `COND_WRITE` last on the ME), eight times over in 10-27's dump. The CP's position in the host IB differs: the end
  (10:08, `CP_IB1_BUFSZ` 0), 91 % (12:20), 88 % (12:21), 57 % (10-27 12:39, a 6,584-dword piece of a 17,748-dword dcb),
  15 % (R4: 1,920 of 12,248 dwords). The PFP prefetches ahead and stops at a `PFP_SYNC_ME`; the ME stands in the check
  of the next indirect dispatch; the waves that never end belong to a dispatch the ME launched earlier — in the same
  IB or the one before it (the check's `ACQUIRE_MEM` waits for all prior work). So the position bounds the candidates,
  it does not name one. No dump holds SQ or SPI wave registers (0 lines in each).
- **F491 — the dispatch lists do not share one program, and R4 is the first event without a runaway grid.** The
  10-26 and 10-27 lists carry the leaf builder 0x909936c00 with garbage grids (±inf as integers: 2139095040 =
  0x7f800000, 3158704128, …), most marked DROPPED by the host's limits and a few marked ran (12:20: one
  1089029120×1077575680×3220189184 at dword 454; 10-27: 3158704128×1000603648×1074773504 at 444 and two 2139095040³ at
  552 and 624; TODO(verify) the probe's "ran" mark for a dropped dispatch) — F403's runaway reading stands for them —
  and 10-26's two hold the reflection traversal 0x11d049aa00 (F113/F116) once each. R4's dcb #103567 has neither: 53
  dispatches with sane grids, the refit-like family 0x11d02a…/0x11d028ae00 (2869×1×1 ×3, 3543×1×1 ×7, arguments at
  0x11d05df300 / 0x11d0571b00) at 1289–1470 before the ME's position and again at 3310–3872, the helpers 0x11d0288800
  (index/argument replicate, up to 24,576 groups) and 0x11d0288a00 later, the direct 320×180 dispatches at 7007–10652.
  R4's candidates are 0x11d02a1800, 0x11d028ae00, 0x11d02a1600 (the three before the ME) or waves of the previous
  IB; the 0x11d02a… programs are not named anywhere in the repo. A sane grid that never ends is a data-dependent
  loop (F113's traversal over a bad tree is the known shape) or a shader spinning on a flag another job writes
  (F360's shape); a label wait on the CP it is not — the ME's last packets are the check's `COND_WRITE`s, not a
  `WAIT_REG_MEM`, in all five.
- **F492 — the program can be named at the next event with what the host already has: `BC5_DIRECT_UMR_ON_TIMEOUT=1`
  (exp 0058) dumps the halted waves 0.9 s into a stalled completion wait, before the kernel's 2-s reset, through
  `sudo /usr/local/bin/bc5-gpu-hang-dump` (registers, `umr -O halt_waves -wa gfx_0.0.0`, the gfx ring with its IBs,
  the fence info; NOPASSWD in the box's sudoers), into the capture directory, synced at once.** F113's program and
  PCs came from that path. None of the five events ran with it (the journals have no `umr:` line and no dump file
  exists). The switch is in the shared build; no private build is needed.

**Verdict.** Offline, the five dumps place every event in one CP state (F490) but name no program (F491): the
devcoredumps carry no wave state, and the lists differ. Neither arm can be chosen blind — A needs the loop and its
program, B needs a reproduction rate the bench does not give (one in ~25 runs). The step that decides is the wave
dump at the next event: the bench's S6N RT-on runs and the maintainer's test shortcut with
`BC5_DIRECT_UMR_ON_TIMEOUT=1`, each box run announced with its lock time; the dump then says whether it is the
traversal's loop (arm A, exp 0137's mechanism) or a refit/build program to skip and bisect (arm B). The risk is the
class's own: the event ends the box either way; the dump adds nothing to it (umr halts the waves the kernel is about
to reset) and is written before the reset.
