# 0441 — the third title's second stall (frame 273), paused and dumped

**Question.** With exp 0439's chained-buffer fix the third title (PPSA26344) runs about 270 frames, presents black,
and then stops flipping with a healthy GPU. Paused inside that stall: what does the title wait for, which host
behaviour is missing, and do the presented surfaces hold a picture?

**Setup.**

- Box as in `CLAUDE.md`; kernel 7.3.3-ogc1.1.fc45, boot `d4d739c7`, display 1920x1080 (EDID read).
- Build: exp 0439's private normal build `e116505c780310f2b5fc0f9034819d32` (on patch `589ef163`), its launcher
  `play439.sh` (`0da1578e`) and settings file `run-log.env` (`d940d85b`), all as pinned private copies under
  `~/bc5-work/exp0441/kit-b/`. Per-run words, exp 0439's run A: the title's own module pack,
  `BC5_DIRECT_DCC_PRESENT=2`, `BC5_DIRECT_EAGER_GPU_WRITE=1`, `BC5_DIRECT_IB_CHAIN=1`, `BC5_DIRECT_IB_CHAIN_FLAT=1`,
  `BC5_0439_IMPORT_PIECES=1`, `BC5_0439_ACB_DEEP=1`, `BC5_0439_ACB_REFUSE=1`, `BC5_0439_XQ_COUNT=1`,
  `BC5_DIRECT_TIMEOUT_PROBE=1`, `BC5_0439_PIECE_DUMP=1`, `BC5_DIRECT_UMR_ON_TIMEOUT=1`, `BC5_0439_UMR_WAVES=1`;
  system software version unset.
- Tools: exp 0440's (`experiments/0440-third-title-memory-code/`: `memdump0440.py`, `ana0440.py`, `idx0440.py`,
  `ahead0440.py`, `chain0440.py`, and for this run `run0440b.sh`, `rings0440.py`, `surf0440.py`), plus
  `jobq0441.py` here. `run0440b.sh` takes the emulator's pid only from a process whose executable is the kit's own
  binary and only after its lock is held (LESSONS R71), and runs everything in one named unit with its own time
  limit (R73). Dry run with a stub binary: the chain reaches the exec with the words above.
- The run (ymd2, 2026-11-21 21:22:42–21:24:00, lock `exp0441`, unit `bc5-0441-ymd2`): paused 30 s after the
  emulator appeared; snapshot A, 5 s of running, snapshot B, then the memory dump with the size rule raised to
  4 GiB so that the whole 0x5000000000 view was included (the top session's yes for this one dump). 80 threads;
  stopped 38.5 s; 3.8 GB real. amdgpu timeout/reset lines 1 before and after, no kernel line, nothing left running,
  lock dropped (`logs/go-ymd2.txt`).
- Private, never in git: box `~/bc5-data/priv/yotei-memdump/ymd2/`. The 0x5000000000 view's file was deleted there
  after the surface statistics (2026-11-21 21:31); the four DCC key arrays and the small results are kept, and a
  copy of those is on the laptop under `Documents/bc5-private/yotei-memdump/ymd2-small/`.

**Result.**

1. *Thread table.* 35 guest threads, 45 host threads. Only `game-main` runs (499 of 500 ticks in the 5 s): in eboot+0xe244f0, seen
   in its timed delay at +0xe2459f and +0xe245b2, called from eboot+0xbda165 (the loop of eboot+0xbda129) ←
   eboot+0xec76d9 in the main-loop function eboot+0xec67c0 ← eboot+0xec6780 ← the entry. All 20 job workers sleep
   in a semaphore wait (from eboot+0xe249b9). ProxySetSync, Uds and Trophy sleep in event-queue waits; the other
   guest threads in condition waits or sleeps, as in exp 0440; the two audio workers use about a quarter of a core
   each. This is not the label wait of exp 0440: the frame-submit function is not on game-main's stack.
2. *What game-main waits for.* eboot+0xe244f0 waits for one job group: it walks the group's entries (state 2 =
   done), tries to take a job itself through eboot+0xe246a0 and delays when it gets none. Its caller walks a batch
   of 15 groups; each has 11 jobs with the function eboot+0x11c3b40 and the same argument, and no job of any group
   has started.
3. *Why nobody takes them.* The groups are not in the job system's queues: both queue lists are empty, so the
   take function returns nothing to game-main and to the workers alike. The groups hang on a gate, a counted latch
   at offset 0x2cb0 of the ProxySet object (eboot+0x6aab050): eboot+0x11c3a42 creates each group and attaches it
   there through eboot+0xe25070. In the dump the gate is held (state 1, count 1) and its list holds the 15 groups.
   A signal that takes the count to zero (eboot+0xe24ee0) hands the groups to the workers.
4. *Who signals.* ProxySetSync, after each wake from its event queue "ProxySet Cull", when the label of its queue
   has reached the expected count (exp 0440, answer c). Its condition holds: expected 0x43, label 6 reads 0x43.
   It sleeps: it was not woken.
5. *What should have woken it.* The ring of the culling queue (2/2/2, id 0x33) holds 67 title buffers, all
   consumed. 66 are 790 dwords long and carry no interrupt. The 67th, the last, is of another kind (166 dwords):
   two waits, two dispatches, a RELEASE_MEM that writes the frame number 0x111 to 0x2000008120 with an interrupt
   (interrupt select 2, context id 0x111), then the write of label 6. Both writes are in memory, so the GPU ran
   the buffer to its end. The run's log has the registration of the title's graphics event with ident 0x52
   ("EVFILT_GRAPHICS ident 0x52 registered") and no return of the "ProxySet Cull" event queue at all (exp 0439's
   build logs every event-queue return; only two other queues appear).
6. *Other state, for the record.* Frame counter 0x111; label 0 = 0x111; labels 1, 2, 4, 8, 0x2000008220,
   0x20000081a0, 0x2000008000 = 0x110; 0x20000081c0 = 0x10f (the asynchronous queue writes N and N+1 of its own
   count, as in frame 1). Every registered queue's ring is fully consumed (ids 0x1, 0x11, 0x19, 0x29, 0x33: the
   read pointer equals the end of what was written; the meaning of that word was confirmed by exp 0439 from the
   host's consumer). The last executed frame's command buffer is a chain of 68 segments, 10,022 dwords, with 39
   draws and 194 dispatches; by the policy table every opcode passes or is the rewritten RELEASE_MEM; its 10
   cross-queue waits are all met in the dump. The next frame's chain exists only as a head and one segment
   (244 dwords), not submitted.
7. *The black picture.* Both display surfaces (indices 2 and 3, 3840x2160) are all zero bytes. Their DCC key
   arrays, the registered metadata and the draw's own DCC base alike, hold only 0x40 (94 %) and 0x00 (6 %); by Mesa
   `0866ae7085c1` `src/amd/common/ac_descriptors.h` those are clear codes (exp 0439 read the lines). So the frames
   are cleared black: nothing visible has been drawn into the display buffers yet. No detiling was needed. What the
   last draw samples was not read.

**Verdict.** The stall has one named cause: an end-of-pipe interrupt carried by a RELEASE_MEM in a compute queue's
buffer is not raised as the graphics event the title registered for that queue (ident 0x52 for queue id 0x33; the
ident rule is exp 0439's, from a public source). The packet's memory write runs, the event never comes, the gate
keeps its one count, and 165 jobs and the main thread wait for it. It is the first buffer of the run with an
interrupt on a compute queue. Proposed fix, behind a switch: raise the queue's event when the job that holds such
a packet has completed, with the packet's context id as the event's data, in the place and order of the graphics
queue's end-of-pipe events; to check in the host is why it did not fire here (the buffer begins with two
cross-queue waits and may be split; it ran on the compute-ring path). Not built or tested here. The black frames
are the title's own cleared start-up frames, not a present fault, as far as this dump shows.
