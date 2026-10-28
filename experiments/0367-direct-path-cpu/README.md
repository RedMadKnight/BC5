# 0367 — the direct path's CPU per frame on the render thread

Asked by the top session on 2026-10-28 after exp 0366 (F482). At the fight the render thread spends ~63 % of its CPU in
the direct path: our backend's code (36 % of its samples) and the direct path's own syscalls and libc (27 %). That is
host time we own. Base: main 5f22c7c (shared normal 1000ad2a, archive bb50b2e0, patch 0001 2db34349); branch
exp/0367-direct-path-cpu; nothing shared changed (D19). The maintainer is away until 23:00, with the top session's
standing GO for box batches under the lock rules, RT on.

**Question.** Where exactly does the render thread's direct-path CPU go per submission, and which change cuts it while
the command stream the GPU sees stays identical?

## Offline: where the time goes (exp 0360's samples and the code)

The render thread's host samples at the scripted fight (exp 0366, M2f t 104–146): `full_state::Tracker::emit_prefix`
27.5 %, `Direct::submit_now` 21.5 %, `full_state::Tracker::apply_level` 10.4 %, `direct::Device::submit` 5.1 %,
`state_stack::Tracker::apply_in_place` 5.0 %, then `indirect_check`, `chain_*`, `shadow_labels` and their containers.
On the S6N route (exp 0360 M2) the shares are the same. What the code does per submission on the render thread
(`bc5LleAgc.cpp` e7cc2f60, `Direct::submit` → `piece_check` → `submit_split`):

1. **`piece_check`**, for every `cc`/`hib`/`dcb`, under its own mutex:
   - for a DCB with `BC5_DIRECT_PREFIX_ALL` on (the default mode 2, "draws", exp 0157 / F204), `t_fs_before = tracker`:
     a copy of the whole tracker, four flat register files (values 0x7000 dwords, flags 0x7000 bytes), the packet
     state and the context stack;
   - then `tracker.apply`, which follows the buffer, its LOAD tables and nested IBs through the mapping reader.
2. **`submit_split`**, for a DCB that draws, `prefix_of(t_fs_before)` → `Tracker::emit_prefix`. That scans every flag
   byte of the four spaces (28,672 slots) to emit ~1,150 dwords: CONTEXT_CONTROL, CLEAR_STATE 0, the tracked
   registers in runs, and the packet state.
   - The prefix then goes through `chain_append` (a copy into the chain buffer) and is filtered, run through the
     state-stack tracker, the indirect check and shadow labels, and executed by the CP. All of that is per drawing DCB.
   - A smaller prefix (only what changed) would change the GPU's command stream. The full prefix exists because other
     processes' jobs run between the title's on the one GFX ring (F204), so it is out of scope here.
3. **CS ioctls per frame** (F461): at his fight 20.3 game-thread jobs + 76.3 ring jobs a frame. The game thread's
   chains are already held across its ioctls (ADR 0010 section B, mode 2, a 2-ms watchdog). Merging more would move
   submission boundaries and the GPU's idle time, and is left alone.

## Candidates

- **C1 — `emit_prefix` without the byte-by-byte scan** (`backend/src/full_state.cpp` only; no header, no layout
  change). The flag bytes are read eight at a time and an empty word is skipped. Each run is written straight into an
  output reserved once, its header patched when it closes. Run boundaries, the 0x3ffe-value split and the order (flat
  slots ascending, then the overflow map) are those of the old code. Expected: most of `emit_prefix`'s 27.5 %, ~10 % of
  the render thread's direct-path CPU.
- **C2 — no tracker copy per DCB** (`bc5LleAgc.cpp`). In the default mode `t_fs_before` is only read by the prefix, so
  the prefix could be emitted in `piece_check` from the tracker before `apply`, under the same lock, and kept for
  `submit_split`. The non-default modes (pieces, CS prefix, sx) keep the copy. Not built: the harness puts the copy at
  5.6–5.9 µs per DCB on the laptop, ~1–2 ms/s on the route, not worth a change to the submit path.

**The proof (offline, laptop, MSVC 19.5 /O2).** `harness0367.cpp`, built by `build-harness0367.ps1` against main's
`full_state.cpp` (29f7dd6d) and against C1's (f6f13f7d). Each build prints every prefix packet by packet:
- after each of the 27 private IB dumps applied in submission order (`private-dumps/2026-10-27`, `-28`; no reader, so
  LOAD tables and nested IBs are not followed);
- after each of 3,000 randomized trackers: SET runs in all four spaces at random offsets, past the flat arrays into
  the overflow maps and across their ends; CLEAR_STATE clears, pushes and pops; SET_BASE and the index packets.

Results:
- **The two outputs are identical:** 3,027 prefixes, 4,064,039 dwords, 146,767 packets, `cmp` equal, zero differing
  packets.
- **C2's reordering** (the prefix before `apply` against the prefix of a copy taken before `apply`) gave the same
  prefix in all 10,758 checks.
- **Timing** on a title-like tracker (F72's shape: 928 context, 150 SH, 57 uconfig registers; 1,146 dwords):
  `emit_prefix` 25.1 µs → **6.5 µs**; the tracker copy 5.6–5.9 µs.

**Setup (box).**
- `build0367.sh` (exp 0360's `build0360.sh` with a backend unit). With `FULL_STATE=full_state-0367.cpp` it:
  - checks that `~/src/bc5/backend/src/full_state.cpp` is main's 29f7dd6d (what the archive was built from);
  - compiles the private copy with the archive's own compile command (`~/bc5-work/backend-ubuntu/compile_commands.json`:
    clang, `-O3 -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wsign-conversion -Werror`);
  - has `build0367.py` link that object in front of `libbc5_backend.a`.
- The variants: `pfx` = exp 0360's meter + sampler (`meter0360.pl`, `prof0360.pl`) + C1, against exp 0360's `meter2`
  (the same without C1).
- Runs: `run0367.sh`, `go0367.sh`, `chain0367.sh`, derived from exp 0360's by `mk-0367.pl`. They cover the S6N route,
  300 s, and the automated fight route of F464 with the job-arena fix on (so the run reaches its end), 200 s; RT on;
  the kernel log streamed; live saves compared only.

**Result.**

**Verdict.**
