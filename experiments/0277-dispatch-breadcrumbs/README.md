# 0277 — breadcrumbs: which dispatch a stopped ring is stuck behind

**Question.** Every hang caught so far (F322 as corrected, F332, F336) is one ring's stream stopping inside its own
dispatches while the other ring waits on it. Neither the timeout probe (exp 0260, 0272) nor the devcoredump names the
dispatch:
- the probe sees the whole buffer, as the host built it;
- the coredump holds a queue's IB read pointer only for the ring whose timeout wrote it (F336), and that pointer marks
  how far the CP fetched, not the dispatch that does not end.

The title runs its dispatches in long stretches with no packet between them that holds the ME back. Those packets are
EVENT_WRITE CS_PARTIAL_FLUSH or PS_PARTIAL_FLUSH (events 7 and 16, `tools/bc5-agc/regdb/gfx10.json`), ACQUIRE_MEM and
WAIT_REG_MEM(64). Counted offline in the local copies of the last two hangs' buffers:
- dcb #68401 (18:52, F336): 1,915 dispatches in 7 stretches, the longest 588;
- acb #23415 (19:04, F337): 1,336 dispatches in 3 stretches, the longest 668.

Can the host have the GPU mark each dispatch twice, when the CP reaches it and when the work up to it is done, so that
the next hang names the dispatch?

**Correction to exp 0275 (F336).** This is the dated note at the start of F336 (2026-10-24, commit 1bc9dbd). Exp 0275's
README stays as committed.
- **Reading (B) is effectively ruled out.** Exp 0052's GPU check was on in that run (journal: "gpu check: 17951
  dispatches checked by the CP"). Before each checked indirect dispatch the CP skips it when a count exceeds its limit
  (backend `indirect_check.cpp`; F106). A float-sized grid would have been skipped, not run.
- **The 147 dispatches of 0x909974400 were all dropped** by the launcher's skip list, so seven of the eight BVH programs
  reached the GPU.
- **"Unguarded" describes the dump**, which is the host's copy before the backend's filter; the backend inserts the CP
  check after it. The probe's "ran" means "passed the filter", not CP progress.
- So the hang is more likely in a dispatch with sane counts (F106/F107, F250), and naming it needs marks written by the
  GPU. That is this experiment.

**Known before this experiment.**
- **The rebuild.** `submit_now`'s rebuild (exp 0038, ADR 0010 section A) copies an IB with insertions. It grows the
  IB's own COND_EXEC counts around them, maps the drop and kept-wait offsets forward and the executed offsets back. It
  runs only with `BC5_DIRECT_MEC_INDIRECT=1`, which no launcher sets (its first converted dispatch hung the GPU, run 64),
  so it has not run in play.
- **The backend's filter.** It passes WRITE_DATA, COPY_DATA and RELEASE_MEM to memory when their addresses are mapped
  (`policy.cpp` `memory_operands`). `opt.mapped` checks the device's sorted mappings, which include the shared ones
  (`direct.cpp` `sorted_mappings`). An IB with a dispatch gets the full BO list, with every mapped imported BO in it.
- **RELEASE_MEM BOTTOM_OF_PIPE_TS** (event 40, regdb) with EVENT_INDEX 5 and DATA_SEL 1:
  - direct-selftest step 3 writes exactly this form, and on compute ring 0 it was written (exp 0129);
  - on the GFX ring the filter rewrites the title's data-less CS_DONE to this event (exp 0016);
  - the title's own buffers carry it, with DATA_SEL 2, twice around each dispatch (307 in dcb #68401).
- **The title's own per-dispatch RELEASE_MEMs cannot serve as marks.** In dcb #68401 they write the same two values to
  two fixed labels (0x1200001ce0, 0x1200001de0), and the probe journals only the first 200 label writes.
- **Host memory the GPU sees.** A memfd imported through udmabuf and mapped at its host address (ADR 0006, the host's
  scratch); the mapping sync leaves shared mappings alone.

**Setup.** `patch0277.py` makes `patch_0277.diff` (483 lines, 16 hunks) against the shared tree's `bc5LleAgc.cpp` after
exp 0272's integration (md5 a2a2c2df; out md5 3879fbe3). Prepared 2026-10-24 19:20–19:45 on the laptop. The diff
applies to a2a2c2df and reproduces the full file, and braces and brackets balance as before. The design was confirmed
by the box supervisor at ~19:45: two marks per dispatch, indirect counts at level 2, no WR_CONFIRM, off byte-identical,
and the probe fix below included.

- **The switch.** `BC5_DIRECT_BREADCRUMBS=1` or `2`, off by default.
  - It is a diagnostic variable (`BC5_DIAG_ENV`), so the lean build never turns it on.
  - Without it the GPU stream is unchanged: the rebuild runs only for `BC5_DIRECT_MEC_INDIRECT`, as before.
- **Per dispatch that goes to the GPU** (not dropped by the host's lists), in the rebuilt IB:
  - **in front**, a WRITE_DATA of the id to the slot (a DISPATCH_DIRECT's with its x, y, z): the CP reached it;
  - **behind**, a RELEASE_MEM BOTTOM_OF_PIPE_TS / 5 with DATA_SEL 1 and the id, to slot + 16: everything before it on
    that ring is done;
  - **level 2 only**: for a DISPATCH_INDIRECT, three COPY_DATA of x, y and z from its arguments to slot + 4 to 12.
    Each makes the ME wait for a read. SRC_SEL 1 is TODO(verify) against Mesa `sid.h`, grepped at build time.
- **No WR_CONFIRM**: nothing on the GPU waits for these writes.
- **The slots.** 2^20 slots of 32 bytes, in a sealed memfd of 32 MiB + 4 KiB (a page more, because the filter checks 8
  bytes at each operand). They are mapped at their host address, and mapped again after a device reopen.
- **The host table** (32 MiB) records, for each id, its submission, title offset, opcode, program (from the scan's
  COMPUTE_PGM tracking) and ring.
- **COND_EXEC.**
  - The inserted packets count in the range they fall in.
  - A breadcrumb in front of the packet that ends a range stays outside the range.
  - Where the growth would overflow a 14-bit count, that range's breadcrumbs are left out first (journaled), before
    any rebuilt compute dispatch is dropped.
- **At a fence timeout** the probe adds lines "timeout probe: breadcrumbs (exp 0277) of #N kind: …". It looks up the
  breadcrumbs it finds in the timed-out IB and reports:
  - how many were reached, done, and reached but not done;
  - **the first one reached and not done**, with the three before and the three after it;
  - the last one reached and the first one not reached after it;
  - for every ring, the oldest breadcrumb reached and not done on the current device.
- **Two probe fixes.**
  - The executed offsets are mapped forward, since the probe reads the rebuilt IB. Before, its "ran"/"DROPPED" marks
    were off wherever the rebuild ran.
  - The breadcrumbs' own packets are left out of the probe's label writes.
- **A health line every 10 s**: inserted, rate, and of the 4,096 that followed the previous line, how many were reached
  and done.
- **One cleanup.** The rebuild's per-packet search of the drop list becomes a binary search in a sorted copy, with the
  same result. The rebuild now runs for every IB with a dispatch.
- **Lines touched** (a2a2c2df):
  - a file-scope block inserted before 4254;
  - 5847 (the reopen);
  - 6079 and 6164 (the probe);
  - 7523, 7558 and 7810 (the scan);
  - 8031–8123 (the rebuild);
  - 8214 and 8227 (the probe's two call sites).

  These do not overlap exp 0273's edits (after line 296, after the skip block at ~7816–7824, and before
  `VideoOutSubmitFlip`). The two patches' edits commute: either order gives the same file (md5 2f92ac35).
- **Size.** dcb #68401 would grow from 27,416 dwords to about 54,500 at level 1 (735 × 16 + 1,180 × 13) and about
  75,800 at level 2.
- **Limits.**
  - Dispatches in nested IBs get no breadcrumbs (the four buffers at hand call none).
  - "Reached" means the ME passed the posted WRITE_DATA in front.
  - "Done" relies on BOTTOM_OF_PIPE_TS waiting for compute work on both ring types. TODO(verify): the health line
    shows whether the marks are written at all, on each ring.
  - At level 2, the counts are what the ME reads. On the GFX ring that can differ from the PFP's prefetch (exp 0038).

**Files.**
- `patch0277.py`, `patch_0277.diff`: the change.
- `run0277.sh build`: the private build, from the shared normal objects as in exp 0272. It also records the Mesa
  `sid.h` field defines and udmabuf's `size_limit_mb` in `raw/packet-fields.txt`.
- `build0277.py`: its compile and link.

**Plan.** Only the first step is the supervisor's to start; the runs need the maintainer's yes.
1. **Build**, on the supervisor's GO, under a BOX-LOCK line, with no emulator running.
2. **Cost runs**, attended, on the same route as exp 0273's test, about 3 minutes each:
   - (a) the shared normal binary;
   - (b) the private binary with `BC5_DIRECT_BREADCRUMBS=1`;
   - (c) the private binary with `=2`.

   Compare fps and the frame profile, and read the health lines. "Done" should be close to "reached", which should be
   close to all, on the GFX ring and the compute rings. If the GFX ring's done marks are not written, stop and revise.
3. **Catch runs** at the cheapest level that works, until a hang. The probe's breadcrumb lines should name the
   dispatch, and its program, that the stopped ring is stuck behind.

**Result.**
- **Built** 2026-10-24 19:46:01 to before 19:46:57, on the box supervisor's GO, under my lock line, with no emulator
  running. The box was free beforehand (no lock, no emulator, load 0.00). The tree's `bc5LleAgc.cpp` was a2a2c2df and
  the shared normal binary 9f74965d at 19:45:42.
  - The private `~/bc5-work/exp0277/kyty_emulator`: 166,604,088 bytes, md5 **13b0e9ba**, with 6 "exp 0277" strings.
  - "4 warnings generated", the 4 the file already had (exp 0272), none in the new code (`raw/build.out`):
    `stringUtils.h:321` (deprecated `wstring_convert`), and lines 73, 366 and 2333 of the unit.
  - The binary was written by this link (19:46; the directory was new).
  - `raw/build-inputs.txt`: tree a2a2c2df (18:33:14), shared binary 9f74965d. `raw/patch_0277.diff` is identical to
    the committed diff.
  - The HOLD for the maintainer's play came in while the build ran. When I went to stop it, it had already finished,
    and the script's exit trap had removed the lock line.
  - The shared normal binary was still 9f74965d at 19:47 (the box supervisor's check before the maintainer's next
    test). My leftover watcher loop on the box was gone by then.
- **The packets' fields, checked against Mesa `src/amd/common/sid.h` @ 0866ae7** (the box's clone; `raw/packet-fields.txt`):
  - `COPY_DATA_SRC_SEL(x) ((x)&0xf)`, `COPY_DATA_SRC_MEM 1 /* only valid as source */`;
  - `COPY_DATA_DST_SEL(x) (((unsigned)(x)&0xf) << 8)`, `COPY_DATA_DST_MEM 5`, `COPY_DATA_WR_CONFIRM (1 << 20)`;
  - `EOP_DATA_SEL_VALUE_32BIT 1`;
  - `PKT3_RELEASE_MEM 0x49 /* GFX9+ [any ring] … */`.

  The COPY_DATA TODO(verify) of level 2 is answered; the comment in the code stays as built.
- **udmabuf's `size_limit_mb`** is 1024, well above the 32 MiB slot buffer.
- Not run.
