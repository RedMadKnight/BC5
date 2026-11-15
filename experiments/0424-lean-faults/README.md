# 0424 — the two GPU faults of the maintainer's lean plays on 2026-11-15

## Question

Two of the maintainer's three plays on the "BC5 emulator (lean, host)" shortcut ended in a GPU fault with exit 86:
- fault 1 at 20:06:25, 227 s into the play;
- fault 2 at 20:08:08, 81 s into the play, before gameplay.

The build was lean `f942676c` (patch `4945ef1b`), with RT on. The maintainer's words, through the top session:
"zbierz dane po crashach w sesjach lean", then "Tak, zleć analizę".

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
