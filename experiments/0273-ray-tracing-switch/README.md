# 0273 — a "Ray tracing" switch in the emulator window: generic detection of ray-intersection shaders plus the second title's BVH build list

**Question.** The maintainer asked (2026-10-24, through the top session) for a switch in the emulator's
menu that turns a title's ray tracing off and on: the ray-intersection shaders found generically, plus a
per-title list of the BVH build programs that feed them. For the second title the build chain of
"Ray Tracing Update" has taken the machine down (F332) and its traversals loop forever with the
compaction's output present (F234); today the launchers hard-code part of that as
`BC5_DIRECT_SKIP_PGM`. Can the host do this as a setting — default on, live, persisted per title —
without changing anything while the switch is on?

**Known before this experiment.**
- `BC5_DIRECT_SKIP_PGM=<hex list>` (exp 0059) drops every `DISPATCH_DIRECT` / `DISPATCH_INDIRECT` of
  the listed compute programs by NOP-ing the packet (`opt.drop_offsets`), in any buffer. The pkg
  launchers set `11d049aa00,11d04a6000,909974400` (two reflection-traversal variants, F173/F232, and the
  BVH compaction, F207).
- The title carries at least four compiled variants of its ray-traced reflection traversal
  (0x11d049aa00, 0x11d04a6000, 0x11d040e200, 0x11d040c900; F113, F232, F234), each built around the
  hardware instruction `image_bvh_intersect_ray` (F184, F103: encoded 0xF1989F01 in the dump). An
  address list cannot keep up with them; their code can.
- The per-frame BVH build is one compute chain inside the title's debug marker "Ray Tracing Update":
  per tree the count kernel 0x909939400, the leaf-list builder 0x909936c00 (indirect), the count
  kernel 0x909939700 and the refit 0x909939900 (indirect) — F104/F107, F332, the exp 0160 note
  `exp0160-f332-bvh-chain-analysis.md` (the parent's notes folder). The compaction 0x909974400
  (neighbour links) feeds the trees the traversals walk (F234).
- The window's menu bar (ADR 0011, exp 0164): the Emulation menu holds the runtime switches (Pause,
  Fullscreen, Logging: on/off as `Log::Bc5LoggingOn()`, an atomic). The Video tab of the F2 overlay
  saves `RenderScale.<TITLE_ID>=<k>` into the input configuration (`hostInput.cpp`, F101; per title
  since 2026-10-15, F237 for what a wrong value does); `HostInputStatements()` / `HostInputSave()` /
  `HostInputApply()` are the overlay's way to the file and the live map; `HostInputTitleId()` the key.
- The gfx10 ray-intersection instructions and their encoding: LLVM `llvm/lib/Target/AMDGPU/MIMGInstructions.td`
  — `IMAGE_BVH_INTERSECT_RAY` is `mimgopc` 0xe6 and `IMAGE_BVH64_INTERSECT_RAY` 0xe7 in the GFX10 column;
  `class MIMGe_gfx10` encodes `Inst{31-26} = 0x3c`, `Inst{24-18} = op{6-0}`, `Inst{0} = op{7}`. F103's dword
  0xF1989F01 decodes that way (top bits 0x3c, `(0xF1989F01 >> 18) & 0x7f` = 0x66, bit 0 set → 0xe6), and
  llvm-mc for gfx1013 names the same dwords `image_bvh_intersect_ray` in exp 0160's disassemblies.
  TODO(verify) against the RDNA 2 ISA document's MIMG opcode table (not consulted offline).

**Setup.** `patch0273.py` edits three files of the shared tree by exact anchors (each must occur the
stated number of times; the script refuses otherwise) and writes `patch_0273.diff`:
- `src/libs/bc5LleAgc.cpp` (three edits):
  1. the switch's state at file scope in `Libs::Bc5Gc::Direct`, before the filter: `g_rt_on` (atomic,
     from `KYTY_BC5_RT`: `0` starts it off, anything else or unset is on), `g_rt_pending`,
     `g_rt_dropped`; `SetRayTracing(bool)` sets the pending value, `GetRayTracing()` reports the
     pending one if any else the active one, `ApplyPendingRayTracing()` moves pending to active and
     prints one stderr line;
  2. in the filter, right after the `BC5_DIRECT_SKIP_PGM` block: with the switch off, a dispatch of a
     program in `KYTY_BC5_RT_BUILD_PGM` (a hex list, `pgm_list`) or of a program whose code holds an
     `IMAGE_BVH(64)_INTERSECT_RAY` is dropped exactly as the skip list drops (`opt.drop_offsets`, the
     journal line "ray tracing off: … dropped", one in 4,096). A program is scanned once on its first
     dispatch (a mutex-guarded map): the mapped part of the 64 KiB from its address (the window
     `shader_dump` uses), stopping at `s_code_end` or at an `s_endpgm` followed by four zero dwords, and
     a dword with the top six bits 0x3c and opcode 0xe6/0xe7 (bit 0 as op bit 7) marks it; the journal
     names every scanned program and its verdict. A literal in the code that happens to match marks a
     program wrongly: accepted, visible in the journal, and only effective with the switch off;
  3. in the VideoOut path, just before `VideoOutSubmitFlip`: `ApplyPendingRayTracing()` — the switch
     takes effect at a frame boundary. Draws are not touched; with the switch on nothing changes.
- `src/graphics/presentation/hostMenu.cpp`: Emulation › **Ray tracing**, a checked menu item after
  Logging, enabled when a title runs: it sets the pending value and saves `RayTracing.<TITLE_ID>=on|off`
  into the input configuration (`HostInputStatements` → the key's line replaced → `HostInputSave`; a
  stderr line says where, or why not when there is no file).
- `src/graphics/presentation/window/hostInput.cpp`: the statement `RayTracing.<TITLE_ID>=on|off` is
  parsed like `RenderScale.<TITLE_ID>` (another title's line is kept as text, as the scales are),
  written back by `Statements()`, and applied where the render scale is applied: at the first load and
  on Apply from the overlay (`SetRayTracing`). The file's value wins over `KYTY_BC5_RT`; an entry is
  written only after the menu item was used once.
- The per-title list goes into the launcher, not the code: `run0273.sh launcher` prints the two lines
  for `play-pkg.sh` (and `play-pkg-log.sh`, `play-pkg-quiet.sh`), after the `BC5_DIRECT_SKIP_PGM` line:
  `export KYTY_BC5_RT_BUILD_PGM=${KYTY_BC5_RT_BUILD_PGM:-909974400,909939400,909936c00,909939700,909939900}`.
  `BC5_DIRECT_SKIP_PGM` stays as it is: with the switch on (the default) the title runs exactly as today.
- Why each listed program is safe to drop with the switch off, and only then:
  - 0x909974400 (compaction): already skipped today by the launchers; its output is read by the
    leaf builders of the other tree family and by the traversals (F234) — the former run on
    incomplete data today without hanging (F207 era onward), the latter are dropped by detection.
  - 0x909939400 / 0x909939700 (count kernels): they only write the group counts the builder and the
    refit read; dropping a count kernel without its consumer would leave the consumer's arguments stale,
    so all four go together.
  - 0x909936c00 (leaf builder) and 0x909939900 (refit): their output (leaf lists, refitted bounds) is
    read only by the traversals, which the detection drops. Nothing else in the title's frame reads
    those trees that we know of (exp 0050/0053: the trees' only readers in user data were an empty
    program and a copy kernel, F115).
  - Not listed: the other tree family's builders 0x909973900/3b00/3f00 (graphics buffers, F104) and
    the compaction's consumers 0x909977100/0x90997a500/0x909977e00 — they run today without the
    compaction and do not hang; they are build work, not ray tracing, and stay.
- Builds: `run0273.sh build` makes a private `~/bc5-work/exp0273/kyty_emulator` from the shared
  normal build's objects (three units recompiled, `build0273.py`, exp 0272's pattern), under the
  BOX-LOCK, no emulator run. Offline: `verify0273.pl` checks every anchor against patch 0001 on main
  (the committed tree); the box's shared tree is newer (exp 0260's integration), and the script checks
  again there.
- For the water session (F333): the switch drops exactly the five listed programs plus whatever the
  detection marks (each marked program is named in the journal as "ray tracing: program 0x… uses
  image_bvh…"), and only their dispatches; no draw, no DMA, no other dispatch is touched. Whether a
  non-RT pass shares those programs. buffers is not known here: the journal.s list of marked programs
  per run is the thing to check before using the switch as the lake.s A/B.
- Not in this diff: the F332 proposal of a compute-ring refusal for `DISPATCH_INDIRECT`
  (`backend/src/policy.cpp`, the exp 0160 note) — kept apart on the top session's instruction.

**Result.** Prepared 2026-10-24 offline (the box queued: water 0271, then TCP's 0272 compile).
- `verify0273.pl`: all 11 anchors match patch 0001 on main (counts 1, 1, 1 in `bc5LleAgc.cpp`; 1, 1 in
  `hostMenu.cpp`; 1, 1, 1, 1, 1, 2 in `hostInput.cpp`).
- Built on the box 2026-10-24 18:35:05–18:35:44 on the top session.s GO (`run0273.sh build`, lock taken and
  released): the shared tree.s `bc5LleAgc.cpp` was a2a2c2df (daca24cc + exp 0272.s probe v2, integrated
  18:33), the dry run applied all 11 anchors without a reject, and `~/bc5-work/exp0273/kyty_emulator`
  (md5 91349485, 166,535,224 bytes) is the shared normal binary 9f74965d (unchanged before and after) plus
  `patch_0273.diff` (131 added lines; `raw/patch_0273.diff`, `raw/build.out`). Four warnings, none from
  this diff: the 0160 zero-page journal line (`-Wformat`, `pa + 0x10000ull` against `PRIx64`) and two
  unused constants. Not run: the tests below wait for the maintainer.
- Test plan (the box, the maintainer reachable for (c)):
  - (a) RT on = unchanged: `play-pkg.sh` with the private binary, the second title's route of exp 0264
    (`route.sh` with `BC5_EMU=~/bc5-work/exp0273/kyty_emulator`), no `KYTY_BC5_RT`: the journal has no
    "ray tracing off" line, the "ray tracing: program … uses image_bvh" lines name the traversal
    variants as they are first dispatched, frame times and the stall comparison as the shared binary's
    (exp 0264's arm A as the reference).
  - (b) the live switch: the maintainer's play of the second title; Emulation › Ray tracing off, then
    on: the reflections vanish and return at the next frame, `host menu: ray tracing off (saved to …)`
    and `bc5-direct: ray tracing off at the flip` in the log, `RayTracing.PPSA03671=off` in `input.cfg`,
    no fault, no timeout, and the fps with the switch off against on (the compaction's ~0.7 ms, F304,
    and the chain's and traversals' time come back).
  - (c) the S6N route with `KYTY_BC5_RT=0` (or the saved `off`), five runs: do the machine-downs of the
    F332 class stop? Any hang with the switch off is then outside the ray-tracing work.

**Verdict.** Pending the build and the runs.
