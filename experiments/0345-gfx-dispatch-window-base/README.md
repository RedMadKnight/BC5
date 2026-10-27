# 0345 — a GFX-form indirect dispatch with base-1 0 gets the title's window as its base, or a NOP

**Question.** Exp 0344 read the machine-down of 2026-10-27 12:52 (the maintainer's RT-on play on the integrated build,
F416's second hang): the second title's BVH bottom-up refit (program 0x90997a500) issues 435 GFX-form
`DISPATCH_INDIRECT`s in its graphics buffer whose offsets (0x9bce4d80 …) are the low dwords of addresses in its 4-GiB
window at 0x1100000000, with `SET_BASE` index 1 deliberately 0 (the title zeroes it, twice, at the end of each of its
buffers). The console resolves that within the process's window; the backend saw no base, took the unbased path (a
`PFP_SYNC_ME` and the dispatch as written, unchecked), and the CP read the arguments at the bare offset: a CPF
permission fault at page 0x9bce4000, a failed ring reset, MODE1. This is the class the maintainer put first ("w pierwszej
kolejności błędy, które powodują restart maszyny"). Does giving such a dispatch its window as the base — a `SET_BASE`
index 1 before the CP check, the check against window + offset, a NOP when that address is not mapped — remove the
fault without changing anything else: the backend's tests, the RT-off route, and then the post-load spot of the
maintainer's play (85 s) and the S6N route with RT on?

**Setup — the change (backend only, on main d0c2668's backend; `backend/include/bc5/indirect_check.hpp`,
`backend/src/indirect_check.cpp`, `backend/src/direct.cpp`, `backend/tests/indirect_check_test.cpp`; no host change,
no GPU change to test offline).**
- `indirect_check::GfxBase { window, mapped }` and a new last parameter of `apply()`. Inside the pass, for a GFX-form
  `DISPATCH_INDIRECT` (3 dwords, not on a compute ring) whose base-1 is 0 at that point — no `SET_BASE` index 1 earlier
  in the IB and no caller's base, or the IB's last one set it to 0:
  - window known and `mapped(window + offset, 12)`: **`SET_BASE` index 1 = window is emitted** (`kSetBaseCompute`,
    PKT3(SET_BASE, 2, 0) with the shader-type bit 1 set: run 64's hang was a SET_BASE for a compute dispatch without
    it), then the usual check — the three `COND_WRITE`s poll window + offset, the product staircase when on — and the
    dispatch. The window then stays the base for the dispatches after it, as the CP's register does, until the IB's
    next `SET_BASE`; a later `SET_BASE` 0 brings the rule back. Draws keep their own handling (the title sets their base
    itself: 167 `SET_BASE`s for 141 `DRAW_INDIRECT`s in the hung buffer).
  - not mapped, or no window known: **the dispatch becomes a NOP** of its own length (its dwords stay as the NOP's
    payload, nothing moves) and is counted; the CP never reads a bare offset. The cost of a lost refit dispatch is a
    frame's reflections; the cost of the read was the machine.
  - Without a `GfxBase` (the switch off): the `PFP_SYNC_ME` alone, as before. `Stats` gains `rebased`,
    `rebased_unmapped`, `rebased_no_window` and one `Rebase` record per such dispatch (offset, the program as
    `SET_SH_REG` set COMPUTE_PGM_LO/HI earlier in the IB, base, address, mapped).
- **How the window is known** — `BC5_DIRECT_GFX_BASE1`, read by `Device::open` (default off; a `Device` field, not an
  option field: the 0341 ABI lesson, the host's objects keep their layout):
  - `learn`: `indirect_check::learn_window()` takes it from the title's own non-zero `SET_BASE` index-1 packets as its
    GFX IBs go by — the high 32 bits of the last one, kept across jobs (a zero `SET_BASE` forgets nothing). The hung
    buffer's own values are 0x1193ad3900, 0x11d083a400, 0x112319ff60: all name 0x1100000000, and 0x1100000000 +
    0x9bce4d80 lies in the title's learned window 0x1196000000 + 0x6000000 (exp 0344, `h2-learned-windows.txt`). This is
    the robust source: the learned mapping windows alone do not say which 4-GiB region an offset belongs to (the title
    has windows at 0x11…, 0x12…, 0x23…), the title's own bases do. Until one has been seen, such dispatches are
    NOP-ed and counted — unless `learn:<hex>` gives the value to use until then.
  - `<hex>`: a fixed window (0x1100000000 for this title).
  The mapped test is the host's `FilterOptions::mapped` callback, the same the filter uses.
- **Lines.** At open, the switch line (`bc5-direct: experiment 0345 switch: …`). One stderr line per program the first
  time it is rebased or NOP-ed (`bc5-direct: experiment 0345 rebase: dispatch at <off> of program 0x…, base-1 0, offset
  0x…: window 0x… -> address 0x…, mapped: SET_BASE + the check | NOT mapped: NOP-ed | no window known: NOP-ed`), and at
  close (with the 0341 summary) the sums: dispatches given the window, NOP-ed unmapped, NOP-ed without a window, programs.
- **Unit tests** (Catch2, `tests/indirect_check_test.cpp`, four new cases): the refit's packet with the window — the
  `SET_BASE` emitted with the compute bit, the check polling 0x119bce4d80 + 4k, the record's fields, the size; not
  mapped → the NOP in place, nothing moved, counted; no window → the NOP, counted; without a `GfxBase` the old
  `PFP_SYNC_ME`; the IB's own `SET_BASE` 0 rebased and a non-zero one kept, the window staying in effect (two
  `SET_BASE`s for four dispatches, six `COND_WRITE`s on the title's base); `learn_window` on none / some / a zeroing
  one. Not compiled on the laptop (no compiler for the backend here): the build and the tests run on the box after the
  GO, as exp 0341's `build0341.sh` did (a private archive, the tests, the shared emulator relinked).

**Run (the box, after the GO).** Exp 0341's pattern: the private archive built from this branch's `backend/`, the
tests, the integrated normal build relinked against it; the RT-off route 600 s with `BC5_DIRECT_GFX_BASE1=learn`
(expected: 0 rebased dispatches, 0 NOP-ed — the route has none of these packets, the switch costs nothing); then the
maintainer's play on a test shortcut with RT on and `BC5_DIRECT_GFX_BASE1=learn:1100000000`: the post-load spot at
85 s where 12:52's run went down. Pass = no CPF fault, no reset, the `rebase` line naming 0x90997a500 with "mapped:
SET_BASE + the check", the close summary's NOP-ed counts 0 (or the few that were not mapped, named). Hang 1's class
(the looping small dispatch of the build chain, ~106 s on the route) is not addressed here and gets its own arm.

**Result — the box, 2026-10-27 13:26–13:29 (the supervisor's GO, window 13:25–14:05).**
- *Build* (`build0345.sh`, `raw/build0345.txt`): the private archive **c65ed368** (0 errors, 0 warnings), **64 test cases,
  32,408 assertions passed** (the four new ones among them), the integrated normal build's objects ddfb9456 relinked
  into `~/bc5-work/exp0345/kyty_emulator` **495f8795**; the shared binary and archive untouched.
- *R1* (`s6n0345.sh dc9d4f25fc2d41ca R1 600 off`, `BC5_DIRECT_GFX_BASE1=learn`, RT **off**): **the box went down about
  90 s in** — the journal stops at 13:29:03, a devcoredump at 13:29:21 (`20261027-132921-devcd1.txt`), then the kernel
  hung 26 minutes without a watchdog reset; the maintainer reset it by hand at 13:55 and the supervisor cleared the
  stale lock. No verdict files (the script died with the box); the live saves dc9d4f25fc2d41ca unchanged. The test
  shortcut was **not** made. What the supervisor read from the box: thread `bc5-chainwd`, fault page 0x11da0e2000,
  status 0x700c30; IB 0x101100000000 of 162,176 dwords, `CP_IB1_BUFSZ` 0x15580; SEs idle; the PFP history
  `PFP_SYNC_ME, WRITE_DATA, COND_WRITE × 5, WRITE_DATA` (a check with the staircase); the host's probe: dcb #81041
  (98,099 dwords, 9,186 dispatches, 6,499 indirect, "the largest grid 17959069687466613312 groups, at 95906") and acb
  #81042 (1,318) both TIMEOUT at 2.06 s; 12 lines of the run match `0345`.

**Finding (from the code; the box reads below will confirm the numbers).** The rule "base-1 is 0 when this IB has no
`SET_BASE` index 1 before the dispatch" is wrong, and R1 shows how: **the CP's base-1 is a register that persists across
jobs**, and a GFX-form dispatch that comes before any `SET_BASE` in its IB is not reading at 0 — it reads at whatever
the last job left, which the title relies on when a buffer's dispatches continue a base its previous buffer set (the
chain watchdog's job, `bc5-chainwd`, is exactly a title buffer submitted on its own, after the pieces before it). Before
0345 such a dispatch took the unbased path and ran at the carried base, unchecked but correct; 0345 put
`SET_BASE 1 = 0x1100000000` in front of it and checked it against window + a small offset, so the CP read its three
counts from an unrelated word of the window — the 10^19 "largest grid" the probe reports at 95906 is one such triple
read back — and, when the counts happened to pass the limits, ran a shader with those counts and user data. Twelve
programs were rebased this way in 90 s of RT-off play, none of them the refit (with RT off the title issues no refit;
`KYTY_BC5_RT_BUILD_PGM` does not even list 0x90997a500). The fault that followed is a **CPG write** (status 0x700c30:
RW bit 18 set, client 6 = CPG, `PERMISSION_FAULTS` 0x3, `MAPPING_ERROR` 0) at a page inside the title's window
0x11ce000000 + 0x6000000 with the SEs idle: the CP itself writing where it may not — the title's packets after the
clobbered base (an `SET_BASE` index 1 also serves the title's `DRAW_INDIRECT`s, as the supervisor noted) or the check's
own writes with a flag address patched for a slot the IB no longer matched; which one, the dump's packet at the fetch
point and the probe's write lines will say. So both suspicions are the same bug: **0345 changed base-1 where the CP had
a valid carried value**; hang 2's base-1 was 0 because the title had set it to 0 itself (the trailing pairs), and that
is the only case the window rule may touch.

**Corrected design (not built; the next private build after the GO).**
1. *Track the register, do not guess it.* The `Device` keeps `cp_base1_`, the CP's base-1 as the GFX ring's jobs leave
   it: after each job, the last `SET_BASE` index 1 of the final IB (the title's, the host's compute conversions —
   `mec_expand_ib` emits `SET_BASE 1 = the argument page` before every converted dispatch — and the backend's own),
   including the nested pieces in order. `apply()` gets it as `base_in` for every GFX-ring job (today a dcb's is 0): a
   dispatch before any `SET_BASE` in its IB is then **checked against the base the CP will actually use**, with no
   packet added — truthful, and more coverage than today's unbased path.
2. *The window only for a real 0.* `SET_BASE 1 = window` + the check only when the tracked register is 0 at the
   dispatch (never set since start, or the title's own `SET_BASE 1 = 0`, as before hang 2); not mapped → NOP, as now.
   Both cases journaled per program as now, with the tracked base in the line.
3. *The compute conversions' clobber.* With one ring the host's acb conversions leave base-1 at an argument page, which
   the console's separate compute queue never did to the graphics queue's register. The `Device` keeps `title_base1_`
   as well, the register as the last **non-conversion** job left it (jobs with `mec_indirect_base == 0`), and starts a
   non-conversion job whose first indirect draw or dispatch precedes its first `SET_BASE` with `SET_BASE 1 =
   title_base1_` when the tracked register differs from it (4 dwords, rare): the register is as the title left it.
   This is independent of the window rule and may explain silent wrong dispatches of the one-ring runs on its own; it is
   counted and journaled separately (`restored`).
4. *Learning stays* (`BC5_DIRECT_GFX_BASE1=learn[:<hex>]`), used only by rule 2.
5. *Tests*: the register carried across two `apply()` calls (a `SET_BASE` in job A, a dispatch before any in job B
   checked against A's base, no packet added); job A ending with `SET_BASE 1 = 0` → job B's dispatch rebased to the
   window; a conversion job between A and B → B starts with `SET_BASE 1 = A's base`; the existing four cases kept.

**Box reads needed (read-only, one window of ~5 min; `probe0345.sh` does them all, text into `~/bc5-work/exp0345/raw/h3-*`):**
1. `~/bc5-work/exp0345/play-last.log`: the `experiment 0345 rebase` lines (which 12 programs, their offsets, the
   addresses given) and the switch line.
2. `ib-timeout-00081041-dcb-98099.bin` through `ibmap0344.pl` (CS 162,176, `CP_IB1_BUFSZ` 87,424): the packet at the
   fetch point and the dispatches around it; and `setbase0345.pl` (in the script): the dump's `SET_BASE` index-1
   packets with their headers (0xc0021102 = a host conversion, 0xc0021100 = the title's) and every GFX-form dispatch
   before the first of them with its data offset — small offsets say "a carried base", 0x9b…-like ones "the window".
3. `play-20261027-1327/gc/direct.log`: the 30 lines before `submit #81041` (what ran just before: conversions?), the
   dcb's probe section (the dispatch lines at the fetch point and at 95906 with their programs and triples; the `write
   op` lines naming 0x11da0e2…), and the host's sampled `indirect op 16 at …: base 0x…` lines (the carried base at
   submit) plus the last `gpu check:` counters.
4. The devcoredump's `CP_ME_HEADER_DUMP`, `CP_IB1_BASE`, `GCVM_L2_PROTECTION_FAULT_STATUS/ADDR` lines, to settle whether
   the CPG write was the title's packet or the check's.

**The reads (2026-10-27 14:08, `probe0345.sh`, read-only, `raw/box/h3-*`): they contradict the premise, so the corrected
design is not built.**
- **0345 did nothing in R1.** The play log holds the switch line (`learn`, "until then 0x0") and **0 `rebase` lines**: in 90 s
  no dispatch went through the window rule or the NOP, so the GPU stream of R1 was the integrated build's. The
  machine-down is **not** 0345's: it is an RT-off class of its own — a **CPG write** (status 0x700c30: client 6, RW set,
  `PERMISSION_FAULTS` 0x3, `MAPPING_ERROR` 0) at 0x11da0e2000, a page of a region the host had never mapped (the
  journal's last lines: `timeout: fault 0x11da0e2000`, `learned: fault … -> region 0x11d6000000+0x6000000 (saved)`), 90 s
  into the S6N route, in dcb #81041 (98,099 dwords: the BVH build chain's programs 0x90985f200 × 3,137, 0x909973900 ×
  3,081, 0x909977100 × 2,968; 4,755 of them dropped by the RT-off switch, `KYTY_BC5_RT_BUILD_PGM`), the chain watchdog's
  job. None of the dcb's four `RELEASE_MEM`s names that page; which CP packet wrote there is open. Exp 0342's R1 (the same
  build, chain and switch state) passed 600 s, so it is intermittent; it would hit the maintainer's play with or without
  0345.
- **Why 0345 saw no base-1 of 0 is open.** The dump has 5,009 GFX-form dispatches (header 0xc0011600, offsets 0x40,
  0x3f40, …: small, a carried base) before its only `SET_BASE` index 1 (at 75652, header **0xc0021102**: the shader-type
  bit set, lo 0x8c7f6100 hi 0x11 — the title's own packet: the tracker's prefix replay emits plain headers and the host's
  conversions always add a `PFP_SYNC_ME`, of which the dump has none). `apply()` with `base_in` 0 should have recorded
  and NOP-ed them; the log says it did not. Either the chain's `apply()` ran with a non-zero base the code does not show,
  or the run's binary did not reach that branch. To be settled by running the backend's own passes over this dump
  offline on the box (a tool against the private archive) before anything else is built.
- **The CP keeps one base-1 per shader type.** The PM4 header's shader-type bit (bit 1) selects compute or graphics
  state: PAL builds `SET_BASE` with the pipeline's type and run 64's hang was a compute dispatch whose `SET_BASE` lacked
  the bit (HANDOFF). The title's refit dispatches of hang 2 are **gfx-type** (0xc0011600) and the zeroing pairs before
  them graphics `SET_BASE`s: the gfx register was 0. The title's `SET_BASE` at 75652 here is **compute-type**, and the
  gfx-type dispatches after it do not read it — but `indirect_check::apply` tracks one `base` regardless of type, so from
  75652 on it checks gfx-type dispatches against a compute-type base: the `COND_WRITE`s poll the wrong words (the probe's
  "largest grid 1.79 × 10^19 at 95906" is such a read) and the limits refuse dispatches the CP would have run correctly.
  This is a pre-existing error of the check (since 0052), harmless where buffers set one type only, wrong in a buffer
  that mixes them; and 0345's window `SET_BASE` carried the compute bit before gfx-type dispatches, which could not have
  rebased them at all.

**Corrected design, second version (not built; after the dump replay above and the GO).**
1. `apply()` tracks **two** bases, gfx and compute, from the `SET_BASE` headers' shader-type bit, and a dispatch or draw
   uses the one its own header's bit selects; `base_in` becomes a pair, carried by the `Device` across GFX-ring jobs as the
   CP's registers (`cp_base1_[2]`), from each job's final IB in order.
2. The window rule only when the register the dispatch reads is 0; the emitted `SET_BASE` carries **the dispatch's own
   shader-type bit**; not mapped → NOP; one line per program; sums at close — as before.
3. The compute conversions (`mec_expand_ib`, compute-type `SET_BASE`s) touch the compute register only, so the title's
   gfx register needs no restore; rule 3 of the first version is dropped.
4. Tests: a gfx-type dispatch after a compute-type `SET_BASE` is checked against the gfx base (carried), not the compute
   one; the carried pair across two `apply()` calls; the zeroing pair then a gfx dispatch → the window with the gfx bit.
5. Before any RT-on test: R1's CPG-write class needs its own reading (the packet that wrote 0x11da0e2000: the dump's
   packets around the fetch point once the chain's replay is exact, the probe's write lines, and the
   `CP_ME_HEADER_DUMP` sequence `COND_WRITE, WRITE_DATA, WRITE_DATA, SET_SH_REG(9), DISPATCH_INDIRECT, PFP_SYNC_ME,
   WRITE_DATA, PFP_SYNC_ME` — a check followed by an unbased dispatch), since it takes the box down with RT off.

**The second version on the box (2026-10-27 14:21–14:25; the supervisor's GO, window to 16:30).**
- *Build* (`raw/build0345.txt`): archive **735e0c00** (0 warnings), **65 test cases, 32,439 assertions passed** (the fifth
  0345 case among them), emulator **9a221a67** (495f8795 kept). The replay of R1's dump through the first version's
  `apply()` offline (`replay0345.cpp` against the private archive, `raw/box/h3-replay.txt`): with the switch off 1,490
  checked and 5,009 unbased; with `learn` and no window yet 5,009 NOP-ed with 5,009 records; with the window
  0x1100000000 one rebase and 6,499 checked — the pass did see the base-1 of 0; the missing lines of 13:29 were the
  play log's lost tail (it ends at t 91 s, the hung job was submitted at 100.46 s; the hard hang dropped the page
  cache), so the first version was **not** dormant there, and R1's 13:29 CPG write stays unexplained by its packets.
- *R1b* (`s6n0345.sh dc9d4f25fc2d41ca R1b 600 off`, 9a221a67, `BC5_DIRECT_GFX_BASE1=learn:1100000000`, RT **off**;
  the first attempt under tag R1 refused: the tag and the 14:22 snapshot of the dead run existed): **the box went down
  at ~110 s and did not come back.** The laptop's kernel stream (`raw/R1b-kernel-stream.txt`, and `R1-kernel-stream.txt`
  of the overlapping first stream): 14:25:12.298 `gmc_v10_0_process_interrupt: 82 callbacks suppressed` — a burst of
  faults — then `[gfxhub] page fault (vmid 6) … thread bc5-ring … in page starting at address 0x00000011dab43000 from
  client 0x1b (UTCL2)`, `GCVM_L2_PROTECTION_FAULT_STATUS 0x00600C30`, **`Faulty UTCL2 client ID: CPG (0x6)`,
  `PERMISSION_FAULTS 0x3`, `MAPPING_ERROR 0x0`, `RW 0x0` — a CP read of a page inside the title's window that the GPU
  may not read**; 14:25:14 `ring gfx_0.0.0 timeout, signaled seq=133120, emitted seq=133122`, `Ring gfx_0.0.0 reset
  failed`, `GPU reset begin`, `bc5-gpu-watch: armed`; 14:25:18 `MODE1 reset`, `GPU reset succeeded, trying to resume`,
  `VRAM is lost due to GPU reset!`, PSP and SMU resumed — and nothing after 14:25:18.66. The box has been offline since
  ~14:30; neither bc5-gpu-watch (armed 14:25:14) nor the hardware watchdog rebooted it; it needs the maintainer's hand.
  The s6n script died with it (no verdict files; the lock file's state after the reboot is unknown). Live saves were
  compared only (dc9d4f25fc2d41ca at the start).

**Verdict.** **Failed, twice, in the same way, and withdrawn.** Both builds took the box down with RT off on a route
the shared build ddfb9456 ran for 600 s (0342 R1): 13:29 (v1) a CPG **write** fault at 0x11da0e2000, a 26-minute hang;
14:25 (v2) a burst of CPG **read** faults at 0x11dab43000, a failed ring reset, MODE1, a dead box. Both addresses lie
in a region (0x11d6000000 + 0x6000000) the host had not learned, and the fault status says the pages were mapped
without the permission — the host's guard pages or placeholders. What both builds have in common is **CP polls
(`COND_WRITE`) at addresses the backend inferred** rather than read from a `SET_BASE` in the same IB: v1 the window +
offset, v2 the carried register + offset; whether the inference was wrong (the hardware's base registers are not what
the backend tracks — per type, or not carried as assumed) or right but pointing at memory the console would have had
and the host had not mapped, a CP fault is what follows, and a CP fault takes the ring reset down with it (F416's 12:52
and both of today's, against the hang-1 class whose ring reset succeeds). So **D16 applies to the CP check itself: no new
GPU read at an address the host has not verified**, and the design below moves the resolution and the verification to
the host, at filter time, where the arguments can be read without the GPU. The per-shader-type base-1 finding stands
(the title's packets prove it); the check's single-base tracking since 0052 is a real error for mixed buffers, to be
fixed on the host side as part of the design below. The sources of both versions stay on the branch (d4ea4f9) as the
record; nothing of 0345 goes into a shared build.

**The safer design for the 12:52 class (the title's refit dispatches after it zeroes base 1) — host side, laptop only,
not built.**
- *Where.* The host's walk over every buffer before `Device::submit` (patch 0001 `submit_now`, the block that already
  resolves each `DRAW_INDIRECT` / `DISPATCH_INDIRECT`'s arguments as `a = base1 + offset` with the carried base and reads
  them through `covered_sorted(maps)`), not the backend. The backend's `apply()` keeps inserting the CP check only for
  dispatches whose base comes from a `SET_BASE` in the same IB (its 0052 behaviour; the CP reads that page anyway), and
  gets no inferred base — the 0345 `GfxBase` path is removed.
- *Two carried bases.* `g_carried[kind].base1` becomes `base1[2]`, set by `SET_BASE` index 1 according to the packet
  header's shader-type bit, and a draw or dispatch resolves against the one its own header's bit names (today the walk
  keeps one `base1` for both: wrong for a buffer that mixes the types, such as 13:29's chain).
- *Resolve and verify on the host.* For a GFX-form `DISPATCH_INDIRECT`, in this order: (1) `a = base1[type] + offset`;
  (2) if `base1[type]` is 0 and the offset looks like a window-relative low dword (the refit's case), the candidate is
  `window + offset` with the window learned from the title's own non-zero `SET_BASE` index-1 values (the high dword;
  0x1100000000 for this title) — a candidate only; (3) the candidate must be inside a **real** mapping of the host's
  table (a userptr / shared / alias mapping of title memory — not a guard, a PRT window or the zero buffer for holes;
  the table knows which is which), the 12 bytes must be CPU-readable there, and the three counts read must pass the
  host's sanity (today's `too_many_groups`) — stale values accepted as in 0038, the CP check is not the point here;
  (4) only then is the packet changed, and only into a form the CP can run without inferring anything: a **real
  `SET_BASE` index 1 of the dispatch's own type to the verified page**, the dispatch with `offset = a − page`, and a
  `SET_BASE` back to the register's previous value (0 for the refit: the title's own state, so its later packets see
  what they saw before) — three packets, no `COND_WRITE`, no poll at an inferred address; the CP then reads the page
  the host read. (5) Anything not verified — base 0 with no plausible window, a candidate outside a real mapping or not
  readable, counts that fail — **is dropped (NOP) and counted**, as the host's "not mapped, DROPPED" already does for
  unmapped arguments; the default for an unverified packet is to leave it alone only when it has a `SET_BASE` in its
  own IB (the CP's read is the title's own, as before 0345).
- *Lines.* One journal line per program for a rewrite and for a drop (the kind, offset, type, base, candidate, the
  mapping it fell in, the counts read), the counts in the existing `gpu check:` periodic line, and the first ten of each
  in full. The journal survives a hard hang where stderr does not (it is synced at the timeout probe).
- *Unit test seam.* The resolution and the rewrite are pure functions over an IB and a mapping table: put them in the
  backend as `bc5/host_indirect.hpp` (`resolve_indirect(ib, bases[2], window, const Table &) -> decisions`,
  `rewrite_verified(ib, decisions) -> ib'`) with Catch2 cases (the refit packet with base 0 → rewritten to
  `SET_BASE page / dispatch / SET_BASE 0`; a guard-mapped candidate → dropped; a compute-type `SET_BASE` then a gfx-type
  dispatch → resolved against the gfx base; the carried pair), and have the host call them — no new GPU read is
  possible from a test, and the host's objects keep their layout (new functions, no changed structs).
- *What it does not do.* It does not check the counts on the GPU for these dispatches (the staircase stays where a
  `SET_BASE` is in the IB); it does not guess a base for anything else; it does not touch draws (they always carry a
  `SET_BASE` in this title). The first test is the maintainer's post-load spot of 12:52 with RT on; the pass line is
  "no CPF/CPG fault, no reset; the rewrite line names 0x90997a500 with a real mapping; drops 0".

**The hang-1 arm (the looping small dispatch of the BVH build chain, ~106 s on the route; ring reset succeeds) —
design, laptop only, not built.**
- *The class.* Exp 0344's hang 1: the CP inside the check of dispatch #49 (0x909873200) while the SEs are busy with a
  dispatch launched before it — #48 0x90986df00 (1 × 1 × 1) or #47 0x90986e700 (11,520 × 1 × 1), direct dispatches of
  the build chain — that does not end; F403's state register for register, no fault, the kernel's 2-s timeout, a ring
  reset that recovers. Not a grid problem: the per-dimension limits and the staircase cannot touch a 1-group dispatch.
- *Arm A — the wave-side bound (exp 0137: `BC5_DIRECT_LOOP_BOUND=<program>:<limit>:<back-edge offset>[,…]`).* The
  host already copies a program into the device's code area and turns each listed back-edge (`s_cbranch_execnz` to an
  earlier instruction) into a trampoline that counts iterations in an unused SGPR and leaves the loop at the limit;
  the tables that name the program are rewritten to the copy (`loop_bound_copy`, "loop bound: table … names the copy").
  Steps: (1) dump the two programs 0x90986df00 and 0x90986e700 (and 0x909873200) with `BC5_DIRECT_SHADER_DUMP` on
  the route (they lie in the title's mapped code, 64 KiB each at most), on the laptop disassemble them with llvm-mc /
  `tools/bc5-agc`'s decoder and list their back-edges and the SGPRs they use (the bound needs a free SGPR; 0137 used
  s104 for the traversal); (2) choose the limit from the loop's nature (a tree walk: the node count; a build step: the
  element count) — generous, so that a correct run never hits it, and journal the hits (the copy can also write a
  marker word the host reads back: "bounded at iteration N"); (3) run the route RT on with the bound on those programs:
  pass = no ring timeout at ~106 s, or a timeout elsewhere with the marker showing which loop was cut; the picture may
  lose what that dispatch computed (reflections for a frame), the box stays up.
- *Arm B — the diagnostic skip.* `BC5_DIRECT_SKIP_PGM=90986df00,90986e700` (exists: drops a program's dispatches in
  any buffer) on the route: if the hang moves or vanishes, the looping program is named without disassembly; the
  consumers of its output then run on stale data (the F404 lesson: skipping the compaction moved the freeze, it did not
  cure it), so B is a bisection tool, not the fix.
- *Why not a per-dispatch GPU timeout.* The kernel's 2-s `lockup_timeout` already is one, and its reset recovers for
  this class; the cost is the 2-s freeze and the lost frame. A shorter kernel timeout is the maintainer's module
  parameter, not the host's.
- *Order.* B first on the route (one run, read-only on the title: which program), then A for that program; both after
  the host-side design above has removed the machine-down class, since A and B share the route with it.
