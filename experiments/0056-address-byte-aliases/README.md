# 0056 — the second title's function pointers with 0x80 above bit 40, and memory mapped under them

**Question.** Experiment 0055 found the second title stopping at its first scene change on an
instruction fetch at its programs' addresses with 0x80 in bits 47:40, no program register carrying
it. Where does the address come from, and does mapping the memory again under such addresses
(as if the PS5 GPU ignored those bits) let the title through?

**Setup.** The title's dumped programs (kept private) disassembled with `llvm-mc -mcpu=gfx1013`
(LLVM 21, ubuntu container), whole 64 KiB dumps. Backend `Device::map_alias` / `unmap_aliases`:
the pages already mapped over a range mapped a second time at another GPU address, from 2^47 up
passed sign-extended (the kernel's VA hole); not in the mapping list, removed with their source.
Host `BC5_DIRECT_ALIASES=1`: windows "byte lo size" from `~/bc5-work/direct-aliases-pkg.txt`
mapped at (byte << 40) + address whenever the mappings change (at most once a second); a timeout's
fault with a non-zero byte adds its window. Seeded with byte 0x80 over 0x11ce000000+0x6000000 (the
programs at 0x11d0288000–0x11d3xxxxxx). Runs 251–253, 2026-10-12 15:03–17:47, with
`BC5_DIRECT_INDIRECT_DRAWS=1`; 252 with `BC5_DIRECT_JOURNAL_SYNC=1`. Raw output in `raw/`; `run-pkg.sh` and `play-pkg.sh` are the launchers as of this experiment (the ring order of 0055 on, aliases and indirect draws off).

**Result.**

1. **The addresses are function pointers in the title's constant buffers.** Dozens of its programs
   call through `s_swappc_b64` on `s[14:15]`; in one, `s_buffer_load_dwordx2 s[14:15], s[4:7],
   0x70`, a test for non-zero, the call. The faulting fetches (0x8011d0288000, 0x8011d0374000,
   0x8011d0375000) are such targets: program pages with 0x80 above bit 40. No program register
   carries the byte (0055), so the title's own data does — consistent with a PS5 GPU that ignores
   bits 47:40 or maps its code there as well, TODO(verify).
2. **Mapped again under 0x80 the fetch no longer faults** (96 MiB aliased in each run), but the GPU
   then hangs without any fault: run 251 at 153 s and run 252 at 124 s, after which the reset took
   the machine down (the firmware reported "a parity error occurred" as the reset reason; no
   journal line after the timeout survived, even fsync'd); run 253 (without the ring order of
   0055) hung at 145 s after given-up cross-queue waits, and three resets recovered.
3. The hung buffers: 252's held 23 `DRAW_INDIRECT` with plausible counts (2–94,322 vertices, one
   instance each) and no given-up wait before it; 253's followed given-up waits.

**Verdict.** Inconclusive, and dangerous. The tagged addresses are the title's function pointers,
and aliasing the code region removes the fault, but what runs after it hangs the GPU, and a hang
without a fault is what takes the machine down (a fault the kernel recovers from). Aliases stay
opt-in; the launchers do not set them, nor the indirect draws.
