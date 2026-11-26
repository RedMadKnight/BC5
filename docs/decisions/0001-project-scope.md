# 0001 — Project scope

**Status.** Accepted, 2026-09-28. Summarises decisions D1, D3, D4 and D5 in `docs/HANDOFF.md` §7.

**Context.** The BC-250 is the same silicon target as the PS5 (Zen 2, `gfx1013`, 16 GB unified GDDR6; HANDOFF F1). Existing PS5 runtimes target generic PCs and translate AGC/PM4 to Vulkan and RDNA ISA to SPIR-V. On the BC-250 that translation can be skipped. The PS5 boot chain (Sony PSP keys, ABL/SMU, hypervisor) cannot run on the board.

**Decision.**
- D1: the project is called **BC5** (BC-250 + PS5); repository `bc5`, fallbacks `bc5-native` / `bc5-agc`.
- Scope is a user-space GPU backend for RPCSX that feeds AGC/PM4 and native shader binaries to `amdgpu`, plus the tooling around it. Not in scope: booting PS5 firmware, writing a new emulator, anything touching Sony keys or firmware.
- D3: the repository is public, in English, and anti-piracy. No Sony material, no links to it; users bring their own console and their own dumps; no warranty.
- D4: work starts with the input layer (`bc5-mount`, phase 0a) before anything GPU-related, so every later experiment uses one canonical, reproducible input.
- D5: the 36/4 CU split (runtime / desktop) is a backend switch, measured in phase 3, not a hard-coded policy.

**Consequences.** Phase 0a needs no BC-250 and no game: fixtures are synthetic. GPU work is gated on experiments (`docs/PHASES.md`). Everything we cannot host (firmware, games) is the user's responsibility and is kept out of the tree by `.gitignore` and review.
