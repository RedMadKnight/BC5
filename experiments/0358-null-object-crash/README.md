# 0358 — the title's null-object crash at eboot.bin+0x3d7eca0

Ordered by the top session on 2026-10-28 after the maintainer's play on the test 0356 shortcut ended at 11:11:30 on
this crash (exit 65, ~80 s after the start): a read of 0xc at `eboot.bin+0x3d7eca0` with rdi = 0, no GPU line. The
same site and frames ended his sessions of 2026-10-26 11:08 (F397) and 2026-10-24 (exp 0326 try 3) and exp 0299's L1:
four crashes, the one that hits him most. Base: main c4f1a19 (shared normal affa0c22, archive bb50b2e0); no change to
the shared builds (D19). Findings from F444. Per exp 0318's rule the title's code was read on the box from the fake-signed
SELF; no code bytes or disassembly are kept here, only what they mean.

**Question.** Why does the title pass a null object there: a host function's null or failure, an unset out-parameter, or
an overwrite (F360's class)?

## What the four dumps and the code say

- **The crash instruction and the object.** At +0x3d7eca0 the title reads a dword at offset 0xc of the object in rdi;
  rdi was loaded a few instructions earlier from the function's own stack slot that holds its *fifth argument* (r8 at
  entry, saved at +0x3d7e8c2; the function starts at +0x3d7e8a0). The function then calls a bump allocator
  (+0x3a04b50: `alloc(arena, size, 0, 0)`, which reads the arena's limits at offsets 0x8–0x18) with that object as the
  arena, and copies 2×n0 bytes into the result (+0x5f1ee20). So rdi is a *per-thread frame arena*, and the crash is
  "allocate from an arena the caller did not provide". The registers agree across the four dumps: rdi = 0, r9 = 1,
  r10 = r11 = rdx = 0, r12 = 0x505 and r14 = 0x50a (constants the function sets at +0x3d7ea11), r13 = the mesh
  record (counts 0xb898/0x242c today, 0x1203/0x335 and 0xb2e/0x1ff in the older dumps), r15 = a small table of
  (index, count) shorts. Nothing was overwritten: the null is a value the caller computed.
- **Where the caller gets it.** The caller (frame [0], return at +0x46621ba; the call at +0x46621b5) builds the
  arguments at +0x4662118–+0x4662174: it reads two ints through pointers it was given — `a` (a local set to 0) and
  `b` — and chooses r8 in three ways: if `a` equals the global at 0xb064020, r8 = the global arena pointer at
  0xb064018; else if `b` ≠ −1, r8 = the entry `b` of a global table at 0xb0636d0 (entries of 0x2f0 bytes) plus
  `a`×0x50 + 8 — a per-worker, per-slot arena; else, **`b` = −1, r8 = 0** (+0x4662171, an explicit `xor r8d, r8d`).
  So the null means: the thread running this code has worker index −1 and the "special" index is not 0.
- **What `b` is.** The title keeps two ints in each thread's thread-local block at fs:−0x104 and fs:−0x108: a worker
  index and a generation. They are written in one place, the worker-registration function at +0x3ccbf30 (its only
  callers are indirect: the worker threads' entry): `[fs−0x104] = index (low 16 bits of the argument)`,
  `[fs−0x108] = argument >> 32`, then the table entry's active count is bumped. A second site, +0x3ccae23, writes the
  *special* index (the global at 0xb064020) into the current thread's slot and stores the address of a stack-local
  arena into the global arena pointer: the main/render thread's registration. Every other reader of the slots
  (+0xe4138d … +0x10f6310, a dozen sites) takes the same −1 → "no arena" branch. Nothing in the chain calls a host
  function: the value is the title's own sentinel for a thread that has not registered with its job system, read by
  a mesh-expansion path that assumes a registered worker. On the console the same code on an unregistered thread
  would crash the same way, so on the console this path runs on a registered thread.
- **The thread.** The host's crash print names it only as "thread = 5" (the host's unique thread counter), the same
  in the four dumps' frames [0]–[2]; frames [3]–[4] show two different entry chains (today's +0x4920dff/+0x3a5e0b9, the
  older dumps' +0x1cc38f4/+0x3a5e5c9), both into +0x3ccb1b8, a function that spins (`pause`) on the frame-block
  pool until +0x3cca600 hands it a block. Which guest thread "5" is, and why its slot reads −1 at that moment (never
  registered, registered on a different thread-local block, or unregistered again), the dumps do not say: the host
  keeps a thread-local block per host thread id (`tlss[GetThreadIdUnique()]`, `runtimeLinker.cpp` line 2518), copies
  the TLS image into it (so the slot's initial value is the image's, or 0 past `init_size`), and `mov rax, fs:0` in
  the title is patched to a call that returns that block's TCB.

## Design: the trap

Not a fix yet, because the host-side cause is not identified: a stub that hands a dummy arena would hide a title
state the console never reaches. The trap makes the next crash name it. In the host's guest-fault print
(`runtimeLinker.cpp`, after the stack trace), for a guest access violation:
1. the faulting thread as the title knows it: its pthread name and guest thread id (`kernel/pthread.cpp`, the current
   thread's record), beside the host's unique id;
2. the main program's TLS layout (`tcb_offset`, `image_size`, `init_size`) and the TLS image's initial dwords at
   tcb−0x110 … tcb−0x100, i.e. what a fresh thread's worker index and generation start as;
3. every guest thread's slots: for each thread-local block the host holds (`tls.tlss`), the dwords at tcb−0x108 and
   tcb−0x104 and the pointer at tcb−0x98, with the thread's name and ids. That shows which threads are registered
   workers (index ≥ 0), which never were (the image's value), and whether the faulting thread's slot was reset.
Output only at a crash; nothing else changes. If the print shows a registered worker whose block the faulting code
did not see (index set on another block), the host's TLS lookup is the cause; if it shows a thread that never
registered (a loader/streaming thread the title drives differently on the console), the title's registration path
is the next thing to read; if it shows an index reset to −1, the un-registration is.

**Setup.** Box: `build0358.sh` + `build0358.py` + `patch0358.pl` (0356's pattern; the units `runtimeLinker.cpp`
e37ed5cd and `kernel/pthread.cpp`, private copies, the shared archive as it is), `s6n0358.sh` (0356's run script),
`raw/selfdis.py` (the SELF reader used for the code above; the played eboot differs from the older copy
`~/bc5-work/eboot.bin`, which has no such code at that offset). Box runs with RT on, under the lock, only without a
MAINTAINER PLAYING line; the crash is the maintainer's play's, so the trap build should also go on his test shortcut.

**Result.**

- **F444 — the null is the title's own sentinel, not a host value.** The object at +0x3d7eca0 is the per-thread frame
  arena the crashing function receives as its fifth argument; its caller (+0x4662141–+0x4662171) selects it from the
  worker table at 0xb0636d0 by the thread's worker index at fs−0x104, or the global arena at 0xb064018 when the
  "special" index applies, and passes an explicit 0 when the index is −1. The index is written only by the worker
  registration at +0x3ccbf30 (reached through the worker threads' entry) and the main-thread registration at
  +0x3ccae23. No host function returns it, no out-parameter is involved, nothing was overwritten (the four dumps'
  registers agree, down to the function's constants 0x505/0x50a). The open question is why a thread with index −1
  runs that mesh-expansion path on the host: never registered, registered on another thread-local block (the host
  keeps one block per host thread id), or unregistered again. The dumps do not name the thread beyond "thread = 5".
- **The trap (build 86ebf2bd).** `patch0358.pl` (4 edits: `kernel/pthread.cpp` 2, `loader/runtimeLinker.cpp` 2; the
  unit `pthread.cpp` is CRLF in the tree, the patch adapts its anchors) adds to the guest-fault print: the faulting
  thread's pthread name, guest id and host id; the main program's TLS layout and the image's initial dwords at
  tcb−0x110 … −0x100; and for every guest thread's thread-local block its generation (tcb−0x108), index (tcb−0x104)
  and the pointer at tcb−0x98, with the thread's name, the faulting one marked. Compiled with the shared build's own
  commands on the shared objects affa0c22 and archive bb50b2e0 (4 warnings, the tree's own); nothing shared written.
- **R1 (S6N, RT on, 900 s), 11:33:27 → pass, F445:** 37.2 flips/s over 899 s, GPU busy 19.92 ms a frame, host prepare
  2.57 (filter 0.99); no crash, no kernel line (`raw/R1-kernel-stream.txt`), no TIMEOUT, live saves unchanged
  (47aefd4567e6d346; the maintainer's plays had changed them again). The trap did not fire: the crash belongs to the
  maintainer's play (three of its four occurrences), not to the S6N route, which 0356's R1 and this one ran 900 s each
  without it.

- **The box repro from the maintainer's save (F446), 11:51–12:08, lock held, RT on, kernel stream on.** His two starts
  on the test 0356 shortcut (11:10:11 and 11:16:23) died at the same site at t ≈ 78 s; the live saves between them changed
  only in `i38-null-prefs.param` (47aefd4567e6d346). A private copy of those saves (`~/bc5-work/exp0358/saves-live-47aefd45`,
  the live ones compared only) in the private working directory, `raw/repro0358.sh` (the run script with the binary and
  the input script as parameters):
  - A, the shared build affa0c22, the S6N Continue route (first press at 85 s), 200 s: pass, 37 flips/s.
  - The host's input recorder (`KYTY_BC5_INPUT_RECORD`, the shared launcher's own) had written his second start's pad to
    `~/bc5-work/route-record.txt` (273 lines: cross at 33.0, 35.9 and 36.8 s — the title, Continue, confirm — then from
    55 s a fight: R2, R3, triangle, seven squares, R2, 110 stick moves until 65 s; kept as `raw/his-start2-record.txt` on
    the box, replayed as `his-start2.cmd` = `wait 33000` + the record, since the record starts at the first press).
  - A2 (the shared build), B2 (the ledger build 187910d8) and C2 (the trap build 86ebf2bd), each 150 s with that
    replay: all pass, 44–45 flips/s at the end. The replay follows his run to the second — 30 flips/s on the title, the
    load at 34–45 s at 15 flips/s, 23–41 at 46–51 s — and diverges at 52 s: his play fell to 15 flips/s for 52–66 s (the
    fight's scene) and crashed 13 s after his last input; the replays stayed at 41–45 flips/s, so the replayed stick
    moves did not bring the character to his fight (NPCs and the per-frame sampling of a time-based replay differ), and
    the mesh-expansion path was never reached.
  So the bench separates nothing: readings (a) and (b) both stand, with B2's pass saying only that the ledger build does
  not change the replayed path. The crash needs his play; the trap build 86ebf2bd is the way to name the thread and the
  state, from a desktop shortcut.

**Verdict.** The cause is narrowed to the title's job system, not the host's imports or memory: a thread whose
worker index reads −1 reaches a path that needs a registered worker's frame arena. Which thread and why is what the
trap prints at the next occurrence. The private build 86ebf2bd runs the route unchanged (F445) and is ready for the
maintainer's test shortcut ("BC5 emulator (test 0358)", scripts in `raw/`), which needs the top session's word; the bench
cannot provoke the crash: the Continue route and his own recorded inputs replayed from his save both miss his fight (F446). Open: the host's per-host-thread TLS lookup (`tlss[GetThreadIdUnique()]`) is the one
host mechanism in the chain — if the trap shows the faulting thread registered on another block, that is the cause;
if it shows a thread the title never registers (a streaming or loader thread), the title's registration path is next.

**The shortcut (12:10).** `~/Pulpit/BC5 emulator (test 0358).desktop`, Exec `distrobox enter ubuntu -- env
BC5_EMU=~/bc5-work/exp0358/kyty_emulator ~/bc5-work/exp0358/play-pkg-0358t.sh`; the launcher (md5 abfaab76) is the
integrated play-pkg.sh 55531ab6 with two changes (`raw/mktest0358.pl`, `raw/shortcut0358.sh`; the diff is 4 lines): the
log line, one log per start in `~/bc5-work/exp0358/play/`, and the input recorder pointed at a per-start file there
(`record-<ts>.txt`; the env file's recorder writes one shared file that each start overwrites), so his pad is kept. The
binary is the trap build 86ebf2bd, md5-checked before the file was written; RT on from the shared input.cfg. Nothing
shared written, the game not started, the 0356 shortcut untouched.

## The trap fired (12:17): what it says, and trap v2

The maintainer's first start on the test 0358 shortcut (12:16:01, log `~/bc5-work/exp0358/play/play-20261028-121601.log`,
pad in `record-20261028-121601.txt`) crashed at 12:17:14 (t ≈ 73 s, the same site +0x3d7eca0). The trap's print, read
against the code (offline; the lock held a `MAINTAINER PLAYING` line throughout, no box run):

- **F447 — the faulting thread is the title's main thread, and the title never registers it as a worker.** The trap
  names the thread "MainThread" (guest id 1, host unique id 5); its thread-local block holds the TLS image's initial
  values in the worker slots (generation −1 at tcb−0x108, index −1 at tcb−0x104, 1 at tcb−0x98), while the worker
  threads' blocks hold what the registration at +0x3ccbf30 writes (Job Lo/Hi/Bk: generation 1/2/0, index 0–4). The
  one host mechanism in the chain is clean: `GetThreadIdUnique()` is a thread_local counter, assigned once per OS
  thread, so the guest main thread keeps one host id from its entry on; its block is made by the first patched `fs:0`
  access on that thread (memset 0 + image copy, `runtimeLinker.cpp` ~2518), i.e. before any title code of that thread
  runs, and every later `fs:` access of the thread lands on the same block. So the −1 is not a lookup gone wrong: no
  registration ever wrote to it. F444's "main-thread registration at +0x3ccae23" was misread: that site is inside the
  pool-grow path and only overrides the slot for the duration of one callback (`[0xb064018]` = an arena on the
  caller's stack at rbp−0x68, the slot = the "special" index from `[0xb064020]`, `call [r14+0x80]`, restored at
  +0x3ccae46; the special index itself is stored once, at +0x3cc9166). The host ids 1–4 have no guest block at all
  (host-only threads started before the guest's main), as expected.
- **F448 — the crash path is the pool's reclaim at frame end, taken on the main thread without the override.** The
  chain in the dumps: [5] +0x3d75d6e (the frame's end) → [4] +0x3a5e0b9 / +0x3a5e5c9 (a loop over the systems'
  virtual calls) → [3] +0x4920dff / +0x1cc38f4 (`call 0x3cca900`, which tail-jumps to 0x3ccb180; the second site is
  guarded by the per-frame done flag at +0x551e4, compared with 1 at +0x1cc38df, set at +0x1cc33ef, cleared at
  +0x1cbcf46 / +0x1cc3880) → 0x3ccb180 spins (`pause`) while `[rbx+0x94] >= [rbx+0x98]` with `[rbx+0x20] != 0`
  (a count at or above a capacity, with work outstanding), sets the flags at `[rbx+0x8c]` and calls 0x3cca600 →
  [1] 0x3cca882, the return from `call [r15+0x80]` at 0x3cca87b (the block callback, r12 the arena chosen from
  (generation, index) through the table at 0xb0636d0, entries of 0x2f0 bytes; 1 MiB allocated through 0x3a04b50) →
  [0] +0x46621b5 → +0x3d7e8a0 → the null at +0x3d7eca0. The pool object is reached from the global at 0x8e51418;
  0x3cca270 (215 callers) picks one of three tables (0xb0639c0, 0xb0636d0, 0xb063cb0) by two flag bits at the
  object's +0x74, locks the mutex at +0x2c8 and compares the count at +0x294 with the capacity at +0x290. So the
  main thread calls the callback meant for registered workers (or for the override's special arena) because the pool
  is full at frame end: on the console that path either never runs on the main thread or runs under the override.
  Why it is full here is the open question; the title's own fault (a race its workers never lose on the console) and
  a host-side timing (frames retired late, so blocks are returned late) are both possible.
- **The flip-label clears do not single out the crashes.** The host clears a flip label still set at the wait after
  serving the wait on the CPU for up to 100 ms (patch 0001, F128/F212). Before each crash they rise (per 10 s of run:
  11:10 — 21, 18, 29, 23, 70, 20, 121, 91; 11:16 — 15, 22, 25, 16, 64, 29, 80, 81; 12:16 — 16, 32, 39, 20, 44, 50, 63,
  6) as the fight starts, with the frame profiles showing 40–74 ms between flips and "flip label still set at the
  wait" lines; but the clean S6N run of 09:10 (900 s, no crash) has 130–260 per 10 s throughout. The clears are a
  property of the host's presentation, not of the crash; what the crashes share is the fight scene at 15 flips/s.

**Design: trap v2.** The next occurrence has to show the pool's state, not only the thread's. Same private units,
`patch0358.pl` extended (v2, nothing shared written):
1. In the fault print: the globals `[0xb064018]` (the override's arena pointer) and `[0xb064020]` (the special index);
   the pool object from `[0x8e51418]` with +0x20, +0x88, +0x8c, +0x94 and +0x98 (the spin's count and capacity); and the
   three tables' +0x290 / +0x294 (capacity, count). If count ≥ capacity with the override's arena null, F448's path is
   confirmed as the pool-full case; if the pool is not full, the main thread took the callback for another reason and
   the flags at +0x8c say which.
2. A journal line per guest thread-local block creation (host id, guest name, run time), so the main thread's block
   and its first `fs:` access are dated against the title's registration code — cheap, a few dozen lines per start.
3. A per-second sample of the pool's +0x94 / +0x98 (and the tables' counts) in the host's flip path, journaled, to see
   whether the fight drives the count towards the capacity over seconds (a host timing) or it jumps at the crash frame
   (a title race). The sample reads guest memory from the host's own thread, no lock: a read of two dwords.
No fix is proposed yet: with F447 the host's TLS is cleared and the lever, if any, is in frame retirement timing,
which v2's samples will show or rule out. Build and the maintainer's test wait for the top session's word; box runs only
without a `MAINTAINER PLAYING` line in the lock, RT on.

## Trap v2 and v3 (12:35–): the job system read right, the sampler's cost

The lock was free from 12:34 (the maintainer done, the top session's word). Everything below is private under
`~/bc5-work/exp0358/` (the shared tree, builds and archive only read); the previous binaries are kept beside the new
one (`kyty_emulator.86ebf2bd`, `.c4a1f713`).

- **Trap v2 (build c4a1f713, `raw/patch0358v2.pl`, `build0358v2.sh/.py`, three units: pthread.cpp, runtimeLinker.cpp,
  bc5LleAgc.cpp).** Its smoke run (`repro0358.sh`, the Continue route from the private copy of the live saves, RT on,
  200 s, 12:38, `raw-v2/` on the box): pass, 7007 flips over 198.6 s (35.3 flips/s; GPU busy 18.08 ms, host prepare
  2.03 ms, 28.3 ms between flips, like 0358 R1's 37.2 flips/s), no crash, no kernel line, live saves unchanged. The
  TLS block journal works: "MainThread" host id 5 at t 0.000 s, the 15 workers at 0.084–0.094 s, IO and render
  threads from 0.213 s, 62 blocks in all. The per-second sampler costs 20–31 µs a sample (max 45 µs; nine reads
  through `process_vm_readv`), i.e. nothing against a 28 ms frame; outside the sampled frame it is one `timing_now()`
  and a compare per flip. But its pool reading was wrong: image+0x8e51418 is not a pointer (the samples show a
  constant 7f05cf4daac2d682 there, "unreadable"; no instruction references that address — F448's "pool object at
  0x8e51418" came from a misread register dump). What the sampler did read right: the special index 5, the override
  arena 0 outside the override, and the three entries' live counts 21–47, 0–3, 11–84 of 512.
- **F449 — the job system, read from the code (the handle decode at +0x3cca900, the owner's pick at +0x3cca600, the
  init at +0x3cc9117–+0x3cc9223).** A job handle is (entry k = bits 0–1, index = bits 2–30, generation = bits
  32–63) into three entries at image+0xb0636d0 + k·0x2f0 (+0x288 the objects array, 0xc0 bytes each; +0x290
  capacity; +0x294 live; +0x2a0 the pending-handle list; +0x2ac pending count; +0x2e0 generation). A job object:
  +0x20 active, +0x80 the block function, +0x88 class bits, +0x8c flags, +0x90 started, +0x94 done, +0x98 total; the
  spin of F448 waits for done ≥ total with nothing active. The init takes the CPU count from an import (+0x5f20280;
  7 here, as on the console: N = min(max(cpus, 7) − 2, 8) = 5 workers per entry, "Job Lo/Hi/Bk 0–4") and derives
  the masks: workers = bits 0–4 (image+0xb06402c), the special index N = 5 (+0xb064020), the owner mask 2 << N = bit 6
  (+0xb064038), "any thread" = workers | bit 5 | bit 6 (+0xb064040). Every thread gets a lazy id at tcb−0x90 (a
  counter at image+0x9b75c38); image+0x9b75c3c holds the id of the thread that last called the setter
  (+0x3984e8d, +0x39dd210, +0x39dd277): the **owner**. When a thread waits on a job (+0x3cca900): a non-owner spins;
  the owner "helps" (+0x3ccb180 → +0x3cca600): it walks the entries' pending lists, takes a job with started <
  total whose class intersects the owner mask, allocates its 1 MiB block from the owner arena image+0xb09bf10 (not
  from a per-thread one), and runs the job's block function on itself. The override window (+0x3ccadc9–+0x3ccae5b)
  is the other inline path: a stack arena in image+0xb064018, the index set to N, one block run, then arena 0 and
  index −1 — the −1 is by design: the main thread is never a registered worker (F447).
  **The crash job** is queued at +0x4663043 (function +0x4661e50, class = image+0xb064040 = any thread, so the owner
  may take it) and, inside, looks its per-thread arena up itself (+0x466212d–+0x4662171: index == N → the override
  arena; entry −1 → **null**; else the entry's slot) — on an unregistered owner outside the override that is null,
  and +0x3d7eca0 dereferences it. So the fault is the owner (main) thread helping with a job that needs a worker's
  arena. The title's code is the same on the console; what differs is how often the owner has to help at frame end
  (the workers' throughput) and what is pending when it does — which is what trap v3 measures.
- **Trap v3 (`raw/patch0358v3.pl`, `build0358v3.sh/.py`; v2's journal kept).** At the fault: the per-thread lines gain
  the thread's job id and an "(owner)" mark; then the job system's globals (workers, special, masks, owner id, ids
  issued, override arena) and, per entry, live/capacity, generation, pending with owner-class / runnable / null / bad
  counts, and every pending job decoded (active, started, done, total, class, flags, function; the crash job's
  function marked). The sampler, once a second at the flip: per entry live, pending, owner-class pending, runnable,
  bad; the owner id and override arena; the cost.
  **Build 1691b436 (12:59), smoke run 13:00 (as v2's: Continue route, private saves copy, RT on, 200 s, `raw-v3/`):**
  pass, 7470 flips over 198.6 s (37.6 flips/s; GPU busy 18.16 ms, host prepare 1.95 ms, 26.6 ms between flips), no
  crash, no kernel line, live saves unchanged. The sampler's cost: median 86 µs, p90 105 µs, max 217 µs, once a
  second (12 reads plus one per live job, 14–84 jobs an entry) — at most 0.3 % of one frame per second, nothing the
  fight's 15 flips/s would feel; between samples the per-flip cost is a `timing_now()` and a compare. What the
  samples say on the route: "pending" ≈ "live" (the list at +0x2a0 holds every live job of the entry, not a backlog;
  21→47, 0→3, 11→84 of 512 over the load), nearly all of them owner-class (class = any thread), and runnable
  (started < total) 0 at every flip — at the flip no job has unstarted blocks, so the decisive print is the fault
  print's list, not the sampler. The override arena stayed 0 at every flip; the owner id is 1 (MainThread's).
  The v2 smoke's root `dmesg -w` stream (`raw-v2/smoke-kernel-stream.txt`) could not be ended without sudo and kept
  writing through the v3 run (no amdgpu line in either).

**The shortcut (13:04).** "BC5 emulator (test 0358)" now runs the trap v3 build 1691b436 (md5-checked against
`binary.md5` and the shortcut script's `WANT_BIN`); the launcher (abfaab76, the 4-line diff: a log and a pad record
per start in `~/bc5-work/exp0358/play/`) is unchanged, RT on from the shared input.cfg; the desktop file's Comment says
v3. The previous builds are kept beside it (`kyty_emulator.86ebf2bd`, `.c4a1f713`). Nothing shared written, the game not
started, the 0356 shortcut untouched.

## Trap v3 fired (13:55): the owner helps with a job no worker had taken

The maintainer's play on the test 0358 shortcut, 13:53:35 → crash 13:55:18 (t ≈ 103 s, exit 65, the same site; log
`~/bc5-work/exp0358/play/play-20261028-135335.log`, the pad record beside it, the journal of the capture
`~/bc5-data/captures/play-20261028-1353/gc/direct.log`). The lock was empty afterwards (the maintainer done).

- **F450 — the owner thread, helping, took the first unstarted Hi job, a crash-type job no idle worker had taken.**
  The faulting thread is MainThread (host id 5), job id 1 = the owner id. The job system at the fault: workers 5,
  special 5, owner mask 0x40, override arena 0, generation 17024 in every entry; entry 0 (Bk) live 4, entry 1 (Lo)
  live 29, entry 2 (Hi) live 31 of 512. The crash job's function (+0x4661e50) has four instances in the Hi entry
  (jobs 22–25, class 0x7f = any thread): 22–24 finished (started 1, done 1, total 1), job 25 **active, started 1,
  done 0** — the one the owner was running (frame [1] +0x3cca882 is the return from its block function). No other
  Hi job was active and none had unstarted blocks (every other Hi job: started ≥ total): the five Hi workers were
  **idle** when the owner reached its wait and helped. The only runnable job anywhere was entry 0 job 3 (fn
  +0x3b05a50, a background job of 1007 blocks, started 815, done 810, 5 blocks in flight on the Bk workers): not
  the cause, the owner scans the Hi entry only (the waited job's flags 0x9, bit 0 → entries 2..2). The [3] site
  +0x4920df2 queues a 1–2 block Hi job of its own (`call 0x3cca270(&desc, 1)`, fn +0x4920f30: entry 2 jobs 6 and
  30, 3/2/2) and waits on it at once (`call 0x3cca900`); the help loop walks the Hi list from index 0 and takes the
  first job with started < total: job 25, queued earlier by +0x4663043, ahead of the owner's own job 30.
  "started" is chunks claimed (`lock xadd [job+0x90]` in the run method at +0x3ccc53b/+0x3ccc566, by chunk size),
  so it may exceed total (entry 1 job 7: 3136/3026/3026 is 110 over-claims, harmless); "done" is `lock xadd
  [job+0x94]` at +0x3ccc58b; started < total is what "a block left to take" means.
  So the race is: a crash-type job sits in the Hi list unstarted; the owner reaches a wait before any Hi worker has
  taken it. On the console the same code runs with the Hi workers on their own cores; here they were idle yet
  absent. Which of the two — asleep with the wake-up still in flight, or runnable without a core — the print cannot
  say; that is trap v4's question.
- **F451 — the host's part of the wake-up, read from the code (no polling, priorities already mapped).** The
  workers wait on one semaphore per entry (`[entry+0x298]`, created at +0x3cc95d0 with attr 1 (fifo), max N<<10;
  the worker loop +0x3ccc0b0 waits `sema, need 1, timeout 8000 µs` at +0x3ccc0c0 through the stub +0x5f202a0; a
  push signals it through +0x5f20260 at +0x3ccbb66 / +0x3ccbe09 / +0x3ccbe36, the owner's push signalling 1, a
  worker's up to min(N, total)) — the import names are inferred from the arguments and the host's semaphore
  signature; `raw/selfimports.py` was written to read them from the SELF's JUMP_SLOT relocations but the PS5 SELF
  keeps its dynamic data in segment types 0x6fffff00/01 that KytyPlus's loader names differently (TODO(verify)
  the names there). The host (`kernel/semaphore.cpp`): Signal adds the count, marks the first waiters whose need
  fits as ready, and broadcasts the condvar; Wait blocks in `std::condition_variable::wait_for` for the remaining
  timeout (`common/threads.cpp` CondVar::WaitFor), with `SIGNAL_APC_POLL_MICROS` = 10 ms only for infinite waits —
  no polling, a futex wake. Thread priorities (`Bc5ApplyGuestPriority`, exp 0180's mapping): guest ≤ 299 → nice
  −15 (the title's audio threads), ≥ 733 → +5 (its Lo/Bk workers at 700–750), the rest 0 — so the main thread
  (300), the render thread (300) and the Hi workers (500) share nice 0 with the host's own threads. The sampler of
  v3 ran (97 lines, 42–144 µs a sample; its lines are in the journal, not the play log): over the fight (t 92–100
  s) the Hi entry's live jobs rose 10 → 96, runnable 0 at every flip, so the backlog is not visible at flips; at
  t 100.7 s the frame took 104.6 ms with the game thread 66.8 ms inside the host (sync 28.6).

**Design: trap v4 (the wake-up, measured).** Same private units plus `kernel/semaphore.cpp`, applied after v1 and
v3:
1. A ring of the last 512 semaphore events (steady-clock µs, semaphore pointer and name, kind: signal/count,
   wait-begin, wait-ok with the signal→return latency, wait-timeout, thread host id), filled in KernelSignalSema and
   KernelSemaPrivate::Wait (the waiter records the signal's time when marked ready). Printed at the fault, newest
   64 first, so the last pushes to the Hi semaphore and the Hi workers' last waits stand next to the crash.
2. At the fault, for every guest thread: its `/proc/self/task/<tid>/stat` state letter (R running or runnable, S
   sleeping, D), utime+stime, and `/proc/self/task/<tid>/status` voluntary / nonvoluntary context switches; plus the
   host-side flag "inside KernelWaitSema on <sema>" set by Wait. Idle Hi workers in S inside the Hi semaphore's
   wait with the push's signal older than their wake would mean the wake-up itself is slow; in R would mean no
   core; not in the wait at all would mean they were busy elsewhere (and the print says where: their last events).
3. The sampler stays; it adds the five Hi workers' CPU seconds once a second (a `/proc` read each, ~15 µs apiece).
Cost: the ring is a lock-free index and a 32-byte store per event (the job system signals a few hundred times a
second), nothing the fight would feel.

**Fix candidates, to be chosen on v4's answer (none built; the title's code stays untouched):**
- (a) *Runnable without a core* → the host's own threads yield first: the pollers and completion threads of the
  direct path (soft CP polls, bc5-flipdone, bc5-labelwatch, the ring thread) at nice +5 (`setpriority` on the
  thread id needs no root for positive values), the Hi workers kept at 0 — a scheduling change the console does
  not need because the title has its cores alone. Measured by v4's R-state counts before and after.
- (b) *Asleep with the wake-up in flight* → `KernelWaitSema` spins on the count for a bounded ~20 µs before
  blocking (an adaptive wait, as glibc's mutexes do): a worker that is signalled within that window never sleeps,
  so the owner's help loop finds the job already started. Costs ~20 µs of CPU per wait that does block; the
  console's kernel does not do this, but the console's workers do not share cores with a host either.
- (c) If v4 shows the Hi workers were busy with other jobs for milliseconds (no idle worker in reach): the host's
  throughput at the fight is the cause (the 66.8 ms inside the host per frame) and the fix is the frame's host
  cost, not the job system — back to the profile's "sync 28.6 ms".
- (d) Last resort, a loader game patch (`loader/gamePatch.cpp` exists): the arena lookup at +0x4662141 given the
  owner arena when the index is −1. It changes the title's code; proposed only if (a)–(c) do not close the race.

## Trap v4 with the fix candidate (14:19–14:25): build f8b849f0 on the shortcut, switch on

The top session's word (14:1x): trap v4 plus one fix candidate in the same build, behind a switch, the shortcut with
the switch on; the maintainer's fight reproduces the crash in five of five plays that reached it, so a clean pass
there is evidence.

- **The candidate chosen: the targeted semaphore wake (`BC5_0358_FIX=1`).** F451 pointed at the one host step the
  console does not have: `KernelSemaPrivate::Signal` marks the waiters it hands the count to as ready and then
  broadcasts the semaphore's single condition variable, so every waiter of that semaphore wakes — the five Hi
  workers all leave their futex wait, take the semaphore's mutex in turn, and the four not made ready go back to
  sleep; the one made ready can be the last through the convoy. The console's kernel wakes the thread it gave the
  count to and no other. Under the switch each waiting thread waits on its own condition variable (one per thread,
  `thread_local`; a thread waits on one semaphore at a time), `WakeWaiters`, `Cancel` and the destructor signal
  exactly the waiters they mark ready, and `Signal` no longer broadcasts; the semaphore's mutex, the fifo/priority
  order, the counts and `KernelDispatchPendingSignalForCurrentThread` are unchanged, and `CondVar::SignalThread`
  (the guest-signal delivery) still finds a waiter through `RegisterCondWaiter`, which every `WaitFor` does. With
  the switch off the semaphore behaves as before. Not chosen for this build: the helper threads at nice +5 (a
  scheduler change touching the GPU feed threads, for the "no core" answer if v4 gives it) and the bounded spin
  (it only helps a worker signalled within the spin window).
- **Trap v4 (`raw/patch0358v4.pl`, after v1 and v3; `build0358v4.sh/.py`, four units: pthread.cpp,
  runtimeLinker.cpp, bc5LleAgc.cpp, semaphore.cpp).** `kernel/semaphore.cpp`: a ring of the last 512 semaphore
  events (µs since start, kind: signal / wait-begin / wait-ok / wait-timeout / wait-immediate / wait-other, the
  semaphore's name, the thread's host id, the count, and for a satisfied wait the latency from the signal that made
  it ready to the waiter's return), and a per-thread "inside a wait on <name> since <µs>" table. The crash print
  adds, after v3's job lines, every guest thread's `/proc/self/task/<tid>/stat` state letter, CPU seconds and
  context switches (voluntary / involuntary) with its semaphore wait state, then the ring's newest 96 events. The
  sampler adds the five Hi workers' CPU seconds and state letters. Dry-run on local copies of the four units (v1 4,
  v3 8, v4 23 edits), built 14:19–14:20 (0 errors; the tree's 11 warnings), nothing shared written, the previous
  binaries kept (`kyty_emulator.86ebf2bd`, `.c4a1f713`, `.1691b436`).
- **F452 — the smoke run with the switch on passes at the route's rate.** `repro0358.sh`, the Continue route from
  the private copy of the live saves, RT on, 200 s, `BC5_0358_FIX=1` confirmed in the emulator's environment
  (`/proc/<pid>/environ`, binary f8b849f0): pass, 7340 flips over 198.9 s (36.9 flips/s; v3's run 37.6, v2's
  35.3), GPU busy 18.26 ms, host prepare 2.00 ms, 27.1 ms between flips, no crash, no kernel line, live saves
  unchanged (`raw-v4/` on the box). The sampler's Hi columns: the five Hi workers asleep (S) in 191 of 196
  samples, 1.8–1.9 CPU seconds each over 200 s on the route. The sampler's cost rose to a median 247 µs (p90 375 µs,
  max 3.1 ms once) because each worker costs two `/proc` reads a second; at 15 flips/s that is 0.4 % of one frame
  per second, and the one 3 ms outlier is the price of the state letters — to be trimmed (the `/status` read is not
  needed in the sampler) if his play shows frame hitches at the sample instants.
- **The shortcut (14:25).** "BC5 emulator (test 0358)" runs f8b849f0 (md5-checked) with the launcher
  `play-pkg-0358t.sh` 4089732d: the 5-line diff against the integrated 55531ab6 = the log line, a comment, the pad
  record line and `export BC5_0358_FIX=1` (`raw/mktest0358v4.pl`, `raw/shortcut0358.sh` with `MKTEST`, `DIFF_LINES`
  and `WANT_BIN`); RT on from the shared input.cfg; the desktop file's Comment names v4 and the switch. Nothing
  shared written, the game not started, the 0356 shortcut untouched.

**What his next play says.** No crash through the fight: the fix signal (the ring in a later crash print, or none,
still shows how the workers woke; a journal line per start is not yet printed — the ring is read only at a fault).
A crash: the print's `proc` lines answer asleep (S, in a wait on the Hi entry's semaphore, with the ring's last
signal to it older than the wait) versus no core (R), and the fix moves to candidate (a).
