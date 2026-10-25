# 0316 — the write trap with the chain's completion state, and the holding mode as the fix test

**Question.** Exp 0313 caught the CPU writer of the count-pass record: the second title's own code, a memcpy of more than
256 bytes re-initialising a recycled per-tree struct slot (a ring of about 29) while the GPU, made late by the BVH
compaction, has not run that slot's leaf builder — F332 at ~2 min on the S6N route (exp 0306). Exp 0314 excluded the
soft CP's early EOP event as the signal the title reuses the slot on, and showed the GPU wedges at the CPU's submission
frontier: the reuse comes within about a frame of the build's submission. Two questions, one binary: (1) at each store
into an armed slot, is the GPU job that armed it (the count pass's acb, by submission number) complete — how often not,
by how much, and from which title code (the raw return words and the anonymous mappings)? (2) If the title's thread is
held until that job completes — the console's semantics, where the CPU cannot reuse a slot the GPU has not consumed —
does the hang go away over 2 × 600 s? A clean run proves the mechanism end to end and says where the host must wait.

**Setup.** `patch0316.py` on the tree's `bc5LleAgc.cpp` (md5 5bccbb80), 4 edits: exp 0313's trap, with the arming
recording the submission being filtered (`g_submits`) and its completion queue (`t_cq`); `x0316::note_done(index, j.n)`
in the completion thread right after the job's fence wait (the per-queue highest completed submission, jobs complete in
order within a queue); each caught store records that number against the arming's, the four words at RSP (journaled
raw, and mapped — an anonymous mapping as `anon@<start>+offset`, the executable anonymous mappings listed once), and in
mode 2 (`BC5_DIRECT_WRITE_TRAP=2`) holds a title thread whose slot's chain is not done, in 50-µs nanosleep steps, until
the queue's completed number reaches it, 2.5 s at most (the fence timeout is 2 s, so a wedged GPU frees the thread);
host threads (comm `bc5-…`, read from `/proc/self/task/<tid>/comm`) are never held — a completion thread held for its
own job would deadlock; the page is not re-armed after a mode-2 fault (one fault per arming, no hard cap in mode 2; mode
1 keeps 0313b's single-step budget of 32 and the cap of 4096). The journal is bounded: the first 512 stores, record
stores (up to 65,536), "NOT done" stores (the first 2,048, then every 64th), every 4,096th; a summary per second with the
counts of not-done stores, holds, held ms, give-ups and host-thread skips. `build0316.sh` (one unit + relink against the
shared objects and exp 0290's archive, as 0313), `s6n0316.sh` (exp 0306's chain: RT on, compaction on, private wd;
`TRAP_MODE`, default 2), `stream0316.sh`.

Runs: **A** `TRAP_MODE=1 ./s6n0316.sh 1 180` — the measurement (the answer comes in the first frames; the hang at ~2 min
is expected and recoverable); **B** `./s6n0316.sh 2 600` — the fix test in mode 2.

**Readings.** A: stores into NOT-done slots in the first frames, their margin (frontier − chain), and the title's caller
(anon@ + offset against the play log's module bases) — the race quantified. B clean 2 × 600 s → the mechanism proven;
the fix is a host-side wait at that point (then: which title signal should have held it, so the wait moves there, and
the stall cost from the hold journal). B hanging as before → the held thread is not the writer that matters (the hold
journal says who was held and how long), or the slot is consumed by more than the count pass's acb.

**Result.** (not run yet; the box is the maintainer's until his play ends)

**Result — run A (mode 1; 2026-10-25 16:42:49–16:46:00; binary 77db89c8 = out 58256c13, built in 27 s; 180 s, RT on,
compaction on, private wd, live saves bb14b6dd35b644ff compared; `raw/S1-*`, `raw/journal-stream-S1.txt.gz`).** PASS,
no hang in 180 s (0 crash / kernel / TIMEOUT lines). The trap: 1,056 stores caught on the 64 LRU pages, 0 dropped,
**0 into a slot whose arming job was not done**, the frontier 6,000–12,000 submissions past the arming at every store.
The arming numbers are right: with `BC5_DIRECT_CHAIN=2` the ring thread flushes thousands of count passes in one chain
(`count pass at 3850, 3864, 3878 … before #28544 (cq 1)`, 14 dwords apart), so one submission number per burst is what
the chain gives (the journal's `submit #…` lines count the soft CP's own submissions, not `g_submits`).

**What the stores say.** The 8 record-1 stores (the title's memcpy; the RSP words now show the title's module:
`anon@0x44000+0x1aa9e0`, and `anon@0x7f8600000000+0xabe00`, beside the stale kyty word) all fall in a 4-s burst at the
route's load (t 2210–2214 of the emulator clock); from then to the end no store touched record 1 of an armed block,
although stores on those pages went on (the rest of the struct region). So **the title does not re-initialise the count
record per frame** — 0313's "per-frame recycle" was an inference; the data showed only the load-time memcpy. The floats
the leaf builder reads at the hang are the load-time template that the count pass had not overwritten yet: the leaf
builder ran before its count pass.

**Ring placement (the finding).** Every count-pass arming is `cq 1` — the ring thread's chains on **compute ring 0**
(`BC5_DIRECT_COMPUTE_RING=0` in the launcher), 1.19 M of them, 0 refused; the buffers with the leaf builder's
`DISPATCH_INDIRECT` are refused to the **GFX ring** by exp 0290's policy — 17 `stays on the GFX ring` lines at one per
1,024 refusals ≈ 17 k buffers in 180 s (723 / 1,434 / 7,457 / 22,710 dwords). On the console both run on one in-order
queue with no wait between them; here nothing orders the two rings. Exp 0317 tests it with every compute buffer on the
GFX ring.

**Verdict (0316).** Run A answers the question in the negative for the CPU: the title's CPU does not race the GPU per
frame, and mode 2 (holding the title's thread) is moot — run B not run. The job attribution and the host-thread exemption
work as designed and can serve again. The lead is the two-ring split of the build chain (exp 0317).
