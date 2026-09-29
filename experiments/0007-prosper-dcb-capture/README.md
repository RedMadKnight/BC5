# 0007 — What a Prosper DCB capture of ASTRO BOT contains

**Question.** HANDOFF D10 allows Prosper to be used locally to capture the DCBs that ASTRO BOT submits
while no firmware dump exists. Does such a capture describe the console's AGC command stream
(phase 1: `docs/formats/agc.md`, Q2–Q4)? Or does it describe Prosper's own encoding?

**Setup.** BC-250 dev box, 2026-09-30, `ubuntu` distrobox (experiment 0006), D8 memory split.
- Game: the maintainer's own `PPSA21567` container in `~/bc5-data/games/` (sha256 `435a2527…9af6d`).
  It was mounted read-only with `bc5-mount` (release build from the `ubuntu` container).
- Prosper: `github.com/mattias800/prosper` commit `1c93ab8`, built from source (targets `screenshot`,
  `prosper-app` and `gpu_replay` only). It carries the local-only DCB dump patch from D10; that patch is
  not in this repository.
- Wrapper: [`raw/run-astro-capture.sh`](raw/run-astro-capture.sh) (60 s warmup, three screenshots, 900 s
  timeout).
- Output: `~/bc5-data/captures/astro-20260930-0005/` (not committed).
- Analysis used our tools only: `bc5-agc report` over every DCB, and [`raw/nop_hist.py`](raw/nop_hist.py)
  for the NOP packets.
- No GPU submission by BC5: Prosper renders through its own Vulkan path.

**Result.**

- **Run.** Exit 0 after 82 s. Prosper linked 3 game modules and resolved 1945 imports. It skipped the
  absent plugin modules. Outputs:
  - 1589 DCB files (18 MB);
  - three screenshots, all blank white. The intro had not produced a frame yet: 60 s of warmup is below
    Prosper's own recipe for this title.
  - `PROSPER_SHADER_DUMP` wrote only `frame_vs.spv` and `frame_fs.spv`. These are **Prosper's SPIR-V
    presentation shaders**, not game RDNA code, so the capture holds no game shader binaries.
- **Decoder** ([`raw/bc5-agc-report.txt`](raw/bc5-agc-report.txt)):
  - 604,038 packets, 0 unknown opcodes, 84 named registers, 0 unresolved offsets.
  - Only four opcodes appear: NOP 452,850; SET_SH_REG 82,886; EVENT_WRITE 53,265; NUM_INSTANCES 8,883.
  - There is no SET_CONTEXT_REG and no standard draw or dispatch packet.
  - 0 writes to CU-mask registers.
- **NOP packets** ([`raw/nop-histogram.txt`](raw/nop-histogram.txt)): header bits 2..7 carry a sub-opcode.
  Its values are exactly the custom sub-op enum in Prosper's HLE (`src/hle/graphics/hle_agc.cpp:75-84`
  at `1c93ab8`, "Custom sub-opcodes carried inside IT_NOP", after Kyty's `Pm4.h`). The builder
  `begin_packet` (same file, :478) writes that value into every header. The counts match the enum:
  - push and pop marker (0x0b, 0x0c): 46,248 each, perfectly paired;
  - draw reset (0x05): 1589, one per DCB;
  - wait-flip-done and flip (0x06, 0x17): 227 each, i.e. 227 frames;
  - release-mem (0x18): 172,368, the largest class.

  The zero-filled length-7 NOPs are Prosper's DrawIndexAuto packet, whose tail it zeroes explicitly.

**Verdict.** The capture is **Prosper's command encoding, not the console's**. Every draw, dispatch,
barrier, flip and marker is a Prosper-defined NOP sub-op. EVENT_WRITE and NUM_INSTANCES are also emitted
by Prosper's builders. Therefore:

- It **does not answer** Q2 (submit-header slots) or Q4 (Sony-specific draw/CB/DB registers).
- It does not validate `docs/formats/agc.md` beyond what public PM4 framing already gives.
- It cannot serve as phase-1 input or as a gate.
- The only game-derived content is the (offset, value) pairs of SET_SH_REG. Those pass through
  Prosper's direct-register HLE unchanged. They show 0 CU-mask writes, which is weak evidence for Q3,
  with "game + Prosper" caveat of D10.
- No game shader binaries were obtained, so phase-2 task 3 still needs another source.

A console-format DCB still requires Sony's own `libSceAgc` running, i.e. RPCSX with the tap patch and the
maintainer's own firmware dump (gate G0b). Prosper remains useful only as a smoke test that the game
starts from a `bc5-mount` mount. This experiment confirms that the mount serves a real title's module
loading end to end.
