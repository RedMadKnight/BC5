# 0300 — a sync packet behind every dispatch of the ray-tracing build families

**Question.** Exp 0294 S1 ran the S6N route for 600 s with ray tracing on and no hang, with exp 0277's breadcrumbs
behind every dispatch (a WRITE_DATA in front, a RELEASE_MEM BOTTOM_OF_PIPE_TS behind); S2 without them hung in the
F360 way (a float in the title's sync label, the compute job's fence lost after the 0x11d03a family's SQC data fault).
Is the per-dispatch end-of-pipe sync alone — no write, no breadcrumb table, no refusal — enough to keep the F332 /
F360 hang away, when it follows only the dispatches of the ray-tracing build families? If so, that is a fix candidate
(a generic rule: an end-of-pipe event behind each dispatch of a program in a per-title list), not a diagnostic.

**Background.**
- F332 (exp 0265), F339 (0279), F360 (0294 S2): with ray tracing on, the S6N route hangs within ~2 minutes in the
  compute work of the BVH families — the first family's chain (0x909939400, 0x909936c00, 0x909939700, 0x909939900)
  and compaction (0x909974400), the second tree family (0x909974200, 0x909973900/3b00/3d00/3f00, consumers
  0x909977100, 0x90997a500; exp 0280's arm B list), and the 0x11d03a family (0x11d03a2000, 3400, 3500, 4600,
  0x11d039f000, 0x11d03a0700) whose scalar load faults and whose `buffer_store_dwordx2` writes a float pair through a
  descriptor read from a constant buffer (exp 0297 step 1). Ray tracing off (exp 0280's list) avoids them.
- The compute-ring refusal of DISPATCH_INDIRECT (exp 0290, on main since F356) makes the machine-down recoverable
  6/6 times but not always (0294 S2: a failed GFX reset).
- The host's rebuild (exp 0038, ADR 0010 section A) copies an IB with insertions, grows the IB's own COND_EXEC
  counts around them and maps offsets both ways; exp 0277 used it for the breadcrumbs. Until now it ran only for
  `BC5_DIRECT_MEC_INDIRECT`.

**Setup — the patch (`patch0300.py`, 12 exact-anchor edits of the tree's `src/libs/bc5LleAgc.cpp`, md5 5bccbb80 =
patch 0001 on main at 64179e6 with exp 0272's probe and without exp 0277's breadcrumbs; `patch_0300.diff` is the
offline result, 10 hunks, 104 added lines, out md5 23bccaa3; the anchors were checked against patch 0001 with exp 0273's
`verify0273.pl` and the edits applied offline to the reconstructed tree — braces, parentheses and brackets balance as
before; the box's `python3` applies them again and stops on any anchor count that differs).**

1. **The list.** `KYTY_BC5_RT_SYNC_PGM=<hex list>` (parsed by the filter's `pgm_list`, as `BC5_DIRECT_SKIP_PGM`).
   The filter records the offset of every DISPATCH_DIRECT (0x15) or DISPATCH_INDIRECT (0x16, either form) of a listed
   program that reaches the point after the skip lists and the ray-tracing-off drop (those `continue` past it); a
   dispatch the indirect checks drop afterwards is skipped at insertion time (the rebuild reads the drop list). One
   journal line per 4,096 listed dispatches (`rt sync (exp 0300): … listed`).
2. **The packet, behind the dispatch in the rebuilt IB.** By default `EVENT_WRITE` CS_PARTIAL_FLUSH, two dwords
   `0xC0004600 0x00000407` (event 7, EVENT_INDEX 4 — `tools/bc5-agc/regdb/gfx10.json`; Mesa `sid.h`
   `V_028A90_CS_PARTIAL_FLUSH` with `EVENT_INDEX(4)`, as RADV's `si_cs_emit_cache_flush` writes it, TODO(verify) the
   line; the console's own compute IBs carry it between dependent dispatches, `backend/src/direct.cpp`). With
   `KYTY_BC5_RT_SYNC=eop` instead the data-less `RELEASE_MEM` BOTTOM_OF_PIPE_TS, eight dwords `0xC0064900 0x00000528
   0 0 0 0 0 0` (event 40, EVENT_INDEX 5, DATA_SEL 0, INT_SEL 0 — exp 0277's done mark without the write; the
   backend's `policy.cpp` passes a RELEASE_MEM with DATA_SEL 0 and address 0 as an event-only packet). Nothing is
   written to memory in either form; no breadcrumb table, no host memory imported. One journal line per 4,096
   insertions (`rt sync (exp 0300): <kind> <n> dwords: <packet> behind the dispatch at <q> (<total> inserted so far)`).
3. **The rebuild** runs when the IB has listed dispatches (`rt_sync_ib`) as well as for `BC5_DIRECT_MEC_INDIRECT`; the
   compute-form conversion (`is_mec`) is now tied to `mec_expand_ib` alone, so an IB rebuilt for the sync packets
   keeps its dispatches as they are, on either ring (as exp 0277 did it). The reserve grows by 8 dwords per listed
   dispatch. Without the list nothing changes: the rebuild's trigger, the stream, the probe's marks.
4. **Exp 0277's probe fix** (its edits 5–8, carried unchanged): the timeout probe walks the rebuilt IB, so the executed
   offsets — mapped back to the original by `mec_back` for the drop tallies and the chain — go forward again for the
   probe (`probe_old_to_new`, `probe_ran`), for the immediate probe and the deferred one (`ran_copy`). Without it,
   every packet of a rebuilt IB behind the first insertion read "DROPPED" in the probe's lines (0277's finding).
5. **Exp 0297 step 2, the table dump** (recorded in that experiment's README; here only because it ships in the same
   private binary): at a fence timeout, for each dispatch of a program in `BC5_DIRECT_PROBE_TABLE_PGM` (default the
   0x11d03a family) the probe reads user SGPRs 12–13 from the SH state it tracks (COMPUTE_USER_DATA_12/13, 0x24c/0x24d)
   and prints the resource table's slots +0x00…+0x90 decoded as V#s, the V# chained from slot +0x80's buffer at
   +0x680, whether a base is unmapped, and whether an extent covers `BC5_DIRECT_PROBE_LABEL`. Read-only, at most 96
   tables a process, `timeout probe: table (exp 0297): …` lines.

**Setup — the build (`build0300.sh`, on the box, CPU only, under the BOX-LOCK, no emulator).** `patch0300.py` on
`~/src/KytyPlus` (read) into `~/bc5-work/exp0300/src/`; the shared normal build's compdb (`ninja -t compdb -x`);
the one unit compiled with the shared flags (exp 0272's `build0272.py` cut to one unit, `-MD/-MT/-MF` removed) and
linked with the shared normal build's other objects (binary e62a97c6, the exp 0298 integration) and, with an argument,
exp 0290's private backend archive (825ae1d1, the compute-ring refusal, md5-checked) in place of the shared one
(549892e8, 2026-10-19, which does not carry the refusal: F356 "not integrated", and the refusal is on main's source,
not in the box's shared builds); a previous binary stays beside the new one under its md5; the result
`~/bc5-work/exp0300/kyty_emulator`, its md5 in `binary.md5`, `strings` checks for the three markers. Nothing shared is
written; the script checks the tree's md5 (5bccbb80) and the shared binary's (e62a97c6) first and stops otherwise.

**Setup — the runs (`s6n0300.sh`, `stream0300.sh`).** Exp 0290's chain with the changes its header lists, in short:
ray tracing **on** through a private copy of the maintainer's input configuration with `RayTracing.PPSA03671=on`
(his file has `off`, saved 10:11, and is only read); a **derived launcher** `exp0300/play-pkg-0300.sh` = today's
`play-pkg.sh` (md5 fde58cda) + exactly exp 0299's edits (its launcher's diff against `play-pkg.sh`, every `0299`
renamed `0300`, applied with `patch(1)`, which fails on a moved anchor; kept as `raw/play-pkg-0300.diff`): the
`BC5_0300_INPUT_CONFIG` re-export after the `bc5-run.env` export loop (that loop exports `KYTY_BC5_INPUT_CONFIG`
unconditionally, so an outer value alone does not get through), its own log, a `cd` into a **private working
directory with its own `_SaveData`** — the supervisor's rule for an RT-on chain after 0294 S2 died with the route's
saves in the live directory. The directory is laid out as exp 0299's (exp 0194's bench: own `_SaveData`, every other entry a
symlink into `~/bc5-work`); the title reads its saves cwd-relative (`_SaveData/PPSA03671`, not `KYTY_BC5_SAVEDATA_DIR`:
the supervisor's check of today's play), so the route's saves (exp 0196) are copied there before each run with their
atime set back, the emulator's cwd must be that directory, and a run stops at 60 s unless a save file's atime moved
(relatime; on a noatime mount the check can only warn). The
maintainer's live saves are snapshot at chain start and their sum must read `8289704a9338a118` at the start, after
every run and at the end, and **nothing is ever restored into the live directory**. `KYTY_BC5_RT_SYNC_PGM` = exp
0280's arm B list + the 0x11d03a family (18 programs), the probe on, up to 4 × 600 s of the S6N route (exp 0203's
`o2-continue.cmd`). Three checks that ray tracing is really on: the emulator's environment carries the private
configuration and save directory (else the run stops at once), the log does not say "ray tracing off" in the first
90 s, and the journal has an "rt sync (exp 0300) … listed" line by 180 s (the host prints "ray tracing on at the
flip" only on a change, so this is the positive proof). **The chain goes on after a recovered hang** (`HANG`
verdict: "ring reset succeeded", no failed reset, no MODE1 — the hang is this experiment's result) **and stops on
the machine-down class** (reset failed / MODE1), an emulator crash, or a change of the live saves. Per run: the
probe's lines, the `rt sync` and `table` lines, the ray-tracing lines, dmesg, the devcoredump paths (never the dumps).
`stream0300.sh` on the laptop follows the kernel log and the journals' key lines over the LAN address for the lock's
lifetime. Daytime, after water's exp 0299 (the build too: not beside its bench, ~300 MiB free during play), the
maintainer reachable (an RT-on run carries the machine-down risk; CLAUDE.md, F332).

**How to read it.** 4/4 passes (no kernel line, no TIMEOUT) against 0290/0294's hang within ~2 min each time: the
per-dispatch sync is the fix candidate, next the narrowing (which family needs it; `eop` vs flush; the cost in frame
time from the journal's flip lines). A HANG with `table` lines: exp 0297 step 2's answer (a V# with an unmapped base
or an extent over the label names the writer's input) even if the sync did not help. A HANG without `rt sync` lines
in that run: the list did not match (the programs' addresses moved) — check `S<n>-sync.txt` and the `listed` lines
before concluding anything about the packet.

**Result — the build (2026-10-25 11:12:35–11:13:02 on the box, under my lock, after the water session released it at
11:10:56).** `~/bc5-work/exp0300/kyty_emulator` md5 **663ae115**: the tree's 5bccbb80 patched to 23bccaa3 (12/12 anchors,
identical to the offline result), 104 added lines; 4 compile warnings, all the tree's own (`stringUtils.h`'s
`wstring_convert`, `bc5LleAgc.cpp` lines 73, 390, 2357, far from the edits); `strings`: "rt sync (exp 0300)" ×2,
"table (exp 0297)" ×3; the shared binary e62a97c6 and object c59ed582 untouched (`raw/build0300.out`, `raw/build-inputs.txt`
on the box). **Caveat found at the build:** the shared backend archive `~/bc5-work/backend-ubuntu/libbc5_backend.a`
(549892e8, 2026-10-19) does not carry exp 0290's compute-ring refusal (no "MEC check unverified" string in it or in the
shared binary; the box's `policy.cpp` has no `kMecIndirectCheckVerified`), so the paragraph above is wrong for the box:
the shared normal build and this binary run without the refusal. The supervisor chose the relink (11:20: the control against 0290's refusal-alone 6/6 hangs and 0294 S1's
refusal + breadcrumbs 600 s, and the lower machine-down odds): **11:16:46–11:17:11, `kyty_emulator` md5 `0bfe9c39`** = the
same unit 23bccaa3 + the shared objects + exp 0290's archive 825ae1d1 ("MEC check unverified" ×1, the other markers as
before, 4 warnings as before); the first binary kept as `kyty_emulator.663ae115`, not run (`raw/binaries.txt`,
`raw/build0300-relink.out` on the box). **The chain runs 0bfe9c39** and waits for its own GO.

**Result — the chain (2026-10-25, binary 0bfe9c39, private wd, RT on; `raw/kernel-stream.txt`, `raw/journal-stream.txt`
from the laptop; the box's `exp0300/raw/S*` files when it is back).**

| run | start | end | verdict |
|---|---|---|---|
| S1 | 11:21:02 | 11:31:14 | **pass**: 600 s, no kernel line, no TIMEOUT, no crash; 23,105,537 CS_PARTIAL_FLUSH packets inserted (the first behind a dcb dispatch of 0x909974200, then acb dispatches of 0x909936c00, 0x909939400, …); route save read at 61 s; live saves unchanged |
| S2 | 11:31:14 | ~11:34 | **HANG, machine-down class**: 11:33:49 `[gfxhub] page fault … 0xb20407c00000 … SQC (data)`, thread bc5-ring; 11:33:51 `ring comp_1.1.0 timeout, signaled seq=2558172, emitted seq=2558174`, `Ring comp_1.1.0 reset failed`, `GPU reset begin`; 11:33:55 `MODE1 reset`, `VRAM is lost`; the box dropped the SSH sessions and stopped answering pings — down (power-cycle by the maintainer); the chain stopped by its rule |

**Before the connection fell**, the laptop's journal stream carried the host's complete probe output for both timed-out
buffers (3,680 probe lines, among them 680 `table (exp 0297)` lines) and the kernel stream the fault and reset lines up
to "SMU is resumed successfully!" at 11:33:56; the box's own files (the devcoredump copy, if its fsync made it, and the
chain's `raw/S2-*`) are the first reads after the power-cycle. The host's probes ran before the box went: `submit #168141 acb 2051 dwords … TIMEOUT 2006.02 ms` and `#168147 dcb 39487
dwords … TIMEOUT 2002.39 ms`, both dumped (`ib-timeout-00168141-acb-2115.bin`, `ib-timeout-00168147-dcb-39551.bin` in
the run's capture directory on the box). The acb: 32 dispatches, 0 indirect (the refusal in), every one marked `ran`;
`timeout: fault 0xb20407c00000 status 0x00601430`, `aliases: fault 0xb20407c00000: no guest memory at 0x407c00000`.

**Verdict.** The per-dispatch CS_PARTIAL_FLUSH behind the ray-tracing build families is **not the fix**. The chain reads
like exp 0294: one clean 600-s run, then the next run a machine-down — S2 reproduced F360's SQC data fault and the
compute-ring hang at ~2.5 min, with the sync packets in (6.5 M inserted in S2 by then) and exp 0290's refusal in.
Two things the chain adds to the record: (1) **the failed reset was on the compute ring, `comp_1.1.0`, despite the
refusal** — the refusal keeps DISPATCH_INDIRECT off that ring (the acb had 0 indirect dispatches), but the hung job was
the direct-dispatch acb itself, so the refusal is no net against this class (0290's 6/6 recoveries were GFX-ring
resets); (2) the hang's cause is a dispatch's bad resource-table pointer (0297 step 2 below), which no barrier behind
the dispatches can mend — a sync changes when the fault happens, not whether. S1's 600 s against 0290's six hangs by
~2 min says at most that the packets delay the hang; one pass is no statistics. Not tried: `KYTY_BC5_RT_SYNC=eop`. What the chain did deliver is exp 0297 step 2's answer (its README):
the faulting dispatch and its descriptor. The next tool is a filter-time descriptor check for the listed programs
(read the table at ud[12:13] and the slots the program loads at the dispatch; compare at the timeout; drop a dispatch
whose slot base is outside the title's mappings), proposed to the supervisor; not started.

**Addendum — the box's files and S2's coredump (copied read-only 11:48, the supervisor's slot; the dump stays on the
box and in my scratchpad, `~/bc5-data/captures/devcoredump/20261025-113351-devcd2.txt`, 5.8 MB, 272,576 lines).**
`S2-start.txt`: the same binary 0bfe9c39, cwd `exp0300/wd`, the private input configuration and save directory in the
environment, the route save read by 61 s — S2 ran exactly as S1. The coredump: `Ring Name: comp_1.1.0`, `[gfxhub] Page
fault observed … 0x0000b20407c00000`, status 0x601430, the three ring buffers (gfx_0.0.0, comp_1.1.0, kiq) and **`IB #0
0x102f00000000 2120 dw` — the hung compute buffer as the host submitted it** (the acb of 2,115 dwords, with the
inserted `0xc0004600 0x00000407` CS_PARTIAL_FLUSH behind each dispatch visible). Its sixteen `SET_SH_REG 0x240…0x24e`
blocks (fifteen user-data registers before each dispatch) give **the resource-table pointers in the IB itself**: for the
last fifteen dispatches ud12 = 0xe0f9f5d8, f538, f498, f418, f388, f2f8, f268, f1d8, f148, f0b8, f028, ef98, ef08,
ee78, ede8 — descending by 0x90 per dispatch, one table each — and for the last one **0xe0fbff70** (ud13 = 0x11 in all).
So the title's own command buffer names 0x11e0fbff70 for that dispatch: not a LOAD table, not a host rewrite, not
memory read late. The jump from a descending run (next would have been 0x11e0f9ed58) to 0x11e0fbff70 = 0x11e0fc0000
− 0x90, the top of a chunk that ends on the page boundary, is an allocator moving to (or wrapping to the top of) a
fresh chunk whose content, as the probe read it at the timeout through the host's mapping, is not a table (8-byte
pointer pairs). Two readings remain: the title wrote the table there and the write did not reach the memory the host
and the GPU read (two views of the page 0x11e0fbf000, case C of exp 0302), or the title had not written it yet when
the GPU read (a write-after-submit the console's timing tolerates, case B). The eleven sane tables before it and the
clean dispatches' `ran` marks say the fault is the last dispatch's alone. Exp 0302 (the filter-time read of the same
slots, with the mapping that covers them) separates the two.
