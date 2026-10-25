# 0308 — what the compaction writes and where: its output against the build chain's indirect arguments

**Question.** Exp 0306: with the compaction 0x909974400 running, the S6N route hangs at ~2 min in both runs in the F332
way — the leaf builder 0x909936c00's DISPATCH_INDIRECT arguments read as floats ("1.8e19 groups"), the argument pointer
landing in BVH node data — and both rings reset; with it skipped the same day, 2 × 600 s clean (exp 0302). The compaction
is the lab's reflections fix (exp 0305, F370). Does the compaction's output overlap the argument / counter block the
build chain reads, and are the arguments already floats when the host submits the chain — or do they turn into floats
between the submit and the GPU's read?

- (a) **floats already at submit time** → the title's own order as we replay it (its count pass ran on a tree the
  compaction had rewritten, or did not run);
- (b) **sane at submit, floats at the GPU's read, the address inside a compaction extent** → the compaction's writes land
  in the argument block in flight: a dependency the host does not track — the strongest lead, the supervisor's: the
  compaction runs in the dcb on the GFX ring (the cs-prefix lines name "dcb … the queue's program 0x0909974400"), the
  chain in the acb on the compute ring (ADR 0009), and nothing orders a dispatch's output on one ring against a
  dispatch's argument fetch on the other (the hold-tail machinery of exp 0195+ orders label waits, not dispatch outputs);
- (c) **sane both times, no overlap** → the CP read stale arguments (the prefetch; exp 0038's PFP_SYNC_ME covers the GFX
  form only) or something else writes there.

**What the compaction stores** (exp 0160's llvm-mc disassembly of 0x909974400, 249 lines, on the laptop; user SGPRs
s0..s7 = COMPUTE_USER_DATA_0..7, s[4:5] the title's header pointer as exp 0050 read it; TODO(verify) the V# word
layout for the strides):

| through | base | records | what |
|---|---|---|---|
| s[24:27] | s[4:5] + header[0x8c] (stride 8: dword 1 bit 19) | header[0x84] + 4 | the compacted node records: 16 `buffer_store_dwordx4/x2/dword` at +0..+112 |
| s[12:15] | header[0x40] + s[6:7] when s2 == 0, else a base from s3:s0 + header[0x80]·16 + header[0x9c]·32 + 0x80 | — | flag words, 5 × `buffer_atomic_or` |
| s[8:11] | **s[6:7] + 0x80** | 1 | **the counter: `buffer_atomic_add v1, off, s[8:11] glc`** (the returned value is the compacted index) |
| s[8:11] | header[0x50] + s[6:7] when s2 == 0, else s3:s0 + header[0x80]·16 + header[0x9c]·32 + s20·4 + 0x90 | header[0x98] / 4 | the compacted index list, one `buffer_store_dword` |

Exp 0160 (its README, line 38) put the chain's DISPATCH_INDIRECT argument block at "BASE_A + 0x40, the same block the
clear writes": the counter at +0x80 of ud[6:7] and the count pass's argument block are candidates for the same block,
and the node table may cover it.

**Setup — the patch (`patch0308.py`, 8 exact-anchor edits of the tree's `bc5LleAgc.cpp` 5bccbb80, verified offline
against patch 0001 as the earlier ones: 8/8, braces balance; run 1 was out md5 f15ee50b, 170 added lines; run 2 — the
fixed register pairs, "header not yet written" with a re-read at the timeout, the buffer kind instead of the ring, and the
count pass 0x909939400's user data journaled — is the file as committed, `patch_0308.diff`). No
packet added, journal only; exp 0277's probe fix carried; exp 0302's descriptor check left out (its negative control is
done).**

1. **Filter time, the compaction** (`compaction (exp 0308)` lines, the first 16 and every 4096th): for each dispatch of
   0x909974400 (`BC5_DIRECT_COMPACTION_PGM` overrides): the ring the buffer goes to, the submit number, ud0–7, the header
   dwords [0x40] [0x50] [0x80] [0x84] [0x8c] [0x98] [0x9c] read at ud[4:5] (covered check), and the four extents derived
   as in the table (the flags' extent is unknown: 4 KiB taken; the ud2 ≠ 0 bases are not derived); the last 64 kept.
2. **Filter time, the chain** (`chain args (exp 0308)` lines): for each DISPATCH_INDIRECT of 0x909936c00 (leaf builder)
   and 0x909939900 (refit) (`BC5_DIRECT_CHAIN_PGM`, `_PGM2` override): the ring, the submit number, the argument address
   (the compute form's own, or SET_BASE 1 + offset as the filter tracks base1), the three dwords there now, a float
   test (exponent 0x7e..0x8f: a magnitude of 2⁻¹..2¹⁶, which a group count never has), and the lookup against the kept
   extents — `ARGS INSIDE the <node table | counter | flags | index list> of the compaction dispatch before #n (ring r),
   Δt s ago` and `ARGS LOOK LIKE FLOATS AT SUBMIT TIME` journaled at once (256 loud lines), else one per 4096; the last
   4096 readings kept by address.
3. **At the timeout** (`timeout probe: chain args (exp 0308)`, exp 0272's dispatch block): for those programs' indirect
   dispatches, the arguments now vs the filter-time reading of the same address (`UNCHANGED` / `CHANGED since filter
   time`, both with the float marks, the submit numbers and rings of both readings), and the extent lookup again, or
   `NO FILTER-TIME READING of this address`.

**Setup — build and runs.** `build0308.sh [<archive>]` as exp 0302's (one unit + relink; exp 0290's archive for the
refusal, as 0302/0306 ran). `s6n0308.sh` = exp 0306's chain (compaction on, RT on, private wd, the live saves compared
only, stop at the first machine-down) on this binary, 2 × 600 s; the F332 hang at ~2 min is expected and was
recoverable 2/2 in 0306 — the filter-time lines come before it either way; extracts per run add the `compaction (exp
0308)` lines. `stream0308.sh` on the laptop. Inputs to confirm on the box first (read-only, one GO with the flips read):
exp 0306's two acb dumps (`ib-timeout-00124870-acb-4361.bin`, `-00119484-acb-4333.bin`: the argument addresses, the
compaction's and the count pass's user data in the same buffers) and the ring placement (dcb vs acb) of the two sides.

**Result — run 1 (2026-10-25, binary 958721ed = the patch as first written, out md5 f15ee50b, linked against the shared
normal build 226bcb82's objects and exp 0290's archive; chain 13:51:26–13:56:34, compaction on, RT on, private wd;
`raw/journal-stream.txt.gz`, `raw/kernel-stream.txt`; the box's `exp0308/raw/S*`).**

| run | start | hang | verdict |
|---|---|---|---|
| S1 | 13:51:26 | 122 s | HANG, recovered (comp_1.1.0 reset succeeded, then gfx_0.0.0) — F332, the acb #130746 (3,782 dwords) |
| S2 | 13:54:00 | 117 s | HANG, recovered — the same, the acb #125855 |

**What held (both runs, the probe lines).** The chain's two indirect consumers differ: **the refit 0x909939900's
arguments are sane group counts already at filter time and unchanged at the timeout** (70 of 70: `00000034 00000001
00000001`, `00000018 1 1`, `000001a4 1 1`); **the leaf builder 0x909936c00's arguments are floats at filter time** (1,112
`ARGS LOOK LIKE FLOATS AT SUBMIT TIME` lines in S1 alone, often the same vec3 `4093a800 4014b000 c049b000` = (4.6, 2.3,
−3.15): position data) **and floats at the GPU's read at the timeout, mostly other floats** (110 CHANGED, 10 UNCHANGED, 6
non-float garbage): the memory the leaf builder's DISPATCH_INDIRECT names is live float data that something keeps
rewriting, and nothing ever writes group counts there — while with the compaction skipped (exp 0302) the same dispatches
ran 2 × 600 s. "Floats at submit" alone is expected for GPU-written arguments (the count pass 0x909939400 writes them on
the GPU); the discriminator is the reading at the GPU's time, which is also floats. So (b) "sane counts overwritten in
flight" is out for the leaf builder — there never are sane counts at its argument address — and the refit shows the
chain's own writes land where they should. The reading left: with the compaction on, the count pass writes its counts
somewhere other than where the CPU-built dispatch packets point: a layout the title derives from the compaction's
result (its counter / the compacted node count, read back by the CPU or by the next pass) that we return differently or
late. The compaction dispatches before the hang: submits #29261 (early), #118987, #120407 — the last one 8.85 s before
the hung acb (#123209 at filter time in S1); the compaction ran in the dcb (RT work in the dcb, the chain in the acb;
both on the GFX ring under the refusal, exp 0306's addendum).

**What did not hold — three bugs of this first patch, so the `ARGS INSIDE the node table of the compaction dispatch #…`
lines of both runs are FALSE and must not be used:** (1) the register pairs: the program moves s1 into s7 before using
s[6:7], so the counter is at ud6 | ud1<<32 (+0x80), and s[3]:s[0] is ud3 | ud0<<32 — I paired ud6 with ud7 and derived
low addresses; (2) the header dwords at ud[4:5] (+0x40…+0x9c) read 0 (14 of 17 compaction dispatches in S2) or
`ffc00000` (2) at filter time — the block that carries the acb's `PSR_BVHL` WRITE_DATA marker is not filled yet when the
host sees the dispatch — so the node-table extent came out 0xa0 bytes or 32 GB wide, and the wide one matched every
0x12… address; (3) `ring -1`: the ring is decided after the filter, so the field must come from the submit. The fixed
patch (run 2, below when it runs) uses the right pairs, marks "header not yet written" and re-reads the header at the
timeout, and prints the buffer kind and the post-decision ring.

**Verdict (run 1).** Open on the overlap question (the extents were wrong); settled on the mechanism's shape: the leaf
builder's argument blocks never receive counts when the compaction runs, while the refit's do — a layout/pointer
mismatch between the count pass's output and the CPU-built dispatch packets, not an in-flight overwrite. Next: the fixed
extents (where the compaction's counter and index list are, against the count pass's user data ud[6:7] — its argument
block base, exp 0306's acb dump: ud6 = the grid × 2, so not a pointer there; the block base is in another pair) and the
count pass's own output address, read from its user data at filter time.

**Run 2 (0308b) — the patch as committed, not yet run.** Beyond the three fixes: the CPU-readback lead (the
supervisor): if the title reads the compaction's counter back on the CPU and lays the next chain out from it, it waits
on a label the compaction's buffer writes after the dispatch; the filter now journals the first four label writes
(RELEASE_MEM / WRITE_DATA to memory) after a compaction dispatch in the same buffer — address, value, and whether the
address is mapped (an unmapped one the backend drops: a title polling such a label on the CPU would read stale data
forever, or go on without the sync) — `compaction label (exp 0308)` lines; and the count pass 0x909939400's grid and
user data 0–15, to match its output block against the leaf builder's argument addresses offline. The title runs on the
host's CPU, so its reads of GPU-written memory are plain loads of the shared mapping; what can go wrong is the order —
reading before the GPU wrote — which the label lines will show.

**Result — run 2 (binary 1afe4a87 = the committed patch, out md5 54e0bc50; chain 14:06:35–14:11:31, compaction on, RT on,
private wd; `raw/journal-stream-run2.txt.gz`, `raw/kernel-stream-run2.txt`).** S1 HANG at 117 s, recovered (gfx_0.0.0
reset succeeded, then comp_1.2.0); S2 HANG, recovered; the chain ended by itself, live saves untouched — the fourth
and fifth F332 hangs at ~2 min with the compaction on today, 0 of 5 machine-downs.

- The chain-args picture of run 1 repeats exactly: the refit's arguments sane and UNCHANGED (36), the leaf builder's
  FLOATS at submit and at the GPU's read (54 CHANGED, 5 UNCHANGED).
- **The "header" at ud[4:5] is no offsets block.** Every compaction dispatch (16 per batch, two batches a run: at load,
  submits #29220 / #26742, and once later, #120950 / #110309 — 8–9 s before the hung acb) reads 0 at +0x40 … +0x9c
  (two of each batch 0xffc00000) at filter time **and** nothing plausible at the timeout's re-read; exp 0160's reading of
  the program's `s_load_dword … s[4:5], 0x84 / 0x8c / 0x98 / 0x9c` as offsets therefore gives: node records at the
  header address itself (4 records of 8 bytes), the flag atomics and the index-list stores at **u61 + 4·index** and the
  counter at **u61 + 0x80**, where u61 = ud6 | ud1<<32 — the compaction's output block is u61: 0x1252b34a00,
  0x121c070900, 0x121c33f000, 0x121be23400, 0x1252a94b00, 0x122e901c00 … (one per tree, 16 trees), on the graphics
  buffer; the count pass's output block (its user-data V# ud6 | ud7<<32, exp 0306's acb dump: 0x12124ff200 …, stride
  0x20, the leaf builder's arguments at +0x20·k) lies in the 0x1212…/0x1271… region. **No address overlap** between
  the compaction's blocks and the leaf builder's argument addresses in run 2 (no `ARGS INSIDE` line with the fixed
  extents; the two address sets are disjoint).
- So the compaction does not write the argument blocks directly. What remains: the count pass's own behaviour after a
  compaction — it runs (`ran`, 1×1×1) but its counts never appear at the leaf builder's argument address, while the
  refit's do: either the count pass writes record k′ ≠ k (its index derived from a compacted node count), or it early-
  exits on a flag the compaction's `buffer_atomic_or` set (the flag words at u61 + 4·index). The `count pass (exp
  0308)` user-data lines and the `compaction label (exp 0308)` lines (the CPU-readback check) are in the box's journals
  only — my stream pattern and the extracts missed those two line kinds; they are the pending read.

**Run 2, the pending read (14:15, the supervisor's slot; the box's journals play-20261025-1409 / -1415).** S2: HANG at
112 s, recovered (gfx_0.0.0 then comp_1.2.0 reset succeeded).

- **The count pass 0x909939400's user data** (54 lines): `ud0-15 104ce500 00000012 104ce600 00200012 00000002 00005204
  104ce600 00200012 00000002 00005204 00000001 00000000 e0f9ffc0 00000011 000000a8 0004dfac` — ud2:3 and ud6:7 are the
  same V# of **base 0x12104ce600, stride 0x20** (the next dispatches 0x12104cfe00, 0x12104d1600, …: one block per
  tree, 0x1800 apart), ud0:1 a V# 0x100 below it, ud12:13 a resource table at 0x11e0f9ffc0 (the F360 family's kind), grid
  1 × 1 × 1. **The leaf builder's argument addresses lie in exactly these blocks at +0x20** (run 1: 0x12104e1420,
  0x12104e2c20, 0x12104e8c20, … = a count-pass block + 0x20), so the count pass and the leaf builder agree on the
  block: the count pass writes record 1 of tree T's block, the leaf builder's DISPATCH_INDIRECT reads it. What the GPU
  reads there is live float data that keeps changing between the host's filter time and the timeout — **so something
  writes floats into the count/argument block after the count pass wrote it**, in the same 0x20-stride record space
  (node bounds are floats; the refit 0x909939900 and the leaf builder write node data), or the count pass's write is
  itself lost; and with the compaction skipped the layout no longer collides.
- **The labels after the compaction batch** (the CPU-readback check): in the compaction's dcb, after the 16 dispatches,
  `RELEASE_MEM` to 0x11e0a7ffe8 value 0 and to 0x11e0d50018 value 1, both mapped and passed to the GPU — the title's
  sync after the compaction exists and the host does not drop it (the other four lines of this kind belong to the next
  buffers: a bookkeeping slip of the probe, not a finding). So the compaction's result is readable by the CPU after a
  sync the host honours; the CPU-readback lead is not supported by this.

**Verdict (run 2).** The compaction's own output blocks (u61, one per tree, in the 0x121c…/0x122e…/0x1252… region) do
not overlap the chain's argument blocks (0x1210…/0x1212…/0x1271…), and the count pass and the leaf builder agree on
the block they share (stride-0x20 records, the arguments at +0x20); yet at the GPU's read the arguments are floats that
keep changing. The mechanism is therefore **a writer of node data into the count/argument records after the count pass**
— inside the chain's own programs when they run on a compacted tree — not the compaction's stores and not a dropped
sync. Next (a new experiment): the output descriptors of the leaf builder and the refit (their user-data V#s, from the
dumps on the box: exp 0160's disassembly of 0x909936c00 / 0x909939900 names which SGPR pairs they store through)
against the count-pass blocks, at filter time; and the count pass's own store target from its code (does it write
record 1 of ud6:7, or an index it reads from the table at ud12:13 — a compacted node count would move it).
