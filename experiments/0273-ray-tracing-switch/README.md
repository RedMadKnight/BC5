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
- Not covered (the supervisor.s call, 2026-10-24): draws whose pixel shaders carry `image_bvh` — the switch
  drops dispatches only; dropping RT draws is a later step. `BC5_DIRECT_SKIP_PGM` stays as it is until the
  detection has proven itself in play; the two traversal variants 0x11d040e200 / 0x11d040c900 stay off
  every list (F234, F249).
- Not in this diff: the F332 proposal of a compute-ring refusal for `DISPATCH_INDIRECT`
  (`backend/src/policy.cpp`, the exp 0160 note) — kept apart on the top session's instruction.

**Result.** Prepared 2026-10-24 offline (the box queued: water 0271, then TCP's 0272 compile).
- `verify0273.pl`: all 11 anchors match patch 0001 on main (counts 1, 1, 1 in `bc5LleAgc.cpp`; 1, 1 in
  `hostMenu.cpp`; 1, 1, 1, 1, 1, 2 in `hostInput.cpp`).
- Built on the box 2026-10-24 18:35:05–18:35:44 on the top session.s GO (`run0273.sh build`, lock taken and
  released): the shared tree.s `bc5LleAgc.cpp` was a2a2c2df (daca24cc + exp 0272.s probe v2, integrated
  18:33), the window files were hostMenu.cpp c2e68685 (2026-10-19 10:13) and hostInput.cpp c5eb3ce2 (2026-10-19 21:17), unchanged since 6401842; the dry run applied all 11 anchors without a reject, and `~/bc5-work/exp0273/kyty_emulator`
  (md5 91349485, 166,535,224 bytes) is the shared normal binary 9f74965d (unchanged before and after) plus
  `patch_0273.diff` (131 added lines; `raw/patch_0273.diff`, `raw/build.out`). Four warnings, none from
  this diff: the 0160 zero-page journal line (`-Wformat`, `pa + 0x10000ull` against `PRIx64`) and two
  unused constants. Not run: the tests below wait for the maintainer.
- Test plan (the box, the maintainer reachable for (c)):
  - (a) RT on = unchanged: `play-pkg.sh` with the private binary, the second title's route of exp 0264
    (`route.sh` with `BC5_EMU=~/bc5-work/exp0273/kyty_emulator`), no `KYTY_BC5_RT`: the journal has no
    "ray tracing" line at all — with the switch on the detection block is never entered (it sits behind
    `!g_rt_on`), so no program is scanned and no program memory is read; the "ray tracing: program …"
    lines appear only once the switch is off, at each program.s first dispatch from then on. Frame times and the stall comparison as the shared binary's
    (exp 0264's arm A as the reference).
  - (b) the live switch: the maintainer's play of the second title; Emulation › Ray tracing off, then
    on: the reflections vanish and return at the next frame, `host menu: ray tracing off (saved to …)`
    and `bc5-direct: ray tracing off at the flip` in the log, `RayTracing.PPSA03671=off` in `input.cfg`,
    no fault, no timeout, and the fps with the switch off against on (the compaction's ~0.7 ms, F304,
    and the chain's and traversals' time come back).
  - (c) the S6N route with `KYTY_BC5_RT=0` (or the saved `off`), five runs: do the machine-downs of the
    F332 class stop? Any hang with the switch off is then outside the ray-tracing work.


**Test (b), first attempt (the maintainer, 18:51–18:52:55, `~/bc5-work/exp0273/play-rt.sh`, binary 91349485):**
ended early — the picture froze in-game at about 1.5 min with the sound going on, after a TCP
read-permission fault and gfx/compute ring resets (the TCP session's class, its exp 0275). The switch was
never toggled (no "host menu: ray tracing" line). The journal's 0 "ray tracing" lines are the expected
state with the switch on (above): nothing of 0273 ran on that session's GPU work. With RT on the diff
touches nothing on the GPU path: the filter's block is gated by `!g_rt_on`, `ApplyPendingRayTracing()` at
the flip is one atomic exchange with no pending value, and the rest is the menu item and the
configuration parser.

**Test (b) as "RT off from the start" (the maintainer, 19:04–19:06, `play-rt.sh` with `KYTY_BC5_RT=0`
in the process environment, binary 91349485, the build list as above; read offline from a read-only
copy of `~/bc5-data/captures/play-20261024-1904/gc/direct.log`, the two `ib-timeout-*.bin` dumps,
`~/bc5-work/exp0273/play-rtoff-1904.log` and `~/bc5-data/captures/devcoredump/20261024-190459-devcd2.txt`):**
- **The menu had no picture.** The detection marked, in the menu's own graphics buffer at journal
  t 2.08 s (23,286 dwords), three programs that carry `image_bvh64_intersect_ray` — 0x11d0323c00,
  0x11d0323900, 0x11d023c300 — and dropped their dispatches (the first "ray tracing off" line; the
  counter is shared, so their later drops are not journaled separately). The menu scene is lit by
  ray queries, and with those dispatches gone its targets stay unwritten: a black menu while the
  flips went on at 28–30 per second (fps counter, t 4.8–6.9 s). So a generic drop of every
  ray-intersection consumer is wrong: those programs write what the title shows, not only
  reflections.
- **The GPU hung at t ≈ 42 s** (gfx timeout 19:04:59, reset succeeded; compute 19:05:01; no fault
  line, but the coredump's fault registers still hold 18:52's `0x1334f81000`, F336). The probe's
  dumps: the stuck graphics buffer #23408 (2,002 dwords) carries the "Ray Tracing Update" count
  kernels and builders (all DROPPED by the build list, as intended), one dispatch of 0x11d04ddd00
  (900 groups, ran), then the **title's own intra-buffer sync**: `WRITE_DATA` 0 to 0x11e0310a40,
  `RELEASE_MEM` writing 1 there at end of pipe, `WAIT_REG_MEM` == 1 at offset 1640 — reached ("ran")
  and **not met: the label reads 7** (64-bit 0x69edddb400000007). Everything behind it waits: the
  buffer's later dispatch of 0x11d04d1000 (2,506 groups), and the compute chain #23415 (14,382
  dwords, 1,336 dispatches of the chain, all dropped, 6 packets ran) at its first packet, a wait on
  0x12004b77c8 == 0 that a later buffer writes. Nothing in this buffer writes 7 after the
  `WRITE_DATA` 0; the value comes from a shader still running from earlier work or from a different
  user of that word, which the dumps cannot show. The hang is therefore not a dropped dependency of
  the kind feared (a consumer outside the list waiting for a dropped producer): the stuck packet is
  the title's own end-of-pipe sync, and whether RT off caused it (the dropped dispatches change the
  buffers' timing) or only exposed it (the wait class the TCP session tracks, F336/exp 0275) needs the
  same test with the consumers running — the next build below. The journal's
  "gpu check: 1 dispatches left to the CP that the host would have dropped" at line 64878 is the usual
  F106 count (one absurd triple left to the CP's check), unrelated to the switch.
- Also seen: with the switch off the detection scanned 131 programs in 60 s (every compute program
  the title dispatched), found `image_bvh64_intersect_ray` in the three menu programs and
  `image_bvh_intersect_ray` in 0x11d03b1000, 0x11d049aa00 and 0x11d040e200 (the traversal variants,
  F113/F232/F234), and the build list dropped 4,097 dispatches by t ≈ 40 s.

**Verdict.** The switch's mechanics work (the environment default, the journal lines, the drops), but
"off" as first designed is wrong on one count and unproven on another: dropping every ray-intersection
consumer blanks the title's menu, and the run hung on the title's own end-of-pipe sync with the
consumers gone, cause or coincidence open. **Fix design (experiment 0278, `patch0278.py`, this script unchanged as the tested binary.s):**
"off" drops the build list alone — the compaction and the "Ray Tracing Update" chain, exactly the
programs F234/F332 tie to the hangs — and leaves every consumer running; the consumers then walk
trees the build never filled, the state the title already runs in today with the compaction skipped
(exp 0160 run 834: the traversal variants through 100 s of play with no hang). The generic
detection stays as a diagnostic behind `KYTY_BC5_RT_DETECT=1`. Next (→ experiment 0278): the same test with that build;
if the end-of-pipe wait hangs again with the consumers running, the cause is the dropped chain (a
label or counter one of its kernels writes) and the list shrinks to the compaction; if not, the
F336 class. The switch stays off by default for integration until that test passes; nothing is
integrated.

**Correction (same day, from the TCP session's reading of the probe):** the probe's "ran" mark is the
backend's `executed_offsets` — the packet passed the filter rather than being NOP-ed — not the CP's
progress. So above, "reached ("ran") and not met" overstates it: the wait at offset 1640 is not met
(the label reads 7, not 1), but whether the CP stood at that wait or inside an earlier dispatch of the
same buffer (0x11d04ddd00, 900 groups, the last one before the sync) the dumps cannot say. The fix
design and the next test are unchanged; the breadcrumb capture the TCP session proposes (a
`WRITE_DATA` of each dispatch's offset before it runs, in `backend/src/indirect_check.cpp`) would
settle where the CP stops.
