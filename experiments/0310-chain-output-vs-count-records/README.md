# 0310 — who writes floats into the count records: the chain's output descriptors against the count-pass blocks

**Question.** Exp 0308 (F373): with the compaction 0x909974400 running, the count pass 0x909939400 and the leaf builder
0x909936c00 agree on the stride-0x20 record block of each tree (the count pass's user-data V#, base e.g. 0x12104ce600,
one block per tree 0x1800 apart; the leaf builder's DISPATCH_INDIRECT arguments at +0x20), yet at the GPU's read those
records hold ever-changing floats — node data — while the refit 0x909939900's arguments next to them are sane and
unchanged; the compaction's own stores lie elsewhere and the sync after its batch passes. **Which program writes node
data into the count records after the count pass, and why only when the tree was compacted?** Candidates: the leaf
builder and the refit (they write node bounds, floats, through their output V#s), or the count pass itself storing its
record at an index derived from a node count the compaction changed (then record 1 of the block is never written and
holds whatever the node writers left).

**Step 1 — offline, from exp 0160's llvm-mc disassemblies on the box (a read-only copy of three files, ~a few hundred
KiB: `~/bc5-work/exp0160/` dis of 0x909939400, 0x909936c00, 0x909939900; 0x909974400's is already on the laptop).**
For each program: the SGPR pairs it stores through (`buffer_store_*`, `buffer_atomic_*`, `global_store_*`), how each
V# is formed (a user-data pair as is, or loaded from the table at s[12:13] / a constant buffer), the stride and the
record index expression (`idxen` with which VGPR), and for the count pass the exact store of its three group counts
(which V#, which record, which offset). Tooling: `gcnstores.pl` of exp 0297 (prints stores, atomics and scalar loads
with their descriptor registers) and the user data of each program from 0308's journal lines (the count pass's
`ud0-15` is there; the leaf builder's and the refit's are in the acb dumps: `SET_SH_REG 0x240…` before each dispatch,
`acbscan.pl` from the 0306 dumps prints them).

**Step 2 — the patch (0310, on the tree 5bccbb80, the 0308 code as the base, no packet added).** At filter time, for
each dispatch of the three chain programs: the output extents from their user-data V#s as step 1 names them (base,
stride, records → [lo, hi)), kept per tree (keyed by the count-pass block the dispatch's own user data name), and the
test: **does a leaf-builder or refit output extent cover a count-pass record block of the same or another tree?**
(`CHAIN OUTPUT COVERS COUNT RECORDS of block 0x… (+0x… = record k)`), and for the count pass: the record index it will
write as step 1 derives it vs the record the leaf builder reads (+0x20 = record 1) — `COUNT PASS WRITES RECORD k, THE
LEAF BUILDER READS RECORD 1`. At the timeout: the same, plus the current contents of record 0…3 of the hung tree's
block. One journal line per hit (bounded), one per 4096 otherwise.

**Step 3 — the runs.** Exp 0306's chain (compaction on, RT on, private wd, 2 × 600 s; the F332 hang at ~2 min is
expected and was recovered 6/6 today) on the 0310 binary; the filter-time lines come before the hang either way. Then,
if step 2 names the writer, the fix candidate: a host-side rule for that one program (e.g. the count pass's record
index clamped / the compaction's node-count readback delayed until its sync), tested against the same chain and
against exp 0305's lab reflections.


**Step 1 — first reading (14:20, the three shader dumps copied read-only to the laptop; `gcnstores.pl` of exp 0297 plus a
hand decode of SOP1 moves; TODO(verify) with llvm-mc).**

- **The count pass 0x909939400** (63 instructions): user data `ud0-15 104ce500 00000012 104ce600 00200012 00000002
  00005204 104ce600 00200012 00000002 00005204 00000001 00000000 e0f9ffc0 00000011 000000a8 0004dfac` — s[0:1] a pointer
  to the tree's struct (0x12104ce500, loads at +0x18, +0x50, +0x6c, +0x78, +0xfc), s[2:5] and s[6:9] the same V#
  {base 0x12104ce600, stride 0x20, **num_records 2**, 0x5204}. Its one store: `buffer_store_dwordx4 V# s[4:7], v7
  idxen` after `buffer_load_dwordx4 V# s[0:3], v7 idxen` — with `s_mov_b64 s[0:1], s[2:3]; s[2:3], s[4:5]; s[4:5],
  s[6:7]; s[6:7], s[8:9]` before them, both V#s are that two-record descriptor: a read-modify-write of **record v7** of
  the block whose record 1 (+0x20) the leaf builder's DISPATCH_INDIRECT reads. A record index outside 0..1 is dropped by
  the hardware's bounds check (the load returns zeros, the store is discarded): then nothing writes the arguments and
  record 1 keeps whatever it held — the floats exp 0308 saw. v7 = `v_lshl_add_u32` of values loaded through the V#
  s[20:23] (from the struct, +0x6c / +0x78 — a flag or count buffer), behind a branch at the top; the hand decode of
  that arithmetic is not reliable (one path reads v7 = 3, which cannot be the normal case) — llvm-mc pending.
- **The leaf builder 0x909936c00** (136 instructions): stores a 0x40-byte node (dwordx4 at +0, +0x10, +0x20, dwordx3 at
  +0x30) through V# s[96:99] built from the struct at s[4:5] (+0x78 the base pair, +0x40 another pair, +0x6c a dword);
  reads a scalar by `s_buffer_load_dword` from the V# at s[12:15] at an offset in vcc — a count readback (the
  compacted node count?); loads nodes through s[80:83].
- **The refit 0x909939900** (two code copies in the dump, ~0x7f8 bytes each): stores records (+0x10 x4, +0x20 x2, idxen
  offen) through s[48:51] / s[52:55], two atomics (ops 0x33 / 0x3a) through s[8:11] / s[0:3], and one fixed-offset
  store (+0x98 x4, +0xa8 x2, no index) through s[4:7] from the struct's +0x60.

The hypothesis for step 2: the count pass's record index depends on a value the compaction changes (a flag it sets by
`buffer_atomic_or`, or the compacted node count the chain reads back), and lands outside the two-record buffer; the
filter can read the same inputs (the struct's +0x6c / +0x78 buffers at ud0:1) at dispatch time and predict the index.

**Step 1 — the reading completed offline (14:30; `gcnfields.pl`, a field decoder of SOP1/SOP2/SOPC/SOPP/SMEM/VOP/MUBUF
written for it, on the three dumps; no llvm-mc, so TODO(verify) the mnemonics — the register and offset structure does
not depend on them).**

- **The count pass 0x909939400** (63 instructions): thread 0 only (a `v_cmpx` on the thread index gates an assert block
  of four `s_trap`s on the struct's +0x18 bits 4/18/29 and +0xfc == 10); s[0:1] = ud0:1 = **the tree's struct**; the V#
  s[20:23] = {struct + struct[0x50:0x54], stride 4, records struct[0x6c]} is a dword array `arr`; `v0 = arr[tid] −
  arr[1 − tid]` for tid ≥ 1 and `v0 = arr[0] − struct[0x78]` for tid 0; **record index v7 = 2·tid + 1** → thread 0
  writes **record 1**; it loads record v7 through the V# at ud2:5 = {struct + 0x100, stride 0x20, 2 records}, packs the
  sign bits of its four dwords into v3, and stores `{v0, 1, 1, v3}` through the same V# (ud6:9) at record v7 — so the
  argument block is **struct + 0x100**, record 1 = struct + 0x120 = the leaf builder's DISPATCH_INDIRECT arguments
  (x = arr[0] − struct[0x78] groups, y = z = 1). The store is in range (record 1 of 2): the count pass does write the
  arguments. (Exp 0306's acb dump: ud6:7 = `124ff200 00200012` = the same V# for struct 0x12124ff100.)
- **The leaf builder 0x909936c00** (136 instructions): s[4:5] = ud4:5 = the struct; `arr` again as V# s[12:15] (base
  struct + struct[0x50:0x54], stride 4, records struct[0x6c]) read by `s_buffer_load_dword` at arr[ud8]; the input
  primitives through V# s[80:83] = {struct + struct[0x40:0x44], stride 20, records struct[0x78]}; **its output node
  buffer is V# s[96:99] = {base struct + (struct[0x7c] << 6), stride 0x40 (dword 1 bit 22), records struct[0x78]}**, and
  it stores a 0x40-byte node (x4 at +0, +0x10, +0x20, x3 at +0x30) at index v28 = arr[ud8] + the thread's index. **So the
  nodes are addressed from the struct: node k lies at struct + (struct[0x7c] + k) · 0x40**, and the argument block at
  struct + 0x100 … 0x13f is exactly node 4 − struct[0x7c]: a node base below 4 − (nodes written) puts node data over
  the counts — floats (bounds) that change every build, which is what exp 0308 saw at record 1, while the refit's
  records elsewhere stay sane. The count of nodes the leaf builder writes depends on arr[ud8] (the per-tree leaf index
  base) — the array the compaction's flags / index list (at u61 + 4·index, exp 0308) may feed when the tree was
  compacted: a changed arr[] or struct[0x7c] after the compaction is the candidate for "only with the compaction".
- **The refit 0x909939900**: s[20:21] a struct pointer too (loads +0x38, +0x48, +0x58, +0x60, +0x74, +0x80); stores
  records (+0x10 x4, +0x20 x2, idxen offen) through s[48:51] / s[52:55] and two atomics; its arguments (sane in 0308)
  come from a different block; not decoded further.

**Step 2 — the patch (`patch0310.py`, 8 exact-anchor edits of the tree's `bc5LleAgc.cpp` 5bccbb80, verified offline 8/8,
out md5 f0df68b3, 124 added lines; `patch_0310.diff`; exp 0277's probe fix carried, no packet added).**

1. Filter time, per leaf-builder dispatch (`leaf (exp 0310)` lines, loud when the nodes cover the argument block or
   struct[0x7c] < 8, else one per 4096): the struct (ud4:5), struct[0x78] records, struct[0x7c] node base, the `arr`
   pointer and records, ud8, arr[0] and arr[ud8], the node extent [struct + 0x7c·64, + records·64) vs the argument block
   [struct + 0x100, +0x40) → `NODES COVER THE COUNT RECORDS` / `apart`, and record 1 as it reads now; the last 4096
   readings kept by struct.
2. Filter time, per count-pass dispatch (`count (exp 0310)`): the struct (ud0:1), the V# at ud2:5 against struct +
   0x100, `arr[0] − struct[0x78]` (the count it will write), record 1 now, struct[0x7c].
3. At the timeout (`timeout probe: leaf (exp 0310)`), per leaf-builder dispatch of the hung buffer: the struct from
   the user data the probe tracks (COMPUTE_USER_DATA_4/5/8), struct[0x7c] / [0x78] now vs the filter-time reading
   (`as at filter time` / `CHANGED since filter time`, with the old values), the node extent vs the argument block, and
   record 1 now vs then.

**Setup — runs.** `build0310.sh [<archive>]` as 0308's; `s6n0310.sh` = exp 0306's chain (compaction on, RT on, private
wd, 2 × 600 s; the F332 hang at ~2 min expected, recovered 6/6 today) on this binary; `stream0310.sh` on the laptop.
Outcomes: `NODES COVER THE COUNT RECORDS` at filter time → the title's struct names a node base that overlaps its own
argument block (the layout the title derives after a compaction; the fix candidate is then at the value it derives
it from — arr[] / struct[0x7c] — or a host-side guard that refuses that one dispatch); `apart` at filter time but
record 1 CHANGED into floats at the timeout → another writer (the refit's records, the compaction's u61 block) — then
its extents next.


**Result (2026-10-25; binaries 71c2e889 = out f0df68b3 for S1/S2, 5d3e81ec = out 54608f55 "0310b" for S3; chains
14:34:36–14:39:08 and 14:41:01–14:43:02 under the supervisor's mandate; compaction on, RT on, private wd;
`raw/journal-stream.txt.gz` (both chains), `raw/kernel-stream.txt`; the box's `exp0310/raw/`).**

| run | start | hang | after the resets | verdict |
|---|---|---|---|---|
| S1 | 14:34:36 | 116 s | box up, emulator up | HANG, recovered (comp_1.2.0 then gfx_0.0.0 reset succeeded) |
| S2 | 14:37:06 | 117 s | **the emulator crashed**: `Access violation: Read [000000000001d880]` in `src/loader/runtimeLinker.cpp:1111`, exit 65 at 14:39:02 | HANG, recovered; FAIL by the crash rule |
| S3 (0310b) | 14:41:01 | 116 s | **the emulator crashed**: `Access violation: Read [000000000004dfac]`, exit at 116 s | HANG, recovered; FAIL by the crash rule |

**Step 2's answer — the overlap hypothesis is OUT.** At the timeout every leaf-builder struct reads sane and unchanged
since filter time: [0x7c] node base 16 … 1495 (× 64), [0x78] records 40 … 2399, so the node buffer [struct + base·64,
+ records·64) lies far above the argument block [struct + 0x100, +0x40) — "apart" in all 63 + 63 + 1 printed dispatches,
no `NODES COVER` line at filter time in ~600 leaf lines a run. The leaf builder does not write over its own arguments.
The count pass's V# is struct + 0x100 (stride 32, 2 records) for every tree, as read from its user data; at load the
structs are all zero (records 0, base 0, arr[0] garbage, record 1 = 0 0 0 — not yet initialised), at the timeout record 1
holds **float triples that CHANGED since filter time for most trees** (57 of 63 in S2: `3f63dc00 3c7d8000 bf21b600`,
`40a26800 403e1800 c09c9000`, `3fb48200 3db6c000 be3cc000` …) and stayed for a few (`400fbe00 3d810000 bb700000`) — values
of a position / translation per tree, changing per frame, the kind of data a refit needs for a moving object. No GPU
program of the four read (count pass, leaf builder, refit, compaction) stores at struct + 0x120; the title's CPU is the
remaining writer: a new position written each frame into the struct region after this frame's count pass ran on the
GPU and before the leaf builder's argument fetch — on the console the count pass runs long before the CPU's next update,
here the GPU is late (the compaction lengthens the frame) and the window opens; with the compaction skipped the title
may not write positions for those trees at all. **0310b's decisive test** — record 1 sampled three times 50 ms apart at
the timeout, when the GPU is wedged, so a moving value has a CPU writer — **got no data**: the emulator crashed within
the probe (one `timeout probe: leaf` line of 63 reached the journal, no `sampled 3x` line).

**The crash after a recovered hang** (new today): 2 of 3 runs with 0310's binaries (S2, S3), 0 of 6 with 0306/0308's.
The read addresses 0x1d880 and 0x4dfac are descriptor-word-sized values (0x4dfac = dword 3 of the title's V#s,
`0004dfac`): the title's thread (runtimeLinker.cpp:1111) dereferences a slot that now holds descriptor words — memory
the aborted GPU work left in a mixed state after the ring reset. Whether 0310's probe (reads only) shifts the timing is
unknown; the chain's crash rule stopped both chains as written.

**Verdict.** Settled: the leaf builder's node buffer does not cover the argument block; the count pass addresses record 1
of {struct + 0x100, stride 0x20, 2 records} and computes x = arr[0] − struct[0x78]; record 1 holds changing float
triples at the GPU's read while the chain's structs are intact. Open: the writer of record 1 — the CPU (the title's
per-frame position update racing a late GPU) is the only candidate left among the readers' sources; 0310c = 0310b with
the three samples taken first and the journal flushed before the per-dispatch lines, one run; and the llvm-mc check of
the decoder's readings (exp 0160's `disf.sh`, approved for the next slot).
