# 0313 — who writes the count record from the CPU: a host-side write trap on the argument-block pages

**Question.** Exp 0310 (F375): the build chain's count pass 0x909939400 writes the leaf builder's DISPATCH_INDIRECT
arguments as record 1 of {struct + 0x100, stride 0x20, 2 records}; at the GPU's read that record holds per-tree float
triples (positions) that change frame to frame and keep still while the GPU is wedged; no GPU program of the chain or
the compaction stores there, nothing writes it asynchronously — a once-per-frame CPU write by the title is the writer
left. **Which thread and which code of the title writes struct + 0x100 … 0x13f, and when relative to the count pass?**
The maintainer's consent for today: "Masz zgodę" (2026-10-25 ~15:20).

**Setup — the patch (`patch0313.py`, 3 exact-anchor edits of the tree's `bc5LleAgc.cpp` 5bccbb80, verified offline
against patch 0001: 3/3, braces balance; `patch_0313.diff`). The supervisor's two notes are in: the handlers are
installed lazily at the first arming and, if a SIGTRAP handler was already installed (a debugger hook, the host), it is
given back and nothing is ever armed ("not armed: a SIGTRAP handler is already installed"); a hard cap of 4,096 caught
stores a process (beyond it no page is armed again) on top of the 32-store budget per arming, and a per-second summary
line (caught, dropped, foreign faults, armed pages). Diagnostic, `BC5_DIRECT_WRITE_TRAP=1`; without it the
binary behaves as the tree.**

- **Arming.** At filter time, each count-pass dispatch (0x909939400; `BC5_DIRECT_COUNT_PGM` overrides) names its struct
  (ud0:1); the page of struct + 0x100 is armed — `mprotect(PROT_READ)` from the host — **only when the device maps that
  page as a shared memfd mapping** (`bc5::direct::Mapping::shared`): a userptr page made read-only would break the
  GPU's own write path (HMM needs a writable VMA), while a shared / udmabuf page keeps GPU access untouched (the GPU
  writes through its own mapping, CPU page protection does not apply to it). Else "not armed (userptr)". At most 64
  distinct pages; each arming carries a budget of 32 caught stores, then the page stays writable until the next
  count-pass dispatch re-arms it (the per-page budget keeps the trap from stalling the game thread, the supervisor's
  note). One `write trap (exp 0313): count pass … ARMED` line per arming (the first 64, then every 4096th, and every
  refusal).
- **The watchpoint.** A SIGSEGV on an armed page: the handler (async-signal-safe: the ring, `mprotect`, the signal
  context) records {thread id, RIP, target address, time, page, struct} into a 256-entry lock-free ring, makes the page
  writable, sets the x86 trap flag and returns; the SIGTRAP handler re-protects the page and clears the flag — every
  store is caught, each costs the writing thread two signals. A fault outside the armed pages goes to the host's
  previous SIGSEGV action (KytyPlus's "Access violation" reporter), installed-before preserved by `sigaction`'s old
  action; the handlers are installed once, lazily, at the first arming.
- **The journal.** The filter thread drains the ring at every dispatch it looks at: `write trap (exp 0313): thread T
  stored to 0x… (THE RECORD 1 of the argument block | the argument block | other data on the page) from <module>+0x…
  (rip 0x…), struct 0x…, t …` — the module and file offset from `/proc/self/maps` (read once per RIP page); the first
  512 stores, every store into an argument block, then every 4096th; the counts of caught / dropped / foreign faults
  on each line.

**Setup — runs.** `build0313.sh [<archive>]` as 0310's (one unit + relink; exp 0290's archive). `s6n0313.sh` = exp 0310's
chain (RT on, compaction on, private wd, the live saves compared only, stop at a machine-down / crash / save change)
with `BC5_DIRECT_WRITE_TRAP=1`, **one run of 180 s** by default: the first frames after the structs are initialised give
the answer; the F332 hang at ~2 min is not needed and was recoverable 9 of 9 today. Extracts per run: the `write trap`
lines, the arming lines, the `THE RECORD 1` lines. `stream0313.sh` on the laptop.

**How to read it.** A `THE RECORD 1` store from the title's module (`eboot.bin+0x…` or a `.prx`) names the writer and its
time relative to the arming (= the count pass's submit): the title writes positions into the record after this frame's
count pass — the race is the title's design meeting a late GPU, and the fix is at the readback / timing (or a host-side
copy of the record right after the count pass). No `THE RECORD 1` store at all while the leaf builder still reads floats
→ the writer is not a CPU store on a shared page (then: the page is userptr and could not be armed, or a GPU program
outside the four read writes it — the refit's or another pass's output extents are next). Stores from the host's own
code (`kyty_emulator+0x…`) → the emulator writes there (a host bug), the most direct fix. "Foreign faults" > 0 → the
trap caught faults that were not ours and passed them on; a crash of the title under the trap means the chaining
broke (then the previous action's restoration needs a look).


**Result — run 1 (2026-10-25 15:20:06–15:22:19; binary c74f9904 = out 691b64db; one run of 120 s, RT on, compaction
on, private wd; `raw/journal-stream-run1.txt.gz` — the 1.17 M refusal lines of defect 1 removed from the stream, 662
lines kept; the box's `exp0313/raw/S1-*`).** PASS: 120 s, no hang, no crash; live saves 8289704a9338a118; the lock
released by the script. The pages of the argument blocks are shared memfd mappings: every arming said `ARMED` (96).

**The writer is caught.** `write trap (exp 0313): thread 1572471 stored to 0x12104f1c20 (THE RECORD 1 of the argument
block) from /usr/lib/x86_64-linux-gnu/libc.so.6+0x197bb7 (rip 0x7f6b80557bb7), struct 0x12104f1b00` — five stores into
record 1, nineteen into the argument block, 506 into the rest of those pages, **all from four RIPs inside one AVX store
loop of libc (+0x197bb7, bbb, bc0, bc5: a memcpy/memset), on the title's worker threads 1572471, 1572472, 1572473,
1555079** (the main pid was 1554921): a bulk copy or fill of the whole per-tree struct region by the title's job threads
— the title re-initialises the struct block, argument block included. With exp 0310 (the structs are per-frame
allocations from a ring, +0x1800 apart, recurring), the mechanism reads: **the title's CPU re-initialises a recycled
struct slot for a new frame while the GPU, late by more than the ring's depth, has not yet run the old frame's leaf
builder; the memcpy's source — a template holding positions — lands over the count pass's record, and the leaf builder
reads floats.** The compaction makes the GPU late enough for the ring to wrap onto in-flight work; without it the GPU
keeps up. Also seen: 491,165 foreign SIGSEGVs in 120 s passed to KytyPlus's own handler (the host uses faults heavily
for its own purposes); the chaining held.

**Two defects of run 1, fixed for run 2 (0313b, the patch as committed, out md5 78258923, 233 lines).** (1) The page
table was 64 fixed entries with "refuse when full"; the structs change every frame, so the trap lived ~4 frames (1,914
stores caught, 998 dropped by the 256-deep ring) and then every count pass was refused — and every refusal was
journaled: 1.17 M lines, a 200 MB `direct.log`. Now: an LRU ring of 64 pages (the oldest arming is replaced, its page
left writable), refusals journaled once per 4096, the ring 1024 deep. (2) The caller was unknown (the RIP is inside
libc): the handler now also records the four words at the faulting thread's RSP, and the drain maps those that fall in
a mapped file to module + offset (`<- eboot.bin+0x… | …`) — the title's code that calls the memcpy.

**Verdict (run 1).** The CPU writer of the count record is found: a libc memcpy/memset on the title's worker threads
re-initialising the per-tree struct block; the race is the title's ring of per-frame structs wrapping onto a frame the
GPU has not finished. Run 2 names the title's caller and the ring's reuse distance.

**Result — run 2 (0313b; 2026-10-25 15:30:47–15:33:13; binary 2568a7b3; 120 s, RT on, compaction on, private wd;
`raw/journal-stream-run2.txt.gz`, the box's `exp0313/raw/S2-*`).** The F332 hang at 112 s (`ring comp_1.1.0 timeout`,
reset succeeded), 0 crash lines, live saves 8289704a9338a118 unchanged, the lock released by the script. The LRU page
table held (64 of 64 pages armed throughout, 2,203 stores caught, 0 dropped, 0 foreign faults in the trap's own count),
12 of them into record 1 of an argument block, every one from the same libc store loop as run 1: `libc.so.6+0x197bb7,
+0x197bbb, +0x197bc0, +0x197bc5` (and the loop's tail +0x197bd3–0x197be6, once each). The box's libc disassembles
them as `__memcpy_avx_unaligned_erms`'s four-ymm copy loop (`vmovdqa %ymm1,(%rdi)` … at `memmove-vec-unaligned-erms.S`
line 488), which runs only for copies of more than 256 bytes and keeps no stack frame — a bulk memcpy of the struct
region, as read in run 1. Struct ring: the first struct armed came back after 29 armings (`S2-table.txt`), i.e. the
title cycles about 29 per-tree struct slots.

**The caller attribution of 0313b is void — read it with care; run 1's reading (the title's worker threads) is the
right one.** Every store line says
`<- kyty_emulator+0x6a3123` (`Libs::LibAmpr::Ampr::AprReaderThread`), which is **not** a return address: `objdump`
puts 0x6a3123 in the middle of `movzbl (%rsi),%eax` at 0x6a3122, with no call before it — a stale word on the stack.
The drain printed only RSP words that map to a file-backed module and skipped `[anon]` ones; the memcpy is a leaf, so
[RSP] was the true return address, and it lay in an anonymous mapping — in this process the title's own code (the
eboot/prx loaded by KytyPlus), calling memcpy through the HLE libc. So the writer is the title, not a host thread
(AMPR, soft CP and the filter are excluded: none of their code appears in any RSP word). A 0313c that prints the raw
RSP words and the title's module bases would name the title's function; it would change nothing on the host, so it is
not run unless the EOP-timing A/B (exp 0314) comes back negative.

**Verdict.** The CPU writer of the count-pass record is the title's own code: a memcpy of more than 256 bytes (a
template over the whole per-tree struct) re-initialising a recycled struct slot, on the title's worker threads (run 1),
with a ring of about 29 slots (run 2). The leaf builder of a frame the GPU has not reached yet then reads the
template's floats as a node count, and F332 follows when the compaction makes the GPU late by more than the ring's
depth (exp 0306). The title reuses a slot when it believes the GPU is done with it; what tells it so on this host is
the next question — the soft CP fires the IB submissions' EOP events at submission unless `BC5_DIRECT_SOFTCP_POST_IB=1`
(F143, exp 0083), which exp 0314 tests on the 0306 chain.
