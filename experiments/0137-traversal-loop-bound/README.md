# 0137 — Bounding the second title's reflection traversal in a patched copy: the copy runs, the hang stays

**Question.** The second title's ray-traced-reflection traversal (program 0x11d049aa00) loops forever
from New Game on, so it is skipped (F113–F116, experiment 0123). F182 suspects that skip for the
opening that does not move. Can the traversal run with its loops bounded, so that it ends instead of
hanging the GPU?

**Setup.**
- BC-250 dev box, 2026-10-16 15:05–15:30, maintainer present.
- **The program:** the private dump of 0x11d049aa00 (64 KiB), disassembled with
  `llvm-mc -triple=amdgcn -mcpu=gfx1013`.
  - Code runs to dword 10,961 (`s_endpgm`), followed directly by data, so there is no free space to
    patch in place.
  - Two `s_getpc` uses address data inside those 64 KiB.
  - One call through a pointer (`s_swappc_b64` at dword 2,332).
  - No `s_barrier`. The program uses SGPRs up to s101.
  - 25 backward branches: 9 `s_cbranch_execnz`, 16 `s_branch`. F113's hung loop ends at dword
    1,892.
- **Run 561** (as experiment 0136's run 559, with the skip, buffers of 900–950 dwords dumped):
  - the 922-dword graphics buffer that dispatches the traversal sets the program address through
    `LOAD_SH_REG_INDEX` tables in memory (0x11e0…), not in the buffer.
- **Backend:** `Device::code_area()`:
  - 8 MiB at the fixed GPU VA 0xFE00000000, below 2^40 because the program address has 40 bits;
  - readable, writable and executable, uncached, on every BO list.
- **Host:** `BC5_DIRECT_LOOP_BOUND=<program>:<limit>:<dword offsets>`.
  - At the first sight of the program in a register table, it copies the 64 KiB into the code area.
  - It appends a prologue and one trampoline per listed backward branch, and points that branch at
    its trampoline.
  - The table's `COMPUTE_PGM_LO` entry is rewritten to the copy's entry.
  - Over the limit the trampoline jumps to `s_endpgm`.
- **Runs 562–564:** as run 560 (no skip; New Game at 100 s, ✕ at 140 s):

  | run | counter | branches bounded | limit |
  |---|---|---|---|
  | 562 | s104 | 2: dwords 1,892 and 3,630 (the two traversal loops) | 262,144 |
  | 563 | s104 | all 25 | 65,536 |
  | 564 | a dword per wave in the code area (`HW_ID1` index, `s_load_dword` / `s_store_dword`) | all 25 | 65,536 |

- Encodings from `llvm-mc -show-encoding`.
- Raw: `raw/runs-561-564.txt`.

**Result.**
- **In every run:**
  - the copy was built, and a register table entry was pointed at it;
  - the GFX ring still timed out twice, at about 77–106 s;
  - the kernel reset only that ring; the machine stayed up, the picture stayed black;
  - the job that times out is the same 922-dword graphics buffer as without the patch (run 560).
- **Run 563:** the hang watcher found the waves inside the copy (PCs 0xfe00001cdc–0xfe00001d50,
  dwords 1,847–1,876), in the loop that ends at dword 1,892. They were still looping, although that
  back-edge counts through the trampoline.
  - Likely cause: the function called through a pointer in the outer loop (dword 2,332) reuses s104,
    so the register counter never reaches the limit.
  - TODO(verify) the callee's register use.
- **Run 564:** the GPU was idle at the hang (`GRBM_STATUS` 0x3028: no GUI, CP or SPI activity), and
  umr crashed on the wave dump.
  - Possible cause: the waves stop on the counter's scalar memory instructions and the workgroups
    never end.
  - TODO(verify): run the trampoline on its own in `direct-selftest`.

**Verdict.**
- **Inconclusive for the opening.** The traversal could not be made to finish, so whether the
  opening waits for it is still open (F182).
- **The mechanism works** and can be reused:
  - a patched copy of a title's program in the device's code area;
  - its address substituted in the title's register tables;
  - waves executing the copy.
- **A bound that survives a call** needs a counter outside the registers the callee may use. That
  needs scalar stores that work on this GPU, tested in isolation first.
- **Next:** the cause of the endless loop itself (F116: the characters' instance records entering
  the traversal's top level), instead of a bound. `BC5_DIRECT_LOOP_BOUND` stays off.
