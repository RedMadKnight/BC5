# 0439 — the third title: install, first runs, fixes

**Status:** claimed 2026-11-21; scripts written and tested on a laptop stand-in; no box step yet. The GO comes after two
box slots on the second title (the reimpl-agc-psml rerun and bake, then exp 0438's diagnosis); no md5 of a NAS file
during their runs (page cache against RT-on memory).

**Question.** What stops the third title (PPSA26344, v01.512, the maintainer's own package on his NAS) on BC5 today,
and which fixes, simplest first, make it playable? Before that, the second title's install (PPSA03671) is removed to
free its 196.7 GB, with every save and per-title setting kept.

**Setup.**

- Box: the BC-250 as in `CLAUDE.md`; shared builds patch `9889b06a` (normal `b1b57df9`, lean `d3485ed4`, archive
  `d6638808`) unless the reimpl bake has replaced them by then (re-read and record the md5s at each run).
- Scripts (copied to `~/bc5-work/exp0439/` on the box):
  - `e0439.sh`: `lock`/`unlock` (one BOX-LOCK line `exp0439 ...`, taken only when the lock is empty and no emulator
    runs); `check2` (read-only: the NAS `game.pkg`'s title id and size, the install record, files newer than the record,
    a dry uninstall, free space, every save location, the second title's shortcut, the mount cache); `md5` (in a
    `systemd-run --user` unit at idle I/O, MATCH/MISMATCH line); `inventory` (md5 of every save file and kept setting);
    `backup` (tar of the live saves and settings into `~/bc5-data/saves/`); `uninstall2` (gated on the md5 MATCH, the
    title id, the inventory, the backup, no emulator and our lock; `bc5-mount uninstall`; the dead shortcut to
    `~/bc5-work/trash-20261121/pulpit`, the mount cache there too if over 1 GiB; the inventory again and a diff);
    `check3`, `install3` (gated on the md5 MATCH, the title id and free space ≥ unpacked size + 20 GiB;
    `bc5-mount install --verify` in a user unit), `after3`.
  - `run0439.sh`: `dry` (the chain `play-any.sh <folder>` → `play-astro.sh` with `BC5_GAME_DIR`, the binary it reaches
    and its md5, LESSONS R66), `run` (a `systemd-run --user` unit with `RuntimeMaxSec`, `ulimit -c 0`, RT on as the
    default, refused if `bc5-run.env` turns it off; the normal build with `PLAY_CAPTURE=1`), `collect`.
  - `klog0439.sh`: the kernel log streamed to the laptop, killed when its stdin closes (LESSONS R67).
- Kept, never moved or changed: `~/bc5-work/_SaveData-pkg-play`, `~/bc5-work/_SaveData/PPSA03671`, `~/bc5-data/saves/`
  (with the snapshot `PPSA03671-20261111-2100-memory-heavy`), `~/bc5-work/menu/titles/PPSA03671/`, `input.cfg`.
- No launcher, shortcut or shared build changes (the third title already goes through `play-astro.sh`'s generic
  path in `play-any.sh`).

**Stand-in test (laptop, 2026-11-21).** A fake home with saves, a game folder, two shortcuts, a NAS package and its
`.md5`, and stubs for `bc5-mount`, `systemd-run`, `pgrep` and `flock`: `check2`, `md5` (MATCH), `inventory before`,
`backup` (a missing save path is skipped and logged), `lock`, the tar check (the tar's file count against the inventory's files under the tarred paths: 3 = 3 goes on; with a save added after the tar, 3 against 4 stops and the folder stays), `uninstall2` (the folder removed, only the shortcut that
names `play-pkg.sh` moved to trash, the generic one kept, the saves equal before and after), `unlock`. `klog0439.sh`
with a stand-in `journalctl`: it ends when its stdin closes. `bash -n` on all three.

**Planned side check (exp 0438, through the top session, 2026-11-21).** Only once the title starts and reaches a scene:
lean runs with `RUN_EXTRA="MALLOC_TRIM_THRESHOLD_=268435456 MALLOC_MMAP_THRESHOLD_=33554432"` in the emulator's own
environment (no build) against a control without them. Read: MangoHud median/p95/p99 and flips/s, MemAvailable at about
150 s (the arm keeps up to 256 MiB per arena resident), `rpm -q glibc` once. `run0439.sh` takes the words through
`RUN_EXTRA` (each word checked as `NAME=value` with no shell characters; stand-in: the arm's words reach the env line,
the control's line has none, `X=1;rm` is refused).

**Result.**

1. *The second title removed (2026-11-21 09:11:56).* The NAS `game.pkg` md5 MATCH (PPSA03671, 101,814,213,551 bytes);
   the tar's 142 files equal the inventory's; `bc5-mount uninstall` freed 196,702,616,991 bytes in 321 entries; the save
   inventory (536 md5 lines) equal before and after; no second-title shortcut and no mount cache existed. Free on `/var`:
   272,036,065,280 bytes. `check2`'s and `uninstall2`'s `pipefail` stops after `head`/`du` were fixed in the script.
2. *The third title installed and verified (11:32:01).* PPSA26344, image `debug`, 95,402 files (95,383 in the tree and
   19 `sce_sys` files of the package), 197,764,242,507 bytes. Three `bc5-mount` bugs on the way, each fixed with a test
   (F873): the first install was OOM-killed at 10,286 files (anon-rss 8.0 GB, peak 12.9 G + 6.9 G swap: the decode
   cache was sized in blocks of the first block's size, `19f84a41`); the resumed install under `MemoryMax=4G` wrote all
   files but its `--verify` failed with no cause shown (kept files had no expected hash; main printed only the top
   context, `1332dbbf`); the next resume was refused for free space (every file counted, `91cbf0c3`). The last run
   (`install3d`, binary `1aa3866a`) hashed every file from the package and from disk: verification passed, record
   written, 47 min, memory peak 4 G. fakelib has libSceAgc, libSceAgcDriver, libScePsml. Free on `/var`: 84,171,689,984.
3. *The shared `bc5-mount` swapped to `1aa3866a` (11:32:50),* the top session's decision; `fa03feda` kept as
   `bc5-mount.pre0439`; `--version` 0.1.0, `inspect` of the package and a dry uninstall of the installed title read
   correctly.

4. *First run n1 (normal `b1b57df9`, RT on, boot `d1ac0537`, 11:36).* The title starts from its folder with its own
   module pack (`BC5_SYSMODULES_PACK_DIR=<folder>/fakelib` per run: without a mount the box's `play-astro.sh` takes
   ASTRO BOT's pack from `bc5-run.env`). Audio opens on the pad; three stubbed network imports are called (Http,
   NpSessionSignaling); no unresolved import stops it. At 2.6 s a compute job on bc5-ring WRITES (TCP, RW 1,
   PERMISSION_FAULTS 0x4, status 0x00641041) at 0x504c932000: the title's 3.4 GB direct view at 0x5000000000 has no
   name ("anon") and is imported by data, so its never-CPU-written chunk is the read-only zero cover of k1r (without k1r
   it would be unmapped: the same fault). comp_1.1.0 timed out, its reset succeeded; exit 86 (fault record
   `faults/20261121-113617`, private). The second title keeps its GPU targets in named heaps on the eager list.
5. *Fix 1 (n2, no build):* a private copy of `bc5-run.env` with `BC5_DIRECT_EAGER_NAMES=GpuGarlicMemory,GpuOnionMemory,anon`
   (through `BC5_RUN_ENV`; `play-astro.sh` re-exports the settings file after the run's own words). No GPU fault, the
   boot's reset lines 16 before and after. Next stop at ~6 s: the emulator exits 65 with "TextureCache: compressed
   video-out read requires clean native GPU contents" (KytyPlus `textureCache.cpp:1248`): the title registers DCC-compressed
   display buffers, which neither earlier title did.

6. *n3 (normal, as n1, `BC5_GUARD_DESC_TARGETS=2`, log only, 11:43):* the same fault from the same 833-dword acb
   (0x504c910000, comp_1.2.0 reset succeeded, record `faults/20261121-114357`). n1 had no ud434 or k1f line; dt412's
   walk (inline user data, the tables its pointers lead to, one level deeper) names 20 targets and none covers
   0x504c9xxxxx. The shader reaches the target deeper or computes it, so no submit-time scan predicts it.
7. *n4 (normal, anon-eager env + `PLAY_ARGS=--printf-direction Console`, KytyPlus's LOGF, 11:48):* the same exit 65.
   Direct maps by GPU mode: ReadWrite 4,110 MiB (0x5000000000 3412 MiB and 0x2000000000 618 MiB by a batch map with
   prot 0xf3, 0x200c00000 78 MiB, SceGnmDumpArea 2 MiB), Read ~127 MiB in 837 maps (prot 0xd3), NoAccess 631 MiB
   (0x1000000000 620 MiB, prot 0xc3). With anon eager, MemAvailable fell from 13.9 GB to 8.36 GB (1 s sampler); peak
   `mem_info_gtt_used` 836 MiB. Display buffers: 3840×2160, compressed, `dcc_control` 0x208 (design:
   `dcc-present-design.md`). Reset lines 21 before and after. `run0439.sh`'s emulator check became `pgrep -x`: another
   session's build named the binary in its arguments.

8. *Decisions of the top session (11-21, about 12:15).*
   - Problem 1: the candidate fix is the map-call rule, not a name list. A direct view the title mapped with GPU write
     (KytyPlus `memory.cpp` `PROT_GPU_WRITE` 0x20; TODO(verify) the bit's meaning against a public source, the
     evidence is n4's map log) is imported whole (`BC5_DIRECT_EAGER_GPU_WRITE=1`, tag mw439). The private anon-eager
     env stays as the fallback arm.
   - Its cost for this title: about 4.1 GB. On the console, direct memory is physical and committed at allocation.
     Backing a never-written chunk lazily for GPU writes would need recoverable GPU page faults for a GFX job. That
     gfx10 has none for GFX jobs (only KFD/SVM compute) is TODO(verify) against an amdgpu source; no kernel tree is on
     the box.
   - Check against other titles before it could become a default: ASTRO BOT, one logged run, comes after exp 0438's
     run. The second title is not checked (it is uninstalled).
   - DCC: design (a) accepted (`dcc-present-design.md`), behind `BC5_DIRECT_DCC_PRESENT` (1 log, 2 decompress). A
     step-1 run first shows whether the surface is still compressed at the flip. Then step 2 for 30 s with the fault
     record on.
9. *A separate lever, no change now: the reported resolution.* The title registers 3840×2160 display buffers, because
   that is what the emulator's video-out reports: KytyPlus's VideoOut answers the resolution query from its own
   configured output size (TODO(verify) the exact call and setting in `videoOut.cpp`). A 1920×1080 report would
   probably give a quarter of the render-target pixels and memory, and less GPU time per frame. Whether the title
   accepts 1080p, and what it does then, needs a run.
10. *Private build dc439 (kit `k439/`, CPU only, no lock line).*
    - Contents: the CB_COLOR catcher, the decompress IB (`dc0439.hpp`, registers and values from Mesa
      `0866ae7085c1`), the flip hook in `SubmitEopFlip`, the present-as-plain hook in `FlipQueue::Prepare`, the map
      rule.
    - Offline test (`test_dc0439.cpp` against the shared archive): PASS. The IB is 149 dwords. The backend's filter
      drops nothing and rewrites the two CLEAR_STATEs to cmd 0. The state stack pushes once, pops once and puts the
      title's registers back.
    - First build, without the map rule: normal `42f9b583`, lean `0af1259a`.
    - Private launcher `k439/play439.sh`: `play-astro.sh` with its two `EMU=` lines on `P439_BIN`. `run0439.sh`
      takes `RUN_PRIV=<binary>`.

11. *p1 (private normal `f3c18e68`, `BC5_DIRECT_EAGER_GPU_WRITE=1` + `BC5_DIRECT_DCC_PRESENT=1`, no anon env, 12:36).*
    - The map rule alone removes problem 1's fault: no GPU fault, no fault record, reset lines 21 before and after.
    - Six views went eager by prot 0x20, 4,110 MiB in all: 0x5000000000 4,032 MiB, 0x2000000000 620 MiB, three
      SceAgcDriver/SceAgcRegShadow views of about 2.2 MiB, and 0x200c00000 78 MiB.
    - MemAvailable minimum 9.13 GB, against 8.36 GB with the anon stopgap.
    - The same DCC stop (exit 65). At the first flip (1.5 s, index 2) no GFX job ended with an MRT on the surface.
    - Two earlier p1 starts did not reach the emulator: `play439.sh` had no exec bit, and then the box's display was
      disconnected (DP-1 and DP-2), so SDL had no display (exit 65, no GPU work).
12. *ASTRO BOT a1 (shared normal `b1b57df9`, map log, 12:41, reset lines 21 before and after).*
    - Seven direct views are GPU ReadWrite, 10,390 MiB in all: 0x10ca000000 4,608 MiB, 0x1000000000
      "BackgroundTaskWorker" 3,232 MiB, 0x500000000 2,172 MiB, 0x400000000 184 MiB, "Sample" 128 MiB, 64 MiB and
      SceGnmDumpArea 2 MiB. Today none of them is eager.
    - The map rule as a global default would pin about 10 GB on ASTRO BOT, so it stays per title or needs a bound.
      The second title is not checked.
    - The run showed that `RuntimeMaxSec` does not bound a run: the emulator lives in the container's cgroup. It was
      stopped by TERM, with its bc5-mount. `run0439.sh` now bounds runs with timeout(1) inside the container.
13. *p1b (per-draw catcher, `875c2fac`, 12:44): the first flip is a buffer nothing wrote.*
    - No draw targets it, and its address is in no GFX or compute job.
    - The surface's first 4 MiB are zero, and all 131,072 DCC keys are 0x00. Mesa `0866ae7085c1`
      `src/amd/common/ac_descriptors.h:29-30`: 0x00 is DCC_CLEAR_0000 ("all bits are 0"), 0xFF is DCC_UNCOMPRESSED.
    - The presenter refused it only for its compressed tag.
14. *Mode 2 with the key classification (`a213c7f0`, p2, 30 s, 13:02, reset lines 21 before and after, no fault).*
    - At each flip the keys are read: all 0xFF, or all 0x00 with an all-zero surface, means plain without a pass.
      The present takes the flag of the buffer's last-flipped index; indices 0/2/4 and 1/3/5 share a buffer.
    - The first flip (1.48 s) was presented as plain, black, with no GPU pass. The title then ran to the bound of
      30 s with no stop.
    - No second flip came. Problem 3, a stall: two compute queues (1/2, 1/3) keep buffers deferred on labels never
      written (0x2010449750, 0x20104aa630; WAIT_REG_MEM function 3, reference 1). CPU waits on 0x20104cd1xx time out
      every 2 s. Job counts barely move from 11.5 s on (gfx 10, comp0 69, comp1 1 → 2).
    - No decompress pass has run yet: no non-blank flip came.

15. *Problem 3, the stall after the first flip (a0-a14, 11-21 13:05-13:49, all resets unchanged).*
    - Not the rings and not r438: a1 (`BC5_DIRECT_ACB_RINGS=0`) and a2 (`BC5_0438_EARLYREG=0`) stall exactly as a0.
    - game-main spins in guest code until the qword at 0x2000000000 exceeds 1. reimpl-agc-psml's description: that is
      label 0 of Agc's semaphore-label table, base + index * 32. The index variable is not assigned after 0.3 s.
    - Nothing writes label 0. Not the CPU: hardware watchpoints. Not any packet we receive: a writer scan three IB
      levels deep, MEM_SEMAPHORE included (`policy::memory_operands` has no 0x39 case, which a9 covered).
    - Not any of the 56 compute queues' rings: their doorbells equal their last IB, and their tails write labels 1, 2,
      4, 6, 7 and 9.
    - The unhandled ioctls' payloads (system-area registrations, per-submit suspend checks) register no label.
16. *SubmitEopFlip's fifth argument (t1, 15:03).*
    - It is an output: AnyPS5 `core/libs/prx/libSceVideoOut/src/VideoOutDriver.cpp` (GPL-2.0, 8b403579) writes a
      flip token there, and reimpl's SetFlip description agrees.
    - We never wrote it. Writing a token (`BC5_0439_EOP_TOKEN=1`, 0x04000000+n) changes nothing: 1 flip, label 0
      = 0.
17. *GPU events (e1-e3, r1, 15:09-15:25).*
    - The title registers one EVFILT_GRAPHICS event, ident 0x52 (kevent filter -14); our `fire_eop` fires only
      0x40, 0 and the compute idents. The meaning of ident 0x52 is unknown.
    - Its dcbs carry 26 RELEASE_MEM interrupts (INT_SEL 4, INT_CTXID 0x08100001): Agc's own context-roll
      notifications (reimpl).
    - The soft CP replays all 14 dcbs (r1: posted, started, ended). Each of those interrupts sits under a COND_EXEC on
      Agc's sync label 0xfe0040060, which reads {0, 1}, so the soft CP skips them (`bc5LleAgc.cpp` ~1460), as the
      console does.
    - No other interrupt packet comes in 30 s.
    - Host defect found on the way, for every title: `release_mem` reads INT_SEL as 2 bits (`(data_cntl >> 24) & 3`),
      so an unguarded INT_SEL 4 interrupt would be lost. TODO(verify) the field's width and value 4 against AMD's
      PAL PM4 headers; Mesa `0866ae7085c1` `sid.h` defines only `EOP_INT_SEL(x) << 24` with 0 and 3.
    - The earlier reading "the ring -1 path never delivers interrupts" was wrong: the guard skip is correct
      behaviour.
18. *Where problem 3 stands.* After 1.365 s the title submits no more graphics work, and the work item that would
    own label 0 is never created. Open: what ident 0x52 is (a flip- or vblank-type system event?), and the producer
    path in the title's own code. Private build `c06dffe7` (normal), generator rebased onto patch `0fede35d`.
19. *Launchers and cleanup (on this branch).*
    - `tools/scripts/launchers/play-astro.sh` and `play-pkg.sh`: a mount counts only when its `sce_sys/param.json`
      reads. A dead FUSE endpoint is unmounted (lazily if needed), and a failure is named. Stand-in
      `test-mount-live.sh`: PASS.
    - `run0439.sh collect` unmounts dead mounts in the container and on the host, and bounds runs with timeout(1).
    - The installed launchers are unchanged.

20. *The 0x52 wake test (f52 / kv439, 11-21 15:38-16:04; resets unchanged in mine).*
    - The survey (`survey-0439-fixes.md` Q4) gives an AGC-era rule:
      - KytyPS5 `graphicsRun.cpp:978-984`, `renderContext.cpp:206-221`, `graphicsRun.h:51` (GPL-2.0, 39936ffa);
        AnyPS5 `libSceAgcDriver/Eq/src/Event.cpp` (GPL-2.0, 19a1993e); UNVERIFIED on hardware.
      - The ident is the queue's (compute: 0x20 + queue id - 1). The event is raised by a RELEASE_MEM with an
        interrupt on that queue, with data = (INT_CTXID << 16) | ident.
      - So 0x52 belongs to queue 0x33 (2/2/2), which got only its two boot IBs.
    - Fired by hand (`BC5_0439_FIRE52`): once, at every flip, at a compute completion, and at 60 Hz.
      - ProxySetSync wakes each time (`KernelWaitEqueue` returns one event ident 0x52, filter -14, fflags 0x1, the
        data we give).
      - It then reads a semaphore label (the table at 0x2000000000, index and target from its own object), finds it
        not past its target and waits again.
      - At 60 Hz it consumes 118 events, and the title then never makes its first flip.
    - The event line is closed. 0x52 is a re-check signal; the real condition is a label nobody writes.
    - Host facts for every AGC title, not fixed here: `fire_eop` uses the PS4 idents (0x40, 0, compute A/B) instead
      of per-queue idents, and fills the data differently. `release_mem` reads INT_SEL as 2 bits.
21. *The waits, as one problem.*
    - game-main waits on label 0 > 1, and ProxySetSync on a label in the same table.
    - Queue 1/2's acb waits on 0x2010449750 and 0x20104cd1e0/1c0/180/140/100. Queue 1/3's acb waits on 0x20104aa630.
      Each is a ping-pong with a partner buffer that releases the labels it waits on.
    - No buffer on any ring or in any job writes them, and no CPU code writes label 0. The partner work and the
      label-0 writer were never created.
    - The question is with reimpl-agc-psml: which Agc/Driver export or title pattern produces that work.

22. *Queue audit (q26, 16:07).*
    - At 3 s and 10 s, every queue's host-consumed pointer equals its doorbell. The exceptions are 1/2/0 and 1/3/0
      (12 against 16): the two acbs our consumer holds on their labels.
    - No ring has dwords past its doorbell. Doorbells are polled (page 0xfe0200000, qword d-1, 200 us), slot 0x33
      the same as all others. There is no unseen or unrung work.
    - Labels 0-10 = 0 0 0 0 1 0 1 1 1 1 1; 11-15 = index + 1 (untouched). Queue tails write labels 1, 2, 6, 7, 8 and
      9; no tail writes label 0.
23. *`BC5_DIRECT_AGC_EOP_IDENT` (tag ae439, off by default).*
    - The AGC-era end-of-pipe event in the soft CP: INT_SEL read as 3 bits; ident 0 on the graphics side, 0x20 +
      doorbell slot - 1 for a compute queue; data = (INT_CTXID << 16) | ident. Helpers in `k439/dc0439.hpp`.
    - Citations checked by a read-only fetch at the commits:
      - CONFIRMED: KytyPS5 39936ffa `renderContext.cpp` ~205-217, `graphicsRun.h:51`, `graphicsRun.cpp`
        (graphics 0, compute base + id - 1, RELEASE_MEM interrupt defers TriggerInterrupt); AnyPS5 19a1993e
        `libSceAgcDriver/Eq/src/Event.cpp` ~80-91.
      - COULD NOT READ: KytyPS5 `agc.cpp` ~4364 and the INT_SEL bit extraction. The line numbers are the fetcher's
        count, +-1.
    - Det tests (`test_dc0439.cpp`): PASS.
    - Smokes (normal `2befcb17`, 16:15-16:18, resets 11 -> 11, fault records 27 -> 27):
      - ASTRO BOT off: 3000 flips by 53.44 s. On: 3000 flips by 53.48 s.
      - With the switch on, ASTRO's interrupts go to ident 0 (graphics, 5 registrations, INT_SEL 1, 2 and 4; the 3
        INT_SEL 4 ones newly fired) and to 0x40 from compute queue slot 0x21 (= 0x20 + 0x21 - 1).
      - The third title on: 0 deliveries, the stall unchanged.
    - With the switch on, ASTRO gets 3 interrupts it never got before (INT_SEL 4, ident 0). The 5 registrations for ident
      0 are the graphics EOP events; ASTRO's frame count and timing did not change visibly (3000 flips by 53.48 s against
      53.44 s). TODO: name the 5 registrations' equeues from the ae27-on log.
    - Lean A/B (`k439/ab439ae.sh`, run 18:00-18:23 on boot c97d43e6). One private lean binary (`25338f8a`) for both
      arms: C without the word, O with `BC5_DIRECT_AGC_EOP_IDENT=1`. ASTRO BOT, no input, 180 s each, MangoHud's frame
      log from 30 s. One warm-up control first, discarded, then C O C O C O. Every run PASS, 0 kernel lines.
      Raw: `logs/ab439ae-q439aeA.txt`.

      | run | flips/s | median | p95 | p99 | max (ms) | over 50 ms |
      |---|---|---|---|---|---|---|
      | W0 (discarded) | 58.08 | 16.67 | 17.23 | 34.38 | 67.16 | 6 |
      | C1 | 58.16 | 16.67 | 17.23 | 34.24 | 66.64 | 6 |
      | O1 | 58.92 | 16.67 | 16.98 | 33.77 | 51.86 | 6 |
      | C2 | 58.14 | 16.67 | 17.22 | 34.16 | 50.29 | 3 |
      | O2 | 58.66 | 16.67 | 17.07 | 33.85 | 66.91 | 4 |
      | C3 | 58.48 | 16.67 | 17.11 | 33.97 | 50.25 | 7 |
      | O3 | 58.28 | 16.68 | 17.20 | 34.03 | 66.88 | 4 |

      - Control 58.14-58.48 flips/s, switch on 58.28-58.92. The ranges overlap, so no cost of the switch is visible.
      - With the switch on, ASTRO gets 3 interrupts it never got before; nothing visible changes.
24. *Cross-pack runs (x28, 16:32-16:33, normal `2befcb17`, resets 11 -> 11, fault records 27 -> 27).*
    - The host LLE-loads every module in the one `SHADPS4_SYSMODULES_PACK_DIR` (KytyPlus `runtimeLinker.cpp`
      `add_lle_dir`) and keeps the rest on HLE, so the packs were mixed with symlinks.
    - ASTRO BOT's pack has Agc `ca1e6fbe` (326,986 B), AgcDriver `84836a01` (122,613), Psml `817f6df6` (1,536,002), Ampr
      and PlayGo. The third title's has Agc `0dced71f` (326,617), AgcDriver `b2a41370` (122,383), Psml `c534dc41`
      (1,524,286); its dump renamed Ampr and PlayGo to `... orig`.
    - Its `fakelib orig/` holds the same three files at the same sizes; each differs in 3 bytes at one place.
      `eboot.bin` and `eboot.bin orig` differ in 19 bytes.
    - X1, the third title with ASTRO's Agc/AgcDriver/Psml: the same stall, 1 flip, labels as with its own pack.
      DISTURBED: reimpl-agc-psml's gdb watcher attached to this run's emulator by mistake from 16:32:06 to 16:32:35 (the
      process stopped on attach; nothing written). That covers most of X1's 30 s, so X1 is not a result; a rerun is
      queued behind the IB_CHAIN work, low priority.
    - X2, ASTRO with the third title's three: 3000 flips by 53.08 s (53.44 s with its own pack), no fault.
    - So the module pack is not the stall's cause.
    - Both titles require system software 11.60 (param.json); the host answers 10.60, and ASTRO plays with that.
25. *The stall's cause (yotei-memdump, exp 0440, from a memory dump at the stall).*
    - The title's frame is one dcb of 73 segments chained by INDIRECT_BUFFER with the CHAIN bit (bit 20 of the size
      dword), 9,346 dwords. Only the head (103 dwords) is submitted.
    - The label-0 write is a WRITE_DATA in the last segment. The partner labels of the two held acbs are RELEASE_MEMs in
      segments 29 and 34.
    - Every IB walker counted a chain as one more nesting level: `submit_impl` (`depth >= 3`, 64 pieces, then the cut IB
      NOP-ed), the soft CP (`depth >= 4`), `policy::refusal_in` (`depth < 3`), `full_state`'s walks (`depth < 4`). So
      only segments 0-3 ran, and the rest of the frame was dropped without a line.
26. *`BC5_DIRECT_IB_CHAIN` (tag ib439, off unless "1").*
    - The rule (`backend/include/bc5/ib_chain.hpp`): a chain keeps its parent's depth, ends the parent's buffer and has
      no limit of its own below 4096 segments. Calls keep the 3-level limit and the 64-piece cap. A chain or call to
      its own ancestor is a cycle: the submit is refused with a line.
    - Sources: AMD PAL c5e8000 `gfx9_plus_merged_f32_pfp_pm4_packets.h:2580`; shadPS4 1b9d159; our PORT-CHAIN note
      (F760, `acb_restore.hpp`).
    - Applied in `direct.cpp` `submit_impl`, `policy.cpp` `refusal_in`, `full_state.cpp` `apply_level` / `walk_draws`
      (a walk budget ends a cycle), and the soft CP's `indirect_buffer` / `execute` (mk439.py, `ib439.txt`).
    - The label-writer and readiness scans (`acb_ready`, `hold_note_writes`, plw) read one buffer and follow no IB, so
      the rule does not touch them.
    - A cut IB is logged even with the switch off: `submit_impl` prints the count of NOP-ed INDIRECT_BUFFER packets
      and how many were chains (first 16 submits, then every 1000th). The backend archive is shared by normal and lean,
      so this line is in lean too.
    - The flip packet in segment 72 writes the VideoOut buffer label. That label lives on an anonymous host page the
      direct path maps for the GPU (exp 0071), and `policy::filter` drops any write outside the mapped ranges
      (`unmapped_drops`). So it either lands on that page or is dropped and counted; it cannot fault.
    - Det tests (`k439/test_ib0439.cpp`, g++ in the ubuntu container), PASS:
      - a 73-segment chain is collected whole at depth 0, and its last-segment label write is found (switch off: 4
        pieces, write missing);
      - with calls and a chain mixed, a 4th-level call is not followed and a chain from level 3 is;
      - two chain cycles are refused;
      - on 2000 random IB trees, off equals the old loop, and on without chain bits equals off.
    - The planted bug (`-DBC5_IB439_PLANT`, a chain counted as a level) FAILS 2 checks, as it must. Output:
      `logs/test_ib0439.out`.
    - Private build: backend archive `81dcf888` (the shared one with `direct.cpp.o`, `policy.cpp.o`, `full_state.cpp.o`
      from the branch), normal `0befd641`, then `e0ae3ba9` with the chain rule in `dc0439.hpp`'s `walk_draws` as
      well, then `3a79a88e`.
    - Runs, 16:48-16:57 (ib29.sh):
      - ASTRO BOT with `BC5_DIRECT_IB_CHAIN=1`: 3000 flips by 52.93 s, no fault. ASTRO submits no chain at all (0 chain
        submits, 0 IBs NOP-ed), so the rule does not touch it.
      - The third title with the switch on, two runs: the frame went whole, twice (73 pieces, 72 chained, longest 72,
        none cut or refused). It flipped a second frame at 1.4 s, its first non-blank compressed surface (keys
        0x40). Then it ended at "TextureCache: compressed video-out read requires clean native GPU contents"
        (exit 65): the decompress pass was not run.
      - With the chain-aware walker the draw into the flip surface is found (job 33). Its DCC_BASE is `0x5007140000`,
        the registered metadata - 0x28000. `3a79a88e` takes the draw's block when its BASE is the surface.
      - A second ASTRO start in one series fails with "invalid file .../PPSA21567/sce_sys/param.json" whatever the
        switch says (3 times): a mount race between runs, not the switch.
    - The third title's 30-s run with `3a79a88e` (started 17:03:27), the first run in which the decompress pass could
      fire.
      - Confirmed (the top session, from the kernel log and the box): comp_1.3.0 timed out at 17:04:56 (process
        kyty_emulator, thread bc5-ring), the ring reset failed, and bc5-gpu-watch crashed the kernel for a reboot.
        Records: `~/bc5-data/captures/faults/20261121-170456` and the devcoredump `20261121-170456-devcd3.txt`.
      - Inferred, not yet read from the record: that the decompress pass fired at the second flip, and that the title
        ran on past 1.5 s.
      - Hypothesis only: that the decompress path's drain of every ring blocked the game thread while a compute job
        waited for a label of the next dcb; or that an acb with an unmet wait in a nested IB went to the GPU.
      - Not yet known: which job hung, on which wait, and where the game thread was.
    - The second ASTRO start in a series died on a dead image mount: `k439/play439.sh` was copied before the
      dead-mount guard. It has the guard since `8c442cfe`.
27. *Guards after the 17:04 hang (offline, built in the next box slot; all off by default).*
    - (a) `BC5_0439_DC_NODRAIN=1` (tag dn439): the decompress at the flip no longer drains every ring.
      - Before the decompress: the title's held chains are flushed, so the job that drew the surface is on the GFX ring
        first; a ring runs its jobs in order (`direct.hpp`, `wait_idle`'s comment).
      - After it: the flip waits only for a marker queued behind the decompress job in its own thread's completion queue
        (`cq_push`: one FIFO per submitting thread), at most 500 ms, with a line when the bound is hit. Compute rings are
        never waited for from the flip path.
      - Not used: a kernel dependency on the drawing job. Its seq number is not kept per surface today, and the GFX
        ring's own order gives the same.
    - (b) `BC5_0439_ACB_DEEP=1` (tag ab439): acb_ready looks into the IBs an acb calls or chains to, with the chain
      rule and a walk budget. An unmet wait found there holds the acb at its IB packet through the existing hold path.
      `BC5_0439_ACB_REFUSE=1` (tag ar439): at the 10-s give-up the acb is not released to the GPU. It stays held, and a
      record (queue, buffer, wait, value, known writers or "no writer registered") is printed and journalled every 10 s.
      This is a guard for diagnosis; the fix is the right order of dcb and compute submissions.
    - (c) `BC5_0439_XQ_COUNT=1` (tag xq439, log only): per GFX job, the memory waits in all its pieces that are unmet at
      submission with no writer in the job, and how many of those are on a label that the acb held right now writes.
    - Det test of (b) on the generated code (`test_ab0439.cpp`, the text cut out by `mkab0439.py`, clang on the laptop),
      PASS: a call's unmet wait is held; a wait at the end of a 6-segment chain is held; the acb's own earlier write
      hides it; a met wait is not held; a chain cycle ends on the budget; with the switch off an IB is not looked into.
      The planted bug (a chain treated as a call level) FAILS case 2. Output: `logs/test_ab0439.out`.
    - (a) and (c) have no det test: they act on the completion queue and the live label state, and are checked on the
      box from their lines.
    - The stated order of the first frame (yotei-memdump's third pass, exp 0440, from the dump; three buffers exchange
      labels 18 times):
      - D, the dcb chain; A, queue 1/2 (`0x201044c900`); B, queue 1/3 (`0x201032c280`).
      - D's segments 29-40 write the labels A waits on; A writes 4 labels D waits on from segment 39. B waits on D's
        writes up to segment 45 and twice on a label A writes near its end, and writes the other 4.
      - There is no cycle in the content, but no order of whole jobs runs it: A cannot finish before D passes segment
        40, B not before 45, D not past 39 before A's write at dword 406.
      - So the three must run side by side: D whole on the GPU, A and B released piece by piece.
      - The GPU resolves the exchange if (1) the whole dcb is on the GPU (it is: one job of 73 pieces), (2) bc5-ring
        keeps polling and submitting while the GFX ring sits in segment 39, and (3) nothing on the game thread blocks on
        compute. The 17:03 flip path broke (3) by draining every ring.
      - The layout alone deadlocks only if an acb waits for a dcb write that comes after a dcb wait on that acb; the
        dump shows none.
    - What the code does with this (read in the baked unit `2e6168de`):
      - `register_label_writes` registers only the submitted buffer, which for D is its 103-dword head, not its chain
        pieces. So D's writes are never pending for anyone. acb waits on D's labels are held on the CPU until the GPU
        writes them, and F4 (`ho430`, a waiter's submit depending on the writer's job) can never fence A or B on D.
      - F4 applies only to a wait that is already satisfied while a registered write is pending on another ring, and
        it skips a writer job holding a GPU wait on a label the waiter writes. Between A and B it can add a fence; to
        be checked from the run's journal (`ho430 F4` lines).
      - `ring_will_satisfy` with way 2 leaves a wait to the GPU only when its writer job is already submitted, on any
        ring; otherwise acb_ready holds the acb on the CPU at that wait.
      - Way 2 starts every guest queue on libdrm compute ring 0 and moves a queue to its own ring only after 256 jobs
        (`w428_queue_ring`). So A and B share a ring in the first frames. That is safe only while every native wait's
        writer is ahead of it on that ring or on another ring. B's waits on A's late write rely on A's part being
        submitted first.
      - The same holds for the IB_CHAIN builds (`3a79a88e` included). The chain rule is only in the walkers that
        follow IBs; the label-writer registration (`register_label_writes`, plw, EARLYREG/r438, q438), acb_ready's
        writer lookup, `ring_will_satisfy` and F4's cycle check stay flat over the submitted buffer.
      - If chain writes are ever registered, F4 must not fence on a chained dcb (its own switch): D waits natively
        for A's and B's writes, so a whole-job dependency of A or B on D is a deadlock.
    - Logged with `BC5_0439_XQ_COUNT=1` for the next run: every acb part's guest queue and ring (first 64, then every
      1024th), and at each flip the number of acb holds released and the longest one, against the kernel's job timeout
      for the buffer waiting natively on the other side.
28. *The 17:04 hang, from the record* (read on boot c97d43e6: the previous boot's kernel log, fault record
    `~/bc5-data/captures/faults/20261121-170456`, devcoredump `20261121-170456-devcd3.txt`, the run's `play-last.log`).
    - The title played: every decompress pass OK in 0.7-1.1 ms, 0.00 ms of drain before it; flips at about 30 fps for 8
      s (frame profile 20-35 ms a flip; label counters near 0xe5, about frame 230); every frame one job of 73 pieces.
    - The hang: submit #3623 at t 9.459 s, guest queue 40's acb (16,364 dwords after a split at dword 4, with a 4-dword
      state prefix; 16,422 dwords submitted), sent after three of its waits passed on the CPU. It timed out after
      2041 ms on comp_1.3.0, the ring reset failed, and bc5-gpu-watch rebooted the box.
    - Queue 40 is neither of the two acbs of the first frame (queues 16 = 0x11 and 24 = 0x19).
    - Not a wait. The devcoredump's HQD of mec 0 pipe 3 queue 0 shows VMID 6, IB base `0x1079_000100a0` and size
      0x3fea = 16,362 dwords: this job. The last headers the CP fetched (`CP_MEC_ME1_HEADER_DUMP`) are NOP,
      INDIRECT_BUFFER, SET_SH_REG and DISPATCH_DIRECT (0x15); there is no WAIT_REG_MEM among them. CPC is busy and
      there is no page fault. So a dispatch's waves never finished.
    - Inferred, not shown: a shader spinning on memory another queue should write, or a dispatch run with the wrong
      state. Queue 40's parts dispatch before they set a program and get the tracked compute registers in front (exp
      0401's line at t 1.657 s: "queue 40 acb part 424 dwords dispatches at -1 before it sets a program", 59 parts).
    - ho430 wrote only its start line ("F4 fences 0"): no F4 fence in the run.
    - Just before it, three soft CP waits timed out after 8 ms on labels with frame counters (`0x20000081c0` ref 0xe6
      value 0xe5, `0x2000008220` ref 0xe7 value 0xe6, `0x201050a8c0` ref 1 value 0): a dcb's replay waiting on compute
      writes not yet done.
    - Not known: the dispatch's offset and program, the queue-to-ring map, and the three waits' writers. The journal was
      `min`, and the timeout probe was off.
    - So neither the decompress drain nor A and B sharing a ring caused it. The next third-title run needs the timeout
      probe (`BC5_DIRECT_TIMEOUT_PROBE=1`) and the full journal.
    - Also on that boot: at 16:58:09 comp_1.1.0 and gfx_0.0.0 timed out with successful resets, pid 928664, not a run
      of this experiment.

(more to come)

**Verdict.** (to come)
