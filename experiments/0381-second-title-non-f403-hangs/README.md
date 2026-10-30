# 0381 — The second title's GPU hangs that are not F403: the 18:08 graphics stall and the 16:25 TCP fault

**Date.** 2026-10-29 (evening, the maintainer away). **Branch.** `exp/0381-non-f403-hangs`. **Box.** Reads only, on the
top session's GO (section 3); everything else on the laptop.

## Question

1. The 18:08:13 hang on the shared normal build (58c4a627, RT on; F588) is a graphics-pipe stall, not F403. Which
   state is it against the healthy baseline of exp 0378, and which draw or pass hangs?
2. The 16:25 start-up fault (exp 0380 start 1, test binary c3c8660b; F582/F586) — a TCP read fault at junk addresses,
   ring resets that succeed, the picture lost, program 0x909977100 — is it F443/Q22's garbage-pointer class, and does
   it tie to the BVH compaction (F207, F370) or to the garbage-pointer work (F92, F467)?
3. For each: the evidence, the hanging pass if the data allows, and the next test or fix candidate.

## Setup

- Read: HANDOFF F207, F403, F443, Q22, F467–F469 (exp 0364), F490–F495 (exp 0368), F519, F525, F534–F535, F553,
  F558, F582–F609 (exp 0380's branch at 6c0c84d), exp 0380 README §16–17 and its `raw/hang-1808/`, `raw/wbplay/`,
  the 0300 close-out (`docs/closed-branches/exp-0300-rt-dispatch-sync/`), the shared notes of the BVH compaction
  session (exp 0160's hand-over, the compaction output design note).
- `ana0381.py`: decodes the 18:08 devcoredump registers, F519's ASTRO BOT stop, the two 16:25 sampler values and
  F525's F403 sample with Linux v7.2 `gc_10_1_0_sh_mask.h` (blob 9b7d219e, ana0378.py's functions), compares 18:08
  field by field with exp 0378's 40 healthy forced samples and tests single-sample rules. Output `raw/ana.txt`.
- `reads0381.sh` (box, reads only): guard, lock, claim, then `walk0381.py` over the two private probe dumps
  (`ib-timeout-00127530-dcb-14945.bin`, `ib-timeout-00032979-dcb-14911.bin`): every draw and dispatch with the
  shader-stage, tessellation, streamout and user-data registers the IB itself sets (state from `LOAD_*_REG_INDEX`
  tables is invisible to it); the two devcoredumps' status registers; the probe and learned-region lines of the two
  journals. `filter0381.py` turns its output into the committed extracts; the dumps and journals stay private.

## 1. Laptop results

### 18:08 is a third stall state (F660)

Decoded (`raw/ana.txt`):

| | 18:08 | F403 (09:48) | F519 (ASTRO BOT 06:34) |
| --- | --- | --- | --- |
| `GRBM_STATUS` | 0xa2712028: GE, PA, SX, SPI busy; CB clean, DB **not** clean, SC/DB/CB idle, TA idle | 0xa0407028: TA, SPI busy; CB/DB clean | 0xe5f100ac: GE, SX, SPI, BCI, SC, DB, CB busy |
| `GRBM_STATUS2` | 0x50000008: no TCP, EA, EA_LINK, UTCL2 | 0x52000008: TCP busy | 0x50000008 |
| SE0 / SE1 | 0x0d000004 both: PA, SX, SPI | 0x0a000036: TA, TCP, GL1CC, SPI | 0x08000000 / 0xec400000 |
| `CP_STALLED_STAT2` | 0x218000: ME waits on a partial flush, EOPD needs SC EOP done | 0x18000: partial flush | 0x31000: ME parsing, RCIU not ready |
| `CP_BUSY_STAT` | 0x448400: EOP_DONE_BUSY, GFX_CONTEXT_BUSY | 0x400400 | 0x428100: ME parsing packets |

- Against the 40 healthy samples it is never close: the nearest differ by 18–20 status bits (F534's F403 sample
  differed from a healthy one by one bit). No healthy sample has GE busy with TA idle together with the partial-flush
  and EOP waits (0/40); 17 have the partial-flush wait, 3 of them with GE busy, 2 with GE busy and the EOP wait,
  and all three of those with TA, EA and `EA_LINK_BUSY` busy (10:51:35, :45, :50).
- The five sampler records over 1.2 s are identical (`GRBM_STATUS` 0xa2712028 in all; exp 0380 `raw/hang-1808/`).
  A draw grinding through a huge count would toggle SC/DB/TA; this is a standstill.
- So: waves resident (SPI busy) with **no memory traffic at all** (TA, TCP, GL1, EA, UTCL2 idle), the geometry
  front end (GE → PA, with SX's export path) holding work, the rasteriser and the back end empty, the CP past the
  IB waiting for the pipe to drain. The class is a geometry-front-end deadlock, distinct from F403 (compute waves
  busy in TA/TCP, GE idle) and from F519 (the back end busy, no partial-flush wait).

### Single-sample rules (F661)

| rule | healthy (40) | 18:08 | F519 | F403 |
| --- | --- | --- | --- | --- |
| F535: partial-flush wait, `EA_LINK_BUSY` clear | 0 | yes | no | yes |
| F589 compute: F535 + TA busy, GE idle, no EOPD wait | 0 | no | no | yes |
| graphics: F535 + GE busy, TA idle, EOPD wait | 0 | yes | no | no |
| graphics without the EA term | 0 | yes | no | no |

The early-warning design of F535 can therefore name two classes from one sample: `f403-early` (compute) and
`gfx-stall-early` (graphics). F519 is caught by neither (no partial-flush wait); it needs the stall clock alone.

### 16:25 is F443's pointer family, not the compaction (F663, F665)

- The ten fault pages 0x8608c654000…0x8608c660000 (TCP, read, `PERMISSION_FAULTS` 0x3, status 0x00601031) have the
  low dwords 0x8c654000–0x8c660000. F443's junk pages were 0xe3808c5f2000…0xe3808c634000, low dwords
  0x8c5f2000–0x8c634000, which exp 0364 showed are one dispatch family's `COMPUTE_USER_DATA_3` offsets under the
  shared high dword 0x11 with that high dword replaced by garbage (F467). The 16:25 pages lie 0x20000–0x6e000 above
  them, under another garbage high dword (0x860 instead of 0xe380). Exp 0380 searched the maps for 0x8608c65c000,
  0x608c65c000 and 0x8c65c000 but not for 0x118c65c000, the address the family's layout predicts.
- The stuck dcb has the family's shape: a `LOAD_SH_REG_INDEX` from a 0x9098… table (0x909842dc0 here; F467:
  0x909841e50, 0x909842900, 0x9098426a0; F422: 0x909842440), then `SET_SH_REG` of `COMPUTE_USER_DATA_3…`
  (registers 0x243/0x247) between unbased GFX-form `DISPATCH_INDIRECT`s (exp 0380 `raw/wbplay/dcb-32979-head.txt`).
- Program 0x909977100 is the BVH adjacency build, one of the three consumers of the compaction 0x909974400's
  compacted list (exp 0160's reading, the compaction session's hand-over), and the compaction runs in the shared
  launchers (`BC5_DIRECT_SKIP_PGM=0`, exp 0378 `raw/B1-start.txt`). That is the only tie to F207: F207's fault is
  the geometry engine (GE2/WD) reading page 0 with the full-state prefix, a different client and mechanism.
- F443 happened on a build without `FORCE_START_AT_000` (the ledger build, 10-28), so the 16:25 test binary's
  FORCE_START is not needed to explain the class.
- Unlike F443, no real-address fault came first: the first printed fault is already a junk address (and the
  kernel's rate limit printed exactly ten). So the high dword was garbage from the start of the access, not
  after a first fault. Where the high dword comes from (the IB's user data, the `LOAD_SH_REG_INDEX` table, or a
  pointer the shader loads from the compacted data) is what the box read decides.

## 2. Hypotheses, ranked

18:08:
- **H1 (lead): a geometry-front-end deadlock in one of the dcb's last draws**, waves resident without memory
  traffic. Sub-cases: (a) tessellation: the dcb holds HS-stage draws (the probe's "HS user data" lines at dwords
  1046, 9233, 12139), the host owns the TF ring and the full-state prefix rewrites `VGT_TF_RING_SIZE` /
  `VGT_TF_MEMORY_BASE(_HI)` in front of every drawing dcb (F599), and exp 0160 tied the second title's GE faults to
  tessellation state; (b) an NGG or GDS ordered-count wait (the title appends to GDS, F207).
- H2: a runaway indirect draw with a garbage count, the graphics twin of F403 sub-class B. Against it: the
  standstill over 1.2 s and TA idle.
- H3: a memory wait (late data after the unpause, page-cache pressure F602). Against it: EA, UTCL2, TCP idle, no
  fault.
- Not F403: TA/TCP idle, GE busy, EOP pending (F588; the table above).

16:25:
- **H4 (lead): F443's dispatch family reading or building a pointer with a bad high dword**, the class of F92's
  junk upper bits. Sub-cases: (a) the bad high dword is in the IB's user data or in the `LOAD_SH_REG_INDEX` table
  (the host's tracking or a stale table); (b) the shader loads it from data that was not written yet at start-up
  (the compacted list or its header, written on another ring or later: the compaction design note's outcomes b/c).
- H5: the lazy-import class of F468 (an unimported view). Against it: no real-address fault preceded the junk.
- H6: the test binary's FORCE_START. Against it: F443 without it.

## 3. The box reads (late evening 2026-10-29, the top session's GO, reads only)

`reads0381.sh` was refused by the laptop's permission classifier as a remote shell write, so it never ran: no lock
line, no claim directory and no queue lines were written on the box (the top session was told). The same reads ran in
read-only form instead, each `ssh` starting with the emulator guard (none ran; BOX-LOCK was empty):
`walk0381.py` fed over stdin against `play-20261029-1716/gc/ib-timeout-00127530-dcb-14945.bin` and
`play-20261029-1624/gc/ib-timeout-00032979-dcb-14911.bin`, `grep` of the status registers and fault lines of
`devcoredump/20261029-162542-devcd1.txt` and `-162544-devcd2.txt`, the last 400 `timeout probe` lines of
`play-20261029-1716/gc/direct.log`, the 16:25 journal's probe lines, and the learned list (109 windows, a7cc8581).
`extract0381.py` made the committed extracts: `raw/hang-1808-indirect-draws.txt`, `raw/hang-1808-walk-summary.txt`,
`raw/hang-1625-dispatch-pointers.txt`, `raw/hang-1625-devcd-regs.txt` (register values, packet offsets, argument
dwords and addresses only; the probe's memory dumps and user-data dumps were dropped; the words left were checked:
register, packet and tool names only). The dumps and journals stay private.

`walk0381.py`'s IB-only state is unreliable for this title (252 `LOAD_*_REG_INDEX` packets in the 18:08 dcb); the
probe's own "state before" lines, which track the loaded tables, are used for stages and programs instead.

### 18:08: the dcb's indirect draws hold index-like counts (F662)

- No tessellation: in the probe's tracked state every draw of the dcb has `hs 0` and `ls 0`. H1(a) is out; the
  "HS user data address 0x0" lines are generic (they also appear at 09:48).
- The dcb's last draws (dwords 12640–14286) are one pass: `VGT_SHADER_STAGES_EN` 0x482030 (ES_EN 2, GS_EN,
  PRIMGEN_EN, GS_FAST_LAUNCH 1, GS_W32_EN; Linux v7.2 `gc_10_1_0_sh_mask.h`), primitive type 1 (point list), ES
  programs 0x11d00f85xx–0x11d01345xx, 15 `DRAW_INDIRECT` with arguments at `SET_BASE` 1 0x1193ad3900 + 0xc4a0 …
  0x229a0, interleaved with `DRAW_INDIRECT_MULTI` (count 1–4, stride 32) from 0x11228fff70 … 0x1122905e70.
- At the timeout the probe read these `DRAW_INDIRECT` arguments (vertex count, instance count, start vertex, start
  instance): **13 of 15 hold ascending 16-bit pairs**, e.g. 000f0101 000f0102 000f0103 000f0104 (dword 12640),
  00050006 00050007 … (13566), 000a01a7 000a01a8 … (14178), i.e. 2^16–2^20 vertices times as many instances; only
  13972 (0x35, 1) and 14061 (1, 1) are sane. The multi-draws' first records are sane (0x1b–0x3b vertices, 1
  instance).
- Such a draw in fast-launch mode would launch 10^10–10^12 primitive-shader threads: GE, PA, SX and SPI busy for
  as long as the GPU runs, and a static status if the waves exit early without vector memory traffic. That turns
  H2 (a runaway indirect draw) into the lead: the graphics twin of F403 sub-class B's index-like dims (F590).
- What the dump cannot say: whether the CP fetched these words, or the title overwrote the slots after the GPU had
  read sane ones (the title's CPU side runs on for ~2 s after the hang). The 12:12 B event shows the opposite case
  (sane memory at the timeout, garbage launched, F553/F590), so the CPU view at the timeout is a lead, not proof.

### 16:25: the IB's pointers are right; the shader makes the bad high dword (F663, F664)

- 887 of the dcb's 893 dispatches set `COMPUTE_USER_DATA_5` = 0x11 with `USER_DATA_3`/`4` low dwords
  0x8c64e600–0x8ce71c00; the other six use other layouts (three direct dispatches among them). Every fault page has
  one of these low dwords: 0x8608c65c000 is exactly `USER_DATA_3` 0x8c65c000 of five dispatches, 0x8608c654000 is
  the page of 0x8c654a00/0x8c654c00 (dword 43), and devcd1's recorded fault 0x8608c728000 lies in the range. The
  intended addresses 0x118c654000…0x118c728000 lie in the learned (imported) window 0x118a000000 + 96 MiB.
- So the IB carried the right high dword and the memory was mapped: neither the host's user-data tracking (H4a for
  the IB) nor a lazy view (H5, F468) explains it. The shader formed 0x860 in place of 0x11 from data it loaded:
  F467's "later loads of a high dword returned garbage", here without a real-address fault first. Where the
  high half comes from (the `LOAD_SH_REG_INDEX` table at 0x909842dc0, the compacted list, a descriptor) needs the
  program's code (0x909977100, read by the BVH compaction session); H4b stays open.
- devcd1 (16:25:42): `GRBM_STATUS` 0xa04030ac, SE0/SE1 0x08000006 (SPI only), `GRBM_STATUS2` 0x50000008, PFP 0xea0,
  ME 0xe15: waves resident without memory traffic after a no-retry fault. devcd2 (16:25:44, after the first
  successful reset): shaders idle, the ME's newest header `WAIT_REG_MEM64` (0xc0079300), `CP_STALLED_STAT2`
  0x10000: the next job waits on a 64-bit label. The killed dcb #32979 had 45 label writes (the probe: e.g.
  0x12004bac80 to be written 2, read 1 at the timeout). **The picture was lost because the reset kills the job that
  would have written the title's labels, so every later job waits on them**: F403's devcd4 pattern (F403's
  correction of 18:45).

## Result

- **18:08 (F660–F662): a graphics-pipe stall of its own class, most likely a runaway fast-launch NGG
  `DRAW_INDIRECT`.** Its state is static and ≥ 18 status bits from every healthy sample. The stuck dcb's last pass
  is the fast-launch point-list pass (stages 0x482030, ES 0x11d00f85xx…, no tessellation), whose argument slots at
  0x1193ad3900 + 0xc4a0…0x229a0 held index-like counts in 13 of 15 draws at the timeout. The candidate hanging draw
  is the first slot the CP read garbage from; on the dump that is dword 12640.
- **Rules (F661):** the graphics stall and F403 are told apart in one sample; F535's rule fires on both.
- **16:25 (F663, F664): F443's class (Q22's family) exactly.** The same `USER_DATA_3/4` pointer family under
  `USER_DATA_5` = 0x11, the same garbage high dword made inside the shader, in the BVH adjacency build's dcb. Not
  lazy import, not the IB, not FORCE_START. The lost picture is the killed job's label writes.
- **Tie to the BVH work (F665):** 0x909977100 consumes the compaction's output and the compaction runs in the
  shared launchers; the tie to F207 (a GE read of page 0) is the program window only.

## Verdict

Both hangs are classified with evidence. 18:08 is not F403 and not F519: a geometry front end busy with no memory
traffic behind a fast-launch pass whose indirect draw counts read index-like at the timeout, sub-class B's twin on
the draw side, with the read-time question open. 16:25 is F443/Q22's garbage-high-dword class in the BVH adjacency
build, decided against lazy import and the IB's user data; the shader's own load is left.

Next (F666), cheapest first:
1. **Control read (box, reads only, ~2 min):** the `op 24 at` / `op 2c at` probe lines of the earlier hang journals
   (09:48, 12:12, 14:04 of 10-29; 18:15 and 23:36 of 10-28). If the same fast-launch slots (0x1193… + offsets) hold
   index-like counts at those timeouts too, while those hangs were compute (F403), the CPU view at the timeout is
   not evidence and 18:08's draw stays unnamed; if they hold sane counts, 18:08's garbage is specific and the draw is
   named.
2. **A host-only submit-time log (no packet, default off):** for `DRAW_INDIRECT` whose base 1 lies in the 0x1193…
   window, journal the four argument dwords at submit and flag counts above 2^16: "garbage at submit" (title data or
   our memory sync) against "sane at submit" (the fetch, as in B). One CPU read per draw.
3. **Fix candidate (design, default off, needs the maintainer's yes):** a CP-side draw guard, the draw analogue of
   the dispatch check: `COND_WRITE`/`COND_EXEC` on the vertex and instance counts of each GFX-ring `DRAW_INDIRECT`,
   skipping the draw if either exceeds a limit (e.g. 2^16 instances), so a garbage count costs one draw, not the box.
   Like the dispatch check it does not help if the CP reads other data than the check polls (F590).
4. **16:25:** read 0x909977100's code (the BVH session's private disassembly) for how it forms the pointer's high
   half. A recovery candidate: after a ring reset that succeeds, have the host complete the killed job's label
   writes (it knows them from the filter), so later jobs do not wait forever (TODO(verify) against the title's
   expectations).

## 4. Follow-up on the laptop (night of 10-29/30): the draw journal, the existing draw check, the program's code (F667–F669)

**The CP already checks these draws (F667).** The shared builds' host puts experiment 0057's check in front of every
GFX-ring `DRAW_INDIRECT` / `DRAW_INDEX_INDIRECT` with a known base when `BC5_DIRECT_GPU_CHECK` is set (patch 0001:
`opt.gpu_check_draw_max` = 2^20 vertices, 64 instances, overridable by `BC5_DIRECT_DRAW_MAX`; `indirect_check::apply`,
`kDrawCheckDwords`). Every index-like slot of F662 has an instance count far above 64 (0x000f0102 = 983,298), so a
check whose `COND_WRITE`s polled those words would have skipped the draw. A runaway 18:08 draw therefore needs one of:
the polls read sane words and the fetch read other data (sub-class B's mismatch, F590, now on the draw side); the
words arrived after the draws ran (then the draws were not runaways and the stuck work is elsewhere); or no check in
front of them (the switch unset in that play). `drawcheck0381.py` lists, from the devcoredump's own IB, each draw with
the `COND_WRITE`s and `COND_EXEC` before it: the read for step 1. So the step-3 "draw-count guard" exists; what is
missing is the same thing as for B, the assurance that the CP fetches what it polled.

**The journal (step 2, F668): `BC5_DIRECT_DRAW_ARGS_JOURNAL=1`, default off, CPU reads only.**
- `backend/include/bc5/draw_args.hpp`, `src/draw_args.cpp`: `scan` (every based `DRAW_INDIRECT` / `DRAW_INDEX_INDIRECT`
  of a filtered GFX IB, the four argument dwords read through a reader), `classify` (over the check's limits,
  index-like: two of three neighbouring dwords step by one with a count above 0xffff, unread), `line`, `reread`.
- `src/direct.cpp`: at submit, after the 0341 histogram and before the CP check is inserted, the job's records are read
  (`process_vm_readv`, so an unreadable slot is reported, not fatal) and kept in its slot; `finish()` (and the
  synchronous path) reads them again when the fence signals or times out. A timed-out job prints every record
  (`bc5-direct: exp 0381 draw-args submit seq … v … flags … | timeout v … flags … changed yes|no`); otherwise the
  first 256 flagged records and then one in 4096, and a summary every 100,000 draws and at close.
- What it decides: healthy completions with index-like words in these slots make the timeout read worthless; healthy
  completions with sane words and a hang with index-like words at the timeout make F662 specific. Its format follows
  the timeout probe's and exp 0380's recorder's "one line per record" journal (`rec0380.inc` read, not edited).
- Tests: `tests/draw_args_test.cpp`, 4 cases (scan with and without a base, the 18:08 words against sane ones, the
  line and the re-read). Laptop: `cmake -S backend -B <scratch> -DBC5_BUILD_TESTS=ON` (Visual Studio 18 2026, Catch2
  from the main checkout's fetch), `cmake --build <scratch> --config Debug --target bc5_backend_tests`,
  `bc5_backend_tests.exe`: all tests passed (33,706 assertions in 95 test cases; 30 in the 4 new ones). `direct.cpp`
  is not compiled on the laptop (it needs libdrm_amdgpu): its compile check is a box step (clang in the `ubuntu`
  container, as exp 0380's A0), not done.

**The program's code (step 4, F669).** No disassembly or binary of 0x909977100 is on the laptop: the scratchpads of the
other sessions and `private-dumps/` hold only journal lines and IB dumps naming it. The read goes into the step-1
request (a `find` for a dump of it on the box, then `llvm-mc -mcpu=gfx1013` there).

**Step-1 request, extended (reads only, guarded ssh, no file written on the box):**
1. the `op 24`/`op 2c` probe lines of the earlier hang journals (09:48, 12:12, 14:04 of 10-29; 18:15, 23:36 of 10-28);
2. `drawcheck0381.py` over stdin on `devcoredump/20261029-180813-devcd3.txt`;
3. `find ~/bc5-work ~/bc5-data/captures -maxdepth 4 -iname '*977100*'`, then, if a code dump exists, its disassembly to
   stdout.

## 5. Codex review (REVIEW-04): corrections (F670)

Codex's independent review of `ab86f97` and the follow-ups (`C:\Users\kjani\Documents\ChatGPT\BC5\audit\REVIEW-04.md`,
with `review04_evidence.py` and `test_review04_guard_heuristic.py`; accepted by the top session) narrows five claims.
They are corrected here; sections 1–4 stay as written.

1. **18:08's state (F660, §1, §3) is a distinct graphics/front-end stall signature, not a shown deadlock.** Five
   discrete register samples cannot show "no movement" or "no memory traffic" across the 1.2 s between them; SPI busy
   is not a wave scan (the sampler ran registers only); and static status bits do not tell a deadlock from work or a
   wait that leaves those bits unchanged. A runaway draw is not excluded on those bits, and a deadlock is not shown;
   both stay mechanisms to decide. The 18–20-bit distance describes how the registers differ; it is not a
   probability.
2. **The counts (F662) mix two definitions.** Of the 15 `DRAW_INDIRECT` slots, **13 have an instance count above 64**
   (the existing check's limit) and **12 are index-like by `draw_args::index_like`** (at least two neighbouring dwords
   step by one, a count above 0xffff): 14127's 0x8a64 0xa418 0xa41d 0xa48d is over the limit without the steps.
   The journal already reports the two as separate flags (`over-instances`, `index-like`; `draw_args_test.cpp`
   asserts 14127's flags are `over-instances` only). "Candidate hanging draw: dword 12640" is withdrawn: 12640 is the
   first slot with suspicious *later* contents; which address the CP fetched is unknown. The stage and program state
   in the probe's lines is also a later read of mutable tables, so "no HS/LS" is weaker than a direct exclusion of
   tessellation in what ran.
3. **`drawcheck0381.py`'s first version counted any `COND_WRITE` and `COND_EXEC` among the 8 packets before a draw.**
   Codex's synthetic counterexample (a poll of an unrelated address, a zero-dword `COND_EXEC`) came out "checked". It
   now verifies, per draw, the six packets `indirect_check::apply` emits, in order and adjacent to the draw: flag
   initialisation, both polls at the args address and address + 4 (the base in effect + data offset), function 6, mask,
   the write target and value, the `WR_CONFIRM` write at flag + 4, `PFP_SYNC_ME`, and a `COND_EXEC` on the same flag
   covering exactly the draw. It names the first mismatch. `test_drawcheck0381.py`: 6 cases pass (the emitted check,
   Codex's counterexample, a shifted poll, a zero-dword and a wrong-flag `COND_EXEC`, no base). The flag word left at
   a timeout may belong to another draw of the job (one flag per IB), so it is not read as that draw's result.
4. **F661 is a signature tag, not a validated detector.** The rules were chosen after looking at these samples; 0 of 40
   on the same set gives no false-positive rate (even for 40 independent samples, the one-sided 95 % binomial bound is
   about 7.2 %, and these are correlated). Use it to label an event the stall clock already caught; never trigger a
   reset or a GPU change on it.
5. **16:25 (F663, F664) narrowed.** `USER_DATA_5` = 0x11 and matching low dwords support the same pointer family as F443;
   they do not show that the shader loaded a bad high dword. The IB is not a snapshot of the waves' registers after the
   `LOAD_SH_REG_INDEX` tables, and offset arithmetic gives the same low dword: 0x118c65c000 + 0x84f00000000 =
   0x8608c65c000. The mapped learned window shows coverage, not the contents at the fetch. The first *printed* fault
   under the kernel's rate limit need not be the first access, so "no real-address fault came first" is withdrawn. The
   address path needs the faulting instruction's dataflow (F669's box step). F664: the data show one later job waiting
   on a label the killed job did not write; "every later job waits" is wider than the evidence.

Consequences for the next steps: the existing guard read (now verified per draw) comes first; the strongest control
for F662 is a healthy, completed job of the same pass whose slots read index-like at completion (F668's journal), not
an earlier compute hang that never reached the pass.

## 6. The box slot (2026-10-30 ~00:5x, the top session's GO, read-only ssh, nothing written on the box) (F671–F673)

**The guard (F672).** Strict `drawcheck0381.py` over stdin on `devcoredump/20261029-180813-devcd3.txt`
(`raw/hang-1808-drawcheck.txt`): **all 15 `DRAW_INDIRECT`s of the hung host IB carry exp 0057's check, verified
packet for packet** (flag = 1; `COND_WRITE`s polling exactly base 0x1193ad3900 + data offset and + 4, function 6, limits
2^20 vertices and 64 instances, writing 0 to the flag; the confirm write; `PFP_SYNC_ME`; a `COND_EXEC` on the same flag
over exactly the 5-dword draw). So a draw ran only if its polls read a vertex count ≤ 2^20 and an instance count ≤ 64.
If one of these draws ran away, the CP fetched other words than it polled (sub-class B's mismatch, F590, on the draw
side); otherwise the index-like words arrived after the draws were polled, and the stuck work is not shown to be these
draws. Which of the two needs F668's journal (healthy completions) or a fetch-side record; the guard is not the gap.

**The control (F673).** The full-journal grep was refused by the laptop's classifier ("interfere with workloads"); the
same grep over the last 8 MB of each journal (`raw/control-earlier-hangs-draws.txt`) found the probe lines of the five
earlier hangs (10-28 18:15, 23:36; 10-29 09:48, 12:12, 14:04): none of their dcbs holds the 0x1193ad3900 fast-launch
pass; their 8 `DRAW_INDIRECT` slots (base 0x11a5c68000) and 4 multi-draws all read sane at the timeout. As Codex
predicted, a weak control: it shows sane slots of another pass, not the same pass completing.

**0x909977100's address path (F671).** A disassembly exists on the box (`~/bc5-work/dis-909/dis-909977100.txt`, 502
lines, from the private shader dump `captures/shaders-0159*/0909977100.bin`); it was read into the laptop's private
scratchpad and is not committed. In it (user SGPR k = `COMPUTE_USER_DATA_k`):
- the program's only vector-memory load (one `buffer_load_dwordx4`, so the source of every TCP *read* fault in it) uses
  a buffer descriptor whose 48-bit base is built as low = `USER_DATA_3` + (header dword 0x9c × 32) + 0x80 and high =
  `USER_DATA_0` + the carry of that add (at most 1), with a stride bit set in the same word; header =
  {`USER_DATA_5`:`USER_DATA_4`} (0x118c654a00 at 16:25, read by scalar loads, not TCP);
- its stores use bases from `USER_DATA_1` (high) with `USER_DATA_6` (low), and a 64-bit pointer from the header plus
  {`USER_DATA_1`:`USER_DATA_6`}.

So the faults' high half 0x860 is `USER_DATA_0`'s low 16 bits (or one less), **not** `USER_DATA_5` and not a pointer the
shader loaded. Offset arithmetic adds at most a carry of 1 to the high half; an index × stride carry would need an index
of at least 0x84f00000000 / stride, impossible for a 32-bit index at the stride the title's 0x0010_xxxx values give
(16), and an out-of-range index is clamped by the descriptor's record count (TODO(verify): the gfx10 V# word-1 layout,
base [47:32] in bits 15:0 and stride in bits 29:16, from the RDNA 1.0 ISA guide's buffer resource table and Mesa's
`ac_build_buffer_descriptor`). This narrows Codex's counter-model to "a wrong `USER_DATA_0`".

**Where `USER_DATA_0` comes from.** `walk0381.py` and exp 0380's `binspan0380.py` over the 16:25 IB (read again for
this, a read-only stdin run after the top session had been told the box was free): **none of the 890
`DISPATCH_INDIRECT`s has `USER_DATA_0` or `USER_DATA_1` set by a `SET_SH_REG`**; the IB's first `SET_SH_REG` at 0x240
is at dword 13824, after the chain. They come from the `LOAD_SH_REG_INDEX` tables the CP fetches at dword 8
(0x909842dc0, 10 entries) and 8418 (0x909843280, 10 entries; format bit 31 set, TODO(verify) PAL's offset-and-data
form) or from state carried in from an earlier IB. F443's high half 0xe380 fits the same register. So the 16:25 and
F443 faults are a wrong `USER_DATA_0` for the adjacency build, which the host never writes: either the title's table
held it (written late or not at all at start-up), or the CP's table fetch read other data (a CP-side fetch like
sub-class B's), or a carried register.

**Next for 16:25:** the title's tables at 0x909842dc0 / 0x909843280 hold the answer. The host already tracks
`LOAD_SH_REG_INDEX` tables (F207: `BC5_DIRECT_DISPATCH_JOURNAL=1` lists program and user data through them); a start-up
run with that journal shows `USER_DATA_0` of these dispatches at submit (0x11-like or not); and the timeout probe could
dump each `LOAD_SH_REG_INDEX` table's pairs at a timeout (host-only, no packet). Not done: a run needs the maintainer's
yes.

**Not done in the slot:** the compile check of `direct.cpp`'s hook (`compile0381.sh`, the throwaway
`~/bc5-work/exp0381cc`) was refused by the laptop's classifier as a remote shell write; listed for the morning.

## 7. Codex review (REVIEW-06): a host replay path for 16:25, and a third reading of 18:08 (F674, F675)

Codex's REVIEW-06 (in progress, `C:\Users\kjani\Documents\ChatGPT\BC5\audit\REVIEW-06.md`), relayed by the top session.

**F672's third reading (F675).** The slots may already have held the index-like words when the CP polled them. Then
the guard did its job and skipped those draws, and the stall came from other work. Fifteen verified guards show that a
draw ran only if its polls read sane counts. They do not show that any of these draws ran. So F672 has three readings:
the fetch read other words than the polls (B on the draw side); the words arrived after the polls; or the words were
there at the poll, the draws were skipped, and the stuck work is elsewhere in the job.

**A host replay path for 16:25 (F674).** F671's "the host never writes `USER_DATA_0`" does not follow from the title IB
alone. Two host prefixes replay SH registers from the CPU-side tracker, and both cover `USER_DATA_0` (SH 0x240):
- the compute-state prefix (`BC5_DIRECT_CS_PREFIX=1`, on in `play-pkg.sh` since 10-24, F321; SH 0x204–0x3ff, in front
  of a dcb that dispatches before it sets `COMPUTE_PGM_LO`; F254 names the BVH 0x0909… buffers with their first
  dispatch at offset 8–27, the 16:25 dcb's shape);
- the full draw prefix (`prefix_of(t_fs_before)`, in front of every drawing dcb; the 16:25 dcb has two
  `DRAW_INDEX_AUTO`s).

The tracker applies `LOAD_SH_REG_INDEX` tables, but from the CPU's view of the table at submit
(`backend/src/full_state.cpp:185-193`), so a table the CPU read early or stale becomes the replayed value. Codex ran
the real `full_state.cpp` on a synthetic table and got a prefix that writes `USER_DATA_0` = 0x860 while the later
table holds 0x11.

What decides it on the CP: the dcb's own `LOAD_SH_REG_INDEX` at dword 8 (table 0x909842dc0, 10 pairs) runs after any
prefix. If that table names 0x240, the prefix value is overwritten, and the bad value comes from the table or the CP's
fetch of it. If it does not, the prefix's replayed value is what the waves use, and a 0x860 there is a host bug. One
conflict stays open: exp 0380's shape scan lists the 16:25 dump as `prefix=0 title_at=0 first_di=13`, and from the
laptop it cannot be told whether that scan read the emitted IB.

The read: `head0381.py` over the 16:25 devcoredump's IB #0, the emitted IB. It lists the packets up to the first three
`DISPATCH_INDIRECT`s, with any `CONTEXT_CONTROL` / `CLEAR_STATE`, every `SET_SH_REG` value of SH 0x200–0x24f and the
`LOAD_SH_REG_INDEX` addresses. At 2026-10-30 ~01:xx the guarded read-only ssh found an emulator running and exited
with nothing read. It runs when the box is free.

**The read (F676; 2026-10-30, the top session's GO, under exp 0379's bench lock, one file read).** The emitted IB of
the 16:25 job (`raw/hang-1625-emitted-head.txt`) begins with the title's own `ACQUIRE_MEM` and its
`LOAD_SH_REG_INDEX` at dword 8 (0x909842dc0, 10 pairs). The host added only a `PFP_SYNC_ME` before each
`DISPATCH_INDIRECT` (initiator 0x65: FORCE_START on this test binary). **No host prefix stands in front: no
`CONTEXT_CONTROL`/`CLEAR_STATE`, and no `SET_SH_REG` of `USER_DATA_0`–`2` before the first three dispatches.** The
first `SET_SH_REG`s set `USER_DATA_7`–`14` and `3`–`14` (0x8c654c00 / 0x8c654a00 / 0x11 / …), the title's own. So
in this job our prefixes did not write `USER_DATA_0`. The value the waves used came from the dcb's table at dword 8 if
that table names SH 0x240, or else it was carried on the ring from an earlier IB. An earlier IB's last write could be a
host prefix's replay, the title's own, or the table load of an earlier dcb. The table's contents are title memory, not
in the dump. They are visible at submit through the host's table tracking (`BC5_DIRECT_DISPATCH_JOURNAL=1`, F207). The
absence of a `cs prefix` journal line for this dcb would mean the table names `COMPUTE_PGM_LO` (`cs_inherit_at`), not
that it names `USER_DATA_0`.

## 8. A second F443-class event at start-up, 2026-10-30 01:26 (exp 0379 D2) (F677, F678)

**The event (the top session's report).** Exp 0379's D2 run used binary e1cc0c92 with the zero skip off and RT on. The
S6N runner started from a copy of the live saves. At about t 57–59 s, before any menu key, TCP read faults came at
0x8608c654000 … 0x8608c65d000. The `GCVM_L2_PROTECTION_FAULT_STATUS` was 0x00701031 and RW 0 (`sudo dmesg`, read
here). The gfx ring timed out at 2012.996 and the ring reset succeeded, with no reboot. The run was then stopped by
TERM. The devcoredump is `20261030-012643-devcd1.txt` (its recorded fault page is 0x8608d027000, status 0x701030), and
the sampler event is `event-20261030-012643-gfx_0.0.0`.

**Read (the top session's GO, read-only, under exp 0379's lock).** `head0381.py` over the devcoredump
(`raw/hang-0126-emitted-head.txt`), `walk0381.py` over `play-20261030-0125/gc/ib-timeout-00034604-dcb-14911.bin`, and
the sampler summary's compute and status lines.

**It is the 16:25 job again (F677).**
- **The same buffer.** dcb #34604 has 14,911 dwords (16:25: #32979, 14,911). It holds 890 `DISPATCH_INDIRECT`s plus
  three direct dispatches. In 887 of them `USER_DATA_5` is 0x11; 2 carry 0x700000 and 1 carries 0x100011, the same
  histogram as 16:25. The first 538 dispatches sit at the same dword offsets.
- **The same opening and no prefix.** The emitted IB opens with the same `ACQUIRE_MEM` and the same
  `LOAD_SH_REG_INDEX` (0x909842dc0, 10 pairs) at dword 8. No host prefix stands in front, and nothing sets
  `USER_DATA_0`–`2` before the first three dispatches. The first `SET_SH_REG`s carry the same `USER_DATA_3`/`4`/`5`
  (0x8c654c00 / 0x8c654a00 / 0x11). Only `USER_DATA_6` and the 0xc22a62xx / 0xc0c9c4xx words differ.
- **The same state.** The sampler shows program 0x909977100, dim [697 1 1], threads [64 1 1]. `GRBM_STATUS` is
  0xa04030ac, SE0/SE1 0x08000006, ME 0xe15 and PFP 0xea0–0xea1. The CP had fetched to `CP_IB1_BUFSZ` 0x38f8 of
  `CMD_BUFSZ` 0x4138. All of this matches 16:25 exactly.
- **The same faults.** The pages are 0x8608c654000–0x8608c65d000, all reads, with the same high half 0x860.
- **Only one thing differs.** The initiator is 0x61 here against 0x65 at 16:25, so FORCE_START is absent. **H6 (the
  test binary's FORCE_START) is refuted.** The zero skip is not involved either: D2 ran with it off.
- **The same faulting value from two runs.** Both events came from different binaries and different sessions, but from
  start-ups from the maintainer's current saves, and both wrote the same garbage high half, 0x860. That fits a value
  the title computes or stores deterministically (its table, or data the table points the waves to) better than a
  random stale register. A carried register from an earlier IB is not excluded.

**A start-up reproducer (F678).** Two of the start-ups from the current saves hit this job at ~57–60 s: the
maintainer's 16:25 start 1 and D2. The scripted S6N runs from older saves did not. A start-up run from the same copy
of the live saves with the dispatch journal decides where `USER_DATA_0` comes from. The run needs box writes that
this session's classifier refuses, so it is listed for the maintainer's morning decision:

- binary and route: exp 0379's D2 invocation unchanged (e1cc0c92, or the shared normal 58c4a627; RT on; the S6N
  runner from a fresh copy of the live saves), plus `BC5_DIRECT_DISPATCH_JOURNAL=1` (F207: program and user data per
  dispatch, tables included). Stop at t 120 s, or at the first gfx timeout.
- read after it: the journal's lines for the dispatches after `LOAD_SH_REG_INDEX` 0x909842dc0 (does the table name SH
  0x240, and with which value?), and `ud0` of the 0x909977100 dispatches.
- expected risk: a gfx ring timeout whose reset succeeds, as both times so far. Both events stayed up, but F399/F413
  show that a reset can fail.
- what it decides: if the table names 0x240 with 0x860, the title's table is the source. If it names 0x240 with 0x11
  while the waves used 0x860, the CP fetched the table wrongly. If the table does not name 0x240, the value is carried,
  and the previous IB's last `USER_DATA_0` write (a host prefix or the title) is next.

**Rate update (10-30, the top session's report, not read by this session).** Exp 0379's D4 at 01:36:40 hit the same
event at t ≈ 61 s. Its fault pages were 0x8608c654000–0x8608c65b000, with program 0x909977100, dim [697 1 1],
initiator 0x61, PFP 0xea1 / ME 0xe15 and `CP_IB1_BUFSZ` 0x38f8. The ring reset succeeded; the devcoredump is
`20261030-013640-devcd2.txt`. Starts from the maintainer's live saves hit it in 2 of 3 bench starts (D3 did not reach
the point), plus his own 16:25 start 1. Starts from the S6N route saves hit it in 0 of 5. The live-save start-up is a
reproducer for F678's dispatch-journal run.

## 9. The start-up run J1 (2026-10-30 08:14, the maintainer's yes in this session's chat): an acb leaves `USER_DATA_0` behind (F679)

**Setup.** `setup0381j.sh` built `~/bc5-work/exp0381` from exp 0379's D2 setup, reading exp 0379's files only:
- the launcher `play-pkg-0358.sh` with its paths moved to exp0381 (md5 3e470c50);
- exp 0379's binary e1cc0c92, its `input-rton.cfg` (RT on), the learned file (a7cc8581) and `in-D2.cmd`;
- a working directory with a fresh copy of the live saves, 377a8d45, unchanged after the run.

The run added `BC5_DIRECT_DISPATCH_JOURNAL=1`. `BC5_DIRECT_GE_PROBE` stayed off because it switches chaining off, so
the tables' contents are not journaled. The tracker's per-dispatch user data are journaled. The page-cache drop
failed (sudo wanted a password), so J1 started with a warm cache, unlike D2. The kernel log was streamed to the
laptop. The emulator was stopped by TERM at 128 s. Extract: `raw/j1-dispatch-journal.txt`; reader: `dj0381.py`.

**The event reproduced.** At t ≈ 60 s TCP read faults hit 0x8608c654000–0x8608c65b000 (status 0x00701031). The gfx
ring timed out and the ring reset succeeded (devcoredump `20261030-081544-devcd3.txt`, private). From the live saves
that makes 3 of 4 bench starts.

**The source of 0x860 (F679).**
- The faulting dcb (15,083 dwords) opens with 0x909977100 dispatches at dword 13. These use the `USER_DATA_0` they
  inherit.
- Immediately before it on the host (t 56.945 s), a 1,051-dword acb ran. Its last dispatch (program 0x11d03a3500)
  sets user data 0 to **0x11d00860**.
- 0x909977100 forms its descriptor base's high half from `USER_DATA_0` (F671). The fault's high half is 0x0860, the
  low 16 bits of that value.
- The host's tracker keeps the dcb's compute state apart from the acb's, so it journals `ud0` 0x11 for the dcb.
- The journal holds 5 runs of 0x909977100 dispatches. The 4 healthy ones sit mid-dcb, right after the dcb's own
  0x909974400 dispatches with `ud0` 0x11. The faulting one is the only run that starts a dcb right after an acb.

With `BC5_DIRECT_COMPUTE_RING=-1` (exp 0342, `play-pkg.sh`), acbs run on the GFX ring and share its `COMPUTE_*` SH
registers. On the console an acb runs on its own queue, so the graphics queue's compute registers would survive it.
So the bad value is carried state, written by the title's own acb. It is not the dcb's table or the CP's fetch of it.

What is not shown:
- that the dcb's table at dword 8 leaves SH 0x240 out (the table was not journaled). That fits the fault: if the
  table set 0x240, the CP would have used the table's value.
- the same order (an acb right before this dcb) in the 16:25, 01:26 and 01:36 events. Their journals have no
  dispatch lines.

**Fix candidate, design only.** In front of a dcb that follows an acb on the same ring, re-emit the dcb tracker's
compute SH state: the CS prefix, SH 0x204–0x3ff, which already exists for dcbs that dispatch before setting their
program. Alternatively, save and restore the compute SH state around each merged acb. Either needs the maintainer's
yes and a build. The test: J1's route with the fix, 3 starts from the live saves (the event hit 3 of 4).

**The compile check** (`compile0381.sh`, `~/bc5-work/exp0381cc`, clang 21.1.8 with libdrm 2.4.131). Its first build
stopped on a `-Wsign-conversion` error in `draw_args_test.cpp`, which MSVC had not flagged; the error is fixed. After
the fix: 0 warnings, 95 of 95 test cases, archive 46aed659. `direct.cpp`, with the draw-args journal, compiled
cleanly. The script also gained `< /dev/null` on its `distrobox enter` calls, which had swallowed `bash -s` input.

## 10. The fix: `BC5_DIRECT_ACB_STATE_RESTORE` (design and code; default off; not yet built or run)

**The choice: re-emit in front of the dcb, not save and restore around the acb.**
- **The ring order is not known where the state is known.** The tracker runs on the submitting thread, ahead of the
  ring. The ring thread decides later in which order jobs land. A restore queued after an acb would hold the
  tracker's newest state, which may be ahead of the ring position it lands at. The dcb's own prefix holds exactly
  the state before that dcb (`t_fs_before`).
- **Nothing can run between the restore and the dcb.** The prefix goes in the dcb's own chain segment (ADR 0010). A
  restore after an acb is a separate job, so another acb, or another process's job (F251), can still run between it
  and the dcb.
- **The GPU cannot simply save.** Saving means reading SH registers back on the CP, and this project has never tested
  that path. Tracking acb state on the CPU instead would need a tracker per guest queue.
- **It reuses a proven path.** The CS prefix (exp 0195, on in `play-pkg.sh`) is this restore with a narrower trigger.
  It only fires when a dcb dispatches before it sets `COMPUTE_PGM_LO`. The F679 dcb's table sets the program, so it
  never fired there.

**The trigger.** With the switch on, every dcb that has a `DISPATCH_DIRECT`, a `DISPATCH_INDIRECT` or an
`INDIRECT_BUFFER` at its top level gets the prefix, unless another prefix already stands there. "Only after an acb"
is deliberately not the rule: whether an acb lands between two dcbs is the ring thread's decision, made after this
point. An unconditional restore also covers other processes' jobs. The cost is one short `SET_SH_REG` set per
dispatching dcb; the journal line gives its size, and J2 can compare flip rates against J1.

**The registers.** All SH offsets 0x204–0x3ff the dcb tracker knows, as the CS prefix replays them: `COMPUTE_START_*`,
`NUM_THREAD_*`, `PGM_LO/HI`, `RSRC1/2/3`, `RESOURCE_LIMITS`, `TMPRING_SIZE`, `USER_DATA_0`–`15` and everything else
in the range. Two exclusions:
- 0x200–0x203 (`DISPATCH_INITIATOR`, `DIM_*`) belong to the dispatch packet.
- 0x214 (`COMPUTE_VMID`) is the kernel's. This is a difference from the CS prefix, which would replay it if the title
  wrote it.

**What it cannot restore.** A register an acb writes that no dcb has written has no known graphics-queue value. The
restore leaves it as the acb left it. `bc5::acb_restore::Touched` scans acbs (`SET_SH_REG(_INDEX)`, `LOAD_SH_REG`,
`LOAD_SH_REG_INDEX`, IB2s) and the journal line names those offsets when their number changes, so J2 shows whether any
exist. The acb side is not covered either: an acb that inherits its own queue's state gets the dcb's registers.
Nothing has shown that happening. The tracker's limit also stands (Codex REVIEW-06): tables are read from the CPU's
view at submit.

**The code.**
- `backend/include/bc5/acb_restore.hpp`: header-only (`wants`, `runs`, `Touched`), so the shared archive links
  unchanged.
- `backend/tests/acb_restore_test.cpp`: 4 cases, 99 assertions. One models the ring with a second tracker: dcb, acb,
  dcb. Without the restore `USER_DATA_0` reads 0x11d00860; with it, every register the dcbs set is back.
- `patch0381-bc5LleAgc.diff`: on top of exp 0379's unit (e62113a5, also J1's), so the binary differs from J1's by this
  switch alone. Made by `mkpatch0381.py`.
- `build0381.sh` / `build0381.py`: exp 0379's private build, into `~/bc5-work/exp0381/kyty_emulator`.

The laptop build (MSVC) passes 99 of 99 test cases, 33,805 assertions. The host unit needs the box to compile.

## 11. J2: the rules, written before the run

**Setup.** J1's setup (`~/bc5-work/exp0381`, launcher `play-pkg-0381.sh`, `input-rton.cfg`, `in-D2.cmd`, RT on) with
the binary from `build0381.sh` and `BC5_DIRECT_ACB_STATE_RESTORE=1`. Each of the 3 starts (`start0381j2.sh`) gets a
fresh copy of the live saves. `BC5_DIRECT_DISPATCH_JOURNAL=1` stays on: J1 is the comparison and ran with it, and the
journal is what shows a start reached the F679 order. The page cache stays warm, as in J1. The kernel log is streamed
to the laptop for each start.

**The comparison.** Starts from the live saves hit F443 in 3 of 4 bench starts (D2, D4, J1 hit; D3 did not reach the
point), plus the maintainer's own 16:25 start. Without J1, the count the top session quotes is 2 of 3 plus 16:25. *The odds that stood here are withdrawn (§14).*

**Each start ends** at 120 s of emulator time, or on the first gfx timeout, whichever comes first. It is stopped by
TERM from the laptop.

**A start is clean** when all of these hold:
- no TCP fault with a high half other than the title's, and no gfx ring timeout, in the kernel stream;
- the emulator reached 120 s;
- the journal has `acb state restore (exp 0381)` lines, so the switch was active;
- the journal shows a dcb opening with 0x909977100 right after an acb, the F679 order. Without it the start did not
  test the fix: it counts as **no test**, and does not count towards the 3.

*The checks below were applied with a faulty detector; J2 is eligibility unverified (§14).*

**Pass:** 3 clean starts, no F443 in any. At most 2 extra starts may replace no-test starts.

**Fail:** any start with the F443 signature (TCP read faults at high half 0x860, or any wrong high half, with
0x909977100 running). Stop the series, keep the journal and the devcoredump, and read the emitted IB: did the restore
stand in front of the faulting dcb, and with which `USER_DATA_0`?

**Stop the series at once**, and tell the top session, on any of:
- a gfx timeout or page fault of another class; that is a new finding, not a pass or a fail;
- a failed ring reset, or a machine-down;
- live saves that differ from 377a8d45 at a start (never restore over them; ask);
- a flip rate well below J1's, or a stall, which would point to the prefix itself.

**A pass does not show** that F443 is gone from play: it covers the start-up job only, on one save state, for 120 s.
The next step would be a test build with the switch on, and that build needs the maintainer's yes (D19).

## 12. J2's result (2026-10-30 08:40–08:53, the maintainer's yes in this session's chat): no event, but no test by the written rule

**The build.** `build0381.sh`: binary 6415be8f, the shared objects with the unit of exp 0379 + this experiment's diff
(9d4649ba) and the shared archive. Clang 21: backend 0 warnings, 99 of 99 test cases; 5 compiler warnings in the host
unit, the older ones, none in the new lines. The shared binary (58c4a627) and archive (bb50b2e0) are unchanged.

**The journal read.** In J1 one dcb opens with a dispatch right after an acb, and it is the faulting one. The other
1,114 dcb dispatches that follow an acb line in the journal sit mid-buffer, which is the journal's interleaving. J1
hit no F403, so it says nothing about the F403 dispatches.

**The runs.** Five starts (the 3 of §11 plus the 2 replacements), each with a fresh copy of the live saves, binary
6415be8f, the switch on, the dispatch journal on, RT on.

| Start | Journal | Emulator time | Kernel faults | gfx timeouts | Opener of F679's shape | Runs of 0x909977100 |
|---|---|---|---|---|---|---|
| J2-1 | `play-20261030-0840` | 123 s | 0 | 0 | 0 | 79 |
| J2-2 | `play-20261030-0843` | 121 s | 0 | 0 | 0 | 80 |
| J2-3 | `play-20261030-0846` | 122 s | 0 | 0 | 0 | 91 |
| J2-4 | `play-20261030-0849` | 123 s | 0 | 0 | 0 | 84 |
| J2-5 | `play-20261030-0851` | 121 s | 0 | 0 | 0 | 85 |

The restore was active in the two starts where its lines were counted (J2-1, J2-2): 40 registers in 58 dwords on each
of ~11,000 dispatching dcbs. Acbs wrote 40 compute registers, and none is missing from the dcb state, so **nothing
is left behind**, which answers §10's open limit for this stretch. Saves were unchanged (377a8d45). Lines mentioning
flips run at about 41–42/s against J1's ~43/s over its first 57 s: a rough count, with no sign of a slowdown.

**The verdict under §11's rules: not a pass.** No start was clean, because none shows the F679 order. All five count
as no test.

*Corrected by §13: the buffer below did not vanish. The journal's `dcb N dwords` and `at` describe host chains, so readings 1 and 2 and their odds are withdrawn.*

**What the runs do show.** In J1 the second burst of BVH work was a dcb of 88,848 dwords, then the 15,083-dword dcb
opening at dword 13, which faulted. In all five J2 starts that dcb did not appear: 0x909977100 stays inside large
dcbs, after their own 0x909974400 dispatches. The J2 starts also ran past the fault's time, 54–57 s, so they reached
the point.

Two readings stay open:
1. The restore removes the shape: an earlier, silent register carry changed what the title builds, and with the
   registers right the title never emits that dcb. Faults stopped because the trigger stopped.
2. The shape varies on the title's side, and these five starts missed it by chance or by timing. Against that, at
   J1's rate of 3 in 4 the odds of 5 misses are about 1 in 1,000, and at 2 in 3 about 1 in 240. Those rates are from
   a few starts, though, and every earlier run differs (binary, journal).

**The test that separates them:** the same binary 6415be8f with the switch off, 3 to 5 starts, same setup. If the
shape and the fault come back, the switch is the cause, and reading 1 stands. It needs the maintainer's yes, because
a start can end in a GPU timeout.

## 13. Correction: the buffer never left; J2 shows a chain boundary, not a title change (F681), and J3's rule

**The error.** §12 read the journal's `dcb N dwords` and `at` as title buffers. They are not. The dispatch journal and
the timing line sit in `submit_now`, which sees a whole chain (ADR 0010): title buffers laid end to end, with their
host prefixes. So "a dcb opening at dword 13" means "a chain that starts with this buffer", and §11's clean-start
test measured where chains start.

**The evidence** (`raw/shape-j1-j2.txt`, `shape0381.py`, from the journal offsets).
- In all five J2 starts the step from the burst's first 0x909977100 run to its second is 32,586 dwords. Across J1's
  chain break it is 32,528 (32,515 to the chain's end, then 13). The difference is **58 dwords, the restore's exact
  size**, five times of five.
- Over the first burst, with no title buffer boundary between the runs, J1 and J2 agree exactly (29,190).
- The chain sizes (47,670, 77,940, 103,865, 67,871) differ from start to start, while that step does not. J2-4's
  103,865 is within 66 dwords of J1's two chains together.

So in every J2 start the title's ~15k-dword buffer is **there, at the same stream position**, with the restore right
in front of it, as a segment in the middle of a chain. This is inferred from offsets; no J2 journal line names a
segment. **§12's reading 1 (the restore changes what the title builds) is refuted at this level**, and its odds are
withdrawn.

**What differs is the chain boundary.** In J1, and by their 13/26/43 offsets in the 16:25 and 01:26 events, a chain
started with this buffer, and in J1 an acb landed right in front of it. In J2 no chain ended there, so no acb could
land there: the restore had nothing to undo at that point. **J2 therefore did not test the fix**, which agrees with
§11's verdict for a better reason.

Why the chain held is open. Chains end on host timing: the 2 ms hold bound (`BC5_DIRECT_CHAIN_HOLD_US`), the title's
observe points, an unsatisfied wait (`chain_flush(1)`), or a class change. The restore's code path touches none of
these directly: it uses `chain_append` with a prefix, as any prefixed buffer does. Indirect effects are possible; for
example, a wait that is satisfied sooner keeps a chain open. So 5 of 5 without a break against 3 of 4 with one is
either timing or an effect of the switch through the GPU's results. J2 cannot tell.

**The fix itself is untested at its target.** F679's cause stands, on J1's journal. The model test passes. No run has
yet put an acb right in front of this buffer with the restore on.

**What decides, before J3.** One read, needing a slot and the maintainer's yes: the chain statistics line and the
timing lines around the burst, in J1 and all J2 journals, plus the journals of the earlier starts
(`play-20261030-0125`, `-0135` and the 16:25 start). It answers:
- which flush reason ended the chain in J1, and whether the older events show the same one;
- where the J2 starts put the acb of that moment, before or after the chain.

**J3's rule as first written; replaced by §14.**

*J3a, the control:* binary 6415be8f, switch off, otherwise §11's setup. 3 starts, up to 5; stop the series at the
first F443, and keep every journal. The measure is a chain that starts with 0x909977100 (below dword 64) right after an
acb.
- That order appears, with F443: the control reproduces J1. Its rate against J2's 0 of 5 says whether the switch moves
  the chain boundary.
- No such order in 5 starts: the order is rarer than 3 of 4 on this binary, whatever the switch does. J3b decides.

*J3b, the real test of the fix:* the switch **on**, with the chain boundary forced so the acb can land in front of the
buffer: a shorter hold, `BC5_DIRECT_CHAIN_HOLD_US`, set from J3a's and the read's data. Not `BC5_DIRECT_CHAIN=0`, which
changes more. 3 starts, up to 5.
- **Pass:** at least 2 starts show the F679 order (the buffer at a chain's head, right after an acb) and none shows
  F443. That also means the restore ran in front of that buffer.
- **Fail:** F443 with the restore in front of the buffer. Read the emitted IB.
- **No test:** the order does not appear. Report it; do not count clean starts.

Both arms keep §11's stop list. J3b needs its own yes: it changes a chain setting, which is off the tested path.

## 14. Codex review (REVIEW-06-J2): corrections, and J3's rule, which replaces §13's (F682)

**A detector false negative.** `j2check0381.py` and `j2job0381.py` filter on the journal's `at < 64`. That offset comes
after prefix insertion and chain assembly, so the same opener at dword 13 reads 71 behind a 58-dword restore, and both
scripts reject it. Codex's probe on the real scripts gives 13 → 1 and 71 → 0. The J2 journals carry no segment or job
identity, so raising the limit would not repair them.

**What that changes in J2.** The rule written in §11 stands; the instrument that applied it did not. **J2's five
starts are eligibility unverified**, not "no test": §11's order was neither shown nor excluded across the 120 s. F681's
offsets still place the buffer mid-chain at the one burst measured, with the restore inside the step. They say nothing
about the 79–91 later runs of 0x909977100. "No start put an acb in front of the buffer" (F680 as first written) was too
strong. J2 stands as five starts with no fault, and it shows no repair.

**Another correction.** The odds in §11 and §12 (1 in 27, 1 in 64, 1 in 240, 1 in 1,000) plug a rate from a few unlike
starts into a model of independent, identical trials. They are withdrawn; they were never a significance level.

**A third reading of J2 (Codex).** The switch is a bundle: it adds packets, copying and chain length as well as
register values. A changed chain boundary may be a host coalescing or timing effect, with no silent register carry
cured. §13's "effect through the GPU's results" is one candidate and this is another.

**What changed in the code.**
- `patch0381-bc5LleAgc.diff`, with the dispatch journal on, now writes a line per job (with the class of the job
  before it), a line per segment (`off`, `prefix`, `n`, and the `USER_DATA_0` read from the prefix's emitted dwords), and
  job, segment and original offset on every dispatch line. The previous job's class is the host's submission order,
  not read from the ring.
- `locate` and `sh_value` in `acb_restore.hpp` compute those, with tests: 101 of 101 test cases on the laptop.
- `last_missing` now compares the offsets, not their number (REVIEW-06-J2's logging finding).
- `j3check0381.py` replaces the two J2 checkers: it uses the original offset and the segment, attributes the restore to
  the target's own segment, and says "eligibility unverified" for a journal without identity. `test_j3check0381.py`: 6
  cases, including 13 and 71.

The new unit (637f964c) is not compiled on the box yet. The new binary differs from 6415be8f by those journal lines and
the `last_missing` comparison. With the dispatch journal off, the new code does nothing except the comparison.

**J3's rule, replacing §13's.** Written before any start.

*Setup.* The new binary for every arm, `BC5_DIRECT_DISPATCH_JOURNAL=1`, §11's saves (a fresh copy per start, 377a8d45),
RT on, warm cache, 120 s or the first gfx timeout (`start0381j3.sh`, `j3run0381.sh`). All starts count; every journal,
no-test start and failure is kept. The eligibility rule below does not change after any result is seen.

*Stage 1, at the default hold.* Switch off and on, alternating, starting with off: 3 starts each, up to 5 each.

*Stage 2, at one shorter `BC5_DIRECT_CHAIN_HOLD_US`.* The value is written here, from Stage 1's journals, before Stage 2
runs. Off and on again alternating, 3 each, up to 5 each, so the comparison is off against on at **one** hold value.
Stage 2 runs only if Stage 1 left the question open, and needs its own yes.

*Eligible start.* `j3check0381.py` reports a target: 0x909977100 as the first dispatch of the job's first segment, at an
original offset below 64, with an acb as the previous job.

*Attributed restore.* On an eligible ON start, that same segment's prefix holds `USER_DATA_0` = 0x11. A restore line
elsewhere in the run does not count.

*Outcomes.*
- **Evidence for the mechanism:** at one hold value, at least 2 eligible ON starts with the attributed restore and no
  F443, and at least 1 eligible OFF start with F443.
- **Fail:** an eligible ON start with the attributed restore and F443. Stop the series and read the emitted IB.
- **No test of the mechanism:** no eligible ON start at that hold. Clean ON starts then count for nothing.
- **Open:** eligible ON starts clean, but no eligible OFF start with F443. The target order was not shown to fault in
  this setup.

*What each comparison means.* Off against on, in the rate of F443 or of eligibility, tests **the switch as a bundle**
(register values, packets, copying, timing). It does not by itself establish the register mechanism; only the
attributed outcomes above speak to that. Counts are reported as counts, with no odds attached. A pass covers this
start-up workload, this save state, this build, 120 s.

*Stop rules.* §11's list holds, with one change: F443 in an OFF start is expected and does not stop the series. F443
in an ON start does. After any gfx timeout, the next start waits for the reset's success line.

*Before it.* The read of §13 stays useful for the old journals' chain statistics, but it cannot make J2 eligible.
