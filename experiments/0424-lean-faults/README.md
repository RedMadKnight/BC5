# 0424 — the two GPU faults of the maintainer's lean plays on 2026-11-15

## Question

Two of the maintainer's three plays on the "BC5 emulator (lean, host)" shortcut ended in a GPU fault with exit 86:
- fault 1 at 20:06:25, 227 s into the play;
- fault 2 at 20:08:08, 81 s into the play, before gameplay.

The build was lean `f942676c` (patch `4945ef1b`), with RT on. The maintainer's words, through the top session:
collect the data on crashes in lean sessions, then yes to delegating the analysis.

Questions:
1. Which dispatch read these addresses, and where did the address come from?
2. Is the pointer junk, or a real address the PS5 would have mapped? Does the PS5 do this?
3. Is any of it tied to the host versus the container (Mesa 26.2.6 vs 26.0.8)?

## Setup

Analysis only; nothing was built or run.

Box access: read-only, to `~/bc5-data/captures/lean-crashes-20261115`, on the top session's GO. The folder was copied
to a private laptop scratch outside git (5.4 MB). It holds:
- the two fault records;
- devcd1–3 (they hold the title's command buffers and are **not committed**);
- the kernel and event lines 19:40–20:31;
- the three stall-sampler events;
- `lean-session.log`.

The scripts here (Python, no dependencies) only read that copy:
- `pm4walk.py`: walks the type-3 packets of a devcoredump's `IB #0` and prints every dispatch with the program and
  user data that the IB itself sets.
- `match.py`: puts each kernel fault page against the dispatches' `USER_DATA_4` and the indirect-argument address
  (`SET_BASE` 1 plus the dispatch's offset).
- `ud5.py`: lists the writes of `COMPUTE_USER_DATA_5`.
- `bucket.py`: sorts each dispatch's pointer by the record's views and GPU mappings.

Register offsets and opcodes come from patch 0001's own citations (Mesa `sid.h` / `gfx10.json` via
`tools/bc5-agc/regdb`):
- SH `COMPUTE_PGM_LO` 0x20c;
- `COMPUTE_USER_DATA_0..15` 0x240–0x24f;
- `SET_BASE` 0x11, `DISPATCH_INDIRECT` 0x16, `SET_SH_REG` 0x76.

Small derived outputs are in `raw/`: fault pages, matches, the user-data-5 writes and the buckets. No IB words beyond
those are included.

## Result

### 1. The reader: the title's BVH tree refit 0x909939900, and its pointer is `{USER_DATA_5:USER_DATA_4}`

**Fault 1** (`raw/match-fault1.txt`):
- The kernel printed 10 fault pages, all `SQC (data)` reads except two `TCP` reads.
- **All 10** equal the page of `USER_DATA_4` of a 0x909939900 dispatch in the timed-out IB, read with a high dword of
  0x11. For example, the first page 0x1113edf000 is `USER_DATA_4` = 0x13edfc00.
- 95 earlier fault callbacks were suppressed by the kernel's rate limit.

**Fault 2** (`raw/match-fault2.txt`):
- 6 of 10 pages match the same way.
- The other 4 lie in the same 0x11139xxxxx–0x1113cxxxxx band, plausibly reads one level down from a bad header
  (inference).

**Exp 0050 already read this program's layout:** `s[4:5]` points at a tree header. That is `USER_DATA_4/5`.

**What `USER_DATA_4` really holds.** In every one of the IB's refit dispatches (727 of 727 in fault 1, 754 of 754 in
fault 2), `USER_DATA_4` equals the low dword of the dispatch's own indirect-argument address minus 0x80. The argument
address is `SET_BASE` 1 plus the packet's offset. That address's high dword is **0x12** in every dispatch: the
title's `CommitIABufferAllocator` heap, 0x1210000000–0x12bb000000 (exp 0330's breakdown), which is mapped. The record
the refit wants is the 0x80 bytes just in front of its own dispatch arguments, at 0x12_xxxxxxxx. The GPU read
0x11_xxxxxxxx instead.

**Where the 0x11 comes from** (`raw/ud5-fault*.txt`):
- The IB never writes `COMPUTE_USER_DATA_5` before the first refit dispatch (dword 687 in fault 1, dword 3227 in
  fault 2).
- The refit's `SET_SH_REG` sets `USER_DATA_0..4` only. The title relies on `USER_DATA_5` keeping the value that its
  queue's earlier work left.
- The IB's own later dispatches write `USER_DATA_5` 13 times. The values are 0x00010011, 0x00040011, 0x00080011,
  0x00100011, 0x00000011, 0 and others. These are buffer-descriptor-like words with base-high 0x11 (the title's
  0x11_… heaps).
- A value of that kind, carried on the GFX ring from other compute work, gives exactly the faulting high half 0x11.
  The 48-bit address keeps bits 47:32, so 0x00080011 and 0x11 give the same 0x11 (TODO(verify): how the shader forms
  the high dword; not disassembled here).
- Which value the ring held at that moment is not in the dump.

**Supporting signs that the IB is an acb that expects its own queue's state:**
- It opens with dispatches before any program write: 59 in fault 1, 344 in fault 2, counted as program 0 in the walk.
- There is no host register prefix at its head; it starts with `NOP`, then `ACQUIRE_MEM`, then the title's packets.
- The graphics-side restore (exp 0381's `BC5_DIRECT_ACB_STATE_RESTORE`, on in code) is applied only to dcbs.

That the buffer is an acb is read from its shape, not from a journal (lean has none).

**The stall samplers' programs:** 0x909939900 (fault 1, first event), then 0x11d04d3400 (fault 1, second event), and
0x11d0421300 (fault 2). These are the dispatches the CP was on while the faulting waves stalled the ring. The faulting
reads are named by address (above), not by the sampler.

### 2. Not junk, and not FileSystem: a real pointer with the wrong high half; the PS5 does not do this

The refit's pointers (`raw/bucket-fault*.txt`), each read as 0x11_`USER_DATA_4`, fall in four places:

| Where the pointer lands | Fault 1 | Fault 2 | Effect |
|---|---|---|---|
| in no view, unmapped | 483 | 383 | a fault |
| in "FileSystem" (mapped, eager since exp 0421) | 160 | 239 | a silent read of the wrong memory |
| in "RenderGpuWcLarge" | 80 | 66 | a silent read of the wrong memory |
| in the unnamed 0x1113400000+0x200000 GPU mapping | 4 | 66 | a silent read of the wrong memory |

None of these is the refit's record. On the console the same dispatch reads 0x12_xxxxxxxx: its queue keeps its own
compute registers from buffer to buffer (exp 0403's addendum, A5: "the queue's own end state"), and the title never
loses its `USER_DATA_5`. So **the PS5 does not read there, and no larger FileSystem heap is involved.** The address
only looks "just past FileSystem" because a 0x11 high half joined to the low dwords of CommitIABufferAllocator lands
in FileSystem's 256 MiB slot, 0x1110000000–0x1120000000.

Two consequences, both inferences from the counts above:
- **Exp 0421 (FileSystem eager) did not remove this class; it hides part of it.** Pointers that land in the 52 MiB now
  read FileSystem data as tree records instead of faulting. A fault comes only when the allocator's low dwords pass
  0x13400000. That fits the faults' variable timing.
- **F840 (n13P4) fits the same mechanism:** TCP reads at 0x11125f2000 and 0x1112a78000 inside the then-lazy
  FileSystem, with no dispatch given a FileSystem address at the first or the second level. This is not verified:
  F840's buffers are gone.

### 3. Host versus container: no mechanism through Mesa; possibly through timing

The faulting value is in the PM4 that the direct path builds from the title's buffers and submits through libdrm.
Mesa/RADV is not in that path; on this build it serves the window's Vulkan presentation and MangoHud. So Mesa 26.2.6
against 26.0.8 cannot change `USER_DATA_5`.

The host can still matter in two ways, neither shown:
- **Timing:** the order in which acbs and dcbs meet on the shared GFX ring decides which value is carried.
- **Where the play goes:** the allocator's low dwords decide fault versus silent misread.

Counts: 2 faults in 3 host plays, 0 records in today's container plays, and 2 clean host walks (exp 0423). That is too
few to separate host from container (R13). The container plays may have misread in silence; nothing records that.

## Verdict

**Both faults are one bug: the second title's BVH refit 0x909939900, in an acb run on the GFX ring, inherits
`COMPUTE_USER_DATA_5` from another queue's compute work, so its 64-bit pointer gets high half 0x11 instead of 0x12.**
The pointer's real target is the record 0x80 bytes before the dispatch's own indirect arguments in
`CommitIABufferAllocator`. This is F679's family (state carried across queues on the shared ring) on the acb side,
which exp 0381's restore does not cover. It is not a heap the host sized too small. The PS5 keeps per-queue compute
state, so it reads the right record.

What this rests on:
- High for the reader and the address arithmetic: 10 of 10 and 6 of 10 pages, and 1,481 of 1,481 argument offsets.
- An inference for the carried value: it is not in the dump.

### Proposed fix at the source (not built)

**What it does.** Every acb head (offset 0 of a title acb, in its own chain segment, as exp 0381's restore does for
dcbs) gets its own guest queue's tracked compute registers in front: SH 0x204–0x3ff without `COMPUTE_VMID`, as
`cs_prefix` builds them. These come from `g_acb_cs[t_queue_idx]`, the per-queue `full_state::Tracker` that exp
0401/0403 already maintain.

**How it differs from exp 0403's `queue` mode.** The prefix is not limited to heads that inherit the *program*
(`cs_inherit_at`). This refit sets its own program and still inherits `USER_DATA_5`. The console carries every
register, so the prefix carries every tracked register. Rests and segments stay as they are, since their head is
replayed.

**Cost and limits.** A queue with nothing tracked yet gets nothing, which is today's behaviour; that case is counted.
Exp 0403's `queue` and `skip` modes were never run, and build W removed the option (exp 0419 row B4: "journal 0 lines
in every arm"). This proposal is therefore new code to test, not a revival of a tested fix.

**Behind a switch first** (fixes-first rule), with one catcher in the same private build: for every 0x909939900
dispatch, compare the pointer the GPU will use against the argument address. In detail, compare the high 16 bits of
the ring's `USER_DATA_5` as tracked at submit against the high dword of `SET_BASE` 1 plus the offset, and count the
mismatches. This turns a rare fault into a per-dispatch count:
- without the fix, mismatches are expected in every RT-on play;
- with it, none.

Not a fix:
- recovery, a learned window, or mapping the hole (memory rules);
- keeping FileSystem eager as a cure. Exp 0421 can be reconsidered once the fix is in.

### Open

- Which value the ring held at the refit, and which buffer left it: a normal-build journal with the catcher.
- How the shader forms the high dword: TODO(verify) in its disassembly (private).
- Why exp 0401/0403's journal saw no inheriting heads when these IBs begin with 59 and 344 such dispatches. It could
  be a different route or position; it is not looked at.
- The fault record classed fault 1 as "K4 junk" (0xeb0edf4ac000, the kernel's *last* fault address, also in
  devcd1/2). The kernel's lines show 0x1113… first. The record should classify the first fault line, not only the
  last register value (small, separate).

## Test build (the top session's GO, 2026-11-15 21:06) and its re-check

### Build and runs

- `mk0424.py` turns patch `4945ef1b`'s unit (`3e847e03`) into `11e0de65`:
  - the fix `aq424`, behind `BC5_DIRECT_ACB_QUEUE_STATE` (off by default; lean reads it too): every acb part that
    dispatches gets its guest queue's tracked SH 0x204–0x3ff, without `COMPUTE_VMID`, in front;
  - the catcher `aq424c`, in `submit_now`, normal build only.
- `b0424.sh` built both on the box in private directories (`~/bc5-work/exp0424`), from a copy of the shared tree
  without `.git`:
  - private normal `dbe0d21a`, private lean `e1aeb11b`;
  - no new warnings in the edited lines;
  - the ffmpeg prebuilt is the shared build's own `ffmpeg-94dde08.zip`, placed under the name that a tree without
    `.git` looks for; nothing was downloaded;
  - the shared builds were not touched.
- `t0424.sh` ran the second title, RT on, from exp 0412's named save snapshot, 21:25–21:58 (`raw/t0424.out`). The
  laptop's kernel stream `raw/kern-0424-test.txt` holds no lines.

| Run | Fix | Flips/s | s with a gap > 100 ms | Longest gap | Faults | Refit dispatches | "match" | "MISMATCH" | "no SET_BASE" |
|---|---|---|---|---|---|---|---|---|---|
| a424f1 | off | 25.6 | 60 | 1289 ms | 0 | 3,314,774 | 347,575 | 2,204,922 | 762,277 |
| a424n1 | ON | 22.3 | 78 | 1492 ms | 0 | 2,344,314 | 278,741 | 1,604,492 | 461,081 |
| a424f2 | off | 25.0 | 61 | 3217 ms | 0 | 2,963,611 | 330,369 | 1,867,524 | 765,718 |
| a424n2 | ON | 22.1 | 81 | 3980 ms | 0 | 2,169,672 | 274,329 | 1,530,646 | 364,697 |

- With ON, 108,006 and 107,643 parts got their queue's state; none found its queue untracked.
- The lean walk `a424l` passed: fix ON, 420 s by time, 51 of 51 key lines, the switch read back from its
  environment. It had no kernel or crash line and ended at RssAnon 176,256 kB.
- No run had a real pad key.

### 1. The catcher compared against the wrong address

The title's acbs use the compute-queue form of `DISPATCH_INDIRECT`: 4 dwords, the argument address in the packet
(dwords 1–2), and no `SET_BASE`. The host rebuilds that form for the GFX ring in `submit_now`, *after* the point
where the catcher runs. In unit `3e847e03` this is the "mec rebuild" (`is_mec`: op 0x16 with length 4). It puts three
things in the packet's place:
- a `SET_BASE` 1 of the address's 4 KiB page;
- a `PFP_SYNC_ME`;
- the GFX form, with the offset in that page.

The devcoredumps show only the rebuilt form (`setbase.py`, `raw/setbase-faults.txt`): every `DISPATCH_INDIRECT`
has length 3, and each has its own `SET_BASE` 1 16 packets before it (755 of 755 and 782 of 782), with the host's
gpu check (exp 0052) in between. So the analysis above (`match.py`, "1,481 of 1,481") read the right address.

The catcher did not. It read the title's 4-dword packet as the GFX form, `SET_BASE` 1 + dword 1. But dword 1 is the
address's low half, and `SET_BASE` 1 was whatever the ring's last GFX-form buffer (a dcb) had set.

What follows from this:
- **"MISMATCH" and "match" compare `USER_DATA_5` with a dcb's stale base, not with the refit's argument.** The counts
  say nothing about the fault mechanism, whether the fix is on or off. That is why they barely move: off 66.5 % and
  63.0 % of the dispatches, ON 68.4 % and 70.5 %.
- **"no SET_BASE"** counts refits seen while the catcher's shadow of the ring had no GFX-form base yet. Why that is
  16.8–25.8 % was not looked at; it stops mattering once the reference is fixed.
- **The first mismatch runs opposite to the faults because of this error.** `USER_DATA_5` 0x01000012 has the right
  0x12 for an argument in `CommitIABufferAllocator`; the "high 0x11" was a dcb's base.
- **The counts do not conflict with "2 faults in 3 plays".** The catcher never counted real mismatches. The 0 faults
  in 4 walks and 1 lean walk give no signal for or against the fix (R13).

The correct reference is the address the rebuild itself uses:
- for a 4-dword 0x16, `dword 2 & 0xffff`;
- for a 3-dword 0x16, (`SET_BASE` 1 + dword 1) >> 32.

### 2. Did the queue state move `USER_DATA_5`? Not shown either way

Because the catcher's reference is wrong, this test cannot say whether ON changed the refit's `USER_DATA_5`. The code
and the dumps do say the following.

**Nothing overwrites the prefix before the refit.**
- The prefix sits in the same chain segment, directly in front of the part (`chain_append(pre, part)`, or one job when
  the chain is off). A dcb cannot come between them.
- In both fault IBs, nothing writes `COMPUTE_USER_DATA_5` before the first refit dispatch (`raw/ud5-fault*.txt`).
- The refit's own `SET_SH_REG` covers `USER_DATA_0..4`.
- The dcb restore (exp 0381) goes only in front of dcbs.

**What the prefix hands over is the queue's own last `USER_DATA_5`, and that may itself be 0x…0011.**
- In the fault IBs the later dispatches write descriptor-like values, 0x00010011 to 0x00080011; the last write in
  fault 1 is 0x00080011.
- If those dispatches belong to the refit's own queue and end its previous buffer, the queue's state, and the PS5
  too, would give the refit 0x11. Then either the pointer is not `{USER_DATA_5:USER_DATA_4}` as assumed, or the 0x11
  comes from elsewhere.
- The dumps do not say which queue each part of the chain came from, so this stays open.
- This is the weakest point of the verdict above. It rested on the queue keeping 0x12, which was an inference ("the
  title never loses its `USER_DATA_5`").

**ON gave fewer refit dispatches per flip:** 299 and 276, against 367 and 338 off. That is two runs each, a route by
journal, and work that varies with the scene, so it is a hint, not a result (R13).

**One run settles points 1 and 2 without turning the fix on.** The corrected catcher keeps a cheap per-queue shadow
of `USER_DATA_5` for every acb part, whatever the switch: `SET_SH_REG` 0x245 sets it, and 0x5f/0x63/0x3f make it
unknown. For each 0x909939900 dispatch it takes the argument high from the packet itself and records:
- the ring's value at the dispatch, against that argument high;
- the queue's value, against the same;
- a histogram of the low 16 bits.

That shows whether the ring's value is wrong, and whether the queue's value would be right.

### 3. The cost: every dispatching acb part, plus the full tracker on every acb part

- **The prefix** goes on every acb part with a `DISPATCH_*` or an `INDIRECT_BUFFER` (`acb_restore_wants`). That was
  about 307 parts/s, about 14 per flip. Each prefix carries every register the queue's tracker holds in 0x204–0x3ff,
  at most 508 registers, as one `SET_SH_REG` per run.
- **CPU work that only ON adds:**
  - `acb_cs_track` returns at once when off; when ON it runs `full_state::Tracker::apply` over every acb part, under
    `g_acb_cs_mutex`, with a reader that follows `LOAD_SH_REG` tables in guest memory;
  - `cs_inherit_at` still walks each part, though its result is now only journalled;
  - `acb_restore_runs` makes 508 lookups per part.
- The fault IBs are chains of about 80,000 dwords, so these walks are long. Which of them costs the 3 flips/s was not
  measured. That the CPU work outweighs the GPU's extra register writes is an inference.
- **The prefix can be narrowed to the refit, and should be.**
  - Only a part with a 0x909939900 dispatch before any write of 0x245 in that part would get it.
  - It would be a 3-dword `SET_SH_REG` 0x245, taken from the queue's shadow of that one register.
  - The full tracker and `cs_inherit_at` then drop out.
  - This is worth building only if the corrected catcher shows that the ring's value is wrong and the queue's value
    is right (point 2). If the queue's value is 0x…0011 too, no prefix will help. The next step would then be the
    shader's disassembly (TODO(verify) in Open).

### Verdict of the test

The test build ran clean: 4 walks and 1 lean walk, with no fault and no kernel line. But it did not test the theory,
because the catcher compared against a stale dcb base instead of the refit's argument address.

The fix as built costs about 3 flips/s (25.6 and 25.0 off, 22.3 and 22.1 ON) and gives longer gaps, with no shown
benefit. It should not go into a shared build in this form.

The K4/K3 misclassification of the fault record stays a separate item (Open, last point) and was not touched here.

## The corrected catcher (aq424q): one walk, fix off (the top session's GO after the re-check)

### Setup

- `mk0424b.py` changes the private unit from `11e0de65` to `aadd0b36` and replaces aq424c with aq424q. The new
  catcher:
  - takes the argument high from the packet itself: dword 2 & 0xffff for the 4-dword compute form, or
    (`SET_BASE` 1 + dword 1) >> 32 for the 3-dword form;
  - has a **ring view** in `submit_now`, which also names who wrote each `USER_DATA_5`: the chain segment's guest
    queue, a host prefix, or a buffer that is no acb part;
  - has a **queue view**, a shadow per guest queue that only that queue's own acb parts update. It runs for every acb
    part, whether the switch is on or off.
  - Packets 0x5f/0x63/0x3f, which the catcher does not follow, count as unknown.
- `t0424b.sh` takes one BOX-LOCK line, 23:02–23:09. It rebuilds the private normal in place (`48b366ca`; 7
  warnings, the 6 in `bc5LleAgc` on the old lines), then walks a424q1 to G+240 with `BC5_DIRECT_ACB_QUEUE_STATE=0`.
  RT was on, with exp 0412's named save snapshot and `ulimit -c 0` (`raw/t0424b.out`, `raw/a424q1-catcher.txt`).

### Result

| Run | Flips/s | s with a gap > 100 ms | Longest gap | Faults | Refit dispatches | Ring: match / MISMATCH / unknown | Queue: match / MISMATCH / unknown |
|---|---|---|---|---|---|---|---|
| a424q1 | 26.2 | 49 | 569 ms | 0 | 3,368,849 | 3,368,849 / 0 / 0 | 3,368,849 / 0 / 0 |

All 31 lines show MISMATCH 0 and unknown 0 in both views. The laptop's kernel stream (`raw/kern-0424b-test.txt`)
holds no lines, there was no real pad key, and there was no fault record.

- **In this walk, every one of 3.37 million refits had `USER_DATA_5` low 16 equal to its argument's high half.**
  That held on the ring, where the GPU reads it, and in the refit's own queue.
- **So the queue's value is right, but so is the ring's.** In a normal container walk the carried value is never
  wrong. The narrowed fix (the queue's `USER_DATA_5` in front of a refit part) would hand over the value the ring
  already has, and an OFF/ON test could show only its cost. The catcher does not count who wrote the matching values.
- **The 0x11 high in the two fault records is therefore a rare state, not the steady one.** Its cause is open; one
  walk cannot rule anything out (R13). Fault 2 came 81 s into the play, before gameplay, on the host's lean build.
  This walk ran in the container on the normal build and passed the same load.
- **Limits (kept from the Verdict above).**
  - The ring's `USER_DATA_5` at the moment of a fault is not measured: no faulting run has had the catcher yet.
  - How the shader forms the high half stays TODO(verify).
  - That the addresses agree (the 0x11_`USER_DATA_4` pages, the 0x12 argument high) supports the hypothesis; it does
    not close the cause.

## Final verdict (the track is parked; the top session's decision, 2026-11-15)

1. **The mechanism is supported, not proven.** In both fault records the faulting pages are the BVH refit
   0x909939900's `USER_DATA_4` read with a high half of 0x11: 10 of 10 pages in fault 1 and 6 of 10 in fault 2.
   Each refit's own argument address has high half 0x12, and its `USER_DATA_4` is that address minus 0x80
   (1,481 of 1,481 dispatches).
2. **In a normal container walk the carried `USER_DATA_5` is never wrong.** With the corrected catcher, 0 of
   3,368,849 refits mismatched, on the ring and in the refit's own queue (a424q1, fix off).
3. **The 0x11 state is rare, and its cause is open.** Both faults came in the maintainer's lean plays on the host. One
   walk rules nothing out (R13).
4. **The fix candidates are not for the shared builds:**
   - aq424, the queue's whole compute state in front of every dispatching acb part, costs about 3 flips/s with no
     shown benefit;
   - the narrowed form (the queue's `USER_DATA_5` before a refit part) would hand over the value the ring already
     has in a normal walk.

   Neither was built into a shared build. The OFF/ON test of the narrowed form was skipped, since it could not show
   a benefit.

Limits:
- The ring's `USER_DATA_5` at the moment of a fault is not measured: no faulting run had the catcher. The lean build
  carries no diagnostics, by the maintainer's rule, so it gets no catcher.
- How the shader forms the high half stays TODO(verify).

Separate small item, not touched here: **the fault record misclassifies fault 1 as "K4 junk"** (0xeb0edf4ac000).
The record takes the kernel's *last* fault address, which is also in devcd1/2, while the kernel's first fault lines
show 0x1113…. The record should classify the first fault line, not only the last register value.

**Next cheap step, queued after exp 0425's box runs (not taken now):** 2–3 walks of the private normal build
(`48b366ca`, catcher aq424q, fix off) on the host, with `P_HOST=1` as in exp 0423, since both faults came in host
plays. If those show 0 mismatches too, the track stays parked until a fault comes again.
