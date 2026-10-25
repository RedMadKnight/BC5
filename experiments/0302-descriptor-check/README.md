# 0302 — the descriptor check: is the bad resource table there at submit time?

**Question.** Exp 0300 S2 / exp 0297 step 2: the compute buffer that hung (F360: SQC data fault at 0xb20407c00000,
`comp_1.1.0` reset failed, MODE1) ended with twelve dispatches of 0x11d03a4600; eleven read sane resource tables from
user SGPRs 12–13, the twelfth — the buffer's last — had user SGPRs 12–13 = 0x11e0fbff70, a "table" straddling the
page at 0x11e0fc0000 whose slot +0x60, read as a V#, has base 0xb20407c00000: the fault address exactly (the program's
first instruction loads that slot). The probe reads memory as it is at the timeout. **Which case is it?**

- (A) **the title handed the GPU that pointer** — the dispatch's user data name a structure that is not its table
  (wrong user data, or a table slot recycled before the submit): the filter sees the garbage already at submit time;
- (B) **the table was overwritten between the submit and the GPU's read** (the title recycles the ring the tables live
  in while the GPU, late, has not read them yet — exp 0300's 23 M sync packets may have widened that window, but 0290
  hung without them): the filter sees a sane table, the probe a changed one;
- (C) **the GPU's view of the page differs from the CPU's** (the supervisor's lead: the boundary at 0x11e0fc0000 — a heap
  or view edge, a learned window, a guard or scratch zero-buffer piece, an AMM page): the filter sees a sane table
  through the CPU's memfd mapping, the probe too, and yet the GPU faulted — then the mapping that covers the table's
  last slot is the question, and the host's `direct_views` and mapping dumps the place to look.

The fix candidate (b) depends on the answer: (A) → drop a dispatch whose slot base is outside the title's mappings
(host-side, generic); (B) → a lifetime problem the host cannot mend by a barrier (exp 0300) — the fix is in why the GPU
is late, or a copy of the table at submit time; (C) → a mapping fix. **This experiment is diagnostic (a) only.**

**Setup — the patch (`patch0302.py`, 8 exact-anchor edits of the tree's `bc5LleAgc.cpp`, md5 5bccbb80, verified
offline against patch 0001 as exp 0300's; `patch_0302.diff`).** No sync packets, no refusal change (the backend
archive is a build argument, as exp 0300's).

1. **Filter time** (`descriptor (exp 0302)` lines): for a dispatch (0x15 / 0x16) of a program in
   `BC5_DIRECT_TABLE_PGM` (hex list; default the 0x11d03a family: 0x11d03a2000, 3400, 3500, 4600, 0x11d039f000,
   0x11d03a0700) whose COMPUTE_USER_DATA_12/13 are set (as the buffer or its LOAD tables set them): the table address,
   whether its 160 bytes are mapped, which mapping (index into the device's sorted list, va, size, shared memfd or
   userptr, read-only) covers its first and its last slot, and the 40 dwords of slots +0x00…+0x90 — a snapshot kept
   (the last 4096) for the probe, keyed by the table's address and the program. Journaled at once when the table is
   unmapped, **spans two mappings**, or a slot's V# base is **unmapped now** (`BAD SLOT +0x..`), up to 256 such lines;
   otherwise one line per 4096 snapshots. A `BAD SLOT` at filter time is case (A) caught red-handed.
2. **At the timeout** (`table (exp 0302)` lines): exp 0297 step 2's table dump as exp 0300 built it (slots as V#s, the
   chained store V# at slot +0x80's buffer +0x680, `BASE NOT MAPPED`, `COVERS THE LABEL` against
   `BC5_DIRECT_PROBE_LABEL`), the mapping covering the table now, and the comparison with the filter-time snapshot of
   the same table address: each `CHANGED` slot with its old dwords, the snapshot's submit number and age, a summary
   (`n slots unchanged, m CHANGED`), or `NO FILTER-TIME SNAPSHOT of this table address` when the probe's user SGPRs
   12–13 were never seen by the filter for that program (the user data differ between the two readings, or the
   dispatch came through a path the filter did not walk).
3. Exp 0277's probe fix (the executed offsets forward into the rebuilt IB), as exp 0300 carried it.

**How to read it.** `BAD SLOT` or `NOT MAPPED` at filter time for the faulting dispatch → (A). Filter-time sane,
probe `CHANGED` on the slot that holds the fault address → (B), with the age telling how late the GPU was. Filter-time
sane, probe unchanged and sane, and still the fault → (C): compare the mapping named for the table's last slot with
the host's views. `SPANS TWO MAPPINGS` at filter time is (C)'s fingerprint even before a hang.

**Setup — build and runs.** `build0302.sh [<archive>]` as exp 0300's (one unit + relink; with exp 0290's archive the
refusal is in, as the 0300 chain ran). `s6n0302.sh` = exp 0300's chain without the sync packets: RT on through the
private input configuration and the derived launcher, the private working directory with its own `_SaveData`, the
live saves compared only, the probe on, default **2 × 600 s** — without the sync packets the hang came at ~2 min in
every 0290 run and each hang of this class has been a machine-down (`comp_1.1.0` reset failed), so each run is one
power-cycle away; the supervisor sets the count and the time, the maintainer reachable. The 180-s check looks for a
`descriptor (exp 0302)` line (a listed dispatch seen with RT on).

**Result (2026-10-25).** Build 12:25:44–12:26:12 on the box under my lock: `~/bc5-work/exp0302/kyty_emulator` md5
**39440597** = the tree's 5bccbb80 patched to 17e40d81 (8/8 anchors, as offline) + the shared objects + exp 0290's archive
825ae1d1 (the refusal); strings: "descriptor (exp 0302)" ×1, "table (exp 0302)" ×6, "MEC check unverified" ×1; the
same 4 tree warnings. The chain (the maintainer's approval "zgadzam się na komplet Twoich testów", the supervisor's GO
12:25 after the water session's release; `stream0302.sh` on the laptop, `raw/`):

| run | start | end | verdict |
|---|---|---|---|
| S1 | 12:27:06 | 12:37:18 | **pass**: 600 s, no kernel line, no TIMEOUT, no probe; 741,377 table snapshots; route save read at 61 s |
| S2 | 12:37:18 | 12:47:29 | **pass**: 600 s, the same; the chain ended by itself, lock released, live saves 8289704a9338a118 at start and end |

No hang, so **no A/B/C answer: the diagnostic is armed and got no event.** What the filter-time side showed in
2 × 600 s (the laptop's `raw/journal-stream.txt`, the box's `exp0302/raw/S*-sync.txt`): every table of the family
mapped, none spanning two mappings; two shared memfd mappings hold them all — 0x11e0000000+0xe14000 (the dcb's
0x11d03a2000 / 3400 tables) and 0x11e0e18000+0x20c000 (the acb's 4600 / 3500 / 9f000 / 0700 tables; it contains the
0x11e0fc0000 boundary, so exp 0300 S2's table did not straddle two host mappings). **Chunk-top table addresses are
normal**: the sampled 0x11d03a4600 tables include 0x11e0f7ff70, f1ff70, f9ff70, e3ff70, f3ff70, efff70, 0x11e101ff70 —
<chunk end> − 0x90 every 0x20000 — with sane slots at filter time, dozens of times, no hang; so 0x11e0fbff70 in 0300
S2 was an ordinary address of the title's allocator and the anomaly is the content read there at the timeout: case
(A) "a wrong pointer" is out, (B) or (C) remain. Two false alarms of the generic any-slot check, to fix in a next
iteration with a per-program slot mask: `BAD SLOT +0x50` for 0x11d03a2000 (257 lines in S1; that program reads only
+0x00 / +0x10, exp 0297 step 1, and the slot holds the same non-V# data the 0300 S2 probe showed) and `BAD SLOT +0x90`
for 0x11d03a4600 at chunk-top tables (its table is 0x90 bytes, slots +0x00…+0x80; +0x90 is the next chunk). No real
bad slot at filter time in either run.

**Verdict.** Open — no event. The tool is ready: the next F360 hang with this binary (or its code in a later one)
gives the comparison. Proposed to the supervisor: run the maintainer's RT-on play sessions on this binary through a
private launcher (it only reads, adds no packet, the refusal in), since chains catch one hang in four 600-s runs today
(0300 S1, 0302 S1, S2 clean; 0300 S2 down at 2.5 min) and his play reaches states the route does not.

**The "clean first run" pattern — setup differences between exp 0290's six hangs (2026-10-25 ~02:00, each by ~2 min)
and today's first runs (0300 S1 600 s with the sync packets, 0302 S1 600 s without any), recorded, not chased (the
supervisor, 12:45):**

| | exp 0290 (and 0294) | 0300 S1 / 0302 S1 |
|---|---|---|
| PlayGo | the title went through ASTRO BOT's `libScePlayGo.sprx` | since 10:04 the host answers PlayGo itself: all 100 chunks reported installed (exp 0298, F361) — the title's streaming and load order may differ |
| the package mount | default malloc arenas | `MALLOC_ARENA_MAX=2` (exp 0288, F353) |
| the launcher | the one of 02:00 | `play-pkg.sh` fde58cda (the noplaygo pack), derived with exp 0299's edits |
| the boot | a long-running box | a fresh boot after a power-cycle (0300 S1: up since 08:41 — a reboot that morning; 0302 S1: up since ~11:40, after 0300 S2's MODE1) |
| the route saves | `ab-restore.sh` of exp 0196's save into the live `_SaveData` | the same exp 0196 save copied into a private wd's `_SaveData` — the same save, so the same route |
| the probe | on | on; 0302 adds the filter-time table snapshot (no packet) |
| the binary | 0290's (refusal) | 0300: refusal + sync packets; 0302: refusal + snapshot code — both on the tree 5bccbb80 (the 0298 integration), 0290 on an earlier tree |

Any of these can move the hang's timing; the second run of each day's chain (0300 S2) hung at ~2.5 min as before.
