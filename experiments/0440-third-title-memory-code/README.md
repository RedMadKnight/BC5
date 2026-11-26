# 0440 — the third title at its stall: threads, all code in memory, what it waits for

**Question.** The third title (TITLE3) shows one flip at about 1.4 s and stalls (exp 0439, problem 3). With
the process paused at the stall, its threads dumped and every title module in memory disassembled: what is the
title waiting for, and which piece of host behaviour is missing?

**Setup.**

- Box: the BC-250 as in `CLAUDE.md`; kernel 7.3.3-ogc1.1.fc45, Mesa 26.2.6 (`mesa-vulkan-drivers-26.2.6-2.fc45`),
  libdrm 2.4.134-2.fc45; boot `c05993c0`. Backend archive `d6638808` (main `f1dd106f`).
- Build and settings of exp 0439, used read-only through private copies under `~/bc5-work/exp0440/`: its private
  normal build `a29080a6` (`k439/normal/kyty_emulator`), its launcher `play439.sh` (`cdfbd363`), its settings file
  `run-log.env` (`d940d85b`), and the per-run words `BC5_SYSMODULES_PACK_DIR=<title folder>/fakelib`,
  `BC5_DIRECT_DCC_PRESENT=2`, `BC5_DIRECT_EAGER_GPU_WRITE=1`. The title runs with its own libSceAgc,
  libSceAgcDriver and libScePsml.
- Scripts (this directory; none holds title data):
  - `memdump0440.py`: SIGSTOP; per thread the name, CPU ticks, context switches, registers (PTRACE_SEIZE on the
    stopped thread, no emulator build) and 64 KiB of stack; SIGCONT for 5 s; SIGSTOP; the same again; then the maps
    and the memory of every anonymous, memfd or shm mapping with x, and every other one up to 1 GiB, as sparse
    files; fsync; SIGCONT. The emulator keeps guest memory in two shared memfds, so those mappings are read from
    the memfd's allocated extents (SEEK_DATA): a read of an untouched page through `/proc/<pid>/mem` would allocate
    it, and pages written only by the GPU are found this way too. Everything else is read only where the page
    tables hold a page. Host files, `/dev/*` and the 3.4 GB view at 0x5000000000 are not dumped.
  - `standin0440.py`: a stand-in process and the check of its dump (threads named, spinner and sleeper told apart,
    a private rwx mapping, a shared memfd mapping written through an alias only, a big mapping skipped with its
    extra range dumped, the memfd's block count equal before and after): PASS on the box, from the host.
  - `run0440.sh`: `prep`, `dry` (the chain to the emulator's exec with a stub in the binary's place, LESSONS R66:
    the stub got the title folder, the title's own module pack and both words), `go` (one `systemd-run --user`
    unit, R65: lock, start bounded by timeout(1) inside the container, R68, 12 s wait, dumper, TERM, collect,
    leftover and dead-mount check, R70, unlock). `klog0440.sh`: the kernel stream, ends when the lock line is gone.
  - `ana0440.py` (thread table, frame-pointer walk, memory reads, PM4 walk that follows chains, search) and
    `idx0440.py` (segments as flat files, `objdump -D -b binary -M intel` of the executable ones, indexes of
    calls, rip-relative references, function starts, import slots with what the loader put there, strings, code
    pointers in data).
- Private output, never in git: box `~/bc5-data/priv/t3-memdump/ymd1/` (mode 700; the dump 156 MiB real,
  listings 227 MiB, indexes 34 MiB), laptop `Documents/bc5-private/t3-memdump/` (one archive). Export names for
  the three Agc modules come from the reimpl-agc-psml session's private tables (offset, size, NID, name).

**Result.**

1. *The run (ymd1, 2026-11-21 16:14:01–16:14:37, lock `exp0440`).* The emulator appeared after 1 s; 12 s later
   the dumper ran: snapshot A (78 threads, stopped 0.06 s), 5 s of running, snapshot B and the memory dump
   (863 mappings: 347 dumped, 12 over the size limit, 351 host files, 153 special; stopped 15.7 s). The emulator
   ended on TERM with exit 0. amdgpu timeout/reset lines 11 before and after, no kernel line during the run, no
   emulator and no dead mount left, core limit 0. (`logs/go-ymd1.txt`; the kernel stream is empty.)
2. *What was covered by tooling and what was read.* Tooling covered everything: all five modules (eboot.bin
   24.6 MB of code, libc.prx, libSceAgc, libSceAgcDriver, libScePsml; 6,338,590 instructions, 53,302 function
   starts by heuristic, 1,313 import stubs), their data segments, the loader's two stub regions, the
   0x2000000000 view and the other small views. No module holds a `syscall` instruction: every kernel request
   goes through an import. Read by me: the frame-submit function's tail and its packet helper, the thread
   function of ProxySetSync, the ProxySet setup, the Driver's ioctl call sites and its one stubbed import, and the
   frame's whole command buffer as packets. The rest of the title's code was not read.
3. *(a) Thread table.* 35 guest threads, 43 host threads.
   - `game-main`: the only thread that runs (499 of 500 ticks in the 5 s, RIP and RSP equal in both snapshots):
     eboot+0xd62b02, a timed busy-wait inside the frame-submit function eboot+0xd5f110, called from eboot+0xbd8c4d
     (function 0xbd8bf0) ← 0xec77c3 (0xec67c0) ← 0xec6780 (0xec5570) ← the entry.
   - Blocked in a host wait with an unchanged RIP: `JobWorker1..10` and `JobWorkerLow1..10` in a semaphore wait
     called from eboot+0xe249b9; `ProxySetSync` (eboot+0x11be7de), `Uds` (0x12df902) and `Trophy` (0x1559749) in
     an event-queue wait; `FaWorkerIo1` (0xc37b0b), `CloseTextures` (0x12e0165), `AudioIn` (0x15a7a32),
     `MovieDecoder` (0xeb58fa), `Http` (0xdeff23), `Psn` (0x11ca633) in a condition wait; `snd_stream_pars` in a
     timed condition wait (0x33b220); `NCA::PumpThread` (0x345a2a) and `snd_stream_read` (0x33a16f) in a sleep.
   - `ScreamWorker1/2` (audio, condition wait from eboot+0x13e44cc) used 76 ticks each; ScreamWorker2 is the one
     thread whose registers differ between the snapshots. The blocked threads above wake about 100 times a second
     (the host's bounded waits) and use no CPU.
   - Host threads: all in a futex, sleep, poll or epoll wait.
4. *(b) game-main's spin.* At its end the frame-submit function hands the frame's buffers to
   `sceAgcDriverSubmitDcb`, and then, when a flag of the renderer object (offset 0x3274fc) is set, waits until
   label[idx] of the Agc label table (base read from eboot+0x459c9a8 = 0x2000000000, 32-byte entries) is greater
   than N. idx is the renderer's field 0xcc (0 here); N is the renderer's frame counter (field 0xd0) as it was
   before this frame (1 here; the field holds 2 now). Three more waits of the same form on other labels follow.
   The writer is a packet of this same frame: before `sceAgcDcbSetFlip` the function calls the title's helper
   eboot+0x16c43e0 with the label's address and N+1, and for these arguments the helper emits two EVENT_WRITEs, an
   ACQUIRE_MEM over all memory, an ACQUIRE_MEM over the label's 32 bytes and a WRITE_DATA (destination select 2,
   two dwords) of N+1 to the label. That WRITE_DATA is in memory at 0x20102344f4 with the value 2. Label 0 reads 0.
5. *The frame is one command buffer of 73 chained segments.* The buffer handed to the Driver is the head
   (0x2010214000, 103 dwords). Every segment ends in an INDIRECT_BUFFER whose size dword has bit 20, the chain
   bit, set, to the next one: 72 chained segments after the head, 9,346 dwords in all, all present in the dump,
   no nested call among them. The label-0 write is in the last segment (72, the buffer the renderer's command
   buffer object points to). After segment 3 the chain holds 114 draws and dispatches and 57 WAIT_REG_MEMs.
6. *What the host does with it.* `backend/src/direct.cpp`, `Device::submit_impl`: the buffer is depth 0; the
   targets of its INDIRECT_BUFFERs are collected with `if (pieces[k].depth >= 3) continue` and
   `pieces.size() < 64`, a chained segment counted as one more level; then every INDIRECT_BUFFER whose target was
   not collected is overwritten with NOPs ("an unmapped or over-deep target: never let the CP follow it"). So the
   GPU runs the head and three more segments, and the rest of the frame is dropped without a word in the log. The
   soft CP of the patch cuts the same way (`indirect_buffer()`: `depth >= 4` returns), and so does
   `policy.cpp` `refusal_in` (`depth < 3`).
   - The dump agrees: the end-of-pipe writes of segments 0 and 1 landed (0x2000008000, 0x2010271fe0,
     0x20000081a0 read 1); segment 10 writes 2 to 0x2000008100, which reads 1; the markers of segments 15 and
     later read 0. The host's replay of this buffer logs end-of-pipe writes from segments 0 and 1 only.
7. *(e) The two parked acbs' partner labels.* 0x2010449750 is written (1) by a RELEASE_MEM in segment 29 of the
   same chain, 0x20104aa630 by one in segment 34. Both are past the cut, so the two compute buffers of the first
   frame wait for packets the host dropped.
8. *(c) ProxySetSync.* Its thread function (eboot+0x11be780) waits on its event queue with no timeout. After the
   wait returns it compares the low 32 bits of label[field 0x15c of its object] with the expected count in field
   0x158. If the label has reached the count it signals the object at offset 0x2cb0 and waits again; if not, it
   busy-waits for the label. An injected event with both at their start values therefore passes the check, makes
   no kernel call and goes back to the wait: the thread is a completion notifier, not a producer.
9. *(d) Queue id 0x33.* eboot+0x11bdc00 creates the event queue "ProxySet Cull", registers the Driver's event on
   it (`sceAgcDriverAddEqEvent`) and starts ProxySetSync. The work for that queue is built and submitted by
   eboot+0x11be890: a marker, two waits, two dispatches, a RELEASE_MEM, then the title's submit wrapper
   eboot+0xb32ad0, which calls `sceAgcDriverSubmitAcb`. It has no direct caller; eboot+0x11c1970 takes its address
   (a job handed to the job system). The frame-submit function calls the same wrapper three times just before
   `sceAgcDriverSubmitDcb`. No worker has the builder on its stack, and the main thread has not left its first
   frame's submit, so the frame work that would queue it has not run. That it was never queued is an inference
   from this state and from exp 0439's ring reading, not a trace.
10. *(f) The Driver against the host.*
    - Kernel requests go through 40 host functions (open, ioctl, kevent, mmap, direct and flexible memory calls,
      process and SDK queries, three video-out calls among them: `SubmitEopFlip`, `GetBufferLabelAddress`, a bus
      query) and libc.
    - ioctl: 52 distinct request codes of group 0x81 are in its code. 18 of them appear in the patch by their code; the
      others are answered "with zeros" (return 0, output zeroed). Called in this run and answered so: 0xc0108139
      (6 times), 0xc0088133 (6), 0xc010813b, 0x80888123, 0x80048134, 0x80048126; one dipsw request (0x40048806)
      returns 0. At every one of those call sites the Driver tests only the return value for zero and copies the
      zeroed output; 0xc0088133's zero output is stored in a module flag and compared with zero. None of them
      explains the stall.
    - One Driver import is stubbed: NID `yu17wG8L5FI` (libkernel), called 6 times at start; the Driver uses the
      answer as a yes/no for a mapping flag and two sizes. The stub's answer selects the same way as the module's
      own fallback in the reimpl session's description (returns 0).
    - eboot has 44 stubbed imports; three were called (two NpSessionSignaling, one Http). The threads `Http` and
      `Psn` sit in plain condition waits, and nothing at the stop depends on them.
    - The flip packet of the last segment writes to `GetBufferLabelAddress`'s page, a host anonymous page that
      the direct path maps for the GPU (exp 0071), so it is not a missing piece.
11. *(g) The earliest missing link.* The platform runs a chained command buffer to its end, whatever the number
    of chained segments; the host follows three levels and drops the rest. The first frame's label write, its
    two partner-label writes, its flip packet's end-of-pipe write and all but the first of its draws are in the
    dropped part. Every waiter of problem 3 (game-main on label 0, the two acbs on their partner labels, the
    compute queues behind them) waits for those packets. No stubbed import, unhandled ioctl or missing event is
    needed to explain the stall.

**Proposed fix (not built here).** A rule, behind a switch (for example `BC5_DIRECT_IB_CHAIN`, on for a test
build): an INDIRECT_BUFFER with the chain bit replaces the rest of the current buffer, so it adds no nesting
level and has no length limit; a call (bit clear) returns and keeps today's limit. Source: AMD PAL `c5e8000`
`src/core/hw/gfxip/gfx9/chip/gfx9_plus_merged_f32_pfp_pm4_packets.h:2580`, already cited for the same rule in
`backend/include/bc5/acb_restore.hpp` (PORT-CHAIN, F760); Mesa `0866ae7085c1` chains its own buffers this way
(`src/amd/vulkan/winsys/amdgpu/radv_amdgpu_cs.c:439` and `:589`, `S_3F3_CHAIN(1) | S_3F3_VALID(1)`). Places that
need it: `Device::submit_impl` (a chain target keeps its parent's depth; the 64-piece cap must hold this frame's
73 segments and more), the soft CP's `indirect_buffer()`, `policy::refusal_in`, and every scan that looks for a
label's writer or for addresses to import (the frame has more than 20 pairs of a RELEASE_MEM that writes into
the payload of its own NOP and a WAIT_REG_MEM on that payload, so a wait's writer is often in an earlier segment
of the same chain). The simplest form follows the chain iteratively and lays the segments out one after
another.

**Verdict.** Passed: the pause-and-dump method works without an emulator build (15.7 s stopped, no side effect on
the box), and the stall has one named cause in host code, with the title's code, the dumped memory and the host's
own log agreeing. What the title does after the chain runs is not known: its first real frame (114 draws and
dispatches, 57 waits, two waits with the engine bit on labels of other queues) has never executed on the host.
