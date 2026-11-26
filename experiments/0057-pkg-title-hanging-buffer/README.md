# 0057 — the second title's hanging graphics buffer, from safe runs

**Question.** With the indirect draws (0054) and the code region aliased under 0x80 (0056) the
second title hangs the GPU at its first scene change, and the reset takes the machine down. Is it
the draws' arguments, the multi-draw packets, or something in the buffer itself?

**Setup.** Host (patch 0001):
- `BC5_DIRECT_INDIRECT_DRAWS=1` now lets only `DRAW_INDIRECT` through; the multi-draw packets
  need `=multi`.
- The CP's check of an indirect draw is ≤ 2^20 vertices and ≤ 64 instances (was 2^22 and 1024).
  The title's largest draw seen has 94,322 vertices and one instance.
- `BC5_DIRECT_IB_DUMP=<min>:<max>:<t0>:<count>[:<dir>]` writes buffers of a size range, as the
  game wrote them, to a private directory.

Runs:
- 254: aliases, no indirect draws.
- 255: `DRAW_INDIRECT` only with the new limits, plus aliases.
- 256: neither (safe); dumps the 2,400–2,700-dword buffers from 130 s, and every new program with
  `BC5_DIRECT_SHADER_DUMP`.

The dumps were decoded with `bc5-agc report` / `dump`. Runs took place 2026-10-12, 17:51–18:10.
Raw output is in `raw/`: summaries, the decoder's opcode counts, and the draws' operands.

**Result.**

1. **Aliases alone are harmless.** Run 254 ran 240 s through the scene change with no fault and no
   timeout.
2. **`DRAW_INDIRECT` alone, with tight limits, still hangs.** Run 255 hung at about 150 s in the
   same 2,533-dword graphics buffer as runs 242, 243, 251 and 252. There was no given-up wait
   before it, and the machine went down. So neither the unchecked multi-draw arguments nor loose
   count limits are the cause.
3. **The buffer is ordinary.** Run 256's dumps (2,588–2,596 dwords, three at the scene change)
   hold 375 packets:
   - 23 `DRAW_INDIRECT`;
   - one `DRAW_INDIRECT_MULTI` (19 draws, stride 32, no count address);
   - 6 `DRAW_INDEX_AUTO`, 2 `DRAW_INDEX_2`, one `DISPATCH_DIRECT`;
   - state set through 28 `LOAD_SH_REG_INDEX`, 42 `LOAD_CONTEXT_REG_INDEX` and 26
     `LOAD_UCONFIG_REG_INDEX` (0x64; the policy passes it);
   - one `COND_EXEC` and one `CLEAR_STATE` pop.
4. **The base-vertex register is unusual.** Every indirect draw names SH offset 0x280 (mm 0x2e80)
   as its base-vertex and start-instance register.
   - That is the register experiment 0012 found unresolved, which the policy drops from
     `SET_SH_REG`.
   - It sits one past Mesa's `COMPUTE_NOWHERE` (0x2e7f).
   - It is probably the PS5 driver's sink for values its shaders do not use, TODO(verify) on
     gfx1013.

**Verdict.** Not resolved from safe runs. The hang comes with the indirect draws themselves: the
graphics work they enable is what hangs, after the tagged function-pointer calls (0056) stop
faulting. Further progress needs the hung waves' state (program counter, instructions), which
`umr` can read but only as root. Changing the board's sudoers is the maintainer's call. Until
then the launchers keep the indirect draws and aliases off.
