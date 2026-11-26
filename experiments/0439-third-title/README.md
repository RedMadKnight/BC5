# 0439 — the third title: install, first runs, fixes

**Status:** claimed 2026-11-21; scripts written and tested on a laptop stand-in; no box step yet. The GO comes after two
box slots on the second title (the reimpl-agc-psml rerun and bake, then exp 0438's diagnosis); no md5 of a NAS file
during their runs (page cache against RT-on memory).

**Question.** What stops the third title (TITLE3, v01.512, the maintainer's own package on his NAS) on BC5 today,
and which fixes, simplest first, make it playable? Before that, the second title's install (TITLE2) is removed to
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
  - `run0439.sh`: `dry` (the chain `play-any.sh <folder>` → `play-t1.sh` with `BC5_GAME_DIR`, the binary it reaches
    and its md5, LESSONS R66), `run` (a `systemd-run --user` unit with `RuntimeMaxSec`, `ulimit -c 0`, RT on as the
    default, refused if `bc5-run.env` turns it off; the normal build with `PLAY_CAPTURE=1`), `collect`.
  - `klog0439.sh`: the kernel log streamed to the laptop, killed when its stdin closes (LESSONS R67).
- Kept, never moved or changed: `~/bc5-work/_SaveData-pkg-play`, `~/bc5-work/_SaveData/TITLE2`, `~/bc5-data/saves/`
  (with the snapshot `TITLE2-20261111-2100-memory-heavy`), `~/bc5-work/menu/titles/TITLE2/`, `input.cfg`.
- No launcher, shortcut or shared build changes (the third title already goes through `play-t1.sh`'s generic
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

1. *The second title removed (2026-11-21 09:11:56).* The NAS `game.pkg` md5 MATCH (TITLE2, 101,814,213,551 bytes);
   the tar's 142 files equal the inventory's; `bc5-mount uninstall` freed 196,702,616,991 bytes in 321 entries; the save
   inventory (536 md5 lines) equal before and after; no second-title shortcut and no mount cache existed. Free on `/var`:
   272,036,065,280 bytes. `check2`'s and `uninstall2`'s `pipefail` stops after `head`/`du` were fixed in the script.
2. *The third title installed and verified (11:32:01).* TITLE3, image `debug`, 95,402 files (95,383 in the tree and
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
   module pack (`BC5_SYSMODULES_PACK_DIR=<folder>/fakelib` per run: without a mount the box's `play-t1.sh` takes
   the first title's pack from `bc5-run.env`). Audio opens on the pad; three stubbed network imports are called (Http,
   NpSessionSignaling); no unresolved import stops it. At 2.6 s a compute job on bc5-ring WRITES (TCP, RW 1,
   PERMISSION_FAULTS 0x4, status 0x00641041) at 0x504c932000: the title's 3.4 GB direct view at 0x5000000000 has no
   name ("anon") and is imported by data, so its never-CPU-written chunk is the read-only zero cover of k1r (without k1r
   it would be unmapped: the same fault). comp_1.1.0 timed out, its reset succeeded; exit 86 (fault record
   `faults/20261121-113617`, private). The second title keeps its GPU targets in named heaps on the eager list.
5. *Fix 1 (n2, no build):* a private copy of `bc5-run.env` with `BC5_DIRECT_EAGER_NAMES=GpuGarlicMemory,GpuOnionMemory,anon`
   (through `BC5_RUN_ENV`; `play-t1.sh` re-exports the settings file after the run's own words). No GPU fault, the
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
   - Check against other titles before it could become a default: the first title, one logged run, comes after exp 0438's
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
    - Private launcher `k439/play439.sh`: `play-t1.sh` with its two `EMU=` lines on `P439_BIN`. `run0439.sh`
      takes `RUN_PRIV=<binary>`.

11. *p1 (private normal `f3c18e68`, `BC5_DIRECT_EAGER_GPU_WRITE=1` + `BC5_DIRECT_DCC_PRESENT=1`, no anon env, 12:36).*
    - The map rule alone removes problem 1's fault: no GPU fault, no fault record, reset lines 21 before and after.
    - Six views went eager by prot 0x20, 4,110 MiB in all: 0x5000000000 4,032 MiB, 0x2000000000 620 MiB, three
      SceAgcDriver/SceAgcRegShadow views of about 2.2 MiB, and 0x200c00000 78 MiB.
    - MemAvailable minimum 9.13 GB, against 8.36 GB with the anon stopgap.
    - The same DCC stop (exit 65). At the first flip (1.5 s, index 2) no GFX job ended with an MRT on the surface.
    - Two earlier p1 starts did not reach the emulator: `play439.sh` had no exec bit, and then the box's display was
      disconnected (DP-1 and DP-2), so SDL had no display (exit 65, no GPU work).
12. *The first title a1 (shared normal `b1b57df9`, map log, 12:41, reset lines 21 before and after).*
    - Seven direct views are GPU ReadWrite, 10,390 MiB in all: 0x10ca000000 4,608 MiB, 0x1000000000
      "BackgroundTaskWorker" 3,232 MiB, 0x500000000 2,172 MiB, 0x400000000 184 MiB, "Sample" 128 MiB, 64 MiB and
      SceGnmDumpArea 2 MiB. Today none of them is eager.
    - The map rule as a global default would pin about 10 GB on the first title, so it stays per title or needs a bound.
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
    - `tools/scripts/launchers/play-t1.sh` and `play-pkg.sh`: a mount counts only when its `sce_sys/param.json`
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
      - The first title off: 3000 flips by 53.44 s. On: 3000 flips by 53.48 s.
      - With the switch on, the first title's interrupts go to ident 0 (graphics, 5 registrations, INT_SEL 1, 2 and 4; the 3
        INT_SEL 4 ones newly fired) and to 0x40 from compute queue slot 0x21 (= 0x20 + 0x21 - 1).
      - The third title on: 0 deliveries, the stall unchanged.
    - With the switch on, the first title gets 3 interrupts it never got before (INT_SEL 4, ident 0). The 5 registrations for ident
      0 are the graphics EOP events; the first title's frame count and timing did not change visibly (3000 flips by 53.48 s against
      53.44 s). TODO: name the 5 registrations' equeues from the ae27-on log.
    - Lean A/B (`k439/ab439ae.sh`, run 18:00-18:23 on boot c97d43e6). One private lean binary (`25338f8a`) for both
      arms: C without the word, O with `BC5_DIRECT_AGC_EOP_IDENT=1`. The first title, no input, 180 s each, MangoHud's frame
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
      - NOT A MEASUREMENT OF NORMAL PLAY (LESSONS R72; the top session, 11-21 evening): every boot since 13:51 logged
        "No EDID read" on DP-1, and the desktop ran at 640x480@59.94 (scale 0.5) instead of 1920x1080@60. This series
        ran in that mode. It stands as a comparison within the series only. A repeat at 1920x1080@60 is planned
        before the bake.
      - With the switch on, the first title gets 3 interrupts it never got before; nothing visible changes.
24. *Cross-pack runs (x28, 16:32-16:33, normal `2befcb17`, resets 11 -> 11, fault records 27 -> 27).*
    - The host LLE-loads every module in the one `SHADPS4_SYSMODULES_PACK_DIR` (KytyPlus `runtimeLinker.cpp`
      `add_lle_dir`) and keeps the rest on HLE, so the packs were mixed with symlinks.
    - The first title's pack has Agc `ca1e6fbe` (326,986 B), AgcDriver `84836a01` (122,613), Psml `817f6df6` (1,536,002), Ampr
      and PlayGo. The third title's has Agc `0dced71f` (326,617), AgcDriver `b2a41370` (122,383), Psml `c534dc41`
      (1,524,286); its dump renamed Ampr and PlayGo to `... orig`.
    - Its `fakelib orig/` holds the same three files at the same sizes; each differs in 3 bytes at one place.
      `eboot.bin` and `eboot.bin orig` differ in 19 bytes.
    - X1, the third title with the first title's Agc/AgcDriver/Psml: the same stall, 1 flip, labels as with its own pack.
      DISTURBED: reimpl-agc-psml's gdb watcher attached to this run's emulator by mistake from 16:32:06 to 16:32:35 (the
      process stopped on attach; nothing written). That covers most of X1's 30 s, so X1 is not a result; a rerun is
      queued behind the IB_CHAIN work, low priority.
    - X2, the first title with the third title's three: 3000 flips by 53.08 s (53.44 s with its own pack), no fault.
    - So the module pack is not the stall's cause.
    - Both titles require system software 11.60 (param.json); the host answers 10.60, and the first title plays with that.
25. *The stall's cause (the dump session, exp 0440, from a memory dump at the stall).*
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
      - The first title with `BC5_DIRECT_IB_CHAIN=1`: 3000 flips by 52.93 s, no fault. First-title submits no chain at all (0 chain
        submits, 0 IBs NOP-ed), so the rule does not touch it.
      - The third title with the switch on, two runs: the frame went whole, twice (73 pieces, 72 chained, longest 72,
        none cut or refused). It flipped a second frame at 1.4 s, its first non-blank compressed surface (keys
        0x40). Then it ended at "TextureCache: compressed video-out read requires clean native GPU contents"
        (exit 65): the decompress pass was not run.
      - With the chain-aware walker the draw into the flip surface is found (job 33). Its DCC_BASE is `0x5007140000`,
        the registered metadata - 0x28000. `3a79a88e` takes the draw's block when its BASE is the surface.
      - A second first-title start in one series fails with "invalid file .../TITLE1/sce_sys/param.json" whatever the
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
    - The second first-title start in a series died on a dead image mount: `k439/play439.sh` was copied before the
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
    - The stated order of the first frame (the dump session's third pass, exp 0440, from the dump; three buffers exchange
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
30. *The display mode of today's runs (LESSONS R72).*
    - Every third-title and the first title run of this experiment since 13:51 (from the cross-pack runs on) ran with the
      desktop at 640x480@59.94, the monitor's EDID unread.
    - The diagnosis findings do not depend on it: the chain cut and its fix, the 17:04 record, the queue audit, the
      cross-pack result.
    - The decompress pass works on the title's own 3840x2160 surface in guest memory, so its result does not depend on
      the output mode. But the flip path and its present scaled that surface to a 640x480 output, so the present's
      cost and look are not those of normal play.
    - Frame rates and frame times from these runs describe that mode only.
    - Now in the scripts: `k439/r72check.sh`, as R72 was amended at 19:52 (the current state decides). It requires an
      EDID size > 0, a first mode of 1920x1080, and an active mode of 1920x1080@60 at scale 1 from `kscreen-doctor -o`.
      The boot's "No EDID read" lines are counted and recorded, not a failure. One line; exit 1 when a condition fails.
      Run before every series.
    - The monitor was replugged on boot 7986fd90 (EDID 128 bytes, 1920x1080@60.00, scale 1; the top session, 19:52).
      - `ab439ae.sh` refuses to measure when it fails, and writes the line to the series header.
      - `ib29.sh` and `x28.sh` (diagnosis) write the line and mark the series.
      - `play439.sh` writes the EDID size and first mode into the log's header.
29. *Rebase notes for the bake after exp 0438's swap* (agreed with exp 0438 by message, 11-21 evening).
    - Base both the backend diff and the unit edits on exp 0438's post-bake files. It will send the md5s of patch
      0001, the shared bc5LleAgc.cpp, memory.cpp, direct.cpp, and the normal, lean and archive builds.
    - `backend/src/direct.cpp`: both experiments edit it. Exp 0438 changes the mapping functions (MappingIndex,
      `sorted_mappings`, `map_userptr` and the rest); exp 0439 changes `submit_impl`'s piece collection and the
      NOP-ed-IB count. The hunks are apart.
    - `opt.mapped` stays a `std::function<bool(uint64_t, uint64_t)>`, so `ib_chain::collect` is unchanged.
      `sorted_mappings()` will return `shared_ptr<const MappingIndex>`. None of exp 0439's hunks names
      `std::vector<bc5::direct::Mapping>` or calls `sorted_mappings`/`covered_sorted` (checked by grep over mk439.py,
      ab439.txt, ib439.txt, mkeq439.py, dc0439.hpp).
    - `acb_ready`: ab439's found waits go through exp 0438's `acb_wait_unready` (its in-flight test included) instead
      of the three inline tests.
    - bc5-ring's 10-s give-up: exp 0438 adds `Direct::ng438_fallback(Direct::t_unready.label)` before the release.
      ar439's branch goes after that call, so a refused acb is still counted.
    - mk439.py's replacements assert that each anchor matches exactly once, so any anchor exp 0438's bake moved
      fails loudly at generation and is fixed then.
31. *t3p: the run for the hang's record (`k439/t3p.sh`, 19:54:43-19:55:50, boot 7986fd90, the top session's GO).*
    - Normal `3a79a88e` with the 17:04 settings, plus `BC5_DIRECT_TIMEOUT_PROBE=1` and the full journal (a private env
      copy without `BC5_DIRECT_JOURNAL=min`). 60-s bound. Display: EDID 128 B, 1920x1080@60.00, scale 1.
    - No hang: resets 1 -> 1, fault records 29 -> 29, the 60-s bound ended it. Only about 50 frames, though: from
      t 2 s every frame took 1.13-1.18 s (game thread inside the host 5-6 ms; GPU busy about 7.5 ms).
    - Each frame, the dcb replay's soft CP wait on `0x20000082e0` (written by B, queue 1/3, at its dword 166) was met
      after about 1.14 s (refs 2, 3, 4 ...).
    - The cause is the full journal, not the title. It logged 949 "ho430: THE BOUND STANDS" lines in 58 s, each after
      F18's 50-ms bound with a writer slot "still busy": about 20 per frame, 1.05 s. F18 sits on the acb submit path,
      so B's parts went out about 1 s late every frame.
    - With the journal unset, every submission is written raw and filtered, with a second filter pass and a sync
      each (the unit's own comment on the mode: "took half of a frame"). At 17:04, with `min`, the same build ran at
      about 30 fps.
    - Also 205 "r438 (exp 0438, b438): BUG: the early-registered write of <label> ... never reached the ring" lines,
      about 4 a frame, on labels B and the others write (`0x20000082e0`, `0x2000008200`, `0x2000008320`, ...). These
      are reported to the top session.
    - Raw: `logs/t3p/` (display, meta, the kernel log stream: empty, and an extract of the journal's frame-profile,
      bound, r438 and soft-CP-wait lines).
    - Next: the same run with the journal at `min` and the probe on, long enough to reach frame ~230.
32. *t3q: run 2, the 17:04 condition with the timeout probe (`k439/t3q.sh`, 20:00:10, boot 7986fd90).*
    - Normal `3a79a88e`, the 17:04 settings with `BC5_DIRECT_JOURNAL=min`, plus `BC5_DIRECT_TIMEOUT_PROBE=1`; bound 120 s.
      Display before the run: OK (1920x1080@60, scale 1).
    - It hung like 17:04: 11.48 s after the start (17:04: 11.49 s), 229 frames at about 30 fps, frame counters
      0xe4-0xe6. The same job: guest queue 40's acb rest "4..16364 of 16364 dwords", submitted as 16,422 dwords
      (#3640). This time it ran on comp_1.1.0; the ring reset failed and bc5-gpu-watch rebooted the box (20:00:30).
      Records: `~/bc5-data/captures/faults/20261121-200030`, devcoredump `20261121-200030-devcd1.txt`, the probe's
      `ib-timeout-00003640-acb-16422.bin` in the capture's `gc/`. All private; not committed.
    - The dumped job (decoded with `k439/decib0439.py`):
      - Dwords 0-61 are the host's prefixes: the head's 4-dword state prefix, then exp 0424's queue registers SH
        0x204-0x280, with COMPUTE_PGM 0x8000343500.
      - The title's buffer follows: waits and the pass markers "Sky LUT Update", "Clouds Update" and "Sh Grid Update";
        475 DISPATCH_DIRECTs, each with its own COMPUTE_PGM_LO set right before it. So a stale queue program
        cannot reach a dispatch here.
      - The last packet is an INDIRECT_BUFFER with the CHAIN bit to `0x2013600b80`, 16,362 dwords (0x3fea).
    - The hung HQD's IB size is 0x3fea = 16,362 dwords, in both hangs: the CP was in the chained continuation, not in
      the dumped job. (Item 28 read 17:04's 0x3fea as the job itself: corrected here.) Its last fetched headers are
      SET_SH_REG and DISPATCH_DIRECT, so a dispatch of the continuation never finished. The probe dumps the top job only,
      so the continuation's dispatches are not in the record.
    - r438 BUG lines: 0 at 30 fps with journal=min (205 shown, 1,281 counted under the full journal in t3p). They are
      not a suspect for this hang.
    - LESSONS note (the top session): the full journal is not usable for timing-sensitive diagnosis of this title.
      With `BC5_DIRECT_JOURNAL` other than `min`, `g_async` is off (`static const bool g_async = g_journal_min;`) and
      every submission waits for its own job. Use `min` plus targeted dumps.
    - umr: `/usr/local/bin/bc5-gpu-hang-dump` and `umr -O halt_waves -wa none` are allowed by sudoers. The helper that
      `BC5_DIRECT_UMR_ON_TIMEOUT` calls reads the gfx ring only.
    - Next, in the guard build: dump every piece of a timed-out job (chained and called); a switch for
      `umr -O halt_waves -wa none` at the first timeout; XQ_COUNT's ring map. Then one run names the dispatch.
33. *`BC5_DIRECT_IB_CHAIN_FLAT` and the import scans over pieces (tags fl439, ip439), the guard build, run t3r-i1.*
    - Flat layout (`bc5/ib_chain.hpp` `flatten`, `submit_impl`):
      - A top-level chain is laid out as one buffer: each segment is copied up to its chain packet, the chain packet
        becomes NOPs, and the target follows. The CP never switches buffers, so the state set before the cut is still
        there.
      - It refuses on a COND_EXEC before the chain, a cycle, an unmapped target, or past 2^20 dwords.
      - Executed offsets are split back per guest segment (`r.nested`).
      - Det tests 6-9 in `test_ib0439.cpp`: PASS. The planted bug (the last chunk dropped) FAILS.
    - `BC5_0439_IMPORT_PIECES=1`: `k1f412_pass` and `dt412_pass` also run on every called or chained piece. Before
      this, every host import scan read the top buffer only.
    - Also in the build: the probe dumps every piece and the parameter blocks around the chain
      (`BC5_0439_PIECE_DUMP`); umr `halt_waves -wa none` at the 0.9-s watchdog (`BC5_0439_UMR_WAVES`); the
      queue-to-ring map. Private normal `5b69b5d2`, lean `1426b2ab`, archive `39f9b3cb`.
    - Run t3r-i1 (20:56:00, the top session's GO, the maintainer watching; both candidates on; display 1920x1080@60):
      - No hang and no reboot: resets 1 -> 1, fault records 30 -> 30.
      - Queue 40's 16,422-dword acb was laid out flat: 5 segments, 65,607 dwords (the SH-grid batch spans five
        chunks). It completed.
      - Imports by the piece scans: 0, and no import line at all in the run. Everything was already mapped, so the
        zero-cover lead is cleared.
      - By elimination the frame-229 hang was the compute engine running a chained INDIRECT_BUFFER from our copy.
        This is an inference from one run.
      - Ring map: queue 16 (A) moved to libdrm compute ring 2, queue 24 (B) to ring 1, queue 40 to ring 3; every
        queue starts on ring 0.
      - New stop: 281 frames, the last at t 11.06 s; then no flip for the remaining 109 s, with no GPU timeout, no
        fault, and no host line (journal=min). A stall, not a hang.
      - The screenshots (private: `~\Documents\bc5-private\t3-screens\t3r-i1-2056\`, never in git)
        show the window black throughout. The "fps: 27.1" in its title bar is the last value before the stop, not a
        running rate: after t 11.06 s no flip came.
      - Before each decompress pass the surface's first 4 MiB held 0 non-zero dwords while its keys read 0x40
        (compressed). The next run's surface readback shows whether the pass fills it.
    - Next: find what the title waits on after the first frame that follows the batch (wait trace, ACB_REFUSE's
      records), in a run that most likely does not reboot.
34. *Build for the black picture and the stall (tags sr439, sv439; run script `k439/t3s.sh`).*
    - `BC5_0439_SURF_DUMP=<private dir>`: after a decompress pass that went OK (decompressed flips 2, 60 and every
      300th), the display surface is written raw, with min/max/mean per byte lane and the non-zero byte count.
    - `KYTY_BC5_SYSTEM_SW_VERSION` sets the version string and number of `GetProsperoSystemSwVersion`:
      - unset: today's 10.60;
      - "param": the title's own param.json value, via `BC5_PARAM_JSON` exported by `play439.sh`;
      - "MM.mm": that version.
      Every answer is logged, and so is `GetCompiledSdkVersion`'s. The third title's param.json sdkVersion is 0, so the
      host answers from the eboot's process parameter.
    - Not covered: `sceNpGetSdkVersion` (libNp.cpp, a unit outside this build), which answers from its own constant
      (0x0A600000; TODO).
    - Revised at the maintainer's request (the firmware version is to be a switch, so
      that it can be changed for a test): the parsing is in `k439/sv0439.hpp`.
      - Accepted: unset (10.60), "param", or any "MAJOR.MINOR" with a two-digit minor (e.g. 9.00, 10.60, 11.60,
        12.00).
      - Encoded as the word `(major << 24) | (BCD minor << 16)`: 10.60 -> 0x0A600000, the host's own constant; 11.60
        -> 0x0B600000. The string is "MM.mm.000".
      - Read once at start by a static initializer. One line names the version in effect and its source. A malformed
        value ends the run at start (exit 2) with its reason.
      - Det test `k439/test_sv0439.cpp`, PASS (`logs/test_sv0439.out`): five values and their encodings, eleven
        malformed values refused, "param" from a param.json text.
      - Not in lean builds. If it is ever baked, it would be a per-title default ("param" for titles whose
        param.json asks for more than 10.60), not a global switch.
      - `box439.sh` compiles `libNp.cpp` when a generated copy is present, so that `sceNpGetSdkVersion` takes the
        same word. That copy needs the shared tree's libNp.cpp read from the box first.
      - TODO(verify): that a console encodes versions other than 10.60 the same way.
    - `t3s.sh` adds ACB_DEEP and ACB_REFUSE, and a box-side stall watch. When the journal's frame-profile lines stop
      for 3 s, it takes one snapshot of every thread (CPU ticks over 1 s, state, wchan, eu-stack) and of labels 0-15
      plus six known labels.
    - Whether `BC5_DIRECT_IB_CHAIN_FLAT=2` (the dcb's chain flat too) is safe is untested. The soft CP's offsets are
      kept per segment. The GFX path's own passes (the state stack, the indirect checks, the light-tail split) would
      then see one long buffer instead of 73 pieces. Try it only after a run with 1 is understood.
35. *Runs A and B (`k439/t3s.sh`, 21:17-21:21, boot d4d739c7): the version switch, the picture, the stall.*
    - Build `e116505c` (lean `bc1e9128`, archive `3fc7f7ea`), rebased onto exp 0438's patch `589ef163`:
      - ar439 now goes after exp 0438's `ng438_fallback` call;
      - ab439's found waits go through exp 0438's `acb_wait_unready` (det test still PASS);
      - `libNp.cpp`'s `sceNpGetSdkVersion` takes the switch's word;
      - the backend changes are re-applied as a diff (`k439/direct439-on-eacf8d2a.diff`, six hunks, offsets only).
      - Lean has no `KYTY_BC5_SYSTEM_SW_VERSION`.
    - Both runs: FLAT=1, IMPORT_PIECES=1, ACB_DEEP, ACB_REFUSE, XQ_COUNT, the surface dump, the stall watch, the Kyty
      log. 60-s bound. No hang, no fault, resets 1 -> 1.

      | | A: version unset | B: version "param" |
      |---|---|---|
      | in effect | 10.60.000 (0x0A600000) | 11.60.000 (0x0B600000), from the title's param.json |
      | `GetProsperoSystemSwVersion` calls | 0 | 0 |
      | `GetCompiledSdkVersion` | 0x04000031, twice | 0x04000031, twice |
      | frames to the stall | 286, last flip 11.62 s | 272, last flip 10.84 s |
      | stub calls | Http x1, NpSessionSignaling x2, libkernel yu17wG8L5FI x6 | the same |
      | flat jobs, piece imports | 1 (5 segments), 0 | 1 (5 segments), 0 |

    - The title never asks the system version before the stall, so the version cannot change its path here.
    - The picture:
      - Both DCC key arrays hold only clear codes: the registered display keys 00:7168 40:122432, the draw's render
        keys 00:7424 40:122176. Mesa 0866ae7 `src/amd/common/ac_descriptors.h:29-38`: 0x00 `DCC_CLEAR_0000`, 0x40
        `GFX8_DCC_CLEAR_0001`; radeonsi `si_clear.c:239-246` uses the GFX8 codes before gfx11.
      - The surface after the decompress pass is all zero bytes (flips 2 and 60, all four lanes 0).
      - So the title clears its frame to black and draws nothing visible into it; the present loses nothing.
    - The stall (the stall watch's snapshot; `logs/t3s/`):
      - game-main is the only running thread: state R, about 1.4 s of CPU per second, in guest code at
        eboot+0xe245b2, called from +0xbda165, +0xec76d9, +0xec6780.
      - Every other thread sleeps: MovieDecoder, Psn and Http on condition variables, ProxySetSync in its equeue.
      - Labels: `0x20000081c0` = N-1 while `0x2000008220`, `0x20000082e0`, `0x2000008200`, `0x20000081a0` and labels
        1/2/4/8 = N (A: 0x121 against 0x122; B: 0x112 against 0x113).
      - Queue 2/1/0 writes `0x20000081c0` = N and `0x2000008220` = N+1 at its buffer's end, so its last finished
        buffer is frame N-1's.
      - Inference: game-main busy-waits for queue 2/1/0's next frame. ACB_REFUSE logged no record, so acb_ready did
        not hold that buffer for 10 s.
    - Next: what eboot+0xe245b2 polls (the dump session's paused dump at this stall), and queue 2/1/0's ring, doorbell
      and consumed pointer at the stall.
    - SUPERSEDED by the dump session's second dump (exp 0441). game-main sits in the title's job system's "wait for this
      job group" (eboot+0xe244f0); the group holds 11 jobs of one ProxySet function (eboot+0x11c3b40), none started.
      All 20 JobWorker threads sleep in a semaphore wait (from eboot+0xe249b9), and game-main's own attempt to take a
      job returns nothing. Labels, rings and ProxySetSync's check are all consistent and met, and every queue's ring is
      consumed. So the reading above ("game-main waits for queue 2/1/0's next frame") is wrong. The stall is on the
      CPU side, between the title's job system and the host's kernel objects.
    - The host side of it (run A's stacks and Kyty log, read offline):
      - All 20 workers are in `KernelWaitSema` -> `KernelSemaPrivate::Wait` -> `Common::CondVar::WaitFor` (host
        `src/kernel/semaphore.cpp` at patch 589ef163).
      - The title creates exactly two semaphores, both "CJobManager", init 0, max 2,147,483,647 (the create lines).
        So the maximum-count refusal in `Signal` (`m_count + n > m_max_count`) cannot apply.
      - `Signal` adds the count, then `WakeWaiters` grants, under the mutex, to every waiting thread whose need fits,
        in queue order, and the condition variable is signalled. `Wait` takes at once when the count suffices, else
        queues and loops on a timed `WaitFor` (the APC poll), so a missed notify is caught on the next poll. Nothing
        in this path loses a wake.
      - So the workers sleep because the count stayed 0: no signal reached their semaphore for these 11 jobs. Which
        call should have given it (a signal with what count, or a different primitive) is not visible without a
        trace.
      - Candidate R (exp 0429) does not act here: its count line reads "held 0 calls 0".
36. *The stall's cause and its fix: `BC5_DIRECT_AGC_EOP_IDENT` (run 21:38:05-21:40:23, build `adace8c5`).*
    - The dump session's second dump (exp 0441):
      - game-main waits in the title's job system for 15 job groups (11 jobs each) that hang on a gate at ProxySet
        object + 0x2cb0.
      - Only ProxySetSync opens that gate, after a wake from its "ProxySet Cull" equeue (ident 0x52).
      - That wake is the interrupt of queue 2/2/2 (slot 0x33): its 67th buffer ends with a RELEASE_MEM with INT_SEL 2
        (context id 0x111).
      - With the switch off, the host fires the PS4 idents, so ident 0x52 never came.
      - The job system's semaphores were never signalled for these groups because the groups were never enqueued.
        The semaphore trace (tag st439, `k439/mkk439.py`) is kept in the build; it was not needed.
    - The run: the t3s set plus `BC5_DIRECT_AGC_EOP_IDENT=1`, 120 s, version unset. No hang, no fault.
      - ProxySetSync's equeue returned 118 times (before: never).
      - No stall: frames to the 120-s bound (about 35 ms each; the window title reads 24-26 fps).
      - The surface turns non-zero at decompressed flip 600 (27.4 s; 600,332 non-zero bytes), about 1.32 M by flip
        1800.
      - The screenshots (private) show the title's first screen, a "Digital Deluxe Bonus" dialog, legible, with a
        loading spinner.
    - So `BC5_DIRECT_AGC_EOP_IDENT` is needed by the third title. With `BC5_DIRECT_IB_CHAIN=1` and
      `BC5_DIRECT_IB_CHAIN_FLAT=1` it forms the bake set (the top session).
    - The code path the switch takes for this packet: a compute queue's ring entry is replayed by the soft CP in the
      queue consumer's completion closure (`t_ae439_slot = qq.d`, then `indirect_buffer` -> `execute` ->
      `release_mem`). That runs after the slice's jobs complete, so the event follows the GPU's write. Ident 0x20 +
      0x33 - 1 = 0x52, data (0x111 << 16) | 0x52.
    - Next problem: blocks of coloured speckle over parts of the frame, growing over the run. From about 27 s the DCC
      keys hold compressed codes (0x08, 0x28, 0x33, 0x66, 0xCC, ...) and 0xFF besides the clear codes. The display
      copy matches the draw's keys apart from the 0x00/0x40 counts. Where the decompress pass or the present goes
      wrong is open.
37. *The scripted confirm (run 21:51:45-21:56:52, build `adace8c5`, the same switches as item 36, `t3s.sh ... script`,
      300 s).* The top session's GO, and the maintainer's word to do it itself relayed by it. Rule: cross at 45 s, then every 20 s one cross
      while three screenshots over 15 s differ by under 1.0 (mean grey, 480x270). Presses: 45 s, 125 s, 245 s; at the
      other ten checks the picture was changing (`runs/t3s-vunset.keys` on the box). Screens (private, on the box only):
      black to 11 s; the bonus dialog with a spinner from 26 s; speckle blocks from 40 s, before the first press; the 45-s
      press left the dialog up to 120 s; after the 125-s press, from 130 s, the brightness-calibration screen (a picture and a line
      of text, the top session's reading of t150s), under dense fine speckle; after the 245-s press, from 250 s, the
      difficulty-choice screen over 3D art (its reading of t280s), heavily corrupted by colour blocks. The window title read
      28-30 fps there (the top session's reading). The flip rate from the journal's frame-profile lines is 21.2/s for 0-30 s and 25.9-27.3/s
      in each later 30-s window: a normal build with diagnosis on, so a diagnosis figure. No stall, no GPU fault, resets 1 -> 1,
      fault records unchanged at 30, exit 124 at the bound. The only unresolved-import stub calls came in the first 2 s
      (libkernel yu17wG8L5FI ×6, Http DK+GoXCNT04, NpSessionSignaling ×2); none came after a press. The flip-1200 dump
      already showed 1.32 M non-zero bytes against 0.46 M at flip 900, and the count rose to 1.57 M by flip 2100.
38. *The speckle, offline then one run pair (build normal `58d4376e`, lean `cdbb35d0`; `t3u.sh`, 22:13-22:16, 60 s each,
      cross at 45 s; first in place, then `BC5_0439_DCC_COPY=1`).* The top session's five questions of 11-21 ~22:45:
    - Keys (ph439/kh439). On the calibration screen of item 37 (t 142-242 s), 91 % of the draw's keys are compressed codes
      (0x66 alone 78 %), 0xFF 3.7 %, clear codes 5.5 %. On the difficulty screen (t 253-276 s) 34 % are compressed and 60 % are
      0x40 (clear 0001). The registered keys (the display copy, 0x28000 bytes behind) hold the same codes. They differ only in
      0x00/0x40 counts, as a display copy in its own layout would.
      So the title's final draw into the display surface is DCC-compressed, and the display keys are a copy of the same
      codes. The title does not decompress for the flip: on the console the display engine reads the surface compressed
      (design section 2).
    - The pass (question 2). Its block is the title's own draw block: BASE = the surface, DCC_BASE = the draw's
      (registered - 0x28000), INFO 0x10008024 (COLOR_8_8_8_8 UNORM, DCC_ENABLE), DCC_CONTROL 0x00080208
      (MAX_UNCOMPRESSED 256 B, MAX_COMPRESSED 64 B, INDEPENDENT_64B_BLOCKS, ENABLE_CONSTANT_ENCODE_REG_WRITE, no lossy, no
      128B blocks), ATTRIB3 0x4dc6c000 (SW_MODE 27 = 64KB_R_X, DCC_PIPE_ALIGNED, CMASK_PIPE_ALIGNED, RESOURCE_LEVEL 1),
      ATTRIB2 3840x2160, CB_DCC_CONTROL 0x10 (field names: Mesa 0866ae7 gfx10.json). The result: in every sample pass of
      both runs, 0 of 163,840 key bytes changed. 90.5 % of the keys were still compressed after the pass on the dialog
      screen. The pass decompresses nothing, so the present shows compressed blocks as plain bytes: the dots and line
      patterns are those blocks, and they grow with content.
      The likely cause is our IB's CB_SHADER_MASK 0. Mesa 0866ae7 `radv_cmd_buffer.c` `radv_bind_fragment_output_state`: with
      any custom blend mode "CB_SHADER_MASK should be set to enable writes to all four channels of MRT0" (0xf). The design
      (section 3) said 0xf; `dc0439.hpp` wrote 0, and its test checked 0. Now a switch, `BC5_0439_DC_SHADER_MASK`
      (default 0 as before), with a det-test case; the run with 0xf is pending.
    - In place against the copy (question 3): no difference can show while the pass changes nothing. The copy mode works:
      33,177,600 + 163,840 bytes saved in 2-12 ms, restored after the present in 2-4 ms, every flip paired.
    - The title's own modes (question 4, cm439): its GFX jobs, chains followed, never wrote CB_COLOR_CONTROL through
      SET_CONTEXT_REG (normal 0, every count 0 but our own pass's MODE 6, 1,201 by 50 s). The title must set the register
      another way (LOAD_CONTEXT_REG or a state the catcher does not read), so question 4 is not answered by this catcher.
    - Health: both runs had no stall, no GPU fault and resets 1 -> 1. The 45-s press left the dialog up, as in item 37.
39. *The fix: `BC5_0439_DC_SHADER_MASK=15` (build normal `14c82ec9`, `t3v.sh`, 22:25-22:31; 150 s each, crosses at 45 s and
      125 s; in place, then with `BC5_0439_DCC_COPY=1`).*
    - After the pass, in every sample flip of both runs: 0.0 % compressed codes, 0xFF 94.3 %, 0x00 5.7 %. The pass changed
      123,873-129,600 of the 163,840 key bytes. The 7,424 0x00 bytes are the same in every histogram before and after,
      most likely padding outside the surface.
    - Screens (private, on the box), the same in both runs:
      - 4-11 s: black;
      - from 26 s: the brightness-calibration screen, clean and legible ("adjust brightness until the wolf's eyes are
        barely visible");
      - after the 45-s press, from 50 s: the difficulty choice ("Medium") over dark art with a lit figure on the right;
      - after the 125-s press, from 130 s: the next choice screen ("Standard").
      No speckle.
    - Still seen: bursts of coloured light blobs over the art at some shots (80-100 s and 130 s in place, 50-60 s and 80 s
      with the copy). Twice a frame is black except a coloured strip at the left edge (120 s in place, 50 s with the
      copy). Whether the blobs are the title's own effect is not known. The strips look like a partly drawn frame.
    - In place against the copy: no difference in the keys or the screens. The copy costs a 2-ms save and a 3-ms restore per
      flip. The pass's job and drain take 3 ms.
    - Rate (diagnosis figure, frame-profile lines per 30 s): in place 21.5, 27.2, 27.2, 24.5, 26.2; copy 22.1, 24.4, 24.6,
      24.2, 22.1.
    - Health: both runs had no stall, no GPU fault, resets 1 -> 1 and fault records 30.
    - The pass's other state against RADV's DCC decompress (Mesa 0866ae7 `meta/radv_meta_fast_clear.c` `get_pipeline`,
      `radv_cmd_buffer.c` `radv_bind_fragment_output_state`) matches:
      - CB_TARGET_MASK 0xf (colorWriteMask RGBA);
      - no blend (the clear state), ROP3 copy;
      - no depth or stencil (DB_Z_INFO and DB_STENCIL_INFO with no format, DB_DEPTH_CONTROL 0);
      - no cull (PA_SU_SC_MODE_CNTL 0), rasterizer discard off (PA_CL_CLIP_CNTL bit 22 clear);
      - one sample, PA_SC_AA_MASK all ones;
      - window, screen, generic and viewport scissors at 3840x2160, a RECTLIST over the whole surface;
      - a PS with both export formats ZERO, which gfx10 allows (RADV adds a null export only up to GFX9, or with a
        discard).
      CB_SHADER_MASK was the one difference.
40. *CB_SHADER_MASK 0xf fixed in the pass (the top session's decision, 11-21 ~22:45).* `dc0439.hpp` `build` now always
      writes 0xf (Mesa 0866ae7 `radv_cmd_buffer.c` `radv_bind_fragment_output_state`). The switch `BC5_0439_DC_SHADER_MASK` is
      gone, and the det test checks 0xf. In place is the mode. The copy mode (`BC5_0439_DCC_COPY`) stays as an off switch until
      the bake, then goes if unused. Two picture defects are open, for after the exploration run:
      - (a) coloured light blobs over the 3D background of the choice screens (purple, magenta and green points with halos),
        which look like bloom over wrong or uninitialised bright pixels;
      - (b) frames black except a strip at the left and top edges with a bright green-white gradient: the 3D scene missing
        from most of the frame while the UI is drawn.
41. *The exploration run (build normal `9b515a04` with the fixed pass, `t3w.sh`, 22:40:08-22:43:48; bound 600 s, crosses by the
      still-picture rule).*
    - Presses: 45 s, 125 s, 145 s, 205 s.
    - Screens (private, on the box):
      - from 50 s: the difficulty choice ("Medium");
      - from 130 s: "Select an experience" ("Standard");
      - from 150 s: "Graphics mode" ("Quality", target 30 fps at a higher resolution).
      Defects (a) and (b) are seen again at 150, 160 and 180 s.
    - The end: about 7 s after the 205-s press confirmed the graphics mode, the emulator died with SIGFPE (exit 136,
      "Floating point exception", 22:43:43, no core: `ulimit -c 0`). No GPU fault, resets 1 -> 1, fault records 30. The stall
      watch saw no stall.
      The log's last lines are AJM batches (ATRAC9 decoders; 2,517 initialised in the run, the ambience streams playing
      from the start), the last a batch for context 1, codec 1, instance 0x403b. A "MovieDecoder" thread had waited on a
      condition variable since the start (205 s, KytyPlus's stall line). Which code divided by zero is not known.
    - No unresolved-import stub was called after 1.8 s.
    - Memory: GTT 11.4 GiB from 30 s on, flat; the emulator's RssAnon 159-168 MiB; MemAvailable 2.1-2.2 GiB; VRAM 0.47 GiB.
    - Rate (diagnosis figure, frame-profile lines per 30 s): 21.5, then 27.5-28.3, and 24.8 in 180-210 s.
42. *The SIGFPE under gdb (build normal `9b515a04`, `t3g.sh` + `k439/fpe439.gdb` through `play439.sh P439_GDB`, 22:50:45-22:53:19;
      crosses at 45, 125, 145 and 205 s).*
    - gdb setup: the emulator ran as gdb's child in the distrobox. SIGSEGV, SIGBUS, SIGILL, SIGUSR1/2, SIGXCPU, SIGPIPE,
      SIGCHLD and SIG32-40 were passed silently; only SIGFPE stopped. A first try that also passed SIGTRAP died at start
      (gdb's own breakpoints use it).
    - The fault came about 7 s after the 145-s press (earlier than item 41's 205 s; presses at fixed times land on
      different screens), with the timing otherwise normal.
    - Where: thread "ScreamWorker2" (the title's audio engine; its streams are `sounds/scream/...`), pc 0x9003502d2 =
      eboot + 0x3502d2. The eboot is loaded at 0x900000000 (KytyPrivateMemory), so this is guest code, not the host's.
    - The instruction: `div esi` with esi = 0, loaded just before from `[r14 + 0x1d4]` (r14 = 0x100ce9ba90, in the title's
      direct memory). The code is `mov esi, [r14+0x1d4]; xor edx, edx; lea eax, [rax+rax-2]; imul ecx, eax; add ecx, esi;
      mov eax, ecx; div esi`, a round-up to a multiple of that field. Other registers: rax = rcx = 6120, r15 = 0x2a000.
    - Not yet known: which call filled the field. The host's AJM ATRAC9 decoder answers its codec-info sideband (super frame
      size, frames per super frame, frame samples) and its format with 0 while an instance is not initialised (KytyPlus
      f266548 `src/libs/ajm/atrac9_decoder.h` WriteCodecInfo, GetFormat). That is a candidate, unproven. The log has no
      AT9 config rejections (1,761 decoders initialised).
43. *The audio catcher (build normal `b5aaeb4e`, `k439/mkfz439.py` over ajm.cpp and libAudio2.cpp, `BC5_0439_AUDIO_CATCH=1`;
      gdb run 23:04-23:07, crosses at 45, 125 and 145 s).*
    - The SIGFPE came again at eboot+0x3502d2, this time on "ScreamWorker1".
    - The thread's last AJM calls: AjmInstanceCreate, AjmBatchJobControl (the init job), then AjmDecAt9ParseConfigData with
      config bytes `30 72 c0 fe`. Our parser returned INVALID_PARAMETER (libatrac9 init 0x81000000) and left the caller's
      info as it was; the SIGFPE followed.
    - The object (r14): 12 channels (byte +0xa4), codec type 1 (+0x1cc), the grain +0x1d4 = 0, +0x1e4..+0x1ef = `40 e0 16 00
      00 01 00 00 30 72 c0 fe`. The rbp chain of callers is eboot+0x350d58, +0x3407dd, +0x340b89, +0x13e4537, +0x13e1e39,
      +0x24faa0, +0x24f28d. exp 0440's reading: the grain is written only when the AT9 parse succeeds.
    - The cause is the host parser's refusal. Its reason is the first byte 0x30, where libatrac9 wants the sync byte 0xFE.
      Channel configurations 6 and 7 (mono and dual mono haptic layouts, exp 0241) are already mapped before libatrac9 is
      called, so they are not it. Every config seen before starts `fe 7x`. Open: where the title takes these four bytes
      from and in which form (exp 0440 is asked), and so what the console's parser accepts.
    - No other ZERO line in the run.
44. *The cause and the fix (dm439, build normal `389521e4`).*
    - `30 72 c0 fe` is an ATRAC9 DMC (multichannel) config. vgmstream's `parse_config_data` (vendored in KytyPlus f266548,
      `3rdparty/vgmstream-atrac9/src/coding/libs/atrac9_dec.c`) reads sync 0x30 as a "DMC header config": profile 4 bits,
      dmc_channels 6 bits + 1, data_version 1 bit, frame_size 11 bits + 1, superframe_index 2 bits. Here that is 48 kHz,
      12 channels, 64-byte frames, 4 frames of 256 samples, a 3,072-byte superframe.
    - libatrac9 knows only sync 0xFE, and AnyPS5 f145139's ParseConfigData uses libatrac9 too. exp 0440 read the title's
      code: it copies the dword unchanged from its stream record (+0x18) into the object (+0x1ec), passes that address to
      ParseConfigData, and puts the same bytes at +8 of its 16-byte initialise job ({total samples, skip samples},
      config, reserved).
    - Fix (`k439/mkdm439.py`, `k439/dm0439.hpp`, no switch): ParseConfigData answers a 0x30 config from
      `atrac9_get_config_info`; the AT9 decoder takes it through vgmstream only, on the frame path the haptic layouts
      already use; that path's S32 buffer is sized by the stream (it was 2 x 256).
    - Det test (`test_dm0439.cpp`): PASS. The planted old behaviour FAILs (8 failures).
    - In the title (walk at 00:10:16): right after the graphics-mode confirm the 12-channel stream set up, through
      ParseConfigData and the decoder init (both lines present), with no SIGFPE and no ZERO line.
45. *The graphics-mode options (walk 2, 00:14:21; shots private).* Quality ("target 30 fps at a higher resolution"),
    Performance ("target 60 fps at a lower resolution"; cutscenes always 30 fps) and Ray Tracing ("higher-quality
    lighting", 30 fps at an intermediate resolution). The default cursor is on Quality; one d-pad right is Performance. The
    run script now checks the option by comparing the name area against reference shots before it confirms.
46. *A compute hang on cloth (F893 draft).*
    - Walk 1 hung 2 s after confirming Quality: kernel ring comp_1.1.0 timed out and the reset succeeded. Walk 2 hung
      1.2 s after Ray Tracing was highlighted, with no confirm; with Performance highlighted it ran 15 s.
    - The job: guest queue 49, a new 1831-dword acb ("CS Cloth", 47 one-group dispatches of six programs, "Build Chain
      Links" at its end).
    - Its waits are on its own labels. The second RELEASE_MEM never landed, because four early dispatches never finish:
      in each group a few waves spin in a BVH traversal loop (`image_bvh_intersect_ray`, node stack in LDS and scratch,
      exit on -1) while the rest wait at the next barrier. All 40 halted waves are on shader array 1.
    - Not the zero cover: every pointer and label lies in the eager views.
    - Candidates: BVH or scratch-stack contents, or the scratch ring (register 0x218 = 0x10500, base 0x5000001000)
      against our wave placement.
    - After these ring resets, the next Performance run hung at 26 s with nothing pressed, on gfx_0 and two compute
      rings; before the first reset the same build ran 600 s clean. State left by the resets was suspected; refuted by
      the 06:28 run on a fresh boot (item 48).
47. *The cloth hang is the second title's flat-aperture traversal (F249), offline.*
    - The two stuck programs (0x8000143400, 0x8000175900) push their BVH stack with `flat_store_dword`. The address's
      high dword is med3(`s_brev_b32 sN, 1` = 0x80000000, the literal 0x70000000, the packed stack pointer): the
      console's fixed LDS and private apertures. amdgpu's graphics VMIDs use 0x2000... and 0x1000... (the patch's
      `flat_aperture_fix` comment, exp 0190, Linux gmc_v10_0.c), so the push leaves both apertures and the wave is
      halted. F249 found the same in the second title, with no fault line, the same "endless" traversal.
    - The patch already rewrites this by pattern: `BC5_DIRECT_FLAT_APERTURE=1` scans each dispatched program for the
      med3/s_brev pair and patches the two constants. It is only on for TITLE2 (`kTitleDefaults`).
    - In this run it was off: no "flat aperture" journal line, and the word is absent from the record's environment.
    - The pattern scan over exp 0440's memory dump finds 18 sites in each of the two stuck programs (each with its
      `s_brev_b32`) and none in the other four cloth programs, whose waves never hang.
    - The two "D" views the waves point into (0x8031c00000, 0x8036e00000) are by-data views of direct memory, each with
      a full 2 MiB GPU mapping: not zero cover.
    - Label 0x201c152190 read 1 with earlier dispatches' waves still resident. That is either a stale 1 or a RELEASE_MEM
      that did not wait for the waves; it is secondary, since the waves are halted either way.
    - Test, with no build, after the reboot: the Ray Tracing walk with `BC5_DIRECT_FLAT_APERTURE=1`. If it passes, the
      word goes to `kSoft` for every title: the scan is by pattern, and a title without the pattern is untouched.
    - exp 0441's listing (llvm-mc gfx1013) gives per program 6 intersections, 18 flat-store pushes, 6 scratch-load pops
      (plus ds_read) and 0 scratch stores. The scratch ring (COMPUTE_TMPRING_SIZE 0x10500: 1,280 waves of 16 units, base
      0x5000001000) is in the eager view.
    - A testable copy of the patch's scan (`k439/fa0439.hpp`, `test_fa0439.cpp`/`.sh`) passes on synthetic programs:
      three pushes behind one s_brev rewritten, idempotent; no brev, another literal, after s_endpgm, or a brev too far
      back, all untouched. Planted bugs (a push skipped, the LDS half left) FAIL.
    - Next run: read SH_MEM_BASES / SH_MEM_CONFIG for the emulator's VMID with umr, with `uname -r`.
48. *~~Ring resets leave the box unfit for further runs~~: refuted (2026-11-22 06:28).* The claim: after the first
    compute-ring reset (00:12) every run hung, each earlier and on more rings (00:16 three rings; 00:20 at 26 s with
    nothing pressed, three rings), though every reset reported success.
    - The refutation: the Performance run of 06:28 (fresh boot 2b5fbf12, no reset before it; on the new kernel
      7.3.4-ogc8.1.fc45, Mesa 26.2.7-1, libdrm 2.4.134-2) hung at 25.2 s with nothing pressed. gfx_0.0.0, comp_1.1.0,
      comp_1.0.1 and comp_1.2.0 timed out within 7 ms, and every reset succeeded (record
      `~/bc5-data/captures/faults/20261122-062903`).
    - Its signature is the 00:20 hang's (record `-002016`): the dcb of 412 dwords and the acb of 3452 dwords (guest queue
      40) were submitted at about 23.2 s. The acb waits at dword 2806 for label 0x2000008040 to read 1; the label read 0
      (not met at submit, kept for the GPU). umr found no active waves.
    - The fault records' environments are identical for 00:12 (147 s), 00:16 (151 s) and 00:20 (26 s), and 06:28 adds
      only `BC5_DIRECT_FLAT_APERTURE=1`, which rewrote nothing before the hang (no "flat aperture" line). No switch
      separates the 25-s hangs from the runs that got further, and neither 25-s run had a key pressed. A start-up race at
      that frame is the leading reading.
    - The umr watchdog (`BC5_DIRECT_UMR_ON_TIMEOUT`, 0.9 s into a completion wait, `halt_waves -wa none`) was on in all
      of them. It fired once, in the hang, after the hung jobs' submit. A rerun with it off is the test (06:32).
49. *The early hang at about 25 s, on the new system image (kernel 7.3.4 and Mesa 26.2.7 changed together; 2026-11-22 06:28-06:55).*
    - The versions: the maintainer's reboot at 06:25 applied a staged image update, 45.20261117.1 (it was 45.20261112).
      - Kernel 7.3.4-ogc8.1.fc45 (it was 7.3.3-ogc1.1.fc45), read with `uname -r`.
      - Mesa 26.2.7-1 (it was 26.2.6-2); libdrm 2.4.134-2 unchanged; both read with `rpm -q`.
      - GPU firmware unchanged (`amdgpu_firmware_info`, 06:38): ME 0x63, PFP 0x94, CE 0x25 (feature 32), RLC 0xd,
        MEC/MEC2 0x90 (feature 32), SMC 88.6.0, VBIOS 113-AMDRBN-003. This is identical to exp 0005's
        `raw/status.txt` (2026-09-29).
      - Comparisons with yesterday below are "on the new image": nothing isolates the kernel from Mesa.
    - Three runs, every one hung at 24.3-25.2 s with nothing pressed, on four or five rings at once. Every reset
      succeeded.
      - 06:28: build 389521e4 with `BC5_DIRECT_FLAT_APERTURE=1`.
      - 06:33: the same with the umr watchdog off.
      - 06:35: yesterday's passing environment, unchanged.
      - Records `~/bc5-data/captures/faults/20261122-062903`, `-063343`, `-063623`.
      - Yesterday on 7.3.3 the same build and environment hung there once in six runs (00:19, record `-002016`).
    - Ruled out:
      - The umr watchdog: off at 06:33.
      - The flat-aperture word: no "flat aperture" line in any of the runs, and off at 06:35.
      - The press schedule: the first press is written at 45 s.
      - Any other switch: the record environments are identical apart from those two.
    - The hang: an acb of 3452 dwords (guest queue 40) waits at dword 2806 (WAIT_REG_MEM, == 1) on label 0x2000008040.
      It wrote that label itself at dword 2655: RELEASE_MEM event 0x28 (BOTTOM_OF_PIPE_TS, Mesa
      `src/amd/registers/gfx10.json:881` at 0866ae7) index 5, CACHE_POLICY 0, DST_SEL 1 (TC_L2), DATA_SEL 2 (64-bit data), data 1. the dump session (exp 0440/0441): the same
      form writes all 87 RELEASE_MEM labels of its first-frame dump and ran for 270 frames, so the form alone does not
      explain the hang.
      After the timeout the label reads 0, and umr found no waves (06:28). A dcb of 412 dwords times out beside it.
    - The host passes that RELEASE_MEM unchanged (`backend/src/policy.cpp:694-713`). It rewrites only CS_DONE/index 6
      without data on the GFX ring, and clears INT_SEL, which is already 0 here.
    - The form is one the compute engine implements: RADV's async-compute fence is BOTTOM_OF_PIPE_TS index 5
      (`src/amd/vulkan/radv_cmd_buffer.c:1985`, `src/amd/common/ac_cmdbuf_cp.c:472-510`, Mesa 0866ae7). It adds GL2_WB,
      DST_SEL MEM and INT_SEL SEND_DATA_AFTER_WR_CONFIRM. TODO(verify): the kernel's compute fence
      (`gfx_v10_0_ring_emit_fence`, shared by gfx and compute) uses CACHE_FLUSH_AND_INV_TS_EVENT index 5 with GCR
      flags; this was read from a summary of v6.18, not yet pinned to a line.
    - `BC5_DIRECT_ACB_RINGS=0` (every acb on the GFX ring), three runs at 06:40, 06:41 and 06:50: all hung, at 24.9,
      25.6 and 25.5 s (records `-064105`, `-064216`, `-065041`).
      - Only gfx_0.0.0 timed out. The first pair was dcb 412 (as before) and an acb of 226 dwords from guest queue 24.
        acb 226 holds one met wait, three DISPATCH_DIRECT of program 0x901e18200 (1,376,256, 1,376,256 and
        344,064 groups), and a RELEASE_MEM 0x1ee to 0x20000082e0; that label still read 0x1ed.
      - In the compute-ring runs this acb was submitted 2 ms before acb 3452.
      - These are post-reset runs (R55, R60), not evidence against a ring layout; the compute-ring question stays
        open. Within them the hang sits at one frame (about 23.2 s), and acb 3452's wait is downstream of it.
      - Raw counts, not independent: 7 of 7 hung on this boot.
    - Marked per LESSONS R55: only the 06:28 run is the boot's first. The 06:33, 06:35, 06:40, 06:41 and 06:50 runs,
      and a stopped 06:55 run, came after GPU resets on the same boot (2b5fbf12). They are not independent repeats.
      - Yesterday's single hang there (00:19) also followed resets (00:12, 00:16).
      - The clean figures: 1 of 1 hung on the new image (06:28, the first run after the 06:25 reboot). On 7.3.3, boot
        d4d739c7, all eight runs before that boot's first GPU reset (21:51 to 00:10; "resets 1", the boot's
        baseline line) passed this point.
      - The 6 of 6 on one boot after a kernel and Mesa change does not isolate the cause (Codex, 11-22).
      - Continuing the series after the first reset broke R55's STOP. It was stopped at 06:55, and further runs wait
        for a slot from TOP.
    - The clock trace of the 06:55 run (`k439/clk439.sh`, 20 Hz, 0-25 s): hwmon freq1_input reads 6-100 MHz
      throughout, while power reads 73-121 W. The governor's journal gives a range of 1850-2150 MHz, and pp_dpm_sclk
      marks 24 MHz at idle. The sensor contradicts the power figures, so this trace does not settle the clock
      question.
      - That run hung too (comp_1.1.0 timeout at about 25 s). It was stopped at the timeout, so no fault record.
    - the dump session's (exp 0440/0441) decider, label 4 (0x2000000080, written at 2734 with CACHE_POLICY 3, bypass): in all four
      compute-ring hangs (00:20, 06:28, 06:33, 06:35) it reads the written value minus one (0x202 for 0x203, and so
      on). That rules out a write left in L2. Both releases are end-of-pipe events, so the CP may have parsed past them.
      The exact statement (the dump session's (exp 0440/0441) correction): neither end-of-pipe write fired, so the compute pipe never
      reported the clouds part (235-2650, new on this queue) done. Either the CP is stuck on a packet there, or a
      dispatch there never completes. Candidates: the six GDS-fed indirect dispatches (885-1294) and the sixteen at
      2016-2511. The CP's IB position separates the two cases.
    - The CP's position, from the kernel's saved devcoredump (`~/bc5-data/captures/devcoredump/20261122-062904-devcd1.txt`,
      the clean run; its gfx_v10_0 IP dump holds every MEC queue's HQD registers and 8 header dumps):
      - mec0 pipe2 q0 runs acb 3452. Its header dumps match the raw packets 885, 879, 876, 871, 868, 864, 861 and 858,
        newest first, and HQD_IB_RPTR is 0x379 = 889.
      - So the CP fetched the DISPATCH_INDIRECT at 885 (MEC form, arguments at 0x500085d0c0, initiator 0x41) and never
        got past it. This is the first of the indirect dispatches fed through GDS.
      - The post-reset dumps devcd2 (06:33) and devcd3 (06:35) show the same IB_RPTR 0x379.
      - A second queue (pipe0 q1) also stands right after a DISPATCH_INDIRECT, in another job of that frame.
      - GRBM_STATUS 0xe5f15028: CP, SPI, TA, SX, SC, DB and CB busy, GDS idle. HQD_ERROR is 0.
      - The host attaches the GDS BO to every job, compute rings included (`backend/include/bc5/direct.hpp:164`,
        `with_gds` true).
    - The arguments are not the cause. The timeout probe prints the indirect arguments as read after the timeout, and
      they are identical in all four compute-ring hangs (00:20 on the old image, post-reset; 06:28 clean; 06:33 and
      06:35 post-reset):
      - 885, 1111 and 1261 (arguments at 0x500085d0c0): 13104 x 1 x 1.
      - 920, 1144 and 1294: 3280 x 1 x 1.
      - The sixteen at 2016-2511: 0 x 1 x 1.
      - The stuck dispatch at 885 runs program 0x8000397500: RSRC2 0x888 (no scratch, LDS 0), 8x8x1 threads.
      - SPI is busy, and no waves were found at 0.9 s. That reads as a wave launch held back, not long-running waves;
        not proven.
    - The GFX layout (`ACB_RINGS=0`, devcd4, post-reset) shows the same picture. The PFP and ME header dumps end in
      SET_BASE and the GFX-form DISPATCH_INDIRECT (c0011600), and GRBM_STATUS 0xa0400028 is CP and SPI busy only. acb
      3452 was submitted 1 ms after acb 226 there, so acb 226 is not its victim.
    - The timeouts: the host's completion wait is 2 s, and so is amdgpu's default lockup_timeout. The default came with
      upstream commit 1bea57ea7544 ("reduce queue timeout to 2 seconds v2"), first in v6.19, and both OGC tags (7.3.3-ogc1,
      7.3.4-ogc8) carry 2000 ms. That is TOP's reader's claim, with sources; a second reader has not checked it. So the
      old image had the same 2 s.
    - The host's GPU mapping changes stop at about 22.9 s. Every submit after that, up to and including the hung frame,
      shows "mappings 38656". Nothing was mapped or unmapped in the last ~280 ms.
    - The reading that led until run 1 (WITHDRAWN as the cause of this stall by run 1 below): the CP fetched the
      arguments at 885 before the GPU's own copy had landed.
      - The ten DMA_DATA (four GDS fills, six GDS-to-memory copies through L2 under lru) all have CP_SYNC clear, and
        our filter passes them unchanged. A det test against the shared `policy.cpp` confirms it.
      - The clouds buffer is the first place in the run where an indirect dispatch follows its copy with only
        register sets between (45, 45 and 14 dwords).
      - F107 (exp 0050) is the same race in the second title. Its fix, `BC5_DIRECT_DMA_SYNC`, is a TITLE2 default
        and acts on the GFX ring only, so it was off in every run here, the `ACB_RINGS=0` ones included (their
        environments have no such word).
    - The private build for the clean boot: normal `0a0f31d6`, lean `802448cf`, private backend archive `256144d7`
      (2026-11-22 08:14; before D2 and F it was `75292fb5`/`f3f37317`); the shared builds are unchanged. It adds:
      - The argument probe (`BC5_0439_ARGS_PROBE`; `k439/pa0439.hpp`, `mkpa439.py`): each job's indirect arguments as
        the host sees them at the submit and at the timeout, its DMA_DATA, the mapping under each argument address,
        the first indirect dispatch's two 3D image descriptors, and the other jobs with an indirect dispatch in the
        100 ms before.
      - The candidates, each behind its own switch and off by default (`k439/be-ds439.diff`, `k439/ds0439.hpp`):
        - D, `BC5_0439_DMA_SYNC_MEC`: exp 0050's wait on the compute rings too.
        - C, `BC5_0439_ARGS_GL2WB`: an ACQUIRE_MEM GL2_WB after it.
        - B, `BC5_0439_DMA_DST_BYPASS`: DST_CACHE_POLICY bypass on DMA_DATA to an address through L2.
        - E, `BC5_0439_WAVES_UNLIMITED`, diagnosis only: WAVES_PER_SH of COMPUTE_RESOURCE_LIMITS cleared.
      - Det tests: `test_pa0439` PASS, with plants READ and DMA failing. `test_dsp0439` (D and C) PASS, with plant
        NOWB failing. `test_ds0439` (B and E against the private `policy.cpp`) PASS on and off; the shared
        `policy.cpp` with the switches set fails, as it should.
    - The clean-boot plan (TOP's): exp 0438's smoke first; then `t3one.sh 75292fb5 fixes` (unit t3one-fx, default
      rings, D + B + C on, the probe on, the umr watchdog off); then `... control` (t3one-ctl) only if run 1 left zero
      kernel lines. Each unit has the gate first and no chain.
    - The gate (`k439/gate439.sh`) refuses a failed or empty kernel log read (rc 3) and any amdgpu/drm timeout or
      reset line (rc 2). It leaves bc5-gpu-watch's start line out: that line names amdgpu resets on every boot, so the
      first gate would have refused every clean boot. It was dry-run on stand-ins: failed, empty, missing, clean,
      dirty, and this boot's log before its first hang (admitted).
    - The title-free tests for a later clean boot (`k439/id439.sh`; `backend/experiments/dispatch-min --indirect
      zero|async|async-sync [--waves-limit 7d] [--two-rings]`) are checked with `--dump-ib` only.
    - Why the host supplies this order (the dump session's census, exp 0440/0441: 10 buffers, 3,948 packets): the
      title's library writes CP_SYNC on every GDS DMA_DATA and a PFP_SYNC_ME before every indirect dispatch on the GFX
      queue (7 of 7), and neither on its compute queues (0 of 27). So the console's compute engine keeps DMA_DATA in
      order by itself and this part's does not. Supplying the order on the host is translation, not a workaround.
    - Our own filter removes the GFX-queue half of that order. The shared `policy.cpp:639-646` strips CP_SYNC from
      every GDS DMA_DATA, on any ring, whenever `drop_gds` is false and there is no GDS shadow, which is the unit's
      setting.
      - A det test on the shared `policy.cpp` (`k439/test_gs0439.cpp`) turns the dcb's copy 0xa0306000 into 0x20306000
        and its fill 0xc6104000 into 0x46104000 (`gds_rewrites` 2).
      - So the dcb's seven title-synced GDS packets ran unsynced in every third-title run, with
        `BC5_DIRECT_DMA_SYNC` off for this title.
      - The rule's comment cites exp 0016's run 49, but runs 50-54 there traced that stall to indirect draws fed by
        GDS counters that were not the console's, not to CP_SYNC.
      - Run 1 therefore also sets `BC5_DIRECT_DMA_SYNC=1` (exp 0050's loop on the GFX ring); the control leaves it off.
      - Candidate F (`BC5_0439_KEEP_GDS_SYNC`, built, off in run 1) keeps the title's CP_SYNC on GDS DMA_DATA. Det
        test `test_gs0439`: PASS kept on and stripped off; the shared `policy.cpp` with the switch set FAILs, as it
        should. F has its own run on the boot, in place of `BC5_DIRECT_DMA_SYNC=1`: a pass means the strip can go
        from the shared filter.
      - The clean-boot order (TOP): exp 0438's smoke; `t3one.sh 0a0f31d6 fixes`; `... f`; the expected-to-pass
        title-free cases; `... control`; the may-hang cases. Each step runs only on zero kernel lines before it.
    - Candidate D-label (`BC5_0439_DMA_SYNC_LABEL`, `k439/ds0439.hpp`): the same zero-byte sync also before the first
      label write (RELEASE_MEM, EVENT_WRITE_EOP, WRITE_DATA to memory) after an unsynced DMA_DATA, and at the end of a
      buffer that ends with one pending.
      - It covers queue 24's nine copies, whose readers are nine GFX-form DISPATCH_INDIRECT in the dcb behind the label
        queue 24 releases before any dispatch of its own; D alone came after that release.
      - Det test (`test_dsp0439`): the three positions (before a dispatch, before a label write, at the end) PASS, and
        plants NOWB, NOLABEL and NOEND FAIL. On in run 1, off in the control.
    - Not covered by anything yet:
      - queue 0x1's GDS fills, whose consumers are shaders in other buffers;
      - arguments written by shaders. The sixteen at 2016-2511 rely on a CS_PARTIAL_FLUSH and on the engine reading
        arguments through L2.
    - Run 1, `t3one-fx`, on the clean boot c133d630 (2026-11-22 08:44; build `0a0f31d6`; D + D2 + B + C +
      `BC5_DIRECT_DMA_SYNC=1`, the probe on; the gate admitted 0 lines in 1698): it HUNG, a GPU fault 26.2 s after
      the start, exit 86.
      - Records: `~/bc5-data/captures/faults/20261122-084458`, devcoredump `20261122-084459-devcd1.txt`.
      - gfx_0.0.0, comp_1.3.0 and comp_1.1.0 timed out within 4 ms; 15 timeout or reset lines; the resets succeeded.
        The boot is closed (R60).
      - The same pair timed out: acb #7957 (3452, q40) and dcb #7955 (412). No press was reached; the frame
        profile stops at 24.018 s.
      - Probe: the six GDS-fed dispatches read 0 x 1 x 1 at the submit and 13104 (or 3280) x 1 x 1 at the timeout.
        Every earlier-frame job with an indirect dispatch also read 0 at its submit and completed: x = 0 in memory
        at the submit is normal, and the GPU writes x later in the frame.
      - B applied ("rewrite 12" against 6). D and C were inserted AND executed: the queue running acb 3452 (mec0
        pipe1 q0, IB_CONTROL 0xa41 = 0xa07 + 58 dwords of inserts, IB_RPTR 0x397) has as its last headers, newest
        first: DISPATCH_INDIRECT, ACQUIRE_MEM (C), two internal headers, the sync DMA_DATA (D), then SET_SH_REGs.
      - So the CP waited out the DMA sync, wrote L2 back, fetched the DISPATCH_INDIRECT with the copy landed, and
        stands behind it again.
      - "Stale x at fetch" is WITHDRAWN as the cause of this stall. D, D2, `BC5_DIRECT_DMA_SYNC` and F stay
        candidates on their own merits (the title's bytes justify the order: CP_SYNC on 7 of 7 GDS-queue copies,
        0 of 27 on the compute queues), but they are not the fix for this stall.
    - What stands after run 1: 13104 x 1 x 1 groups of program 0x8000397500 do not complete. A second queue stands
      behind its own DISPATCH_INDIRECT at the same time: guest queue 16's 1824-dword buffer of the same frame, at its
      third one (dword 867; IB_RPTR 0x385 = 867 + 4 + 30 with two of D/C's inserts; 0x367 = 871 at 06:33).
      CP, SPI and TA are busy. Two families remain: the waves cannot launch or do not retire (the wave limit 0x7d,
      two queues inside an indirect dispatch at once, something held by the GFX pipe), or the waves run and never
      end (the march loop on bad inputs). The next evidence has to be about waves, over several snapshots.
    - Open note, the F852 shape (not a candidate): acb 3452's waits at 62, 235 and 2749 were all judged met by the
      host at submit and dropped.
      - 235 waits on 0x2000008020 == 1, a per-frame flag the dcb writes by an end-of-pipe release in a chained
        segment (0 in frame 1). wd438 at 08:44 (#21429, #21434) and 06:28 (#21233, #21238): "memory 0x1 … writer in
        flight 0". The dcb was submitted 5 ms before the acb.
      - `register_label_writes` (private unit :9700) scans only a job's top-level dwords, never its chained pieces.
        So the dcb's label writes are not in `g_plw`, and F848's presets, r438 and ng438 cannot see them.
      - The keep rule (:7852) keeps a cross-queue wait for the GPU only while memory does not satisfy it.
      - TOP's reading: a 1 at submit means this frame's release had already fired, so the GPU too would have found
        the wait met. It stays a note unless a record shows the 1 was an earlier frame's.
      - 2749 waits for the frame number and cannot be stale. 62's label is a slot that changes from run to run.
      - The next run's record lists both labels at every kept job's submit (tag lb439), and the first submit at which
        0x2000008020 read 1.
    - The writer scan does not follow chains (TOP: a finding of its own; exp 0440's choice to leave it top-level is
      withdrawn).
      - `register_label_writes` (private unit :9700, called at :17043) and the F10 write list (:8587) scan only a
        job's top-level dwords. This title's dcb is one chain of 73 segments, so its label releases are never
        registered.
      - Blinded by that, all on `g_plw`:
        - `ring_will_satisfy` (:10577): the keep rule's "a ring will satisfy this wait", at :7852 and :10889;
        - F848's XQ preset and fence, and r438's early registration (`r438_begin`/`r438_end`, :10171, :10196);
        - ng438's and wd438's "writer in flight" (`wd438_record`, :10325);
        - `chain_given_up_at` (:8724).
      - So for this title every cross-queue wait on a dcb label is judged from memory. If memory satisfies it, it
        is dropped at submit. If not, it is served on the CPU or given up, never kept for the GPU.
    - Candidate G (`BC5_0439_KEEP_XQ_WAITS`, `k439/kw0439.hpp`, glue in `mkpa439.py`, default off): on a compute ring,
      a wait on a label the buffer does not write itself is kept for the GPU even when memory satisfies it at the
      submit, as the console decides it at the packet. The open chain is flushed first, as on the unsatisfied path
      (:10814).
      - No case found where keeping it can deadlock on our side but not on the console. A kept satisfied wait
        passes at the packet unless the title rewrites the label first. Its later writer is then on another ring,
        in this queue's own later buffers (the console's own order), or in the flushed chain.
      - The acb gate holds only waits memory does not satisfy (`acb_ready`, :8055), so it never holds a writer
        behind such a buffer.
      - Det test `test_kw0439`: all 32 input combinations PASS; plant GFX FAILs. On in `t3one-wv`.
    - Candidate CW (`BC5_0439_CHAIN_WRITERS`, `k439/cw0439.hpp`, default off): after a job's top-level registration,
      its chained and called pieces (`ib_chain::collect`, the same walk as the import scans) are registered too, under
      the same seq and ring. Every packet start of a piece is taken as executed.
      - Risk: a piece's label write that the filter would drop is registered anyway, and a wait on it would then be
        kept for the GPU and never met. RELEASE_MEM, EVENT_WRITE_EOP and WRITE_DATA to memory pass the filter
        unchanged.
      - Det test `test_cw0439` on a stand-in chain below 2^40: a chain to piece A (a RELEASE_MEM) and a call from A
        to piece B (a WRITE_DATA). Both pieces are visited, both labels found, PASS; plant FIRST FAILs. Off in
        `t3one-wv` unless TOP adds it.
    - Boot c47f9290 (clean; exp 0442's first-title smoke passed first with 0 kernel lines), 2026-11-22 09:35-09:42:
      - The title-free cases sync, sync7d and gdssync PASS with 0 kernel lines. Each indirect dispatch ran all 16 groups
        from the copied x, at limit 0 and at 0x7d, and through the GDS path with the title's copy control.
      - `t3one-wv` (build `a0d14f4c`; D + D2 + B + C + `BC5_DIRECT_DMA_SYNC` + E + G + CW, the probe, five scans) HUNG at
        the first clouds frame again. The frame came at 43.67 s instead of 23-25 s, because frames ran at 28.1/s over
        0-30 s instead of 17-18 (a normal build's diagnosis figure; which of E, G and CW raised it is not measured).
        - GPU fault 45.9 s after the start. gfx_0.0.0, comp_1.1.1 and comp_1.2.0 timed out; the resets succeeded.
          Record `~/bc5-data/captures/faults/20261122-094230`, devcoredump `20261122-094230-devcd1.txt`.
        - The probe's label series: 0x2000008020 read 0 at every kept submit until the hung frame's (#19452,
          43.671 s). So the 1 at 235 is this frame's release, and the dropped wait was not stale.
        - With G, the clouds buffer (#19455, 3448 dwords) waited on the GPU for that flag and stands at IB_RPTR 0x122
          = 290, right behind its FIRST dispatch: the DISPATCH_DIRECT at the clouds part's start, the title's dword 289.
          Queue 16's shadow buffer (#19452, 2083 dwords, the timed-out job) stands at 0x757 = 1879 = 1845 + 4 + 30,
          behind a DISPATCH_INDIRECT of program 0x80001dfb00 (4096 x 1 x 1, COMPUTE_RESOURCE_LIMITS 0 in its bytes).
        - The GFX side is the same in all three dumps (06:28, 08:44, 09:42): GRBM_STATUS 0xe5f15028/0xe5f14028, i.e.
          CP, SPI, TA, SX, SC, DB and CB busy. IB1 and IB2 are fully fetched (CMD_BUFSZ 0x1c8 and 0xa8), and the PFP/ME
          headers are the end-of-IB fence sequence.
        - The five scans: all "No active waves!", at 09:42:30.12-31.33. The kernel's timeout lines fall at about
          09:42:29.95, so every scan came after the reset. The watchdog's start is the job's submit
          (`j.queued_ns`, private unit :15406); the delay was the launch of distrobox-host-exec and umr at the stall
          (~1.4 s; 650 ms between scans 1 and 2). The 06:28 single scan has the same problem.
      - Withdrawn: every reading about one program, i.e. the march loop of 0x8000397500, the dispatch at 885,
        indirect dispatches, the wave limit and the arguments.
      - The unit of the stall is the clouds FRAME. Whatever compute dispatches are current on two queues stop
        completing there, with loop-free programs among them, while the pixel pipeline is busy.
      - Clean-boot runs that reached this frame: 0 of 3 on the new image (06:28, 08:44, 09:42), against 8 of 8 on the
        old image as far as the records show. The image is a prime suspect again.
      - The watchdog fix (ms439 v2): one host shell is started at the watchdog's start and waits for a trigger file
        that the watchdog writes, so the first scan follows the trigger within milliseconds.
        - Stand-in dry run (`k439/test_ms0439.cpp`): the scanner woke at the trigger and took five scans 104 ms apart.
        - Without a trigger it ended when its process died (`kill -0` across the container).
      - Prepared: the old-image comparison, `t3one.sh <md5> base` (no candidates; the probe and the five scans), to
        run with the same binary on 45.20261112 and on 45.20261117.1. The old deployment (b3cc94c8) has kernel
        7.3.3-ogc1.1, the same umr binary (md5 b2f8f1a8) and the same three services in its /etc; its sudoers file
        is not readable without root.
    - The old-image run, boot bdec4c92 (clean; image 45.20261112, kernel 7.3.3-ogc1.1, Mesa 26.2.6-2), 2026-11-22
      09:57: `t3one.sh bafd7539 base` (no candidates; the probe and the fixed five-scan watchdog) HUNG the same way.
      - GPU fault 25.9 s after the start. gfx_0.0.0, comp_1.2.0 and comp_1.1.1 timed out at 213.80 s, comp_1.3.0 at
        215.84 s; 20 lines; the resets succeeded. Record `~/bc5-data/captures/faults/20261122-095810`, devcoredumps
        `20261122-095810-devcd1`, `-095812-devcd2`.
      - The same positions as at 06:28: the clouds acb 3452 at IB_RPTR 0x379 (behind 885's DISPATCH_INDIRECT);
        queue 16's shadow buffer at 0x28c = 648 + 4 (behind its second DISPATCH_INDIRECT). GRBM_STATUS 0xe5f140a6:
        the same busy units as 0xe5f15028, with DB not clean and a CP fetch pending (bits 12 and 7; field names
        TODO(verify)). 0x2000008020 first read 1 at the hung job's own submit (#7921, 23.730 s).
      - The five scans came in time this time: scan 1 at 09:58:10.816, about 0.5 s before the kernel's timeout
        (~09:58:11.33). All five read "No active waves!". The same umr form caught 40 halted cloth-pass waves at 00:12,
        so this is evidence: no wave is resident while both compute queues stand behind their dispatches.
      - The probe: the march loop's inputs are healthy (constants; direction (-0.79, 0.39, 0.47), +0x120 = +0x130;
        list A valid cells). The two 3D images and the 2D one read zero in their first 64 bytes.
    - The reframe:
      - The image is CLEARED: the old image hangs the same way on a clean boot.
      - Yesterday's eight "passing" runs never reached this point. Each showed the title's Graphics-mode choice
        screen first (at about 125-145 s) and no 3D scene within 25 s.
      - 00:12 confirmed a mode, which the title keeps in its save-data memory
        (`~/bc5-work/_SaveData/TITLE3/sce_sdmemory/memory.dat`, rewritten by every run). Every run since enters
        the 3D scene at about 23 s, and the stall comes 2-3 s later: it is the title's FIRST 3D GAMEPLAY FRAME (clouds,
        shadows, terrain), on both images and with every candidate.
      - Withdrawn: the system image as the cause; every per-program reading; the stale-argument race as the cause;
        "8 of 8 passed".
      - The 00:12 hang is a DIFFERENT class, as the record shows: 40 waves resident and halted with the memory
        violation (TRAPSTS bit 8) in the cloth programs (PC 0x80_0017c6xx-0x80_0017f5xx). One queue was polling a
        wait, and the pixel pipe was idle (GRBM_STATUS 0xa0403028). That is F893's flat-aperture fault, answered by
        `BC5_DIRECT_FLAT_APERTURE=1` and still untested in the title, because the earlier stall blocks the way.
    - The build for the next clean boot (2026-11-22 08:58): normal `8e7e6c28`, lean `0d49c801`, private archive
      `256144d7`; the shared builds unchanged. It adds to `0a0f31d6`:
      - ms439, `BC5_0439_UMR_SCANS=5`: the watchdog's wave dump as five `umr -O halt_waves -wa none` scans 100 ms apart,
        each with a timestamp, in one host shell. The sudoers has no "bits -wa none" form. Stand-in dry run
        (`k439/test_ms0439.cpp`, the umr call swapped for an echo): five scans 103 ms apart.
      - mi439, in the probe's timeout record, for the first indirect dispatch with a table:
        - the program and COMPUTE_RESOURCE_LIMITS of every indirect dispatch, from the job's bytes;
        - tables 1 and 2 whole (0x700 bytes) and every job of the hung frame as files;
        - the march loop's named constants as floats;
        - the buffers at table 1 +0x120 and +0x130 (the direction) decoded, at the submit and at the timeout;
        - list A through the V# at +0x140;
        - the 3D images at +0x350 and +0x38c and the 2D one at +0x540: descriptor plus the first 16 dwords at each
          base.
      - The dump session reads the march loop of 0x8000397500 as having no iteration cap: a zero or NaN direction, a
        zero step or a growth factor not above 1 keeps a lane in for good. It reads queue 16's buffer (the shadow
        resolve, program 0x8000304100, no backward branch) as a victim.
    - The next clean boot's order (TOP): the title-free cases sync, sync7d, zero, async, async7d, two, each its own
      unit behind the gate, stopping at the first kernel line. Then `t3one.sh 8e7e6c28 waves`: the fixes of run 1, the
      multi-scan, the march-loop inputs and switch E (`BC5_0439_WAVES_UNLIMITED=1`). If that passes with zero kernel
      lines, the control with E off follows.
    - The system prefix never went out for this title (2026-11-22 ~10:20, pc439).
      - What the prefix carries: the TF ring, HS offchip, the start-state rows and the GS rings.
      - When it goes out: only in front of a dcb whose top level has a draw packet. In the unit, the call site
        `prefix_mode() == 1 || ib_has_draw(ib, num_dwords)` (exp 0157, default mode 2 "draws") calls
        `ib_has_draw`, which reads the top level only.
      - This title's dcbs draw only in chained pieces. The 09:57 hung dcb #412
        (`~/bc5-data/captures/play-20261122-0957/gc/ib-timeout-00007919-dcb-412.bin` and its six piece files) has
        no draw packet at the top level of the dcb or of any of the six pieces: one INDIRECT_BUFFER each.
      - Evidence that the writes were skipped: the prefix's `tf ring:` journal line is printed the first time a
        prefix programs the ring, and it is missing from every capture of the title today (06:46, 08:39, 09:41,
        09:57). 06:46 and 08:39 carry only the once-only "not mapped (yet)" line, from an early dcb that came before
        the `/dev/gc` ioctl.
      - So the ioctl handler's "programmed, row VGT_TF_RING" says only that the row is on. The registers kept the
        GPU's values: top read `VGT_TF_RING_SIZE` 0xc000 and `VGT_HS_OFFCHIP_PARAM` 0 on the idle desktop, which
        are another client's values.
      - That fits the stall at the first tessellated draw and the all-zero TF ring dump.
      - Candidate, `BC5_0439_PREFIX_CHAINS=1` (tag pc439, default off): the draw test also walks the chain
        (`bc5::ib_chain::collect`, which needs `BC5_DIRECT_IB_CHAIN=1`, set by `t3s.sh`).
        - The det test `k439/test_pc0439.cpp` passes: a draw in a called piece behind a chain gives top level 0 and
          chain 1; no draw gives 0 and 0; a top-level draw gives 1. The plant `BC5_PC439_PLANT_TOP` fails.
        - Build b439pc2: normal `caa14a98`, lean `144bc70e`, archive `256144d7`. It also carries the capture records
          gp439, lr439, ad439 and ia439, and the capture order trigger, then `bc5-gpu-hang-dump` (v2), then the
          scans. Variant `t3one.sh <md5> pc`.
      - This is the second defect of one class today, after F899 (`register_label_writes`): a host scan that
        reads a chained buffer's top level only. A sweep of every such scan follows.
    - Run pc (2026-11-22 10:42, boot a949fe42, new image, `t3one.sh caa14a98 pc`): the same stall.
      - The ring is now programmed. The journal has `tf ring: base 0x5000011000 size 0x3fff8 … -> VGT_HS_OFFCHIP_PARAM
        0xff` and `pc439 t 1.422 s: a dcb of 103 dwords draws only in its piece 26 of 73`.
      - The hang dump's block 1 reads the GPU's values: `VGT_TF_RING_SIZE` 0xfffe, `VGT_TF_MEMORY_BASE` 0x50000110,
        `_HI` 0, `VGT_HS_OFFCHIP_PARAM` 0xff.
      - So pc439 fixes a real defect, but not the stall.
      - The stall: dcb #9575 (1639 dwords at the top level, 98 pieces) and acb #9577 (3452 dwords, the clouds acb)
        timed out. 14 kernel lines; the gfx ring timeout came at 10:42:36.34.
      - Block 1 ran 36.158–36.597 and overlaps the reset, so its other readings are mixed (GRBM_STATUS 0xa0003028;
        the VGT draw registers, the IB offsets and the SPI wave counts 0). Block 2 is after the reset.
      - Per R55 the box stopped: no control on that boot.
      - The fault record ended the process while gp439 wrote 98 piece files, each with an fsync. Only the oldest kept
        dcb's lines came out, and lr439 and ia439 never ran. gp439 v2 writes the journal first.
    - The sweep (`sweep-chains.md`): nearly every host decision scan reads the top level only.
      - The submission's GPU copy and `policy::filter` follow pieces. The filter does so with the root's options: it
        is called per piece with `nested_opt = fopt` (`backend/src/direct.cpp:1514`).
      - So in a piece, a memory wait on a label the piece does not write earlier is dropped (`self_waits_only`,
        `policy.hpp:151`, rule at `policy.cpp:526-542`). The drop is "left to the host", but the host's wait handling
        (`submit_split`, `submit_segment`, ho430, F10) never sees piece waits.
      - The root's `keep_wait_offsets` and `drop_offsets` are root dword offsets, and they are matched by offset in
        every piece.
      - In the 10:42 hung dcb, 22 piece waits sit on labels their piece does not write. They are in pieces 12, 33, 37,
        45, 50, 56, 59, 60, 63, 65 and 66; most labels are in 0x2000008080–0x2000008320, and the list includes piece
        33's wait ahead of the tessellated draw.
      - That count is from the capture's piece files, with WRITE_DATA and RELEASE_MEM as the writers.
      - In a frame made of one chain, then, no cross-queue wait reaches the GPU or the host: the third defect of the
        class today.
    - Candidate pw439, `BC5_0439_PIECE_WAITS` (private backend copy, `k439/be-pw439.diff`):
      - =1 clears the root's offset lists for pieces;
      - =2 also keeps every piece memory wait for the GPU.
      - The det test `k439/test_pw0439.cpp` runs the real filter and passes; its plant fails.
    - For the capture, tag lw439:
      - `BC5_0439_WAIT_MS` sets the host's 2-s fence and submit bound.
      - `BC5_0439_UMR_AFTER_MS` and `BC5_0439_UMR_ARM_S` set the watchdog's age threshold and its arming time.
      - `BC5_0439_DUMP_AT_MS` adds later dumps.
      - `t3one.sh <md5> pcpw` reads `amdgpu.lockup_timeout`. At 10000 it waits 12 s and dumps at 0.9, 4 and 8 s;
        at the default it uses the watchdog at 0.4 s, armed from t 20 s.
      - The 0.4 s rule was dry-run against the held job lines of 09:41, 09:57 and 10:42: only the hung jobs pass
        400 ms; the longest healthy job is 121.5 ms.
    - Tag uw439 journals each still-unmet piece wait of the newest kept dcb, with its writers in the job ring, at the
      watchdog and at 4 and 8 s.
    - Build b439uw: normal `481547d1`, lean `b8b67a8b`, archive `60c0b53b`.


50. *The ray-pass stall is F249's flat-aperture halt, missed because the rewrite never reached programs bound in
    chained pieces (2026-11-22 16:21-17:21; runs d2211 and fp2211, boots 249ac5d2 and 984cb832).*
    - Run d2211 (normal `87c8c1bb`, sc439/sx439/ud439): the stalled dispatch is DISPATCH_INDIRECT of the SCRATCH_EN
      program 0x8000387500 in a chained piece. It is bound through a 12-pair LOAD_SH_REG_INDEX table whose 11th pair
      is COMPUTE_TMPRING_SIZE 0xc500, so the title supplies its scratch size itself (Q43 answered: the scratch state
      is there; FLAT_SCRATCH differs per wave, from 0x2000014000). The filter dropped nothing the dispatch needs:
      its 17 register writes there are debug-marker text to register 0xc343.
    - The waves (exp 0441's count: 768) are not looping: all are FATAL_HALT with TRAPSTS 0x40000100, MEM_VIOL
      (`SQ_WAVE_TRAPSTS_MEM_VIOL_MASK = 0x100`, Linux `cwsr_trap_handler_gfx10.asm`), at their first BVH stack push.
      There is no VM fault: no gfxhub line, and an empty fault cache in the devcoredump. That is exp 0190's
      signature: the push's high dword is med3(s39, 0x70000000, v28), with s39 = 0x80000000, the console's aperture.
    - `BC5_DIRECT_FLAT_APERTURE=1` was on, but there was no "flat aperture" line: `flat_aperture_fix` was only called
      from the top-level scan, and the third title binds every program through pair tables in chained pieces. This is
      the fourth defect of the "chained frame treated as top level" class (F899, F901, F902). Item 49's "rewrote
      nothing" reading was wrong for the same reason.
    - Fix fp439 (`k439/fp0439.hpp`, `mkfp439.py`; det test `test_fp0439.cpp` with plants NOTABLE, NOCARRY and
      TOPONLY; `test_fa0439` unchanged):
      - It walks the top level and every chained or called piece before the submit, following PGM_LO/HI from
        SET_SH_REG, LOAD_SH_REG and LOAD_SH_REG_INDEX.
      - It rides on `BC5_DIRECT_FLAT_APERTURE`; `BC5_DIRECT_FLAT_APERTURE_PIECES=0` turns the new reach off for an A/B.
      - The rewrite cache is now checked by the program's identity and its rewritten sites.
    - Run fp2211 (normal `0a637a90`): "flat aperture: program 0x8000387500: 3 stack pushes (1 s_brev_b32) …, bound via
      LOAD_SH_REG_INDEX in a chained or called piece", and the same for 0x80003b1600. Over 379,730 dispatches, 0 had
      no program and 0 followed an unreadable table. It died at t 42.6 s, before the ray pass, of a CPU-side null
      write in eboot (0x900c3233f, the error path after a call returning 0x80020005, near the path
      cache_ps5/bitmaps). No kernel line. Whether the stall is gone is not shown yet.
    - Run fp2211b (the same binary, 17:23, 420 s bound through the new `T3P6_BOUND`): no stall over 138 s, past the
      old stall point at about 70 s. Rate 27.8/23.9/25.2/25.5 per 30 s, then 15.6 during the menu presses; 2,701 flips
      by t 105 s. The run ended with exit 0 because t3s's mode check read "quality" after the right press. No kernel
      line, and the same two rewrite lines (at about t 1.5-2.1 s in fp2211). fp2211's CPU crash did not recur here
      (once in two starts; open). Not verified directly: that the ray dispatches completed, inferred from the frames
      going on through that pass.

51. *The evening and night of 11-22/23: the movie, the touchpad, the frame-dump catcher, the A/Bs, and the piece waits
    (2026-11-22 20:40 to 11-23 01:16; boots aef3e9b1, 98b6af80 (hung), decf809d).*
    - **Movie (vd439).** libVideoDec2's memory answers sized from the stream (`KYTY_BC5_VD2_SIZES`): 3,358,720 B a
      1080p slot, 1 MiB for the cpu/gpu/compute areas. The intro movies decode (30 pictures by t 22 s) and the black
      at the old point is gone. Frames arrive as YUV420P and are converted to NV12 (pitch 2048, luma 2048×1080, chroma
      2048×540 from pitch×1080).
    - **Bake-2 rows (b2fix).** `switch_defaults.hpp` is also included by `main.cpp` (which applies the tables),
      `kernel/pthread.cpp` and `libs/libAmpr.cpp`; built without them the binary kept the old tables and none of
      bake 2's rows took effect. `box439b2.sh` compiles all three; `rowcheck439.sh` compares each kSoft row of the
      effective-words line with the header.
    - **Window title (wt439).** No frame rate in the window title for every title and build (the rate is shown by MangoHud
      only); the title is set only when its text changes.
    - **Touchpad (tc439, `KYTY_BC5_0439_PAD_TOUCH`, on unless "0").** Exp 0193's opt-in touch path was removed by exp
      0419, so the title always read touch_num 0 and the name-writing scene could not be written. `k439/tc0439.hpp`
      (det-tested on synthetic USB 0x01 and Bluetooth 0x31 reports through a copy of SDL's HIDAPI decode,
      `test_tc0439.cpp`): finger count, a new 7-bit id per contact, x/y in the pad's own units (SDL's 1/1920, 1/1070
      undone; the box's SDL 2.33.0 checked, `SDL_hidapi_ps5.c` l. 1323-1338, both report forms), both fingers,
      nothing when no finger is down, resolution answer 1920×1080 (AnyPS5 27c88a8d75 `PadState.hpp`:9-10; TODO(verify)
      the console's answer). In his play the brush followed the touchpad.
    - **Pad timestamp (tp439, `KYTY_BC5_0439_PAD_TIME`, on unless "0").** A state read with no new input event carries
      the read's own time. Withdrawn as a suspect for the black character by the second A/B (below); kept, as it is
      what the console does (TODO(verify) the unit and sampling period).
    - **Frame-dump catcher (sr439b, `BC5_0439_FRAME_DUMP=<private dir>`, diagnosis build only).** `k439/sr0439b.hpp`
      (det test `test_sr0439b.cpp`), glue `mksr439b.py`, reader `sr439read.py`. One capture records a frame on every
      ring (each draw's colour targets, each op's user-data V#s inline and two pointer levels deep, the clears),
      censuses every surface at the flip after a drain, dumps it raw, records F+1, and repeats 5 s later; disk floor
      20 GB, 8 GB a dump, guest memory read with `process_vm_readv`. `events.bin` carries per op the shadow SH and
      context registers, the 0x200/0x600 table blocks deduped by content, programs on first sight (cap 0x20000: a real
      program is 0xc4c4 bytes) and the frame's pieces, for the dump session's offline resolver. Arming: L3+R3 held 1 s
      from a CONNECTED pad (the title reads a second, unconnected handle every frame, which flipped the hold state on
      every read; found with `KYTY_BC5_INPUT_TRACE=1`, run st439-1122-2340); the dark-fraction auto-arm rides on the
      DCC decompress path and never runs in this title (no compressed display buffer): dead, unfixed.
    - **The scripted capture (run st439-1122-2346, build 7277b404).** Two captures, 5 s apart, ~11,300 ops in 20
      submits each. Census v1 was wrong in three ways: it counted raw and integer buffers as f32 (1,143 false NaN
      surfaces), decoded 10_11_11_FLOAT with R10 low (it is R11G11B10, Mesa ab2374a `gfx10_format_table.py`:37) and read
      DCC-compressed targets raw. Census v2 fixes all three (compressed images flagged by SQ_IMG_RSRC_WORD6
      COMPRESSION_EN [21]). Then no credible NaN surface remains. The dump session's resolver adds that three of the
      four flagged addresses hold several surfaces within one frame (0x5053890000 is the velocity buffer, not the
      colour; the HDR colour is 0x5055810000), so an end-of-frame read by (base, format) is not evidence. A census per
      incarnation (read after its own last write) is the next form.
    - **A/B 1 (one run per arm, 120 s, fresh save, no input).** 7277b404 control; DMA_SYNC_MEC, DMA_SYNC_LABEL,
      CHAIN_WRITERS, PREFIX_CHAINS each off; 5f582a73; c82fe3b0. **A/B 2** (shots every 15 s, 5 counted frames a run):
      "character fully black" ctl 1/5 and 1/5, PAD_TIME=0 2/5 and 2/5, PAD_TOUCH=0 1/5, DMA_SYNC_LABEL=0 0/5 and 1/5,
      CHAIN_WRITERS=0 0/5 and 0/5 but large white/purple/teal blobs in the sky (as in A/B 1's CW-off arm and the
      afternoon build). Readings: the black silhouette is intermittent on every build, the control included (it comes
      and goes between shots 15 s apart: a per-frame fault, not a NaN accumulating); tp439 is not its cause;
      CHAIN_WRITERS=1 removes the sky blobs (fits his report of far fewer glitches on 28ae20cf).
    - **The piece waits (the black character's likely cause, F902 class, offline from events.bin).** 50 cross-ring
      waits in one frame; the GFX dcb carries ~20 WAIT_REG_MEM on labels released by acbs on rings 1-3, nearly all in
      chained pieces 13-146. The piece filter runs with the root's options (`nested_opt = fopt`), so such a wait is
      dropped (`self_waits_only`) and the host never sees it: those GFX passes run without waiting for the compute
      results they depend on. The cloth acbs (ring 3) signal nothing to GFX in the stream. pw439
      (`BC5_0439_PIECE_WAITS`) existed only in the pre-rebase private backend: 7277b404 ran the launcher's `=1` as a
      silent no-op. Now in the kit (`prep439d.sh` runs `pw439patch.py`); `st439.sh` and `t3test.sh` report every
      switch word the binary does not carry. Exp 0444's `BC5_DIRECT_GPU_WAITS` contains pw439 mode 2 and removes the
      CPU holds that make mode 2 deadlock-prone; pw439 mode 2 ×3 against ctl ×3 was approved as the filter-half test
      and is postponed (box down, below).
    - **Intro-movie noise (open).** Whole-frame colour noise over an intact luma in the maintainer's two shortcut starts
      of ce23a3eb (before and after his reboot); clean in 3 + 3 scripted starts, his own launcher on his own save
      included (mn439, mn439b). Not the switches, not the fresh objects (source diff: only the new hunks; no header
      drift), not the save, not PLAY_CAPTURE. CopyFrame writes every byte of both planes; vf439
      (`KYTY_BC5_VD2_FILL`, on unless "0") writes the slot's padding and tail neutral and logs each slot's address;
      it cannot explain a whole-frame change. On 28ae20cf he saw it in two frames only. Next: a screenshot at the
      moment he sees it (app image vs display path), and the slots' GPU mapping.
      11-23 play-1123-1502 (15:02-15:07, build 757bd9e9: bakeR base, BC5's re-created modules in the shared objects):
      again about 2 noisy frames (flashes) over the whole start movie, by his eye; the run's log
      (bc5-private/sc2-1123/play/play-1123-1502/play-last.log) is to be read at the movie's time when the VideoDec2 path
      is next touched.
    - **Builds** (private, diagnosis; shared state unchanged throughout): ce23a3eb (tc/tp), 28ae20cf (+sr439b, vf439),
      e8087036 (program cap), 7277b404 (connected-pad arm; his shortcut since 23:58). Every run 4 → 4 GPU kernel lines.
    - **Hang (play-1122-2307, 28ae20cf, his play).** A hard machine hang after 12 min of normal gameplay, no kernel
      line, no pstore record; memory steady (MemAvailable ~1.2-1.4 GB, GTT 12.2 of 13.3 GB, PSI low), no catcher
      dump. Cause open; my screenshot loop had run 50 s at the time.
    - **Box down at 01:16** (the top session's driver trial). The pw439 arm waits for the box.
    - **pw439 mode 2 deadlocks at once (F917, 11-23 07:17, boot of 06:54, kernel 7.3.4-ogc8.1).** (Renumbered from F916 on 11-23: main's F916 is the libraries bake; the kit's pinned code comments keep "F916".) Build 47e76e93
      (unit b34a7a26, backend direct.cpp 07046497 = 4d870ac7 + pw439; rows checked: 10 printed kSoft rows effective).
      ab439 interleaved ctl / pw on fresh saves: ctl ran 129 s clean (4 → 4); pw (`BC5_0439_PIECE_WAITS=2`) hit a fence
      timeout 3.4 s after the start, before any picture (exit 86), and the kernel timed out and reset comp_1.1.0
      (signaled 8848, emitted 8849: one job) and gfx_0.0.0 (15903/15906); both resets succeeded. The series stopped
      there, so no black frames were counted. The records (private): fault record faults/20261123-071716 with the timeout
      probe and wd438's last 57 acb wait decisions, devcoredump 20261123-071724-devcd1.txt with the hung job's IB.
      - The stuck wait: submit #90, acb 0x201044c910 (1023 dwords + a 55-dword prefix = the dumped 1078-dword IB on
        comp_1), dword 55, WAIT_REG_MEM function 3 (equal) reference 1 on label 0x2010449750, still 0 at the timeout.
        Every later wait in that IB (0x20104cd1e0/1c0/180/140/100, and its own 0x2010449730, 0x20104cd1a0/160/120,
        0x20105005e0) was still 0 too: the queue never got past dword 55.
      - The host kept that wait for the GPU: at bc5-ring's gate it was deferred first (wd438 #7) and then "met at the
        gate" 3.7 ms later with memory 0 (#19), so `ring_will_satisfy` had found a pending write of 0x2010449750 with
        value 1 from a job already submitted; under the acb rings (w428) a writer on another ring counts. Neither the
        acb nor the timed-out dcb #86 (1894 dwords on gfx, 9 root label writes, 0 root waits) writes that label at the
        top level, so the registered writer sat inside a piece. The only piece pw439 reported filtered is dcb #86's
        call at dword 1890 (IB 0x2010264000, 1006 dwords), and gfx is the other ring that hung. Inferred, not read: the
        writer is that GFX piece, stopped at one of its own waits that mode 2 now keeps; the piece's dwords were not
        dumped (the timeout probe dumps the hung acb only), so its wait's label and that label's writer are unknown.
      - So the cycle-free argument of w428 ("only jobs already submitted are pending, so the waits form no cycle") no
        longer holds once piece waits reach the GPU unchecked: a submitted writer can itself be stopped by a piece wait
        the host never saw. It is not a shared-ring hang: comp_1 held this one job, gfx is its own ring.
      - Exp 0444's `BC5_DIRECT_GPU_WAITS` (pw439 mode 1 for pieces plus `apply`'s self_waits_only off, no CPU holds, a
        fixed queue-to-ring binding) changes neither link of this pair: the binding only spreads compute queues, and
        removing the CPU holds helps only if the piece's writer was a job the host was holding. wd438's last decisions
        show no acb still deferred at the timeout. With the piece's writer unknown, a GPU_WAITS run on the stock kernel
        is expected to hang the same way, with the shared-ring risk of its own on top.
      - The smallest form that can run on stock (pw439 mode 3, proposed): keep a piece's wait only when the host can
        prove its writer is already submitted (the label's last pending write in `g_plw` satisfies it: the same test
        `ring_will_satisfy` gives a root wait) or memory already satisfies it; otherwise the piece is filtered as today.
        Every kept wait then points at an earlier-submitted job, so the waits keep submit order and cannot form a cycle.
        Waits whose writer comes later stay dropped (the race behind the black character may live there); holding such
        a piece's job until its writer is submitted is the deeper step (ab439's ACB_DEEP walk, for dcbs too). With it,
        in the same build, the timeout probe should dump the pieces a hung job calls, so the next hang names its wait.
      - **The mode-3 kit (laptop, 11-23; the top session's yes).** `k439/pw0439.hpp` (the decision, tested by
        `test_pw3_0439.cpp`: PASS), `pw439patch.py` (modes 1-3 in the piece loop; mode 3 fills the piece's
        `keep_wait_offsets` only, so the FilterOptions layout, the host's ABI, is unchanged; the host's answer comes
        through a weak hook), `mkpw439.py` (the unit's hook on `g_plw` without r438's early entries, normal and lean; per
        64 flips the decisions per frame and each dropped label once, with the writer ring seen since; the timeout
        probe writes every IB a timed-out buffer calls or chains to, depth 3, at most 64, and journals their waits and
        label writes). Stand-in results from the box's own bases: unit ccaacfbe, direct.cpp 962811ea, pw0439.hpp
        3b482094; the inserted code compiles against stubs (normal and lean); direct.cpp and the unit compile only on
        the box. The slot is one script, `slot439m3.sh`: prep, build into d2/priv9, ctl ×3 against mode 3 ×3
        interleaved (shots every 15 s), then one mode-2 run last for the piece dump.
      - **The mode-3 slot (11-23 08:57-09:49, boot of 08:33).** The first build stopped at compile (direct.cpp used
        std::atomic above its own `<atomic>` include; fixed in pw439patch, 0d36f1cf), before any run. Build d382eabc
        (lean aade1c10, archive 63d060f1; unit ccaacfbe, direct.cpp 67daa9d6; shared state unchanged); 10 printed kSoft
        rows effective. ctl, m3, ctl2, m32, ctl3, m33: all 128 s, 4 → 4 kernel lines: **mode 3 does not deadlock** (3 of
        3). The backend's piece counter in mode 3: of the open piece waits, ~11 % kept (63 per 4096 pieces against 512
        dropped; steady through the run). **The black character is not removed**: fully black frames by eye at 60-120 s,
        ctl 2/5, 1/5, 1/5 against mode 3 2/5, 3/5, 3/5 (about 4/15 against 8/15; an eye count on 15 frames each, so no
        claim beyond "not fewer"). The per-frame decision lines and the dropped labels went to the journal (gc/direct.log
        of each run's capture), which the slot did not copy off; they are on the box.
      - The deliberate mode-2 run (pw2) hung exactly as F917 (acb #103 at dword 55 on 0x2010449750, the same labels
        all 0; dcb #101 timed out on gfx; 4 → 19 kernel lines; fault record 20261123-094705). The piece dump read the
        dcb's call at 1890 (0x2010264000, 1006 dwords: no memory wait, writes 0x2010271fe0 and 0x20000081a0), which ends
        in a chain of 9-dword stubs (LOAD_SH_REG_INDEX 0x63, policy.cpp, then the next chain link, CHAIN bit 20,
        bc5/ib_chain.hpp kChainBit). The probe counted chain links as depth and stopped at 3, so the GFX piece that holds
        the inner wait (and the write of 0x2010449750) lies further along that chain, unread. Fixed in the kit (calls to
        depth 3, chains without a depth limit, each address once, 512 IBs; unit 1b724fbe); it needs one more mode-2 run.
      - **The mode-3 journals (copied off in one read, 11-23 ~10:10).** Per GFX frame (steady, flips 2432-2624 of all three
        runs, the same to 0.1): open piece waits 23, of them 0 kept by a submitted writer, 3 kept as already met, 19
        dropped with no submitted writer, 1 dropped as written in the same job; 114 piece waits are on labels written
        earlier in their own piece. Every waiter is the GFX ring. The dropped labels are fresh: new ones every second
        through the run (20-90 a second; regions 0x20133e/0x20104e/0x201056/0x201346xxxx), so they are labels the
        title allocates per frame, not a fixed set satisfied by an earlier frame's memory. One dropped label is
        0x20104cd1a0, which the hung acb of F917 releases (RELEASE_MEM at its dword 513): GFX pieces wait on labels that
        acbs release. Whether and when each gets its writer was **not measured**: the instrument looked for a writer
        only every 64 flips and only while the write was still pending in g_plw (entries leave it when done), so its
        "a writer seen since for 5 of 512" (ring 0, compute) is a floor, and "never gets a writer" cannot be claimed.
        The hold below measures it directly (the wait for each writer, in us, and the writer's ring).
      - **The dcb hold (tag ph439, `BC5_0439_PIECE_HOLD`, on unless "0", acts only with `BC5_0439_PIECE_WAITS=3`;
        `k439/mkph439.py`).** What the console does there: the GFX CP runs the dcb's chained IBs in order and stalls the
        graphics queue at a memory WAIT_REG_MEM until the label meets the compare, while the compute queues run beside
        it and release the label; nothing holds the buffer on the CPU and nothing drops the wait. The host form is
        exactly the treatment exp 0428 (SPLIT_LATE=3) gives a dcb's root wait, applied to its piece waits: in
        submit_split, before a dcb goes (game thread, acb rings on, device not wedged), its pieces are collected as the
        filter will see them (`bc5::ib_chain::collect`); each open wait that is neither met nor proven by a submitted
        writer is polled every 20 us after the thread's held chain went first (ADR 0010); it ends when the mode-3 hook
        proves it (the filter then keeps it and the GPU waits, as the console's CP does) or memory meets it. Cycle: the
        ring thread blocked on a label this job writes (exp 0132's rule) ends the hold, and the remaining waits are
        dropped as today. Bound: 8 ms for the buffer (exp 0428's), then the same. Each cycle and each timeout is
        journaled (the first 64 with label and pending writes; a bug to explain, not a fix). No title, no learned
        list: it reads only the buffer, the host's pending-write table and memory. The deviation from the console is
        timing only: the dcb's head before the wait runs later (no split inside chained pieces), not out of order.
        Counts per 64 flips: dcbs held, waits held, proven (mean and max wait, the writer's ring), met, cycles,
        timeouts, the hold's ms per frame. Kit: unit a0c442c0 (stand-in), syntax-checked against stubs (normal, lean);
        `slot439ph.sh`: ctl ×3 against the hold ×3, then the mode-2 naming run last.
      - **The 8-px grid (laptop, from the 23:48 captures c0/c1; tag dk439).** The intermediate targets: two 3072×1728
        colour targets of the title's G-buffer pass (about 260 draws in one dcb, programs 0x8032b0fb00, 0x803fe79a00,
        0x805b292b00, ...), MRT0 0x5053890000 COLOR_16 UINT and MRT1 0x5054310000 COLOR_32 UINT (integer ID-style
        targets; CB_COLORn_INFO 0x10050408 / 0x10050410: DCC_ENABLE, bit 28 in tools/bc5-agc/regdb/gfx10.json), written
        with DCC_CONTROL 0x00180028 (MAX_UNCOMPRESSED 256 B, MAX_COMPRESSED 128 B, INDEPENDENT_128B_BLOCKS,
        ENABLE_CONSTANT_ENCODE_REG_WRITE; field bits from the same file), DCC_BASE 0x508de02000 / 0x508de0e000 (regs 0x31e
        and 0x325 + 0x3a8, gfx10.json). Read right after, in the same dcb, by the compute programs 0x80003fec00 and
        0x80003e5900 through image V#s of formats 11 and 20 (16 and 32 UINT, the same sizes): word6 0x203b0000 /
        0xe03b0000, COMPRESSION_EN (bit 21) set, metadata address word6 [31:24] + word7 = the target's own DCC_BASE. So
        the compression state at the read is **compressed, read through the metadata** (a texture-compatible DCC read),
        not a raw read of compressed bytes: the census v1 index of these captures shows dcc 0 for every image because
        v1 did not record the V# bit (v2 does). The title's stream holds no decompress, no fast-clear eliminate and no
        CB_COLOR_CONTROL mode other than 0 (the only mode-6 draws are our own flip pass). With 32 bpp one 256-byte DCC
        block is 8×8 pixels, the grid's size. The open question is whether this GPU's texture path decodes
        INDEPENDENT_128B_BLOCKS compression as the title expects. TODO(verify): Mesa's ac_surface.c rule for GFX10
        against GFX10_3 (the web copies were not reachable from the laptop: gitlab's anti-bot page, the GitHub mirror's
        404); the slot reads the box's checkout first (ph-mesa-dcc.txt). No fix is proposed until that is read.
        The catcher in the next build (census, normal build, frame dump only): each DCC colour target's DCC_CONTROL and
        DCC_BASE, the key bytes at the end of the frame (a histogram, and the keys file), each image's V# words 6-7, and
        the reader's check that a read's metadata address is the target's DCC_BASE (`sr439read.py` dcc_report). The
        slot takes one scripted capture in the writing scene for it.
      - **The blackening in the writing scene** is the black character of the A/Bs above (the scene a fresh save
        reaches by itself, the shots at 60-120 s); its candidate in the next build is the hold (ph439).
      - Aside for the top session: `BC5_DIRECT_DCC_PRESENT=2` (dc439's flip decompress) is set for this title by a
        `kTitleDefaults` row (bc5LleAgc.cpp line ~16214 of the base); per the rules a per-title default is a defect to
        move to every title or remove.

    - **The hold slot (x439ph, 11-23 12:44-13:12, boot of 10:22, kernel 7.3.4-ogc10.1, bakeR as the shared base).**
      Re-pinned on bakeR first (133d1b3d: backend policy.cpp 99303017 gained the register catcher, so the kit's
      policy.cpp is e8541e0a with the same edits; direct.cpp's base unchanged); the kit's own -Werror bug in mkdk439be
      (an implicit int-to-double in its journal line) fixed in 4c7eca74, direct.cpp 5706c7b3. Private build normal
      757bd9e9, lean eff7cffc, archive b37bc6e9 (it carries 0002's modules: the shared objects); shared state unchanged
      after. Rows: 10 printed kSoft rows effective (EAGER_GPU_WRITE and DCC_PRESENT print no start-up row). Eight A/B
      runs and the capture: 0 GPU kernel lines.
      - **The hold does not remove the black character.** Shots at 60-120 s (5 per run, the writing scene; by eye,
        private montages in bc5-private/ph-1123): control 0 + 2 + 3 = 5 of 15 black (3 more half-dark), hold
        (`BC5_0439_PIECE_WAITS=3` with PIECE_HOLD) 1 + 2 + 4 = 7 of 15. With the mode-3 slot: control 9 of 30, mode 3
        with or without the hold 15 of 30. Keeping the GPU waits the hook proves, and holding the rest up to 8 ms,
        does not help and may make it worse (three runs each, not separable from chance). The piece waits are not
        shown to be the cause; the candidate is set aside.
      - **The grid: Mesa says this GPU decodes it.** The box's Mesa (~/src/mesa 0866ae7, src/amd/common/ac_surface.c,
        is_dcc_supported_by_L2): for CHIP_NAVI10 and CHIP_GFX1013 "only independent 128B blocks are supported", i.e.
        INDEPENDENT_128B_BLOCKS with MAX_COMPRESSED_BLOCK_SIZE 128B, which is exactly the G-buffer's DCC_CONTROL
        0x00180028; the same file's image-store rule (line ~252) names the same setting as the one shader stores
        support. So the texture/L2 path is not expected to misread these targets, and the grid needs another cause.
        The capture (13:08:55, c0) confirms the census: 5 DCC colour targets, the two ID targets read through their
        own DCC_BASE with COMPRESSION_EN 1. One target is outside that rule: cb #0, 3840x2160 (the display-sized
        target), DCC_CONTROL 0x00080208 (INDEPENDENT_64B, MAX_COMPRESSED 64B), which gfx1013's L2 does not support
        per the same function; it is what DCC_PRESENT decompresses at the flip (through the CB, not the texture path).
      - **The dk439 arm is broken, not a result.** With DCC_ENABLE cleared and the keys set to 0xff at the submit, the
        whole picture became colour noise in horizontal runs (both runs, every shot). The likely reason: the title
        rewrites the metadata itself (27 DMA_DATA fills in the capture, keys 0x00 and others in the histogram), and its
        reads keep COMPRESSION_EN, so plain colour is decoded through stale keys. A valid arm also clears COMPRESSION_EN
        in the V#s that point at a stripped target (or refills the keys after each of the title's metadata fills).
      - **The mode-2 run (pw2)** ended in a fence timeout 3.5 s after start (exit 86, record
        ~/bc5-data/captures/faults/20261123-131049), the kernel's comp_1.1.0 then gfx_0.0.0 timeouts at 13:10:57, both
        ring resets succeeded. The chain-following piece dump is in that record's journal on the box (not copied before
        the release); reading it is the next box read.

    - **Locating the stage (top's order of 11-23 ~13:45: no more causes, find the pass).** What the captures can and
      cannot say, on the laptop:
      - No captured frame is known to be bad. The slot's capture (13:08:55, ~96 s) falls between the shots at 90 s and
        100 s of its run, both with the character right (that run's shots at 100-190 s are all right, only 60 s is
        black); the 23:48 captures have no shots on the laptop. The good/bad pair needs his L3+R3 dumps, taken when he
        sees the black character (bad) and again when it is right in the same scene (good).
      - The catcher cannot name a stage even with a pair: it censuses each surface once, at the flip after a drain, and
        dumps raw bytes only of flagged surfaces (5 files in c0). The resolver showed several surfaces share one base
        within a frame (0x5053890000 is G-buffer MRT0 early and the velocity buffer later), so an end-of-frame read is
        the last incarnation only. Per-pass outputs are not recorded anywhere.
      - **The one addition for the next build (sr439c, the pass census, capture frame only).** In the armed frame F,
        after every pass (a run of draws with one colour/depth target set, or one dispatch), the host inserts into the
        GPU stream itself (no split, no CPU wait): a cache flush and write-back (the same end-of-pass flush the title
        uses before a read) and CP DMA_DATA copies of every surface the pass wrote (its CB targets, and the buffers
        and images its user-data V#s name with write access; for a DCC target its metadata too) into a dump arena
        (8 GB cap, the dump floor as today; the stream's own order is kept, so the GPU does what it does now plus the
        copies). After the frame: per incarnation (pass index, program, ring, piece, target, format) the census
        zero / dark / NaN-Inf / bytes equal to its previous incarnation, and a 1/8 thumbnail; raw kept for the targets
        of the passes the reader asks for. The resolver adds, per pass, each input's path: the last writer in the frame
        (which pass, ring, chained piece or root), a CPU write (no GPU writer in F, the page written by the guest
        between flips), or a label-gated copy (DMA_DATA behind a WAIT_REG_MEM). Offline: the bad and good frames
        matched pass by pass (program and order); the first pass whose output differs in kind is the stage. For the
        grid: the period-8 energy of each plain incarnation (and of DCC targets' plain-coded blocks, keys 0xff), the
        first incarnation showing it, and the reading pass's own output compared with its input. Risk: the inserted
        flushes change timing for one frame; if the black character never appears in an armed frame, that is itself
        a finding (a timing-dependent stage).
      - **The pass census kit (sr439c; the top session's yes of 11-23 ~14:00, with its three conditions).** Laptop only so
        far; built and run in the next slot (`k439/slot439sc.sh`). Files: `k439/sr0439c.hpp` (host-free: copy geometry,
        packets, the sampled hash, the plan and its degrade order, the depth tracker, the arming machine; det test
        `test_sr0439c.cpp` PASS, its three plants NOCHAIN, NOWINDOW, NOSPLIT each FAIL), `mksr439c.py` (the unit; normal
        build only, nothing of it active under BC5_LEAN, checked by a preprocessor walk of the stand-in), `mksr439cbe.py`
        (the backend: the arena and the block placement; inert unless the unit defines its weak hook), `sr439cread.py`
        (the reader). Stand-ins: unit cdcb13d5 -> 5ecbf2c8, backend direct.cpp 5706c7b3 -> 4c5ed838, sr0439c.hpp
        a7f114f6; syntax-checked with clang (the unit's new code in a stub unit, the backend against stub libdrm
        headers: no error in the new code).
        - How a pass is copied: in an armed frame each submit is walked piece by piece before the device sees it
          (sr0439b's recorder per piece, plus a depth-target tracker), and consecutive pieces with the same output set
          form one pass (a G-buffer pass drawn over ~100 chained pieces is one pass). At the end of the pass's last
          piece, inside the title's stream and before its outgoing chain packet: on the GFX ring an end-of-pipe
          CACHE_FLUSH_AND_INV_TS_EVENT writing a fence and the ME's wait on it, on a compute ring CS_PARTIAL_FLUSH; then
          CP DMA copies (CP_SYNC) of the pass's outputs into a GTT arena at 17 TiB. Nothing else in the job moves: the
          backend reserves the room when it lays out the scratch and grows the IB size of the packets that point at the
          piece. Sources in the header (regdb events, the backend's own packet forms; DST_SEL 0 and the MEC's DMA_DATA
          are TODO(verify), and run 1 keeps the compute rings untouched).
        - Memory, computed from the 23:48 captures (condition 1): all outputs of a frame are 16-17 GB, colour targets
          5.8-6.0 GB; with copies only at pass ends and in 64 KiB tiles (the window's tiles whole, every 16th tile
          elsewhere, a DCC target's keys whole) one frame needs ~1.6 GB, colour targets ~0.4 GB of it (stride 64 or a
          narrower window: 0.7-1.3 GB). The budget is read at the survey's end (the cap word, MemAvailable - 768 MiB,
          the GTT headroom - 256 MiB) and the arena allocated then, not at start; the degrade order is the top
          session's: unchanged surfaces skipped (sampled hash over the survey frame; colour and depth targets never),
          depth at half rate, the frame's copies split over two consecutive frames; what still does not fit is skipped
          and counted in meta.txt.
        - Arming (condition 2): L3 + R3 held 1 s, and `BC5_0439_PASS_AT=60,100`. The armed frame's black/good label
          comes from the shots next to it (the final target is DCC-compressed in this title and cannot be decoded on
          the CPU): sr439cread.py --classify, from the share of robe-yellow pixels in the character's box. Calibrated on
          the hold slot's 30 eye-labelled shots (hue 45-55, saturation >= 0.4, value 0.25-0.9; good >= 0.0023, black
          <= 0.00028, threshold 0.0008): it reproduces every label, the half-dark shots as black; an in-sample fit, so
          the next run's labels get a look by eye too.
        - Normal build only, off by default (condition 3): `BC5_0439_PASS_DUMP=<dir>` turns it on.
        - Limits, stated before the run: a pass is a piece run, not a draw; the copies change the armed frame's timing
          (each pass end waits for the GPU); DCC targets' tiles are compressed bytes, so their kind comes from the key
          histogram, not the pixels, and the grid metric skips them (the 8x8 question for the G-buffer targets is
          answered only through their readers' plain outputs); a root buffer the unit rebuilds or splits before the
          device gets no copies (counted as unplaced); a 64 KiB swizzle's tile order (row-major blocks) and its block
          sizes are TODO(verify) against addrlib.
      - **The pass census slot (x439sc, 11-23 14:11-14:24, boot of 13:27).** Build 8cb27e89 (lean 061ebd0f, its warning
        count unchanged; shared state unchanged); the first attempt stopped at the build on my header (std::min of
        uint64_t and unsigned long long: Linux's uint64_t is unsigned long; 14de58cb). Three scripted runs, two arms
        each, 0 GPU kernel lines, run 1 GFX-only, runs 2-3 with copies on the compute rings too (so the MEC ran CP DMA
        with CP_SYNC without a fault). Each of the 6 arms: survey need 1.9-2.4 GB (all) / 1.5-2.0 (hash skip) /
        1.2-1.8 (+ depth half) / 0.6-0.9 GB (+ two frames), budget 1074 MB (the cap; MemAvailable 2.6-3.1 GB), level
        3, arena 617-891 MB; every block placed (0 unplaced), 1-51 incarnations skipped for room. Data: 7.2 GB in
        ~/bc5-data/priv/passes (tables on the laptop in bc5-private/sc-1123; the raw window tiles stay on the box).
        - **No pass named yet: the labels are the problem.** The shots next to the armed frames show the character
          changing within a second or two, and in more states than black and good: dark horizontal stripes across the
          robe (partial) in most of them. A shot 0-1 s from the capture cannot label the captured frame.
        - **What the census already shows (unlabelled):** the 3072x1728 u8x4 colour target 0x5000860000 (CB format
          1080) is filled by the G-buffer pass (pieces 49-98, zero fraction 0.99 -> 0.06-0.11 in every frame), and a
          later draw pass at piece ~128 (programs 0x800037f400, 0x80003cb300, 0x80003d2300, ...) leaves it ~90 % dark
          over the whole window in four frames and bright in two; in two frames the target also entered the G-buffer
          pass half filled (0.47) instead of cleared. Per-tile maps of the window (one value per 128x128 tile) show the
          difference is screen-wide, not the character's shape. Other "differences" were artefacts: memory reused by
          another surface later in the frame (0x504ef10000), and a raw buffer read as floats (0x500cdb6600).
        - **Next (one addition, v2):** the label from the frame itself. With BC5_DIRECT_DCC_PRESENT=2 the display
          surface is decompressed in place at each flip, so right after a copy frame's flip the unit can count the
          robe-yellow pixels in the display surface's window tiles (the same classifier, on 2_10_10_10 pixels) and
          write the label into that frame's meta.txt. Then pairs are exact and the reader names the first pass.
      - **Pass census v2 kit (11-23 ~15:00, the top session's yes):** each copied frame saves its own picture: right
        after its flip, once dc439 has decompressed the display surface in place, the unit writes the whole surface
        raw (display.raw, ~33 MB, tiled as the GPU left it) with display.txt; `sr439cread.py --display DIR` detiles it
        into display.png (KytyPlus tile.cpp Gen5RenderTargetOffsetInBlock<uint32_t>, GPL-2.0; laptop round trip of a
        synthetic picture PASS; the real block order is checked by the first picture) and prints the robe-yellow count
        beside it. The picture is the label (black / striped / good kept apart). `--lead BASE PIECE DIR...` prints, per
        frame, the target's state at the pass and each input's last state and path. Unit stand-in ce2b5824; slot
        slot439sc.sh with four arms per run (60, 80, 100, 120 s).
        - On the unlabelled frames of 14:17-14:23, `--lead 0x5000860000 128`: in three of the four frames where the
          pass leaves the target dark, compute passes earlier in the frame (pieces 32-48 and 106-125; programs
          0x80003e5900, 0x8000351e00, ...) bind an sRGB image view (format 130) of the G-buffer target 0x504ef10000
          while it is all zero; in the two bright frames they do not bind it. A hint for the labelled run, not a
          finding (the dark/bright split is the target's own state, not the picture).
      - **The labelled slot (x439sc v2, 11-23 14:46-14:59, build 2ce84306).** Three runs, four arms each, 0 GPU
        kernel lines; all 24 copy frames (A and B of 12 arms) saved their picture. The detiled pictures are correct (the
        render-target block order is row-major, as assumed). Labels by eye from the pictures (private,
        bc5-private/sc2-1123/chars24.png): good 15, striped 6, black 3; black at 14:55:39 (A and B) and 14:57:45 A, the
        latter with the ground and water also gone black around him (the maintainer's "objects blackening").
        - **The lead is refuted by the labels.** The piece ~128 pass leaves 0x5000860000 ~90 % dark in 8 B frames, 6
          of them good; it stays bright in 4, one of them striped. Whether the target entered the G-buffer pass cleared
          (0.99) or half full (0.42-0.48) does not follow the label either. So that target's state is a normal
          per-frame variation, not the stage.
        - **What the labels alone show:** the first copy frame of an arm (A) is bad in 7 of 12 arms, the second (B) in 3
          of 12, and B is never bad where A is good. A follows the survey frame's two drains and carries the copies of
          the early passes (to piece ~100); B carries the late ones. Not separable yet: host stalls before the frame,
          or the copies inside it.
        - The tile-level comparison of black/striped against good frames waits for the 14 GB of tiles (on the box until
          the maintainer's play ends).
      - **The DCC resolve arm (rsv439, slot x439rsv 11-23 15:42-16:03, build 12d33837).** `BC5_0439_DCC_RESOLVE=1`:
        at the end of every GFX pass that wrote a DCC colour target, dc439's in-place decompress on the real target
        inside the stream (CLEAR_STATE cmd 0, the decompress, the title's registers written back from a tracker of the
        GFX stream; sr0439c.hpp CtxTrack / resolve_block, det test PASS). Two build fixes on the box (the unit's code
        sits in namespace Libs::Direct: the declaration moved there, the hook reads the switch itself). Six runs, 0 GPU
        kernel lines; the arm ran (~54,000 targets decompressed per run, 0 unclaimed). **Invalid as a test:** under it
        nearly every shot of all four rsv runs is black except a strip at the right edge (last ~10-15 % of the width) and
        large coloured glows; the controls look as before (intermittent black/striped character). The arm breaks the
        frame itself. Candidates: the decompress rectangle from CB_COLORn_ATTRIB2 too narrow or a scissor left behind
        (the intact right strip), registers the tracker did not know left at the clear state, or the decompress writing
        wrong data into a fast-cleared mid-frame target. Next: the rsvp census (7.7 GB on the box: the DCC targets are
        plain under the arm) shows which pass output turns black first.
      - **Read of the rsv census (laptop).** Under the arm the DCC targets are plain in the copies, so the lit/colour
        target 0x5055810000 (f16, 3072x1728) is seen for the first time: at pieces ~93-98 it is an MRT of the G-buffer
        pass itself (its draws write seven MRTs: 0x5000860000, 0x504ef10000, 0x5050410000, 0x5051910000, 0x5052e10000,
        0x5053890000, 0x5055810000; programs 0x80219fea00, 0x80003ff500, 0x802209d000, 0x80209f4000, ...). In the same
        pass end its sibling 0x5053890000 is complete while 0x5055810000 has a black top band and block-granular holes
        along the character, in every frame read. Points at that target's own DCC state on write (fast clear or
        partial blocks), not at the inputs; but the arm's own decompress ran between this pass's pieces, so the v3
        copies (sr439c v3, `BC5_0439_PASS_DCC_ONLY=1`, the COPY decompressed after the frame; kit bf4ffe94, slot
        slot439v3.sh) are the test, with the keys of the hole blocks.
      - **v3 slot (x439v3, 11-23 16:24-16:37, build 2109f30f).** Three runs, nine arms (eight fired), 0 GPU kernel lines;
        each armed frame in one frame (level 0); every DCC copy decompressed in the arena (12 or 23 per frame), all
        placed; 3.6 GB pulled, box copy deleted. Labels from each frame's own picture: good 2, striped 4, black 2. The
        frames with 12 copies (both good, both black) hold no copy of the lit HDR 0x5055810000 (the copy frame missed
        those passes), so no good-vs-bad pair of it. In the four striped frames the decompressed HDR copy (pieces
        147-168) carries a block checkerboard along every edge, while the frames' own pictures (16:30:15, 16:35:47) show
        none: **our dc439 decompress mishandles this 8-byte-per-pixel (f16x4) DCC target.** The same checkerboard was in
        the rsv data (decompress on the real target at its real address), so it is not the copy placement; it likely
        also made the rsv arm's black frame. The rsv test and the v3 pictures of 64-bit DCC targets are therefore
        invalid, and the "holes" read from them were ours. DCC_PRESENT has only ever decompressed the 32-bit display
        surface. Next (laptop): dc439's decompress for 8-byte pixels against Mesa's radv DCC decompress.
      - **Correction (11-23 ~17:00).** "Our dc439 decompress breaks 8-bpp DCC targets" is withdrawn: the 8-byte detile
        (KytyPlus render-target layout) keeps fine detail continuous in flat areas and textures, so the layout is right,
        and the block checkerboard in the decompressed HDR copies sits only on the character, in the four frames that
        are all STRIPED. It may be the title's defect itself; no good-frame copy of that target exists to compare.
        Mesa's DCC decompress (radv_meta_fast_clear.c, ab2374a) uses the same state as dc439 (CB_DCC_DECOMPRESS, ROP3 copy,
        CB_SHADER_MASK 0xf, a no-op PS, the target's own registers); radv also programs the RB+ registers
        (SX_PS_DOWNCONVERT, blend-opt, DISABLE_DUAL_QUAD) per format, which dc439 leaves at the clear state; no difference
        proven for 8 bpp.
      - **The sharpest split so far (v3 tables):** in all four striped frames the late draws (submit 7, pieces 147-172,
        ~125 draws) write the 8-bpp DCC target 0x5055810000; in all four good and black frames the recorder sees no draw
        writing it (0 references) though the frames hold the same number of ops (11,360 vs 11,369). Either the title
        renders those draws elsewhere there (a target the recorder cannot see: CB registers from an unreadable table, an
        unreadable base) or the recorder dropped the target. Next: log every draw's CB_COLOR0-7 BASE/INFO/ATTRIB and
        target mask in pieces 140-175 of an armed frame, recognised or not, with the reason when not.
      - What stands (the top session's list): labels good/striped/black per frame from each frame's own picture; the
        photos' reading (lighting missing in blob regions, block-granular borders, dashed lines); plain targets identical
        across labels; the title's RT menu setting irrelevant; the defect sits in or behind the DCC colour targets
        (0x5055810000, 0x5053890000, 0x5054310000, the display). The rsv arm is invalid (it breaks the frame), and the
        rsv-era "HDR holes" are not evidence on their own.
      - **Our rewrites that touch CB/DCC state (the top session's list, 11-23 ~17:10).** (1) CLEAR_STATE cmd 1/2 -> 0
        (policy op 0x12) with the state-stack emulation restoring the context at a pop only on a GFX job's root; (2)
        DCC_PRESENT=2 (display surface, 32 bpp, at the flip); (3) dk439 (off). Nothing else rewrites CB or DCC registers.
        Count from the 23:48 captures (every piece of frame F, 201 and 199 pieces): no CLEAR_STATE inside chained or
        called pieces, so (1) cannot wipe CB state mid-frame there. In the main GFX dcb's root a pop (cmd 2) arrives with
        no push in that submit: the emulation leaves it unmatched and the policy makes it a kernel clear, every frame (a
        fidelity gap, not a per-frame split).
      - **CB-register log (slot x439cb, 11-23 17:20-17:34, build c3a0b573, 30 arms).** 0 GPU kernel lines; 29 labelled
        copy frames (11 good, 6 striped, 12 black). Every frame's late draws (pieces 140-175, ~123-130 draws) write the
        8-bpp DCC target 0x5055810000 with the same MRT set and INFO, their CB registers loaded from tables
        (LOAD_CONTEXT_REG); every bound base is mapped. The v3 "4 of 4 vs 0 of 4" split was an artefact of the old
        recorder (it does not follow those loads) and is withdrawn. The colour targets the late draws sample
        (cbreads.tsv) are the same in every frame, read uncompressed; the per-frame ping-pong pairs (0x50bfe00000 /
        0x50bfc00000, 0x50c87b0000 / 0x50c87d0000) fall on good and bad frames alike. The colour-target state, written or
        read, does not separate the labels; left: the compute-written inputs and their completion when the GFX job goes.
      - **System image (the top session, 11-23).** From the boot of 08:33 on 11-23 the box runs image 45.20261123: kernel
        7.3.4-ogc10.1.fc45, Mesa 26.3.1-2 (before it ogc8.1 with Mesa 26.2.7). The pw439 mode-2 run of 07:17 (F917) ran on
        ogc8.1; the mode-3 slot and everything after it (hold, sr439c v1-v3, rsv439, cblog) on ogc10.1. The maintainer saw
        the same picture defect on both (his play of 11-22 night and play-1123-1502), so the update did not cause it.
**Serial arm, ctl vs ser (slot x439ser, 11-23 18:15-18:33, ogc10.1).** Six runs alternating control and
`BC5_0439_SERIAL=1`, 168 s each, census arms at 50/70/90/110/130 s, shots every 3 s; GPU kernel lines 4 -> 4 in
every run. Bad scene shots (classifier from the first scene shot): ctl 13/27, 12/30, 14/31 = 39/88 (44 %); serial
0/19, 1/18 (the first shot of the scene), 0/19 = 1/56 (2 %). Picture labels of the census frames in the scene: ctl
6 bad of 13, serial 0 of 8. Serial cost: about 9.8 % of submits at the 50 ms bound (1925 of 19456, 1912 of 19456,
1839 of 18432), mean wait 6.5-6.6 ms. Verdict of the arm: the defect is an ordering race between jobs in flight on
different rings; making every submit wait for all earlier jobs removes it.

`submits.tsv` (jobs in flight at each census submit, read at the hook before the serial wait): each frame is one GFX
dcb (submit 7) followed by 10-14 acb submits on compute rings 0-3. In the controls 6-12 jobs are in flight at those
acb submits, so they run while the dcb is still running; in serial they hold 0-1. Pairs from `ops.tsv` (laptop,
address-range overlap of each acb dispatch's resources with the dcb's ops, nine control frames): acbs that share
memory with surfaces the dcb's draws write, in every frame: programs 0x8000396500 and 0x8000375600 with the
3072x1728 target at 0x504ef10000 (fmt 130; 1813 draw writes from piece 49, first writer pgm 0x802218ee00; read by
the lit pass); 0x80003afe00 with the 2048x2048 fmt 14 array at 0x50141d0000.. (written once, pgm 0x80002ec500,
piece 28); in 6-7 of 9: 0x901e18200 with 0x5000860000 and 0x8000264100 / 0x80002d3700 with the 256x256 fmt 13 at
0x50c87b0000 (lit pass 32 reads). Limit: the census records a compute dispatch's resources as bound ("v"), not as
read or written, so the direction of each pair is not known from it.

**Direction arms (slot x439dir, 11-23 18:54-19:22, ogc10.1; kit fdb94ef7, unit 66c8ad10, private normal 3939f323).**
`BC5_0439_SERIAL` gained modes a (an acb submit waits until every earlier GFX job has completed), b (a GFX submit waits
for every earlier acb job) and c (as a, only for an acb whose top-level stream waits, WAIT_REG_MEM, on a label a GFX
job in flight has a pending write of in g_plw), with per-class in-flight counters at the completion queue; same 50 ms
bound and journal. Eight runs, ctl a b c ×2 interleaved, 168 s, 4 -> 4 GPU kernel lines each. Bad scene shots
(classifier, every 3 s from 63 s): ctl 16/29 + 16/29 (55 %), a 0/29 + 0/29, b 15/29 + 14/29 (50 %), c 0/29 + 0/29.
Cost per submit: a 0.85 ms, c 0.8 ms (about 2.9k acbs held per run, 0-6 at the bound); b held one submit in a run:
the dcb has no acb in flight at its own submit. So the defect needs the frame's acbs to run beside their dcb, and
nearly every acb that a holds waits on a label the in-flight dcb writes. a and c serialise the acb behind the whole
dcb; the GFX passes then read the previous frame's finished acb results, which is not the console's order either.

The mode-2 fault record 20261123-131049 (3.55 s, `BC5_0439_PIECE_WAITS=2`) shows the structure: acb #71 (1078 dwords;
programs 0x8000399500, 0x80003f7b00, 0x8000304100, 0x80003c0300, 0x80003ec200, 0x800037ce00, the pairs' programs)
alternates with the GFX dcb through labels: it waits on GFX-written labels (0x2010449750 at dword 55, never met,
then 0x20104cd1e0/1c0/180/140/100, 0x20105205e0) and releases 0x2010449730, 0x20104cd1a0/160/120, the labels the GFX
pieces wait on. BC5 serves the acb-waits-for-GFX half (kept for the GPU, ho430) and drops the GFX-waits-for-acb half
(the ~19 piece waits per frame), so the GFX passes read acb results while the acb writes them (H1). H2 (acb waits
passing early) is not excluded by the arms; an arm that holds an acb only until its own wait labels are met in memory
would separate the two. Mode 2 keeps the GFX half and deadlocked (F917, 131049): likely head-of-line blocking on the
shared kernel compute rings (the acb releasing the label GFX waits on queued behind #71 on the same ring); to check
from the 13:10 gc dumps.

**F917's continuation (11-23 evening): the black / striped character is an ordering race between a frame's GFX dcb
and its acbs.** The chain of leads refuted or withdrawn today, in order: pw439 mode 2 (keeps every piece wait for the
GPU) deadlocks (F917, and again in the 13:10 naming run); mode 3 (keeps a piece wait only when its writer is already
submitted) kept none of the ~19 dropped waits per frame, so it changed nothing; the dcb hold ph439 (submission-based,
inside the title's own submit call) did not help (7 of 15 against 5 of 15); the DCC reading claims (our decompress
breaks 64-bpp, the v3 4/4 split, the rsv HDR holes) withdrawn; rsv439's in-stream decompress invalid (it blackens the
frame); CB state, written or read, and ping-pong colour targets identical across good and bad labels (cblog); the
unmatched pop (a full context reset follows it); push/pop in pieces (none); 0x5000860000; the RT menu setting; the
system update (the defect on ogc8.1 and ogc10.1). What held: serial (every submit after all earlier jobs) 44 % ->
2 % bad shots; acb-after-GFX (a) and its narrow form c 55 % -> 0 % at about 0.8 ms per submit; GFX-after-acb (b) no
effect.

The 13:10 gc dumps (pulled 11-23 19:35): dcb #69's root and pieces 0-2 (0x2010264000 -> 0x2010254000 ->
0x2010715800) hold no memory wait; the chain goes on into 0x2010725800, which the probe did not dump, so the GFX wait
it stopped at is not in the record. The umr read (13:10:58, 9 s after the fault) ran with the rings not halted and
CP_IB1/IB2_BUFSZ 0: it does not show where the GFX CP stood. The journal has no per-job kernel ring. After acb #71
(queue 16, the rest of a 1027-dword acb held on the host until 0x2010449750 had a submitted writer) the title submitted
acb rests on queue 24 (1060 dwords) and queue 40 (479 dwords) that never completed before the timeout: releaser
candidates for the GFX wait. Head-of-line blocking on a shared kernel compute ring is therefore neither shown nor
excluded; H1 (dropped GFX piece waits) against H2 (acb waits passing early) stays open.

Candidate launcher (prepared 11-23 ~19:40, not live): `k439/t3-test.sh.arm-c` on the box (md5 76db0204, beside the
live `t3-test.sh` da4a33dc): the pinned 3939f323 with `BC5_0439_SERIAL=c`, the shortcut's words otherwise, no
census words, the frame dump (L3+R3) kept; DRY=1 passes (every word carried, gate admitted). Arm c is a diagnosis
(GFX reads the previous frame's acb results), not the fix.

**Arm-c smoke and the rr439 slot (11-23 19:38-20:06).** Smoke sm439c-1123-1938: 3939f323 with exactly
`t3-test.sh.arm-c`'s words (no census), 153 s, fresh save: reaches the scene, 4 -> 4 kernel lines, 0 of 32 scene
shots bad, 0.81 ms per submit. Slot x439rr (kit 2c0a3bd3, unit fc5c4552, private normal a01b2850): the job record
(`BC5_0439_RR_RECORD=1`) on in every run; ctl 11/29 + 11/29 bad (38 %), arm d (`BC5_0439_SERIAL=d`: an acb held until
its own top-level waits, all on GFX-written labels, are met in memory; about 5.1k holds a run, 1 at the bound) 11/29 +
17/29 (48 %): d does not help, so H2 (the acb reading GFX output early) is not the cause; H1 remains (GFX passes read
acb output while the acb runs, the GFX piece waits being dropped), and only arms that keep the acb from running beside
its dcb (serial, a, c) remove the defect. The ring-rule candidate (`BC5_0439_PIECE_WAITS=2`, `BC5_0439_RING_FREE=1`)
hung 3.6 s after the start (rr1; fault record 20261123-200246; gfx_0.0.0 timeout 20:02:54, comp_1.1.0 20:03:04, both
reset; series stopped, reboot): 4 holds, 2 at the bound (queue 24's acbs onto ring 0 behind #74 of another queue still
waiting on 0x20104cd140: the head-of-line case occurs), but the hang is the same dcb #69 (1894 dwords) as at 13:10, and
the other timed-out job, acb #72 (queue 40, 479 dwords), stopped at a wait on its own label 0x2010271fc0, released by
its own RELEASE_MEM at dword 216 and still 0: its own dispatches before it never finished. The dcb's root and pieces
0-1 hold no memory wait; the chain continues through 9- and 18-dword stubs (op 0x63, probably LOAD_SH_REG_INDEX,
TODO(verify) Mesa src/amd/common/sid.h, then a chain). The probe's piece walk and the job table did not reach the record:
the fault record ends the game first (the table's dump sits after the timeout handling). Records private in
bc5-private/rr-1123. Arm c stays the working diagnosis (GFX reads the acb results one frame late); the faithful form
needs the kept GFX wait and the stalled dispatch named first.

**What arm c is and is not.** `BC5_0439_SERIAL=c` (normal build only; a diagnostic arm, journaled): an acb whose
top-level stream waits on a label that a GFX job in flight has a pending write of is submitted only after the earlier
GFX work has completed (50 ms bound). It gives a correct picture in this title (0 bad scene shots in 4 slot runs and the
shortcut smoke against 38-55 % in the controls) at about 0.8 ms per submit (5-9 % fewer frames by submit count). It is
not the console's order: the console runs the acb beside its dcb and the dcb's piece waits stall the GFX passes until
the acb has released their labels; with arm c the GFX passes of a frame read the acb results of the previous frame, one
frame late. It is not a fix and not a default: an interim default for every title is NOT decided; it would need the first
title's function check, a lean performance check and the maintainer's view first. The faithful form (the GFX piece waits
kept for the GPU) still hangs on this kernel (F917; rr439 slot) until the kept wait and the stalled dispatch are named
(build b, `slot439rb.sh`).

**The mode-2 naming runs (11-23 20:14-20:33; build b 85c63f4c, build c ad3b1e98; each hung, records private in
bc5-private/rb-1123/{m2,b2}, a reboot after each).** With the job table and the whole piece walk inside the timeout
probe (the fault record now waits for the probes: 3.0 s), `BC5_0439_PIECE_WAITS=2` names the cycle. m2: the GFX dcb
(1894 dwords) stops at piece 19 dword 58, WAIT ==1 on 0x20000082e0, value 0xffffffff, no registered writer in g_plw and
no write of it in any of the 72 GFX pieces; every title acb in flight sits on libdrm ring 0 (w428 keeps a queue on ring
0 until its 256th acb), #102 (queue 16) at the head waiting on 0x2010449750, which GFX writes in piece 28, and behind it
queue 24's and queue 40's acbs; the title submits nothing after t 1.300 s. Head-of-line blocking on one kernel ring
(FIFO) is a host artifact. Ring binding v2 (tag rb439, `BC5_0439_RING_BIND=2`: a queue keeps the ring of its jobs in
flight, a queue with nothing in flight takes a ring without an unmet wait; w428's rule stays the off state, and a bake
would need the first title's function and lean checks) put queues 16, 24 and 40 on rings 0, 1 and 2 (0 host holds), and mode 2
still hung the same way (b2): GFX at piece 19 on 0x20000082e0, acb #160 (queue 16) on 0x2010449750, #162 (queue 24) on
0x20104aa630 (GFX piece 33), nothing submitted after t 1.407 s. The title initialises 56 guest compute queues, 5 are
active in the first seconds; only rings 0 and 1 held a waiter at the timeout. Correction to the record's reading: a
job is marked done by the completion thread, which retires fences in submit order, so "not done" for small acbs on other
rings behind a stuck fence does not show they did not run (the "acb #72 stalled in its own dispatches" of rr1 is
withdrawn: it sat behind #71 on ring 0). Open: the writer of 0x20000082e0 (the CPU, a later job, or a write inside an
acb piece that g_plw does not register) and what the title waits for after t 1.4 s. Mode 2 is not runnable on this
kernel yet; arm c stays the working diagnosis.

**The writer found (w2, 11-23 20:44, build d 095fd6a9; record bc5-private/rb-1123/w2).** 0x20000082e0 is not the
video-out buffer label (g_labels is host memory, 0x7fb3ba3bd000; FLIP_LABEL_GPU off) but one of eight per-frame title
counters 0x2000008200-0x20000082e0 (set to 0x11-0x18 by the init dcbs, reset to 0 and 0x20000082e0 to 0xffffffff at the
scene's first frame). With `BC5_0439_RR_WATCH` the last 64 jobs and their pieces were searched at the timeout: the
writer is acb #171 (queue 24, 1060 dwords, ring 1, submitted, not done), RELEASE_MEM of 0x20000082e0 at dword 200, gated
only by a WAIT ==1 at dword 55 on 0x2000008000, which the GFX dcb's own root writes by RELEASE_MEM at dword 1882 before
its chain into the pieces. At #171's submit that wait reads as met (value 1 from before) while the in-flight GFX job has
a registered pending write of the label: exp 0430's F4 then makes #171's kernel submission depend on the whole GFX job
("acb wait at 0 on 0x2000008000 was satisfied with a pending write from job ... on ring -1: the submission depends on
it"), and the GFX job waits in piece 19 for #171's release: a cycle of the host's making. F4's cycle guard (F2) sees only
the root's kept waits; the piece waits that mode 2 keeps are invisible to ho430. No guest queue was deferred on the host
in any of the hangs (no "[bc5-q] ... deferred" of 1 s or more). On the console the compute CP decides #171's wait when
it reaches it; GFX writes 0x2000008000 at root dword 1882, long before piece 19. Candidates: F2 counting the writer's
kept piece waits (no dependency, but a stale pass, the F848 risk), or the acquire form (the writer's pending label preset
to busy at its submit, the acb's wait kept for the GPU; no kernel dependency, no stale pass), behind switches, with
mode 2 and ring binding v2.

**Arm A (fa, 11-23 20:59, build e; record bc5-private/rb-1123/fa).** `BC5_0439_F4_PIECES=1` (F2's guard counts the
writer job's kept piece waits; `k439/f4p0439.hpp`, det test PASS) with mode 2 and ring binding v2: F2 refused the
whole-job dependency 10 times ("a cycle, not ordered": waits on 0x2000008000, 0x2013172fe0, 0x2010272fe0, 0x20000081a0)
and F4 never fired; the per-frame counters advanced to 3 (the first frames ran with the GFX piece waits kept), then a
later hang: GFX dcb #203 at a piece wait ==4 on 0x20000082e0 (value 3), its writer again queue 24's acb (#207, ring 1,
RELEASE data 4 at dword 203, gated only by a wait ==4 on 0x2000008000 that was met at submit and three dispatches of
program 0x901e18200), which never reached dword 203. Why it did not progress is not named (no F4, no host deferral,
alone on ring 1 behind its own 8-dword prefix job). The reading "compute jobs started only at the GFX reset" from the
kernel's timeout times is withdrawn (the timers may restart at a reset). B (a preset busy value) was dropped: exp
0430's F3 chose it from a runtime table of seen values (a learned table) and 0430 showed that looking at the label's
value cannot close F848's window. Arm C (`BC5_0439_DCB_TAIL_SPLIT=1`, the dcb root before its tail chain as its own
job, so F4 orders behind the job that holds the root's releases; `tail_chain_at`, det test PASS) is built for the next
slot. A bake of anything that narrows F4 needs the second title's fight test (F848), not installed.

**Arm C (tc, 11-23 21:10, build f; record bc5-private/rb-1123/tc) and the kernel's dumps.** The tail split never
fired (no split counted; the dcb went as one 1894-dword job) and F4 ordered queue 24's acb behind it as in w2: the same
hang. Why C's gate stayed shut (no tail chain in the buffer submit_split sees, no register state, or another submit
path) was not journaled. The devcoredumps of the five hangs: in m2 both compute timeouts are on one hardware ring
(comp_1.1.0, IBs of 1224 and 1080 dwords: queue 16's acb, then queue 24's behind it; the head-of-line case in the
kernel's own record); in every run with ring binding v2 (b2, w2, tc, fa) the second compute timeout is comp_1.0.1, 10 s
after the first reset, and its dump lists no IB (that ring ran 9-23 jobs in the run): queue 24's acb is never the job
the kernel names as hung, so it was likely still waiting in the kernel's scheduler (a dependency, or an entity not yet
run; exp 0427: a libdrm compute ring index is no fixed hardware queue) rather than stalled on the GPU. Not proven.

**The kernel-submit record (fn, 11-23 21:23, build g 4ace16c8; `k439/mkfn439be.py`; record
bc5-private/rb-1123/fn with the top session's root fence log).** Arm A's run with `BC5_0439_FN_RECORD=1`: no kernel
submit carried a CS dependency (F2 refused F4 as in fa). At the host's timeout 8 of our jobs were pending: the GFX
dcb (1648 dwords) and seven compute jobs on libdrm rings 0, 1 and 2, among them two 8-dword prefix-only jobs that cannot
stall by themselves, and queue 24's acb (1128 dwords, ring 2). The root fence log (amdgpu_fence_info, twice a second)
shows at 21:23:13.747 the GFX ring with two jobs emitted and unsignaled and every hardware compute ring with emitted
equal to signaled: if our compute jobs were submitted by then, they had not been emitted to any hardware ring (held in
the kernel's scheduler). The next sample is 10.6 s later (the read blocked during the stall), so the submits' order
against that sample is not fixed to the needed 0.3 s: likely, not a finding. Next: a 20 Hz root reader that cannot
block, and wall-clock times in the submit record.

**The kernel's VM ordering (fn2, k0, vk; 11-23 21:32-21:57; records bc5-private/rb-1123).** With every GEM VA op and
kernel submit recorded in wall-clock time (fn439, `k439/mkfn439be.py`) and the top session's 20 Hz root log of
amdgpu_fence_info: in fn2 the host unmapped 2 MiB at 0x1011600000 (K1R's read-only zero cover, dropped because the CPU
had written the chunk; all 104 unmaps of the run are that cover) 2 ms after the GFX dcb's submit, and every later
compute submit stayed pending, 8-dword prefix jobs included. Kernel source (gregkh/linux v7.3.4, read by a fetch
agent; the ogc10 patches are not visible): a GEM_VA UNMAP or REPLACE puts the old mapping on vm->freed and the ioctl
runs amdgpu_vm_clear_freed, which syncs to the VM root's reservation with AMDGPU_SYNC_EQ_OWNER ("Implicitly sync to
command submissions in the same VM before unmapping") and stores its fence in vm->last_update; every command submission
syncs to vm->last_update (amdgpu_cs_vm_handling). So one mapping removal while the GFX job with kept piece waits runs
holds every later job of the process, the releaser of its label included: a whole-VM ordering the console does not
have. k0 (`BC5_GUARD_K1R=0`, no cover) hung the same way on the one unmap left (16 KiB private page 0x200070000, 0.8 ms
after the dcb's submit). vk (`BC5_0439_VA_DEFER=1`, `k439/mkvd439be.py`: an unmap is kept while a GFX job is in flight,
with K1R off) ran about 1,100 frames with every GFX piece wait kept for the GPU (15,940 kernel submits; one unmap kept,
never issued), then hung once more on F4: an acb's satisfied wait on 0x2013172fe0 got a whole-job dependency on GFX job
2257, whose piece 36 waits for 0x20000081c0, which that acb releases; F2's piece-aware guard missed this case. REPLACE
over the cover syncs the same way (v7.3.4), so K1R's saving needs another form (real backing from the start, about 588
MiB pinned in this title, the faithful option; or none).

**F4 in mode 2 (vk2, vk3, 11-23 22:09-22:22; records bc5-private/rb-1123/vk2, vk3).** With every F4 journaled (f4p439
step 2): in vk2 the slipping F4's writer, a GFX job, was not in ho430's job_waits at all (its root packets were not in
the executed list job_submitted walks, so arm A's piece walk never ran for it). Step 3 takes the writer's buffer from
the rr439 job table at F4 time and walks its pieces (`bc5/f4p0439.hpp`); in vk3 it refused two cycles and the run got
about 815 frames with every GFX piece wait kept, then hung on an F4 whose writer GFX job held 48 kept waits, none on the
waiting buffer's own writes: the cycle ran through work queued behind the ordered buffer, which no question about the
waiting buffer can answer. So in mode 2 the whole-job dependency itself is what does not fit (on the console each
queue's CP decides its waits when it reaches them). The arm `BC5_0439_F4_OFF=1` (tag f4off439, mode 2 only; exp 0430
F848's stale-pass risk taken) is built (unit d15a2d6c) and not yet run: the box went to the maintainer's play of arm c
at 22:31 (the live launcher switched to `t3-test.sh.arm-c` by the top session; the previous one kept as
`t3-test.sh.before-armc-1123`).

**Mode 2's remaining obstacles (vf, vn, vs, v3; 11-23 22:49-23:18; records bc5-private/rb-1123/{vf,vn,vs,v3}).**
Each run kept every GFX piece wait for the GPU with the arms before it, and each ended in a named, host-made stop:
- vf (`BC5_0439_F4_OFF=1`, no F4 dependency; F848's risk taken): about 676 frames, then an unmap the deferral rule had
  to issue at once because a new mapping overlapped a kept one: the direct-memory BO merge pass (exp 0022/0169)
  re-cut 0x1006c00000 (0x7200000 -> 0x7400000) 2.6 ms after the dcb's submit.
- vn (+ `BC5_0439_NO_MERGE=1`, tag nm439, the merge pass skipped): about 819 frames, then the backend's own job slot
  regrow (a 65,608-dword acb over a 256 KiB slot: unmap and map of the slot, outside va_unmap).
- vs (+ `BC5_DIRECT_SLOT_PREALLOC=1024:1024`, exp 0432's existing word): about 1,041 frames, no unmaps; then
  head-of-line: queue 24's acb that the GFX dcb waited for (0x20000080c0) sat on libdrm ring 1 behind queue 0's
  waiting acb.
- v3 (`BC5_0439_RING_BIND=3`: a queue not placed behind another queue's waiter, held until its own jobs end): about
  1,164 frames, the same head-of-line (queue 24 behind queue 0 on ring 1; its own earlier job counted in flight because
  the completion thread retires fences in order and was waiting on the stuck GFX fence).
The limit: 4-5 guest compute queues are busy in steady frames (16, 24, 40 and 0 always, 50 at times; 56 touched once
at start), against BC5's 4 libdrm compute ring indices (`kComputeRings`), while the kernel has 8 hardware compute rings
(amdgpu_fence_info: comp_1.0.0-1.3.0, 1.0.1-1.3.1) and re-picks the hardware queue of an idle ring index (exp 0427).
The faithful order needs each busy queue on a hardware queue of its own while it has work in flight: the brief for exp
0443's pin module. No scene picture of mode 2 yet: every run ended in the load screen or the scene's first seconds.
The box went to the title swap at 23:25 (the second title's regression test; the third title to be reinstalled from
the NAS package before morning).

(more to come)

**Verdict.** (to come)

**Memory wall, scripted (tag mw439, 11-24 05:03-06:31, the top session's order; records private in
bc5-private/mw-1124/{a,b}).** `mw439.sh` runs the arm-c launcher's words (PIECE_WAITS=1, SERIAL=c) with a fresh
KYTY_BC5_SAVEDATA_DIR, no pad input, 2,600 s, the 1-s sampler (`memsample439.sh`), BC5_GUARD_LEDGER=1 (a 10-s guard line
in the capture's `direct.log`) and BC5_DIRECT_BREAKDOWN=1. It carries a test guard (MemAvailable < 500 MiB or swap used
> 3 GiB: record, then end the emulator); that stop is a diagnostic in this script only, never in a shortcut. Neither run
reached it. `mwsum439.py` summarises both records.
- Neither run reached the scene. Run a (binary 3939f323) stayed on a black loading screen with the spinner for the whole
  43 min. Run b (priv30 e96631ec, + BC5_0439_NO_MERGE=1 BC5_0439_VA_DEFER=1) reached the Digital Deluxe bonus dialog
  after about 40 min and waited there for ✕. This route is a load, not a play.
- The growth is the title's direct memory, pinned by data, in 512-MiB import steps, with pauses between steps:

  | | t 10 s | t 310 s | t 1210 s | t 2590 s |
  |---|---|---|---|---|
  | a: pinned direct / reserved (MiB) | 4,362 / 4,869 | 8,224 / 8,537 | 9,762 / 10,026 | 10,790 / 11,113 |
  | a: GTT / MemAvailable (MiB) | 4,757 / 8,809 | 8,619 / 4,899 | 10,155 / 3,474 | 11,181 / 2,455 |
  | b: pinned direct / reserved (MiB) | 4,362 / 4,869 | 8,738 / 9,061 | 10,276 / 10,625 | 11,020 / 11,252 |
  | b: GTT / MemAvailable (MiB) | 4,784 / 8,882 | 9,160 / 4,472 | 10,698 / 2,851 | 11,452 / 2,173 |

  - Heaps: anon[D] 244 → 6,674 MiB pinned (a) and → 6,899 (b). anon[E] stays at 4,030, the rest under 100.
  - Direct BOs: 13 → 1,083. Guard views: 846 → 37,395. Emulator CPU maps: 126 → 10,662. RssShmem follows the pinned bytes
    (6.4 GiB in a).
  - Swap used stayed under 0.6 GiB.
  - Pinned follows reserved within about 300 MiB: BC5 pins nearly all of the direct memory the title maps and writes.
    Neither the job slots, the K1R covers nor merges grow on their own.
  - NO_MERGE + VA_DEFER (b) does not change the curve: the same 512-MiB steps, b slightly ahead in time. Its 885 merge
    lines against 224 count log mentions, not merges done.
- Not yet answered: whether the title's direct memory on the console reaches the same size (the ~11 GiB it reserves
  suggests it does); and the play's rate, since the maintainer's freeze came within about 10 minutes of play, where these
  loads took 40 minutes to reach 11 GiB.

**mw439 read again (11-24 morning, laptop, from the two runs' journals).** Correction to the section above: the 512-MiB
steps and the 40-min loads are both caused by `BC5_DIRECT_BREAKDOWN=1`, which mw439.sh turned on. The breakdown
(exp 0051) walks every view of the memfd with SEEK_DATA/SEEK_HOLE on the game thread each time the imports grow by
512 MiB. Its own comment gives 25-80 s at 11,000 views. Here it ran at 800-37,000 views:
- Each of its 13 calls (run a) and 14 (run b) is followed by the run's long flip gaps: 16, 20, 24, 49, 98, 166, 255,
  429, 592 and 769 s in run a.
- Those gaps add up to 2,420 s of run a's 2,600 and 2,209 s of run b's.
- The time sits in `direct_sync`, outside all of its profiled parts (views, scan, merge, maps under 0.3 s).
- So the steps are the breakdown's threshold. Game time between steps was seconds: run a reached 11.2 GiB pinned on
  the loading screen with about 3 min of unstalled game time. The real rate is much faster than the section above
  says. The 40-min loads are the breakdown too; the shortcut's launcher does not set it.

Who owns the pinned memory (run a, the last breakdown at 10,274 MiB, against the first at t 9 s):

| Owner | Views (first → last) | Reserved MiB (first → last) | With data MiB (last) |
|---|---|---|---|
| anon, large views | 6 → 1,047 | 4,656 → 6,738 | 6,496 |
| views under 1 MiB | 802 → 32,447 | 100 → 3,798 | 3,731 |
| SceAgcDriver + private | 3 | 90 | 84 |

- The eager heaps (GpuGarlicMemory, GpuOnionMemory; anon[E] 4,030 MiB) are pinned in one go at t 9 s: GTT 220 → 4,560
  MiB. SEEK_DATA cannot tell their written pages from pages the pin allocated.
- The rest is pinned by data: chunks of 2 MiB under a view where SEEK_DATA finds data, imported at the next submit's
  `direct_sync` (`ls415_import`). So BC5 pins at the title's first write, not at map time and not at first GPU use.
- Under the by-data rule, with-data is 96-98 % of reserved. The title writes what it maps: a streaming allocator, about
  3.7 GiB of it in 32,000 small mappings.
- Those pages are resident in the memfd (RssShmem) whether pinned or not; pinning only makes them unswappable.
- Not in these logs: which guest call maps them (guest memory calls are not journaled), and how much of the eager 4 GiB
  the title ever writes.

**Wall run in the 11-24 07:46-08:42 slot (tag mw439, run mw439a-1124-0746; arm a, 3,300 s, `BC5_DIRECT_BREAKDOWN` off;
records private in bc5-private/mw-1124/r).**
- The route did not run. My edit left a literal backslash-n in the line that starts `mwroute439.sh`, so the shell ran a
  command named `n`: no press, no key log. I had skipped the laptop stand-in. Rerun after the slot, it reproduced the
  failure. With the fix (a byte replace, `fixcont.py` in the session scratchpad) the stand-in writes the press and the
  key log. The fixed script is on the box.
- So the run sat on the Digital Deluxe dialog for 55 min. Without the breakdown the load is fast:
  - GTT went from 166 to 11,371 MiB by t 43 s. MemAvailable went from 13,633 to 2,057 MiB.
  - The guard reads 11,018 MiB pinned and 38,530 views at t 310 s. That is the end state run b reached after 40 min,
    and it stayed flat to the bound.
  - No flip gap over 2 s; 65,205 frame-profile lines.
  - RssShmem fell from 3,124 to 1,904 MiB over the hour, with swap used 34 → 57 MiB; MemAvailable stayed at
    2.2 GiB.
- At the dialog the title holds 11.0 GiB pinned, 4,030 of it eager and 6,897 by data. The 500-MiB guard needs about
  1.5 GiB more: that has to come in the scene.

**The 08:46 OOM kill and the 08:50 freeze (11-24 morning; the box went silent at about 09:00, reset by hand).**
- Run mw439a-1124-0846 (arm a, 1-s sampler): the kernel OOM killer killed the emulator at t 72 s, 27 s after the first
  cross dismissed the bonus dialog and the world load began.
  - The fault came from `bc5-apr-q1` in `shmem_fault`: a fresh page of the direct-memory memfd.
  - The sampler, one second before: MemAvailable 2,372,004 kB, GTT 11,299 MiB, emulator RssShmem 7,154,824 kB.
  - The kernel's report:

    | Field | Value |
    |---|---|
    | shmem | 11,279,476 kB |
    | inactive_anon | 11,079,236 kB |
    | inactive_file | 2,242,384 kB |
    | mapped | 7,443,492 kB |
    | free | about 140 MB |
    | free swap | 7,237,112 of 7,778,300 kB |

  - So more than 2 GB went in under a second. Reclaim freed neither the file cache nor shmem, because nearly all the
    shmem is GUP-pinned userptr memory that cannot be swapped. Why the 2.2 GB of inactive file pages were not taken is
    not shown: TODO(verify) with /proc/vmstat at the next kill.
- Run mw439a-1124-0850 (0.1-s sampler): the route left a chain of gift dialogs (crosses added by hand to the input
  file), and the opening cutscene was on at 08:55:40 (shot private). The box stopped answering ssh and ping at about
  09:00. The sampler file (fsync per line) is still on the box.
- What is shmem-backed and pinned is the guest's direct memory, one memfd imported as userptr BOs. At the dialog
  (run 07:46): 11,018 MiB, of which 4,030 MiB is the eager heaps (GpuGarlicMemory, GpuOnionMemory), pinned whole at
  start, and 6,897 MiB is chunks pinned by data. BC5's own share is small: private 94 MiB, RssAnon about 0.1 GiB.
- The PS5's direct-memory budget for a title is not recorded here (TODO(verify)). The title had mapped 11,252 MiB of
  direct memory before the world load, all of it physical on the console too.

**Run x439mwu (11-24 09:30-10:45; the maintainer played in it, so the numbers are a record, not a measurement) and the
freeze watch (10:00-10:45, nobody pressing). Records private in bc5-private/mw-1124/u.**
- **No freeze in 75 min.** The emulator was alive at 10:45 and was ended there. The 08:50 run froze at 09:02:29 with
  the same memory picture, so the measured memory does not explain that freeze.

  | Time | MemAvailable | Swap free | GTT | Shmem | Unevictable | SUnreclaim | PageTables | VmPTE | CPU maps |
  |---|---|---|---|---|---|---|---|---|---|
  | 09:35 | 1,250 | 7,051 | 12,131 | 11,925 | 104 | 300 | 58 | 35 | 22,203 |
  | 09:45 | 1,403 | 6,810 | 12,229 | 11,869 | 62 | 312 | 73 | 49 | 35,372 |
  | 10:00 | 1,398 | 6,633 | 12,212 | 11,857 | 62 | 315 | 76 | 52 | 36,568 |
  | 10:40 | 1,378 | 6,646 | 12,212 | 11,859 | 62 | 314 | 75 | 52 | 36,568 |

  All values in MiB except CPU maps. Mlocked equals Unevictable throughout.
  - The lowest MemAvailable was 986 MiB at 09:33:33, in the load after the route's crosses. That is the spike that
    OOM-killed the 08:46 run.
  - The 08:50 run's last line (09:02:29): MemAvailable 1,388 MiB, swap free 6,845 MiB, GTT 12,212 MiB, CPU maps 29,987.
- **What makes the CPU-map count grow** (60-s snapshots of /proc/<pid>/maps):
  - `memfd:KytyDirectMemory` rw-s mappings went from 6,477 to 26,747 while their total stayed at about 25 GB (views
    alias the memfd).
  - The PROT_NONE reservations between them went from 4,289 to 9,043. Nothing else changed.
  - So the guest's direct views fragment: its physical map ops ran at about 800/s in the scene (exp 0438's A1P
    counter: 77,073 at t 180 s, 377,028 at t 660 s in the 08:50 run). Each piece that is not file-contiguous with its
    neighbour is its own VMA, and each hole left is a PROT_NONE VMA.
  - The count grows only while the title streams: it held at exactly 36,568 through the 45-min idle watch, and the
    08:50 freeze came at 29,987. So the count is not the freeze's cause.
- **Kernel stream** (`journalctl -kf` to the laptop; `sudo -n dmesg -w` was refused by this session's permission
  check): one line, at 09:38:05, `clocksource: Watchdog remote CPU 2 read timed out`. Its meaning here is open
  (TODO(verify): a CPU stalling with interrupts off?).
- **Saves.** The run's save, read-only, with md5 lists beside each:
  - `~/bc5-data/saves/TITLE3-20261124-x439mwu` (09:59);
  - `-end` (10:46), because the title rewrote `memory.dat` after the first copy.
  - The original folder `save-mw439a-1124-0930` is kept.
- **Route.** Crosses every 15 s from 45 to 330 s pass the gift dialogs (the 11-22 menu route does not handle them). A
  route from the new save to the scene is not worked out yet.
- **Still unknown:** the cause of the 08:50 freeze. Its kernel lines are lost: journald had not flushed since 08:56,
  and pstore was empty.

**The freeze (08:50 run) against x439mwu, and the edge blocks (11-24 ~11:00, laptop).**
- **Same between the runs:** binary 3939f323 and every switch word (diffed from both meta.txt), kernel
  7.3.4-ogc10.1, sampler about 0.16 s a line, and the memory plateau (MemAvailable 1.39 GB, GTT 12,212 MiB).
- **Different:**
  1. **Boot.** The 08:50 run ran on the boot where the kernel OOM-killed the 08:46 emulator (08:47:16), 3.5 min
     earlier. x439mwu ran on a fresh boot (09:06). gate439 counts only amdgpu/drm lines, so it admitted the 08:50 run.
  2. **Input.** 08:50: crosses at 45 and 126 s, four by hand at 08:54, the menu step's every 5 s to 301 s, then
     nothing for 6.5 min in the opening cutscene. x439mwu: crosses every 15 s to 330 s, then the maintainer's pad play
     to about 10:00, then 45 min idle.
  3. **Place.** 08:50 froze in the opening cutscene. x439mwu went further: the fight at the burning hut, the overlook
     on the horse.
  4. **Maps snapshots.** x439mwu also gzipped /proc/<pid>/maps every 60 s.
  5. **The kernel line.** `clocksource: Watchdog remote CPU 2 read timed out` came at 09:38:05 in x439mwu's boot.
     Whether the 08:50 boot had one before 08:56 is not read here.
- **The freeze moment:** about 09:02:29.4, the sampler's last fsynced line. Unsynced files lost their tail:
  `direct.log` ends about 17 s earlier, and play-last.log ends in 12,627 zero bytes.
- **The box was not dead:** it did not reboot itself, and the hardware watchdog (RuntimeWatchdogSec=30s, fed by PID 1)
  and the panic-on-lockup settings did not fire; pstore was empty. So no CPU lockup was detected, and PID 1 kept
  running while the network and display stopped.
- **Catcher without sudo, now in memsample439.sh:**
  - `MS_KLOG=1` tees `journalctl -kf` into `<tag>-klog.txt` with an fsync per line, ahead of journald's own flush.
  - Each sample line now ends with memory and IO pressure (avg10), allocstall, pgscan_direct, oom_kill, and
    procs_running/procs_blocked.
  - The laptop stand-in passes: the tee stops with the sampler.
- **With sudo (the top session's part):**
  - a journald drop-in with `SyncIntervalSec=5s`;
  - `dmesg -w` from a root unit into an fsynced file, which works even when journald stalls;
  - `kernel.sysrq=1`.
  - netconsole would need the laptop on the box's LAN: Tailscale's tun device is no netpoll target, TODO(verify).
- **Edge blocks.** In shot t990s (09:47, the fight on wet ground) the reflection on the puddle around the moving
  character ends at straight vertical and horizontal cuts, and a dark blocky copy of his silhouette trails beside him.
  The still shot t1650s (on the horse, dry ground) shows clean edges.
  - The blocks are tied to motion and to the wet-surface reflection (SSR or its temporal/denoise pass). That points at
    a pass reading a buffer a frame stale, for example arm c's one-frame-late acb results (tile classification,
    hierarchical depth, motion), rather than static DCC/HTile state.
  - The pass itself is not named yet: no frame dump of this scene exists.

### Edge test from the snapshot save (11-24 12:30-13:06, tag eg439, the top session's GO)

- **Setup:** `k439/edge439.sh 600`, one boot.
  - Each arm runs `mw439.sh a` with a fresh copy of the read-only snapshot `TITLE3-20261124-x439mwu-end`
    (`MW_SAVE_SRC`) and a fixed pad route: crosses from 40 to 110 s, then from 125 s the `edge` step of
    `mwroute439.sh` (stick moves) with a shot every 2 s.
  - The sampler ran with `MS_KLOG=1` at 0.5 s.
  - GPU kernel lines 4 -> 4: all four are boot lines (the command line, TMZ, the watcher); the kernel logged nothing at
    all from 12:30 on.
- **Arms and results** (the horse on the overlook, dry ground):
  - **c** (3939f323, PIECE_WAITS=1 SERIAL=c): stuck at about 15 s, after the intro movie's first decoded pictures (8
    flips). The game threads sat in cond waits for 190+ s, with no GPU line. Ended by hand at 262 s; log in
    `runs/mw439a-1124-1230-egc/stuck-play-last.log` on the box. Not repeated.
  - **c-E** (c without `BC5_DIRECT_EAGER_GPU_WRITE`): in the game, 23-24 fps. Max GTT 9.90 GB, min MemAvailable
    3.63 GB, zram used about 0.4 GB.
  - **S** (`SERIAL=1`, EAGER on): same scene, 5.5-6 fps. Max GTT 9.90 GB, min MemAvailable 3.59 GB.
  - **D** (c + `BC5_0439_DCC_UNCOMPRESSED=1`, EAGER on): the whole picture is covered in noise speckle. Max GTT
    9.94 GB, min MemAvailable 3.47 GB.
- **EAGER_GPU_WRITE:** in this scene, c-E's memory equals S's and D's, which both had EAGER on. So no gain is shown
  here. The morning's 12.2 GiB GTT came from the fight scene after 45 min of play; a same-scene c run is still owed.
- **Edge blocks:** small rectangular cuts at object borders (the hat, the shamisen head, pine branches, the mountain
  edge) show in both c-E and S. SERIAL=1 removes arm c's one-frame lateness, so lateness is **refuted** as their cause.
  D cannot separate DCC, because the word breaks the whole picture. Open: HTile/DCC metadata, or a temporal/upscale
  pass. Next is a frame dump of c-E in this scene.
- **The shortcut** (the maintainer's word, 11-24 ~12:55): `t3-test.sh` (`ada55925`) is arm c without EAGER, with
  `MS_KLOG=1` in its sampler; the old one is kept as `t3-test.sh.before-noeager-1124` (`6542b003`).
- **Host-run candidate** (ADR 0015, the model of 9490cd82): `k439/t3-test.sh.host`.
  - The emulator is exec'd under `systemd-run --user` with no distrobox hop.
  - A `hostdeps` check runs before the start: ldd shows no missing or non-system library, and the binary needs no
    GLIBC/GLIBCXX newer than the host's.
  - Its DRY=1 check on the box waits for a free box. `play439.sh` needs no change for the host (an unpacked title, no
    mount).

### cs439: the edge-block suspects 1 and 2 as switches (11-24 ~15:00, laptop; build and runs in the top session's next slot)

- **Kit:**
  - `k439/cs0439.hpp` and `k439/mkcs439be.py` patch `direct.cpp` and `state_stack.cpp`; `state_stack.hpp` is unchanged,
    so the class layout other units see stays.
  - `box439b2.sh` takes `UNITS_BE` with `src/state_stack.cpp` as a fourth backend unit.
  - `k439/slot439cs.sh` runs the cleanup, the build (priv30's kit + cs439 into `d2/priv31`), then the arms.
- **Switches,** all off by default, each testable alone:
  - `BC5_0439_CS_COUNT=1` counts CLEAR_STATE cmd 0/1/2 per level (root, piece depth, inside COND_EXEC), plus the root
    tracker's push/pop/unmatched/conditional.
  - `BC5_0439_PUSH_NO_CLEAR=1`: a push is NOP-ed instead of becoming a clear. The root tracker keeps the context valid
    and its pop restores.
  - `BC5_0439_PIECE_STATE_STACK=1` runs the tracker over the GFX job's pieces in collected order. Each pop outside
    COND_EXEC gets 2048 dwords of room for its restore, and the referencing IB's size is set to the grown size.
  - `BC5_0439_PASS_CONTEXT_CONTROL=1`: the guest's CONTEXT_CONTROL passes (policy.cpp:614, `safe_context_control`).
  - `BC5_0439_REGTAB_DUMP=<dir>` with `_AT=s,..` writes the next GFX dcb's pieces (frame.py naming) and, for every
    LOAD_*_REG[_INDEX] packet, the memory it loads. The data is read on the CPU at submit; there is no chip readback,
    unlike exp 0400.
- **Laptop checks:**
  - `test_cs0439.cpp` with the patched `state_stack.cpp`: ok, with the switch both unset and set.
  - `test_cs0439b.cpp` (walk helpers, COND_EXEC, the one-arm dump): ok.
  - clang -fsyntax-only of the patched `direct.cpp`: no error outside the missing libdrm headers.
- **Why suspect 1 can survive the root's per-frame reset of about 920 context registers.** That reset repairs any
  root-level loss at the next frame. What it cannot repair is a CLEAR_STATE that clears in the middle of a frame:
  - a pop inside a piece, which gets no restore;
  - a pop inside COND_EXEC;
  - an unmatched pop at the root (empty stack: the filter's cmd 0).

  Each one leaves the draws that follow, until the guest writes the registers again, on clear-state values.
  CS_COUNT tells whether any exist. If every push and pop is at the root and matched, suspect 1 is dead without a
  picture test.

### cs439 slot (11-24 14:42-15:45, on the host since ADR 0015; private builds priv31 eec0a702, priv32 551618d3)

- **Launcher.** From 14:41 the test launcher runs the emulator on the host under the user manager, with no
  distrobox: `t3-test.sh` 0ceaeb1c (the candidate `t3-test.sh.host`). A host-library check runs before each
  start; DRY passed. The old launcher is kept as `.before-host-1124`. `mw439.sh` runs on the host too
  (`MW_DISTROBOX=1` for the old way).
- **Correction to the edge test above.** `BC5_DIRECT_EAGER_GPU_WRITE=1` is a kSoft default row in this kit
  (`mkb2439_add.py`), so dropping the word from the environment does not turn it off. The c-E run's log reads
  `BC5_DIRECT_EAGER_GPU_WRITE=1 (1: GPU-writable direct views eager)`. Arm "c-E" was arm c, and the shortcut has
  run with EAGER on throughout. Only `=0` turns it off.
- **Cleanup.** d2/priv11..29 and 22 obsolete pinned binaries were deleted, about 13 GB. 56 GB free afterwards.
- **Arms** (each 420 s from the snapshot save, scripted edge route):
  - **cE1** (DCC_PRESENT=1): exit 65 at 2 s: `TextureCache: compressed video-out read requires clean native GPU
    contents`. That mode cannot run this title.
  - **cE2:** stopped by the test guard at 135 s, MemAvailable 0.43 GB. The emulator was flat; system-wide AnonPages
    jumped to 3.8 GB within 20 s in another process (not identified). The sampler now writes the top-RSS processes
    below 1 GB.
  - **N0** (counts only):
    - CLEAR_STATE per frame at the root: one push and one matched pop, plus one pop inside a COND_EXEC.
    - The tracker leaves that pop to the filter, so it becomes cmd 0, a full clear with no restore.
    - Pieces: no push or pop at all.
  - **N1** (PUSH_NO_CLEAR + PIECE_STATE_STACK): no change seen; the piece stack had nothing to do.
  - **N2** (PASS_CONTEXT_CONTROL):
    - The maintainer played in it (CPU maps 9,203 -> 11,735 and GTT 9.86 -> 11.04 GB from 15:07, while both stayed
      flat in N0 and N1; shots of the spyglass, a cutscene and the ride).
    - His words: the squares at the characters' borders were gone. The close-up's hat border is clean.
    - It ended in a whole-machine freeze at 15:10:45, with no kernel line: MemAvailable 2.4 GB, memory PSI 8-9 %,
      IO full 43 %, 5-6 tasks blocked, pgscan_direct 0.4M -> 8.3M.
    - The emulator's resident shmem fell 5.9 -> 0.2 GB while swap use rose only 0.4 GB, and Unevictable was
      0.19 GB. So reclaim kept scanning and unmapping pinned memfd pages it cannot free. TODO(verify) the kernel path.
  - **N3** (COND_POP_NOP): 420 s, no GPU line. Scripted shots show no blocks, but neither do N0's or N1's in this
    dry horse scene, so scripted shots do not separate the arms here.
  - **D0:** the CC census and the register tables.
- **CC census** (all four arms of priv32):
  - CONTEXT_CONTROL per frame: `0/0` (as often as the conditional pop), `91018003/80000000`, `91018003/80018003`,
    then `80000000/80000000` (as often as the push).
  - Per frame: three LOAD_SH_REG (0x5f) and three LOAD_CONTEXT_REG (0x61); every load address is mapped.
- **The register tables** (`regtab-1124`, private):
  - LOAD_CONTEXT_REG reads 960 dwords at 0xfe0008000 and LOAD_SH_REG 641 dwords at 0xfe0010000, and both areas are
    all zero.
  - Under the forced CONTEXT_CONTROL the CP never shadows into them.
  - Mesa 0866ae7: radeonsi without register shadowing writes CONTEXT_CONTROL as update-enables only, i.e.
    0x80000000/0x80000000 (`si_state.c:4980-4983`). With shadowing it sets the LOAD/SHADOW enables, then LOAD_*_REG
    packets on a shadow buffer (`ac_shadowed_regs.c:3070-3086`, `si_state.c:4973-4978`).
  - The guest's pair is that shadowing setup. Bit positions: TODO(verify); the generated headers are not in the
    sparse Mesa checkout.
- **Why the value was forced.** 9c91296e (2026-09-30, exp 0016) gives "the console's load/shadow enables hung the
  BC-250". But exp 0016's run 1, the one that reset, passed the raw stream: CLEAR_STATE cmd 1/2 (F27 shows those stop
  the CP), LOAD_*, COND_EXEC. CONTEXT_CONTROL alone was never isolated. N2 ran the guest value for 5 min with no GPU
  line.

### N2d and the next build (11-24 15:44-16:05)

- **N2d** (the guest CONTEXT_CONTROL + the register tables, 240 s, scripted, the top session's GO): no GPU line,
  min MemAvailable 3.59 GB. Under the guest value the CP fills the title's shadow areas, in both dumped frames:
  LOAD_CONTEXT_REG's 0xfe0008000 has 163 of 960 dwords non-zero, LOAD_SH_REG's 0xfe0010000 has 15 of 641. Under BC5's
  forced value (D0, N3) both areas are all zero. **The mechanism is confirmed on the BC-250:** forced, the title's
  per-frame restore loads nothing current; passed, it loads the shadowed state.
- **Other titles.** The same preamble is built by the system driver (`libSceAgcDriver`), not by the game:
  - exp 0011 (title TITLE1) shows CONTEXT_CONTROL plus three LOAD_{CONTEXT,SH,UCONFIG}_REG from the
    shadow-register tables at the same 0xfe0008000 (`SceGnmShadowRegInfo`);
  - F35 describes the console driver toggling context shadowing around its push/pop.

  So every title shadows. A bake would change every title; each needs its own check.
- **Written for the next build** (`cs0439.hpp`, `mkcs439be.py`), off by default:
  - **`BC5_0439_CC_GUARDED=1`:** the guest CONTEXT_CONTROL passes in a GFX submit whose root holds at least one
    LOAD_UCONFIG/SH/CONTEXT_REG and all of their table ranges are GPU-mapped. Otherwise the forced value stays and is
    counted (no LOAD / unmapped). `mapped` vouches for a GPU mapping; BC5 maps direct imports read+write.
    TODO(verify) write permission per range.
  - **`BC5_0439_MLOCK_IMPORTS=1`:** each udmabuf import of direct memory gets a host read-only mapping of the same
    memfd range, `mlock`ed, so its pages are mlocked (unevictable LRU) for every mapping; it is released at
    `free_shared`.
    - Kernel path, recalled from the public source, TODO(verify) the lines on 7.3: udmabuf pins
      (`memfd_pin_folios`), a pin does not make a folio unevictable, and reclaim decides by `folio_evictable()`
      (mapping_unevictable / mlocked).
    - Cost: no extra RAM (the pages are already resident and pinned), one VMA per import.
    - RLIMIT_MEMLOCK: read on the box at 2,199,023,616 bytes for the emulator (limits.d/memlock.conf) against about
      10 GB pinned. Past about 2 GiB the locks fail and are counted, so the full effect needs a raised limit or
      CAP_IPC_LOCK (root).
  - Tests: `test_cs0439c.cpp` (the guard rule) ok; the earlier tests ok. The patcher applies to the repo's backend.
    The kit's prep regenerates `d2/be` at the next build, where it is applied again.
- **Candidate launcher, not live:** `t3-test-cc.sh` (7133ee80, on the box beside the live 0ceaeb1c) is the live
  launcher on priv32 551618d3 with `BC5_0439_PASS_CONTEXT_CONTROL=1`, the arm in which the maintainer saw the border
  blocks gone. DRY passed on the host.

### Prepared for the next slot (tag mp439; after exp 0442, about 18:30, and the reboot that applies the raised memlock limit)

- **Build priv33:** `CS_CLEAN=0 CS_PRIV=33 CS_ARMS="G1 P0 P1" bash slot439cs.sh` builds the priv30 kit plus cs439 with
  `CC_GUARDED`, `MLOCK_IMPORTS` and `COND_POP_NOP` (all off by default), then runs:
  - **G1:** CC_GUARDED + COND_POP_NOP + MLOCK_IMPORTS, scripted, 420 s. Read: the ccg counts (all GFX submits passed
    is the expectation), the ml lines (locked GiB, failures), and the emulator's `/proc/<pid>/limits` and VmLck, which
    are noted 40 s in. The limit should read unlimited after the reboot.
  - **P0 / P1:** CC_GUARDED + COND_POP_NOP with MLOCK_IMPORTS off / on, plus `memp439.py`.
    - memp439.py applies pressure from outside, 180 s in: it allocates and touches anonymous memory until
      MemAvailable reads 1500 MiB, holds it 90 s, then frees it.
    - Brake: memory PSI full avg10 > 10 % or MemAvailable < 700 MiB frees everything at once; its oom_score_adj is 1000.
    - The run's own guard stays at 512 MiB.
    - Read per second, from the 0.5 s sampler and memp's log: pgscan_direct/s, PSI some/full, the emulator's resident
      shmem, blocked tasks, and whether the brake fired.
    - Expectation if F927's reading holds: P0 shows scans in the millions, resident shmem falling and PSI rising
      (maybe the brake); P1 keeps resident shmem, with VmLck about the pinned size and scans far lower.
- **The thrash shown without his riding:** P0 against P1 under the same applied pressure; streaming is not needed.
  The other route (a scripted long ride that streams) stays second, because the horse's path from the snapshot is not
  scripted.
- **Risk:** P0 may freeze the box even with the brake, as N2 did at 2.4 GB available. One manual reset at most; it
  runs only on the top session's word, with the maintainer told.

### mp439 slot (11-24 16:51-17:13, clean boot 16:49 with memlock unlimited; priv33 c0ec7b38)

- **Build.** The first try stopped on `-Werror,-Wimplicit-int-float-conversion` in cs0439.hpp's ml line (fixed with a
  cast). The second attempt built normal c0ec7b38, lean e65e588e and archive 02c7facc; the shared builds are
  unchanged. Its arms were skipped by the slot script's old start guard (16:33), so the arms ran a third time
  with `CS_LAST_START=1800`.
- **G1** (CC_GUARDED + COND_POP_NOP + MLOCK_IMPORTS, 420 s, scripted): no GPU line, min MemAvailable 3.31 GB.
  - Emulator limit `Max locked memory unlimited`; VmLck 8.31 GB at 40 s. ml: 0 lock failures.
  - ccg: about half the GFX submits passed the guest value and half kept the forced one because their root holds no
    LOAD (P1 at 21,000 submits: 10,511 / 10,489 / 0 unmapped). Whether those no-LOAD submits carry a CONTEXT_CONTROL
    of their own is not recorded, so CC_GUARDED is not yet shown to equal N2's plain pass.
- **P1** (as G1, plus memp439.py from 180 s: MemAvailable driven to about 1.55 GB, held 90 s; no brake): no GPU line.
  - Unevictable = Mlocked 9.85-9.90 GB throughout (N2: 0.19 GB).
  - The emulator's resident shmem was flat at 15.66 GB, which counts the lock mappings on top of the guest views.
  - Over the whole hold, pgscan_direct rose about 5,800 and allocstall 80; per second it was 0 apart from one burst
    of 135. Memory PSI full peaked at 3.3-4 % for seconds, otherwise under 1 %. Blocked tasks 0. Swap used about
    0.15 GB.
  - Against N2's freeze (pgscan_direct 0.4M -> 8.3M, PSI 8-9 %, IO full 43 %, 5-6 blocked, resident shmem
    5.9 -> 0.2 GB): no thrash under the lock.
  - Without P0 (the same pressure with the lock off, not approved: it may freeze the box) this does not yet prove
    the lock is the reason.
- **Candidate launcher, not live:** `t3-test-ml.sh` (b41facfa) is the live 7133ee80 on priv33 c0ec7b38 plus
  `BC5_0439_MLOCK_IMPORTS=1`. It keeps N2's plain PASS_CONTEXT_CONTROL, the form the maintainer saw, rather than
  CC_GUARDED, until the no-LOAD half is understood. DRY passed on the host.

### The maintainer's play-1124-1901 froze the box (analysis from records, 11-24 19:0x; no box runs)

Launcher t3-test-all.sh (50b6c182): priv33 c0ec7b38 with PASS_CONTEXT_CONTROL, MLOCK_IMPORTS and COND_POP_NOP; started
from the title start (opening film), not a save. Records: sampler `memsample/play-1124-1901.txt` (to 19:03:17),
`captures/play-20261124-1901/gc/direct.log` (7493 lines); no runs/ log.

- **Measured, direct memory pinned (direct.log "MiB pinned", by emulator time):** 30 s 8.5 GB, 40 s 10.0 GB,
  60 s 10.6 GB, 85 s 11.3 GB, still rising ~40 MB/s, BOs 476 -> 1517, views 4.6k -> 39k. Same counter in the
  save runs: G1 9.49 GB flat from 60 s, P1 9.49 GB, N2 (no lock) 10.05 GB at 90 s and 10.57 GB at 240 s. Sampler:
  shmem 11.9 GB = GTT 11.9 GB (no double import), unevictable = mlocked 11.7 GB, anon 0.14 GB, swap untouched.
- **Measured, the end:** MemAvailable 1.46 GB, PSI under 1.5 % until the last second, when allocstall +161,
  pgscan_direct +11.7k, procs_running 15, procs_blocked 5, IO full 4.8 %; the sampler then stops. No amdgpu line.
- **Reading, Q1:** the route, not a switch. None of the three switches decides what is imported (PASS and COND_POP_NOP
  change packets; MLOCK only locks what is already imported). The import is lazy and never released, so the pinned
  size is what the title has touched so far; the title start plus a new game touches more than the save route, and
  N2 also kept growing without the lock. udmabuf already pins every page of an import at creation, so MLOCK_IMPORTS
  makes nothing unreclaimable that was reclaimable before; it moves the pages to the unevictable list (no scanning)
  and so the failure changes from scan thrash (N2) to file-page starvation (this play). Neither form survives a
  footprint of 11.9 GB + desktop on this box. The fix belongs to the import: release views the GPU no longer
  references, and measure how much of the 2 MiB-chunk rounding is padding (view bytes against pinned bytes: not
  logged yet).
- **Q2, film grain:** no record separates it. The save runs' shots at 30 s are black (before the film) and the next
  shot is at 90 s; frame-profile lines for G1 and this play are equal for the first 30 s. Candidates: COND_POP_NOP
  (the only switch that changes what a clear restores) and PASS_CONTEXT_CONTROL (new on the film's submits since
  7133ee80); priv33 with its new switches off matches priv32 in code, and MLOCK cannot change pixels.
- **Q3, performance:** not memory pressure alone. From 45 s on, frame time 52-85 ms against ~40 ms in G1 at the
  same emulator time, while PSI was 0-1.4 % and pgscan flat. The rise is the game thread outside the host (45-75 ms
  against 35 ms) and GPU busy (17-29 ms against 19-20 ms), with prepare up to 5.4 ms (import work) and 958 soft-cp
  8 ms wait timeouts in ~90 s (G1: 177 in 7 min). Reading: the new-game route's loading and import churn.

### Film noise in play-1124-1901: sources and the separating runs (11-24 19:2x; reads only)

- **Source diff, measured:** `d2/priv32/src` against `d2/priv33/src` differ in two files only, `cs0439.hpp` and
  `backend/src/direct.cpp`. The kyty tree (`libVideoDec2.cpp`, `videoDec2Decoder.cpp`, `vf0439.hpp`) is byte-equal;
  `KYTY_BC5_VD2_SIZES` and `KYTY_BC5_VD2_FILL` are on unless "0" in both. direct.cpp's diff is the MLOCK lines
  (lock at import, unlock at release) and the CC_GUARDED branch, all behind switches. So priv33 with MLOCK and
  CC_GUARDED off runs priv32's code; "priv33 itself" is not a separate candidate.
- **The film's time, measured from gc/direct.log:** the emulator's memory line gives available 8.73 GB at 10 s,
  8.77 at 20 s, 6.03 at 30 s, 3.38 at 40 s, PSI 0.00-0.08 to 40 s. Memory did not run short during the first
  40 s; "memory running out during the film" holds only if the film lasted past ~45 s (PSI 2.1 at 50 s).
- **Import path, measured:** lazy release (exp 0401 e7, 30 s) is on and cut 0 MiB: every imported chunk is under a
  view. K1R covers never-written view parts with the zero buffer: 594 MiB at 0 s, 464 at 31 s, 235 at 41 s,
  ~200 after, "0 chunks known written" throughout. The "STILL NOT MAPPED" user-data lines (3 here) appear in
  nearly every play since 11-22, clean-film plays too, so they don't separate.
- **Reading:** MLOCK cannot change a pixel by data (the lock maps the same memfd pages read-only), but it adds work
  inside the import (mmap + mlock of each new range) while the decoder's CPU-written slots are being imported. If
  the noise is a race between the slot's CPU write and the GPU read (the open "slots' GPU mapping" lead), MLOCK's
  timing could move it; COND_POP_NOP and PASS can change what the film's draws see. All three stay candidates.
- **Separating runs (title start, fresh save folder, no route keys, `MW_SHOT_FROM=4 MW_SHOT_S=2`, bound 120 s, all
  on priv33 so the binary is constant):** F3 forced (no PASS, the clean-film baseline), F0 PASS only (= 7133ee80's
  code), F1 PASS + MLOCK, F2 PASS + COND_POP_NOP; the noisy arm repeated once, since a race may not show every
  start. Film judged from the shots by eye. mw439.sh gained `MW_SHOT_FROM` (first shot's second, default 30).

### fn439: the opening film from the title start (11-24 19:13-19:37, clean boot 19:05, GPU kernel lines 4 -> 4)

Seven scripted starts from the title start (fresh empty save folder, no keys, a shot every 2 s from 4 s, 150 s each),
`slot439cs.sh` arms F*, judged by eye from full-size crops of the shots at 10 s (the face scene) and 16 s (the
logo film):

| arm | build | words | film |
|---|---|---|---|
| F3 | priv33 c0ec7b38 | forced CONTEXT_CONTROL | fine horizontal-line colour noise over the whole frame |
| F0 | priv33 | PASS | the same |
| F1 | priv33 | PASS + MLOCK_IMPORTS (VmLck 9.40 GB at 40 s on the title screen) | the same |
| F2 | priv33 | PASS + COND_POP_NOP | the same |
| F0 | priv32 551618d3 | PASS | the same |
| F3 | priv32 | forced | the same |
| F0L | priv32 | PASS, the live 7133ee80 word list exactly (BC5_GUARD_LEDGER dropped too) | the same |

- **Measured:** the noise is in 7 of 7 starts, on both builds, with and without each of the three switches, and with
  the live launcher's words. No switch brings it, and neither build does. Game scenes later (from ~50 s) look clean.
- **Not explained:** the maintainer's word that the film was clean in his earlier 7133ee80 play today. Its record is not
  among the run folders, so it cannot be compared; whether that play showed the film at all (a save start skips it)
  is unknown. The 11-22/23 scripted starts (mn439, mn439b) were judged clean, but their one shot each (4 s, text on
  black) cannot show this noise, so "clean then" is not established either.
- **Reading:** the long-open intro-movie noise above (VideoDec2 output or the slots' GPU mapping), now constant rather
  than in a few frames. It belongs to the VideoDec2 path, not to the CONTEXT_CONTROL/COND_POP_NOP/MLOCK candidates.
- Private shots: box `~/bc5-data/priv/t3-screens/mw439b-1124-19{13,16,19,22,27,30,34}-csF*`, laptop
  `bc5-private/film-1124/fn/` (crops).

### fn439b-c: what brings the film noise back (11-24 19:40-20:11, same boot, GPU kernel lines 4 -> 4)

Records (journal, runs/, e0439.log, captures): the test shortcut started three times since 11-23: 11-23 15:02
(757bd9e9, distrobox, his save; ~2 noisy frames by his eye), 11-23 22:33 (3939f323, distrobox, his save), 11-24 19:01
(c0ec7b38, host, his save; noise). No start of 7133ee80 is recorded. Host Mesa is 26.3.1 (built 11-22, image
45.20261123); the container's is 26.0.8; libdrm 2.4.134 and kernel 7.3.4-ogc10.1 unchanged. His live save folder is
`~/bc5-work/_SaveData/TITLE3` (launchers set no KYTY_BC5_SAVEDATA_DIR); its `sce_sdmemory/memory.dat` differs from
the 11-23 22:33 set-aside copy in 262,866 of 585,728 bytes (rewritten 19:02 by the 19:01 play).

More starts from the title start (copies of his saves are cp -a, read-only; the originals untouched), judged by eye:

| arm | build | switches | save folder | ran in | film |
|---|---|---|---|---|---|
| FD | priv32 | PASS | empty | distrobox (Mesa 26.0.8) | noise at 8-10 s, clean logos at 14-18 s |
| FM | priv32 | PASS, LimitMEMLOCK 2.05 GiB | empty | host | noise |
| FS | priv32 | PASS | his 11-23 save | host | clean |
| FSr | priv32 | PASS | his 11-23 save | host | clean |
| FL | priv32 | PASS | his live save (copy, 19:52) | host | clean |
| F12L | priv33 | PASS + MLOCK + COND_POP_NOP (the 19:01 set) | his live save | host | noise |
| F1L | priv33 | PASS + MLOCK | his live save | host | noise |
| F2L | priv33 | PASS + COND_POP_NOP | his live save | host | noise |
| F0L33 | priv33 | PASS | his live save | host | noise |

- **Measured:** priv32 with one of his saves: clean 3 of 3. priv33 with his live save: noise 4 of 4, also with PASS alone
  (F0L33, the same words as the clean FL). Empty save folder: noise in 8 of 8 host starts on either build. The memlock
  limit changes nothing (FM). The container start (FD) was partly clean.
- **Measured:** priv32 and priv33 differ in source only by switch-gated lines in `direct.cpp` and `cs0439.hpp`, and the
  kyty tree is byte-equal; yet the two binaries behave differently with every switch off.
- **Reading:** a defect whose outcome depends on the binary's layout or timing rather than on any switch: the save state
  and the build both move it, the switches do not. That fits an uninitialised read or a CPU-write/GPU-read race on the
  decoder's slots (the open lead of 11-22), not the CONTEXT_CONTROL, COND_POP_NOP or MLOCK candidates. The NV12 slot
  dump (decoder bytes against the shot of the same frame) is the next step that tells VideoDec2 from the GPU side; it
  needs a new build.
- For his play: 7133ee80 (priv32 + PASS) on his save gave a clean film here 3 of 3, which agrees with his word.

### vz439: the decoder's slot bytes against the screen (11-24 21:26-21:44, same boot, GPU kernel lines 4 -> 4)

- **Build priv34 (binary 9cb2cec6):** priv33's kit plus `mkvz439.py` (tag vz439, diagnosis builds only, off unless
  `BC5_0439_VD2_DUMP` is set). The decoder writes the slot of chosen pictures to a private file right after the CPU
  copy (`-w`) and again just before the next picture overwrites the same slot (`-r`), with an FNV-1a hash of each. It
  logs one line per picture and one at the first CPU write into each slot. The unit describes every slot's start, each
  2 MiB boundary in it, its chroma start and its last byte at each mapping sync (`wa412_text`: view, WRITTEN by
  SEEK_DATA, IMPORTED, GPU mapping), with a line when that changes.
  - It's built on the host with the shared builds' toolchain (`B2_HOST=1`, `CS_HOST=1`), because the shared builds were
    rebuilt host-native at 17:15-17:23. The source pins are unchanged (patch 8a9ed0cf, unit ea564dbd). The reference
    objects compiled here match the shared archive's members (09567e4a).
  - So priv34 is not priv33's layout; the comparisons below are within priv34.
- **Arms** (`slot439cs.sh` VE/VL/VS, PASS_CONTEXT_CONTROL as in 7133ee80, title start, no keys, a shot every 2 s, 120 s):
  - VE, VEr: empty save folder.
  - VL, VLr: a copy of his live save (`fn439-live-1124`).
  - VS: a copy of his 11-23 set-aside save.
  - Pictures 60, 120, 180, 240, 300, 360 and 450 were dumped.

| Arm | Save folder | Screen, t4-t20 (mean row-to-row / column-to-column luma step of the shot) | Decoder bytes |
|---|---|---|---|
| VE | empty | noise: 32-42 / 13-16 | smooth: 0.5-0.9 / 0.6-1.3 |
| VEr | empty | noise: 36-45 / 14-17 | the same hashes |
| VL | his live save | clean: 0.4-1.1 / 0.4-1.1 | the same hashes |
| VLr | his live save | clean: 0.4-1.1 / 0.4-1.2 | the same hashes |
| VS | his 11-23 save | clean: 0.8-1.3 / 0.6-1.3 | the same hashes |

- **Measured, decoder:**
  - All five starts decode the same film: 582 pictures in 120 s, the first at t 1.6-1.8 s, 1920x1080, pitch 2048,
    10 slots of 3,358,720 B. Every dumped picture has the same hash in all five.
  - In every dump the rows are as smooth as the columns (U/V 0.4-0.8 both ways), and the chroma padding is all 128.
  - The `-r` re-read equals the `-w` write in all 35 cases (7 pictures in 5 starts). Nothing changed the slot's bytes
    while the GPU could read them.
- **Measured, import:** every slot lies in the "anon" view (0x2000000000, eager), imported whole. At the first look
  every watched address reads "WRITTEN by the CPU, IMPORTED; GPU: the title's memory". No line changed during the run
  (46 lines, all "first look"). No slot address is under a K1R zero cover, under no mapping, or under a lazy import.
- **Measured, screen:** with the same binary and the same film bytes, the empty-folder starts show the film dim with
  greys lifted and fine horizontal-line noise. The PS Studios logo is grey on a brown, noisy ground. The save starts
  show it clean, with a white logo on black (private grid `film-1124/vz/grid-vz-VE-VL-VS.png`).
- **Film files:** the fd sampler (from 3 s, every 0.5 s) saw no separate film file in any start. The pictures and
  their sizes are identical, so the empty-folder and save starts play the same film at the same size.
- **Reading:**
  - The noise isn't in VideoDec2's output, and it isn't the slots' import or K1R. It arises on the GPU side, after the
    slot, in how the frame is drawn to the screen.
  - What separates it in priv34 is the save folder alone. A setting the title keeps in its save (brightness or HDR
    calibration, or a picture option) likely sends the film through another GPU path whose output is wrong here.
  - Not yet squared with fn439c: priv33 with the same live-save copy gave noise 4 of 4. So the build still moves it.
- **Next step:** compare the GPU work of one noisy and one clean frame. Use the frame dump (`BC5_0439_FRAME_DUMP`) on VE
  and VL at the same second, with the passes and the texture descriptors that read the slot.
- Private: dumps `~/bc5-data/priv/vz439/<arm>-<hhmm>/`; shots `~/bc5-data/priv/t3-screens/mw439b-1124-21{31,34,36,38,41}-csV*`.
  Telling pair: `mw439b-1124-2131-csVE/t10s.png` (noise) and `mw439b-1124-2134-csVL/t10s.png` (clean).

### vz439b-d: what the title draws in the noisy and the clean start (11-24 21:48-22:10, same boot, priv34, GPU kernel lines 4 -> 4)

- **Arms** (title start, no keys, shots every 2 s, 60 s unless noted; PASS_CONTEXT_CONTROL as in 7133ee80):

| Arm | Save folder | Screen t4-t20 (row / column luma step) |
|---|---|---|
| VM | only `sce_sdmemory/memory.dat` of his live save | clean: 0.3-1.0 / 0.4-1.4 |
| VN | his live save without `sce_sdmemory` | noise: 35-45 / 13-16 |
| VW, VWp | only the save memory VE's empty start wrote itself (585,728 B) | noise: 35-45 / 14-17 |
| VLp | his live save (a repeat of VL) | clean: 0.4-1.1 / 0.4-1.2 |
| PW, PL | VW / VL with `BC5_DIRECT_DCC_PRESENT=1` | not run: the emulator refuses a compressed video-out buffer without the flip decompress (exit 65, textureCache.cpp:1248) |
| DW, DL | VW / VL, frame dump (sr439b) armed by a scripted L3+R3 hold at 3.5 s | captured: noisy F 131 ops, clean F 184 ops |

- **Measured, the setting:**
  - The save memory decides: his `memory.dat` alone is clean, and everything else of his save is noisy.
  - The memory the title wrote itself on an empty start (its defaults) is noisy again when read back by a later start.
    So the empty folder isn't the cause; a value in the save memory is. The file is high-entropy (280,834 of 585,728
    bytes differ from his), so the value can't be read from it.
- **Measured, the guest-visible display (same in both starts):**
  - The registered video-out buffers are byte-identical: groups 0x8000000022000000 and 0x8100000022000000,
    3840x2160, option 8, dcc_control 0x208. The first flips also go to the same buffer indices.
  - BC5's answers can't differ between the starts (same binary and environment): GetOutputStatus writes dynamicRange 1
    (AnyPS5 Output.cpp:148 writes 1 too; prosper 1c93ab8 hle_graphics.cpp:1453-1478 reads the field as 0 SDR / 2 HDR,
    MED confidence), and GetHdrToneMapLuminance answers 80/1000/0.
  - The title imports GetOutputStatus, GetHdrToneMapLuminance, IsOutputSupported, ConfigureOutput and
    GetDisplaySafeAreaInfo. GetOutputStatus' first-call line never appears in 120 s. The other calls aren't traced in
    these logs.
  - The three unresolved stubs are sceSystemServiceInitializePlayerDialogParam, sceSystemServiceLaunchPlayerDialog
    (ps5rs data/nids.csv) and a VideoOutVrrStatus NID: none of them is a display answer.
- **Measured, the frames (sr439b, frame F at ~4.5 s, the "presents" card):**
  - The noisy start renders its scene at **3840x2160**: 204 references to 3840x2160 surfaces in F, none to 3072x1728.
  - The clean start renders it at **3072x1728**, plus 1536x864: 240 references, none to 3840x2160 besides the display.
  - Both end with the same compute passes and the same final pass (pgm 0x8000343500, reading the 3840x2160 u10x3
    0x5000860000). The clean frame runs 31 more compute programs (100 ops).
  - The noise on the card is full-strength random colour on every other row, over pure black.
- **Reading:**
  - The saved value is the title's graphics mode or render resolution. His save holds the mode the scripted route also
    picks (`T3S_WANT=performance`): 3072x1728, upscaled. The title's default renders natively at 3840x2160, and that path
    comes out as the noise here.
  - So it isn't a display-capability answer (identical in both) and it isn't the film. It's a GPU-side defect on the
    3840x2160 path, likely in a pass that only that mode runs or sizes differently (a 4K surface's tiling, DCC or a
    size-dependent dispatch). The next step is a per-pass census of DW's frame (sr439c, from the first op whose output
    carries the alternating rows).
  - What the PS5 does: it runs both modes, and the title picks its first mode from the system or its own default
    (TODO(verify): whether it reads the system's game preset, e.g. through the exp 0405 system-service params). No
    per-title or per-mode workaround: the fix is the 3840x2160 path itself.
  - Still open: fn439c's priv33 on the same save copy was noisy 4 of 4. Either that build broke the 3072x1728 path too,
    or the save copies it read differed; to recheck on the frame census.
- Private: captures `~/bc5-data/priv/frames/sr439b-20261124-220004-c0` (noisy, 5.0 GB) and `-220633-c0` (clean),
  their tsv files in `film-1124/vz/frames/`; shots `mw439b-1124-21{48,50,52,54,56}-csV*`, `-2159-csDW`, `-2206-csDL`.
- **Finding row (draft for HANDOFF; the number is the top session's):** The third title's film and title-card grain
  (fine full-strength colour noise on alternate rows, dim) is not in the decoded film. The decoder's NV12 bytes are
  smooth and stay unchanged until the slot is reused. The slots are eager, imported whole, and have no K1R cover. The
  noise follows a value in the title's save memory: the title's own default memory brings it back, and his memory alone
  removes it. With the noise the title renders at 3840x2160; without it at 3072x1728. The display registration and
  BC5's display answers are identical in both. So it's a GPU-side defect on the title's native-4K path (exp 0439
  vz439, 11-24 21:26-22:10, priv34 9cb2cec6, 0 GPU kernel lines).

### vz439e-g: the noise is a flip-label race, cured by serving the chained-piece flip-label waits (11-24 22:12-22:29, same boot, GPU kernel lines 4 -> 4)

- **fn439c corrected (measured):** F12L, F1L, F2L and F0L33 never read his save. Their logs say "save data memory:
  no file", and their save folders hold only what the title wrote. In `slot439cs.sh` the generic
  `F3*|F0*|F1*|F2*` case (empty save) comes first and caught those four names. So they were empty starts, and "priv33 +
  his save noisy 4 of 4" is void. Rerun on priv33 c0ec7b38 with his save (DL33): 3072x1728, clean at t4-t8. So far
  every start that read his save memory has been clean, on priv32, priv33 and priv34.
- **The census cures its own subject (measured):**
  - CW (default-settings save, sr439c armed 3 s and 6 s after the first flip): t4 noisy (38.2 / 14.4); from t5 on, the
    film and the SP card are clean to the end (58 s).
  - The detiled display surfaces of both armed frames (CW and CL, read right after dc439's flip decompress) are clean
    (row / column step 0.41 / 0.50 and 0.32 / 0.41).
  - The frame dump did the same: DW is noisy at t3 and clean from t5 on.
- **A stall alone cures it (measured), with no capture and no flush:**
  - SW: the emulator SIGSTOPped for 1 s at 22:22:48.7. Shots noisy through 48.6 (37.7 / 14.7), clean from 50.4 on.
  - SW2: the stop at 22:23:54.8. Noisy through t11 (32.2 / 14.6), clean from t13 (56.5) on.
  - So a steady CPU/GPU phase holds the noise, and one stall breaks it for good.
- **The fix candidate (measured):** `BC5_0439_FLIP_LABEL_PIECES=1` (vl439 (b), compiled in since 11-22, off by default).
  - It serves a flip-label wait inside a chained or called piece on the CPU before the submit (exp 0069's rule: wait
    while that buffer's flip is queued, at most 100 ms, then clear a label still set), exactly as the top-level wait is
    served.
  - Without it the filter drops that wait packet and nothing waits.
  - LP and LPr (default-settings save): clean from the first card through t21, 2 of 2. LPL (his save): clean. About
    1,025 such waits are served per run; the sampled ones were 0.00 ms, none cleared still set.
- **Reading:**
  - The title puts its wait for a display buffer's flip (the buffer label) in a chained piece. BC5 serves that wait only
    at the top level and drops it in chained pieces. So the title's next frame renders into a display buffer whose flip
    (dc439's in-place DCC decompress and the presentation's read) is still in progress.
  - In the native-4K mode the frame cadence keeps that overlap in a steady phase, and the screen shows the half-written
    DCC surface as full-strength noise on alternating rows. Any stall (a capture, a census, a SIGSTOP) breaks the phase.
  - The 3072x1728 mode's cadence avoids it in these runs, though it can still meet it (his 19:01 play saw the noise).
  - The gameplay of the default mode (VE, from ~61 s) shows no line noise in the shots.
  - On a PS5 the wait is in the command stream and the GPU honours it wherever it sits.
- **The fix is universal:** every title, every chained piece; it's no per-title or per-mode switch. It's a candidate
  for the shared builds: make vl439 (b) the code path, not a switch (the top session's decision, D-rule). Its risk is
  small (a CPU wait bounded at 100 ms, like the top-level one). Its cost isn't measured yet (lean fps A/B owed).
  vl439 (a) (the labels in GPU-visible memory) stays off: it hung the ring twice in exp 0071.
- **Finding row (draft for HANDOFF; the number is the top session's):** The third title's grain (film and card
  noise, alternating rows) is a display-buffer race. The title waits for a buffer's flip through a flip-label wait inside
  a chained piece; BC5 drops waits there (only the top-level one is served), so the next frame renders into a buffer
  still being flipped. Measured:
  - The decoder bytes and the slot imports are clean.
  - The noise appears only in the title's native-4K mode (its default) and holds until any stall.
  - A 1-s SIGSTOP ends it for the run.
  - Serving the chained-piece flip-label waits on the CPU (`BC5_0439_FLIP_LABEL_PIECES=1`) removes it: 3 of 3 clean
    against 6 of 6 noisy without it in the same mode.
  - (exp 0439 vz439, 11-24 21:26-22:29, priv34 9cb2cec6, 0 GPU kernel lines.)

### vz439h-j: the three graphics modes, and the fix build priv35 (11-24 22:30-23:14, same boot, GPU kernel lines 4 -> 4)

- **The modes, set through the title's own menu (measured):**
  - A start from a copy of his live save (MV), driven by hand with `k439/live439.sh`: one key line into the run's
    input file, then a shot.
  - His save holds **Ray Tracing** (Settings > Display > Graphics Mode).
  - Each mode was set there, and each save memory copied right after the title rewrote it (22:55:34, 22:56:44,
    22:57:53). Menu shots `live-s06` (Performance), `live-s11` (Quality) and `live-s13` (Ray Tracing). The copies are
    `~/bc5-data/saves/fn439-mode-{p,q,r}`, read-only.
  - An empty start never shows the first-start menus any more: film, then the title, then the overlook. So the route
    based on them (MQ, MP, MR) was dropped after two tries (its menu match has no threshold, and it matched the film).
- **The table, priv34 9cb2cec6 (PASS_CONTEXT_CONTROL on, title start, no keys; render surface from a census frame at
  30 s; film = row / column luma step of the shots t2-t20):**

| Start | Render surfaces | Film | Gameplay (MV, three shots each, same save) |
|---|---|---|---|
| Quality | 3840x2160 | clean (0.3-1.0 / 0.3-1.1) | clean (1.6 / 1.6), 15.9 fps |
| Performance | 3840x2160 | **noise** (37-42 / 14-16) | clean (1.5-1.7 / 1.6-1.7), 20.6 fps |
| Ray Tracing (his) | 3072x1728, 1536x864 | clean | clean (1.6-1.7 / 1.6-1.7), 16.9 fps |
| empty start | 3840x2160 | **noise** (34-43 / 13-16) | earlier: clean from 61 s (VE) |

- **Measured:** the noise follows the **Performance** mode (60 fps target), not the render size: Quality renders at
  3840x2160 too and is clean. The empty start renders like Performance and is noisy. Which mode the empty start
  actually is can't be read off its menu without keys, because it shows none. So "the native-4K path" in vz439b-d was
  wrong: the render size there separated Ray Tracing from Performance, not 4K from the rest.
- **Reading:** this fits the flip race of vz439e-g. A 60-fps presentation reuses each display buffer twice as fast, so
  the next frame's rendering overlaps the dropped flip-label wait. The 30-fps modes leave the buffer idle long enough.
  Gameplay shots show no noise in any mode (stills, three each); whether gameplay frames are ever hit is not measured.
- **The per-pass census (step 2):** it can't show a noisy frame. Arming it drains the GPU, and that drain alone ends the
  race for the rest of the run (CW, and SW/SW2 with a bare SIGSTOP). So there is no wrong pass to name: every pass
  renders correctly, and the defect is when the next frame starts on a display buffer. The first wrong step is BC5
  dropping the title's flip-label wait inside a chained piece.
- **The fix build priv35 (138e6779; lean built too, warnings 27):** priv34 plus `k439/mkvlon439.py`, which makes vl439
  (b) the default for every title. A flip-label wait inside a chained or called piece is served on the CPU before the
  submit, as the top-level one is (exp 0069's rule: wait while that buffer's flip is queued, at most 100 ms, then clear
  a label still set). `BC5_0439_FLIP_LABEL_PIECES=0` turns it off.

| Start, priv35 | Film t2-t21 |
|---|---|
| Quality | clean (0.3-1.0 / 0.3-1.1) |
| Performance | clean (0.3-1.1 / 0.3-1.1) |
| Ray Tracing | clean |
| empty start | clean |

  About 1,025 chained-piece waits are served in each run, none cleared still set. PASS_CONTEXT_CONTROL was on in all four.
- **Still owed:** the lean cost (an fps A/B on the lean build of priv35 against the lean of priv34), gameplay with the
  fix over a longer ride, and the bake into the shared builds (the top session's decision).
- **Finding row (draft for HANDOFF; the number is the top session's):** The third title's grain (film and card noise,
  full-strength colour on alternate rows) is a display-buffer race in BC5.
  - The title waits for a display buffer's flip with a flip-label wait inside a chained piece. BC5 served such waits
    only at the top level and dropped them in chained pieces, so the next frame could render into a buffer still being
    flipped.
  - It shows in the 60-fps Performance mode and in an empty start; Quality and Ray Tracing are clean. Any stall ends
    it for the run.
  - Serving the chained-piece waits like the top-level one, for every title, removes it: on priv35 the film is clean
    in Quality, Performance, Ray Tracing and the empty start, with PASS_CONTEXT_CONTROL on.
  - Not the decoder (its NV12 bytes are clean), not the slot imports, not K1R, not display capability.
  - (exp 0439 vz439, 11-24 21:26-23:14, priv34 9cb2cec6 / priv35 138e6779, 0 GPU kernel lines.)

### vz439k: the fix's open ends on priv35 (11-24 23:15 - 11-25 00:13, same boot, GPU kernel lines 4 -> 4)

- **(a) 20-min scripted ride** (GF; priv35 138e6779, PASS_CONTEXT_CONTROL on, the fix on by default; a copy of his live
  save, Ray Tracing; the edge moves; the 0.5-s sampler; a shot every 30 s):
  - It ran 1205 s with 0 GPU lines. MemAvailable went down to 1.31 GB and GTT up to 11.8 GB (11.26 GB at 5.5 min).
    Memory PSI was 0-0.2 apart from one 3.8 % moment at 2.5 min.
  - All 39 shots are normal gameplay in the village and fields at 11-16 fps, with no line noise. They show a
    notification left by a refused DRY of the launcher (it was started while the ride ran).
- **(b) lean A/B (R74)** (priv35's lean 2d08049d for both arms; C = `BC5_0439_FLIP_LABEL_PIECES=0`, F = the default;
  his save, no keys, 180 s, MangoHud's frame log from 60 s; order W0 C1 F1 F2 C2 C3 F3):

| Arm | flips/s | frame time median / p99 |
|---|---|---|
| W0 (warm-up, C) | 22.81 | 33.4 / 67.0 ms |
| C1 | 24.59 | 33.4 / 67.2 ms |
| F1 | 18.14 | 66.6 / 67.2 ms |
| F2 | 18.51 | 66.6 / 66.9 ms |
| C2 | 18.23 | 66.6 / 66.9 ms |
| C3 | 18.23 | 66.6 / 66.9 ms |
| F3 | 18.36 | 66.6 / 66.9 ms |

  - The frame times sit on the title's 30-fps pacing (33.4 ms) or its half (66.6 ms). The first two runs sat higher
    and the next five lower, C2 and C3 included, so that step follows the series, not the arm.
  - From F1 on, the arms overlap (F 18.14-18.51, C 18.23): the fix's cost is in the noise.
- **(c) other titles on priv35's normal build:**
  - The first title (exp 0413's `start0413g.sh`, 180 s, no input): PASS, 0 kernel and 0 crash lines, the GFX jobs steady at
    ~115/s to the end.
  - The second title (`k439/vz2t439.sh`: its package from the NAS, RT on, the launcher's words through a copy that
    differs only in the save folder, a fresh copy of the 11-17 play snapshot, 300 s, no keys): the title screen at
    49-50 flips/s, no gap over 40 ms, 0 GPU lines. No gameplay was reached (no keys). A ride with the fix is left to
    the way-2 session's bake 2 if wanted.
- **Step 2:** `k439/t3-test-fl.sh` (78698196, not live) is 7133ee80's words on priv35 with
  `BC5_0439_FLIP_LABEL_PIECES=1` written out (no MLOCK, no COND_POP_NOP). DRY=1 passed on the host: words complete,
  host libraries fine, lock free, gate admitted.

### mg439: what the direct-memory growth is (11-25 00:13-00:23, same boot, GPU kernel lines 4 -> 4)

- **Build priv36 (e8642162; lean built, warnings 28):** priv35 plus `k439/mkmg439.py`. `BC5_0439_MG_CENSUS=1` writes a
  journal line every 10 s:
  - allocated: offered minus the allocator's free list (memory.cpp `Bc5FreeStats`);
  - released: sceKernelReleaseDirectMemory, cumulative (KytyPlus does not punch released ranges out of the memfd);
  - resident: the memfd's data bytes (SEEK_DATA / SEEK_HOLE walk);
  - viewed: the union of the file ranges under the live views (aliases counted once);
  - pinned: the imported BOs.
- **Run GM:** an empty-folder title start, the cross at 45 s into the overlook, then the edge moves; 300 s; PASS on;
  the fix on.

| t | allocated (free) | released | resident | viewed (union) / views | pinned / BOs |
|---|---|---|---|---|---|
| 0 s | 622 MiB (13,046) | 0 | 38 MiB | 622 / 4 | 0 / 0 |
| 10 s | 13,668 MiB (0) | 0 | 4,384 MiB | 4,869 / 846 (eager 4,110) | 4,364 / 19 |
| 30 s | 13,668 (0) | 0 | 5,716 | 6,147 / 4,604 | 5,692 / 378 |
| 50 s | 13,668 (0) | 0 | 8,528 | 8,792 / 17,656 | 8,506 / 801 |
| 70 s | 13,668 (0) | 0 | 9,502 | 9,722 / 25,154 | 9,482 / 1,179 |
| 80-290 s | 13,668 (0) | 0 | 9,516 | 9,736 / 25,267 | 9,496 / 1,184 |

- **Measured:**
  - The title takes the whole pool BC5 offers (13,668 MiB) at about 10 s and releases nothing.
  - What the box holds follows what the title maps and writes in that pool. Resident equals pinned to 20 MiB, and both
    stay below the viewed union (the difference is never-written view parts under K1R's zero cover).
  - No import outlives its view: there is nothing imported and unviewed to release. The views grow with the title's
    streaming (846 -> 25,267) and are live mappings, not stale ones (they come from the guest's mapped ranges and
    vanish on unmap; the lazy release cut 0 MiB in 1901 for the same reason).
- **Reading, against the PS5:**
  - On the console the whole pool is physical memory from the allocation on, so the title's footprint there is the
    full pool. BC5 already backs only what is touched.
  - The title's working set is what it is (9.5 GB here, 11.9 GB in his 19:01 play). The freeze comes from that set
    plus the host (desktop, emulator) on a 15.2 GB box, with every touched page pinned for the GPU (udmabuf; not
    swappable).
  - So the step-3 question ("does BC5 miss an unmap or keep stale views?") is answered **no**, and a "release of
    unreferenced imports" would release nothing.
  - The levers left are not faithful-behaviour fixes:
    - the pool size BC5 offers. 13,668 MiB comes from KytyPlus's `PhysicalMemory::TotalSize` (12.5 GiB target, capped
      by host RAM minus 3.5 GB); TODO(verify) the PS5's figure for a game. The title may size its streaming to it.
    - host memory: the desktop, zram.
    - making GPU-pinned pages reclaimable (not with udmabuf).
  - These are the top session's decisions.

### sn439: the memory budget at the lowest point (11-25 00:25-00:46, same boot, GPU kernel lines 4 -> 4)

- **Run GS:** the 20-min ride from a copy of his live save (priv35, the fix on, PASS on), plus `k439/snap439.sh` every
  30 s: meminfo, zram, the emulator's smaps by name, user processes over 50 MiB, every process's DRM fdinfo.
  - It ran 1,204 s with 0 GPU lines. The lowest MemAvailable was 1.40 GB, in the snapshot at 00:37:35.
  - The journal then read: direct 11,460 MiB pinned in 1,800 BOs under 40,829 views; private 124 MiB pinned.
- **MemTotal 15,192 MiB at 00:37:35:**

| Item | MiB | Source |
|---|---|---|
| the title's direct pool, pinned (udmabuf imports of the memfd) | 11,460 | journal; Shmem |
| the title's private guest memory, pinned (modules, stacks) | 124 | journal |
| other shmem (K1R zero buffer, pipewire, SDL) | 16 | Shmem 11,600 minus the two |
| file page cache (Cached minus Shmem; 1,223 inactive) | 1,318 | meminfo; mostly reclaimable |
| anonymous memory, all processes (the emulator's own: 108 = [anon] 108 + [heap] 1) | 384 | AnonPages; smaps |
| kernel slab (unreclaimable 327, reclaimable 218) | 545 | meminfo |
| GPU driver pages outside shmem (GPUActive 381): the emulator's own BOs 191 (GTT 11,777 minus 11,586 imported: tiler scratch, k1r, rings), plasmashell 139, Xwayland 22, the rest 29 | 381 | meminfo GPUActive; fdinfo |
| zram (541 MiB swapped in, compressed to 130) | 130 | mm_stat |
| vmalloc 107, page tables 53, per-cpu 14, kernel stacks 13 | 187 | meminfo |
| free | 257 | MemFree |
| unattributed (drivers, fragments) | 390 | the rest |

  - The VRAM carve-out (512 MiB, 467 used, the emulator 359) is outside MemTotal.
  - Processes over 50 MiB RSS: the emulator (5.48 GB RSS, almost all of it mapped pool pages) and plasmashell
    (147 MiB). Nothing else on the desktop is over 50 MiB; Steam is not running.
  - The emulator has 82 threads and 15,638 mappings. Page tables 53 MiB in total, so the 40k views cost little there.
- **Measured:** the pinned pool is 76 % of MemTotal. "Everything else" is about 3.7 GB:
  - the page cache, 1.3 GB, already counted as available;
  - kernel slab 0.55 GB;
  - anon 0.38 GB;
  - GPU driver pages 0.38 GB;
  - small kernel items 0.19 GB;
  - zram 0.13 GB;
  - unattributed 0.39 GB.
- **Avoidable, largest first, with what each would take:**
  1. Slab, 0.33 GB unreclaimable. The owners can't be named without root (`/proc/slabinfo`). Candidates: the
     per-import sg tables and dma-buf objects (1,800 BOs) and the VMAs. It needs one read of slabinfo by the top
     session (sudo), then possibly fewer, larger imports.
  2. plasmashell, 0.29 GB (147 RSS + 139 GTT). The lean shortcut already stops it for a play
     (`lean-session.sh`); the normal shortcut does not. The maintainer's choice.
  3. The emulator's own GPU buffers, 0.19 GB (tiler scratch 96 MiB, and others). It would take sizing them down,
     a code change for a small gain.
  4. The normal build's own logs, in the page cache (the journal and play-last.log). The lean build writes none, and
     the cache is reclaimable anyway.
  5. Xwayland, 22 MiB GTT: negligible.
- **Reading:** nothing avoidable comes near the 1-2 GB that separate a ride from a freeze. The working set of the
  title's pool dominates, and with udmabuf every touched page is pinned. On the console the same pool is physical
  memory from the allocation on.

### The pool size against the console (11-25 00:40; reads only)

- **How 13,668 MiB is formed on this box:**
  - KytyPlus's `PhysicalMemory::TotalSize` (src/kernel/memory.cpp) has a 12,800 MiB target. On a host with less
    than 12.8 + 3.5 GB of RAM it caps the target at physical RAM minus 3.5 GB, with an 8 GB floor.
  - It then lets `KYTY_GUEST_MEMORY_MB` override all of that.
  - `~/bc5-work/bc5-run.env` (and the exp 0439 copy `run-log.env`) sets `KYTY_GUEST_MEMORY_MB=13824`, so the total is
    13,824 MiB.
  - `Size()` gives the direct pool the total minus the flexible memory. The title's param.json asks for 156 MiB of
    flexible memory, so direct = 13,668 MiB (play-last.log: "total 13824 MiB, flexible 156 MiB, direct 13668 MiB").
- **What a PS5 game is given:**
  - Sony publishes 16 GB of GDDR6 and no game budget.
  - The often repeated 12.5-13.5 GB "for games" figure comes from articles without a source (recalled; one found:
    cyberpost.co).
  - AnyPS5 (f145139, `core/libs/prx/libkernel/DirectMemory/DirectMemory.hpp:9`): `DIRECT_MEMORY_SIZE = 13824 MiB`,
    the direct pool alone, also returned by sceKernelGetDirectMemorySize.
  - prosper (1c93ab8, `src/hle/memory/hle_kernel_mem.cpp:1062-1067`): 16 GiB by default. Its comment says real
    hardware reports a smaller game budget, without a figure.
- **Reading:** BC5's direct pool (13,668 MiB) is smaller than AnyPS5's (13,824 MiB), and no source shows the console
  giving less. So the step's condition ("if BC5 offers more than the console") isn't met, and nothing was changed or
  run. Exp 0412's record adds that the second title does not start with `KYTY_GUEST_MEMORY_MB=12288` (exit 65 at 6 s).
  A smaller pool remains a host-fit choice, not a fidelity fix.
- **Step 3 (MLOCK_IMPORTS with the console figure) was not run.** Its condition was a step-2 run that kept
  MemAvailable above 2 GB, and there was no step-2 run. The budget above also gives no room: at the lowest point
  MemAvailable was 1.40 GB, and the page cache is the only large slack.

### vz439k step 4: the lean A/B reversed, and the two pacing states (11-25 00:47-01:12, same boot, GPU kernel lines 4 -> 4)

- **The same recipe in reversed order:** priv35's lean 2d08049d; F = the fix on, C = `BC5_0439_FLIP_LABEL_PIECES=0`;
  his save, no keys, 180 s, MangoHud from 60 s. A warm-up (C), then F C C F F C. Temperature, power and CPU clock were
  logged every 2 s (`k439/therm439.sh`; the GPU busy file is not supported on this chip, and the hwmon clock reads
  implausibly).

| Arm | flips/s | share of 33-ms frames from 30 s |
|---|---|---|
| warm-up (C) | 18.68 | 58 % |
| F4 | 18.81 | 59 % |
| C4 | 17.64 | 47 % |
| C5 | 18.18 | 39 % |
| F5 | 17.62 | 49 % |
| F6 | 17.91 | 50 % |
| C6 | 17.87 | 49 % |

- **Measured, the fix's cost:** F 17.62-18.81 against C 17.64-18.18: in the noise in both orders.
- **Measured, the two states** (`k439/pace439.py`: per 10-s window, F = over 70 % of frames at 25-45 ms, S = over 70 %
  at 55-80 ms):
  - Every run of both series starts in the 33-ms state and moves to the 66-ms state or a mix after 50-90 s. In the
    first series' first two runs (W0, C1, right after the 20-min ride) the move came at 110-130 s, which is why they
    read 22.8 and 24.6 flips/s from 60 s.
  - Over the second series' 49 clear windows: 33-ms windows at GPU 61.2 °C and 94 W; 66-ms windows at GPU 73.6 °C
    and 134 W. CPU 67.3 against 76.6 °C, mean CPU clock 3,420 against 3,460 MHz.
- **Reading:**
  - The slow state is more GPU work per frame (more power at a lower frame rate), not throttling (that would lower the
    power and the clocks).
  - It starts about a minute into each run from the same save: the title's own load grows, as streamed detail or
    effects come in, and the 30-fps pacing then halves to 15.
  - So "24 -> 18 flips/s" was where in the run the window fell, not the arm. A fair measure of this title needs runs
    long enough to settle, read after the switch.
  - Why the first two runs after the long ride kept the fast state twice as long is not known. One case; candidates:
    warm caches, or a cooler start.

### Step 5: the rainbow patches (11-25 01:13-01:44, same boot, GPU kernel lines 4 -> 4)

- **Saves:** `~/bc5-data/saves/fn439-live-{q,p,r}` (read-only) are copies of his live save with `sce_sdmemory` replaced
  by the Quality / Performance / Ray Tracing memory of vz439h. So it's his progress in each mode.
- **Runs** (priv35, the fix on, PASS on, the edge moves from 40 s):
  - RQ, RP, RR: 240 s, a shot every 10 s (60 shots).
  - RP2, RQ2, RR2: 140 s, a shot every 2 s from 60 s (112 shots).
  - The earlier rides GF and GS (59 shots, Ray Tracing).
- **Seen once:** RP t90s (Performance, the character on the dark field west of the village). Horizontal streaks of
  saturated blue-violet, magenta, red and green lie over the ground behind him (saturation up to 0.63, lightness
  0.3-0.5), with violet specks on the robe. Private crop: `film-1124/vz/rb/RP/t90-crop.png`.
- **The detector** (`k439/violet439.py`): the share of saturated violet-to-magenta pixels (hue 235-330 degrees), which
  nothing in this night village has. RP t90s scores 1.26 per 1,000 px. All 230 other shots of the six rides score 0
  (one 0.01).
  - The first form (`k439/rainbow439.py`, several hues per block) finds a synthetic patch but misses the real streaks:
    each block of them holds mostly one hue.
- **Measured:** the patches exist on this build (with the film fix and PASS_CONTEXT_CONTROL), in Performance at least.
  They are rare and brief: 1 shot of 60 in the first rides, 0 of 112 in the dense repeat of the same moves. Quality and
  Ray Tracing showed none in these rides, but at this rate that does not exclude them.
- **Left open:** no scene that shows them on demand was found in two rides. The colours (violet and magenta over
  ground, specks on a character) suggest a screen-space pass reading uninitialised or stale data for a frame, but
  that is not shown. Catching one needs a trigger on the frame itself, such as a violet count on the display surface
  at the flip, before a capture can name the pass.

### gv439 / pg439: what the GPU can reach, and why "import on first GPU reference" cannot be exact here (11-25 01:50-02:30)

- **Can a CPU-side census see every GPU reference? Measured: no.**
  - `k439/pgmscan439.py` disassembles every program a frame dump caught (events.bin type 4). It uses the host Mesa's
    LLVM through its C API (`/usr/lib64/libLLVM.so.23.1`, LLVMCreateDisasmCPU gfx1013; the box has no llvm-mc), up to
    the first s_endpgm.
  - Noisy-start frame: 83 programs. 2 use global/flat loads or stores (9 instructions) with a 64-bit address formed in
    registers by the shader; 75 use s_load (descriptor tables read through pointers in memory).
  - Clean-start frame: 114 programs. 8 use global/flat (46 global, 6 flat); 96 use s_load; 2 use scratch.
- **The mechanisms that reach memory without the CPU seeing the address before the submit:**
  1. global_*/flat_* with addresses computed in the shader (measured above);
  2. s_load chains: descriptors (V#, T#) read from tables whose pointers are read from memory, to any depth (sr439b
     follows two levels);
  3. descriptors, indirect arguments or pointers that the GPU itself writes during the frame and a later dispatch reads
     (GPU-built tables, BVH nodes in Ray Tracing): they do not exist when the CPU walks the submit.
  - So a page must be mapped before any of these can read it. On gfx1013 a GPU access to an unmapped page is a fault,
    not a retry: amdgpu offers no recoverable (XNACK/retry) faults for this chip's graphics queues (TODO(verify)
    against the amdgpu sources). "Import on first reference" therefore cannot be made impossible-to-miss by
    construction. It would be a catch-after-the-fact (the learned-window class), which is not wanted. **Step 2 is not a
    contained change and is not written.**
- **The exact rule that does exist, the console's own: GPU protection** (`k439/mkgv439.py`, build priv37 2646925b, see
  below).
  - On the console a direct-memory page mapped without PROT_GPU_READ (0x10) / PROT_GPU_WRITE (0x20) cannot be
    addressed by the GPU at all (KytyPlus memory.cpp:73-74 defines the bits and already splits its page-table counts
    by them, :608, :1219).
  - So "import only chunks under at least one GPU-mapped view" can't miss by construction, as long as the title maps a
    page with GPU access before its GPU uses it (it must, on the console).
  - `BC5_0439_GV_CENSUS=1` measures what that rule would leave unpinned.

| Run (priv37, the fix on, PASS on) | pinned | under GPU-mapped views | under CPU-only views alone | CPU-only viewed (union) |
|---|---|---|---|---|
| GV1: title start, the overlook route, 290 s | 9,484 MiB | 9,100 MiB | 384 MiB | 630 MiB |
| GV2 (300 s): his save, the ride, 292 s | 10,482 MiB | 10,054 MiB | 428 MiB | 630 MiB |

  - Bytes per protection value (views' sizes summed, at 292 s):
    - 0xd3: 5,939 MiB (GPU read);
    - 0xf3: 4,030 MiB (GPU read and write; these are the eager views);
    - 0xc3: 620 MiB (no GPU bit);
    - 0x32: 78 MiB; 0x2: 10 MiB; 0x33: 2 MiB.
  - The 0xc0 bits are set on most views and unnamed here (TODO(verify): their meaning).
  - The CPU-only pinned bytes lie in 9 runs: 5 of up to 2 MiB, 2 of up to 8 MiB, 2 of up to 256 MiB.
- **Reading:**
  - The title maps 96 % of what it touches with GPU access. The exact rule would leave about 0.4 GB unpinned, which
    is below the 2 GB the top session set as worth a change, and below the margin a freeze needs.
  - The pin is not mostly CPU-only data. It is memory the title has declared GPU-readable, which on this host must be
    pinned for as long as it may be read.
  - The 20-min GV2 follows below.
- **GV2 over 20 min** (1,200 s, 0 GPU lines, lowest MemAvailable 2.41 GB): at 1,191 s, pinned 10,466 MiB in 1,434 BOs;
  10,038 MiB under GPU-mapped views; 428 MiB under CPU-only views alone; the CPU-only union is still 630 MiB. Nothing
  grew on the CPU-only side over the ride. The memfd resident is 10,486 MiB under 32,825 views, and nothing was
  released.

### vt439: the rainbow trigger at the flip, and what it caught (11-25 02:31-02:52, same boot, GPU kernel lines 4 -> 4)

- **Build priv38 (fb049873):** priv37 plus `k439/mkvt439.py`, inside sr439b_dark (the flip hook after dc439's in-place
  decompress; it runs while BC5_0439_FRAME_DUMP is set, normal build).
  - With `BC5_0439_RB_TRIGGER=<n>` (off by default) the 4096 evenly spaced samples of the display surface
    (2_10_10_10) are counted for saturated violet-to-magenta pixels (violet439.py's rule).
  - At n or more, the decompressed display surface is written raw: at most one every 5 s, 40 in all.
    `BC5_0439_RB_ARM=1` would also arm sr439b's capture (not used: the frame dump needs 20 GB free).
- **Run RBP:** his save with the Performance memory, the edge moves, 1,200 s, trigger 3; the film fix on, PASS on.
  - 0 GPU lines; lowest MemAvailable 1.51 GB.
  - Largest count in the opening film: 933. Two writes came in the film, false positives: the logo's own
    blue-violet light. The trigger needs a start delay before its next use.
  - In gameplay the trigger fired 38 times, mostly at 3-5 (the scene's background level), with peaks of 260, 45, 29,
    15, 13, 11 and 10.
- **What the peaks show** (detiled with `sr439cread.py --display`; private, `film-1124/vz/vt/`):
  - 45, 29, 15, 11: **the rainbow patches.** Magenta, pink, blue and green streaks over the dark grass behind the
    character, coloured specks on her clothes, and colour fringes in the hair. They are in the display surface the
    title rendered, so it isn't the presentation.
  - **260: one whole frame of the old grain** in gameplay: dim, with lifted greys and line noise. The display-buffer
    race of F930 is therefore not fully closed in Performance mode, even with the chained-piece flip-label wait served.
    It is one frame in about 20 minutes. Its next step is a capture of such a frame and a look at its submit's flip-label
    waits.
- **Next for the patches:** a capture of the frame that triggers. It takes the trigger with a start delay and a
  higher threshold (10), `BC5_0439_RB_ARM=1`, and about 5 GB free above the frame dump's 20-GB floor.
  The box has 23 GB free after removing my own clean-start dumps and the low-count surfaces.
- **Slab, settled (the top session's slabinfo read at idle, 11-25 01:50, no emulator):** SUnreclaim is already 236 MiB
  at idle, so the emulator adds about 90 MiB. The largest caches are radix_tree_node 77 MiB, btrfs_inode 49 MiB,
  dentry 15 MiB and vm_area_struct 7 MiB. Slab is not a lever; item 1 of sn439's avoidable list is dropped.

### fr439: why his 19:01 play froze and tonight's rides did not (11-25 02:55-, records first)

- **What the records hold:** the 1-s sampler (`memsample/play-1124-1901.txt`, its klog) and the journal
  (`captures/play-20261124-1901/gc/direct.log`).
  - There is no pad record and no runs/ log. Which route he took is not in the records beyond a title start that
    reached his game (his save, Ray Tracing).
  - `k439/fr439.py` gives the same figures for both sides; GS is the 20-min ride from a copy of his save on priv35, no
    lock:

| | his 19:01 play (priv33, PASS + MLOCK + COND_POP_NOP) | GS (priv35, PASS + the flip fix) |
|---|---|---|
| GTT at 30 / 60 / 85 / 108 s | 7,384 / 10,614 / 11,502 / 11,868 MiB | 5,949 / 9,524 / 10,354 / 10,718 MiB |
| unevictable at 108 s | 11,431 MiB (= the lock) | 49 MiB |
| lowest MemAvailable | 1,411 MiB (frozen at 108 s) | 1,352 MiB (at 12 min, ran on to 20 min) |
| swap used at the low point | 238 MB | 639 MB |
| allocstall / pgscan_direct | 2,729 / 0.76 M by 108 s | 50,812 / 78 M over 20 min |
| PSI mem full / IO full, max | 2.35 / 4.77 (rising in the last 3 s: 0.95, 2.56, 4.77) | 6.57 / 11.92 |
| frame time median / p90, 40-150 s | 54.0 / 85.9 ms | 38.6 / 70.6 ms |
| journal lines "TIMED OUT" | 958 in 108 s | 2,000 in 1,200 s |

- **What the records rule in or out:**
  - **MLOCK_IMPORTS is ruled in** as the difference in how the box fails. Both runs reach the same available memory
    (about 1.4 GB). Without the lock the kernel reclaimed hard (78 M pages scanned) and swapped anon to zram (639 MB),
    and the run lived. With the lock 11.4 GB were unevictable, little was swapped (238 MB), IO pressure climbed in the
    last seconds and the box froze: the file-page starvation of F929.
  - **The pace is ruled in as a second difference:** his play pinned 1.2-1.4 GB more at every point to 108 s (a title
    start into his game, then whatever he did).
  - Frame time and the wait timeouts were higher in his play from 40 s on: 54 against 39 ms, 9 against 1.7 TIMED OUT
    lines a second. The records cannot assign that to COND_POP_NOP, priv33 or the route.
  - **COND_POP_NOP and priv33** are neither ruled in nor out by the records; the runs below separate them.
- **The separating runs** (his save copy, the ride, 150 s each, guard: MemAvailable < 1,200 MB, or IO full > 1.5 with
  MemAvailable < 2,000 MB; `slot439cs.sh` arms FA/FB/FC/QD; 0 GPU lines, no guard stop; the first attempt's "FD" was
  caught by fn439b's older distrobox arm and is not counted):

| Run | configuration | GTT 30 / 60 / 85 / 108 s (MiB) | unevictable | lowest MemAvailable | PSI mem full / IO full, max | frame median / p90 | TIMED OUT |
|---|---|---|---|---|---|---|---|
| A (FA) | priv33 c0ec7b38, t3-test-all's words: PASS + MLOCK + COND_POP_NOP | 6,305 / 10,640 / 11,056 / 11,056 | 10.6 GB | 2,428 MiB | 12.48 / 3.72 | 62.4 / 74.2 ms | 878 |
| B (FB) | A without MLOCK | 7,482 / 10,604 / 10,894 / 11,290 | 0 | 2,119 MiB | 0.00 / 3.66 | 62.7 / 75.5 ms | 717 |
| C (FC) | A without COND_POP_NOP | 7,960 / 11,022 / 11,032 / 11,032 | 10.7 GB | 2,432 MiB | 16.19 / 2.39 | 60.4 / 70.8 ms | 703 |
| D (QD) | priv35 138e6779, t3-test-fl's words | 8,234 / 10,824 / 10,902 / 11,204 | 0 | 2,154 MiB | 0.90 / 4.34 | 63.8 / 75.0 ms | 732 |

- **Measured:**
  - His pace reproduces in all four: about 11 GB by 60-108 s, against GS's slower start.
  - His frame times reproduce in all four: median 60-64 ms against his 54 in the same window.
  - His wait-timeout rate reproduces in all four: 4.7-5.9 TIMED OUT lines a second against his 8.9.
  - So none of these comes from COND_POP_NOP or priv33. They come with the route, a ride from his save in its first
    minutes.
  - **The lock brings memory stalls by itself:** PSI memory full peaked at 12.5 and 16.2 % with MLOCK_IMPORTS, against
    0.0 and 0.9 % without, at higher MemAvailable (2.43 against 2.12-2.15 GB).
  - None froze. Tonight's box kept 0.7-1.0 GB more available at the low point than his 19:01 play had (1.41 GB).
- **Reading:**
  - His freeze = this route's footprint (~11.9 GB pinned) + the lock + about 1 GB less headroom than tonight's box. The
    candidates for that last part are the plain shortcut's desktop (plasmashell) and his session's other processes at
    19:01; it is not measured.
  - The lock is harmful on this box: the same footprint without it lived through 1.35 GB available in GS. That is
    consistent with F929.
  - COND_POP_NOP and priv33 are cleared of the freeze. The launcher candidate t3-test-fl.sh (no MLOCK, no COND_POP_NOP)
    stays as prepared.

### vt439b: the armed trigger in Performance (11-25 03:18-03:59, priv39, the same boot, GPU kernel lines 4 -> 4)

- **Build priv39:** priv38 plus a start delay for the trigger: `BC5_0439_RB_FROM=<s>` after its first flip (60 here,
  past the film).
- **Runs:** VTP and VTP2, 1,200 s each, his save with the Performance memory, trigger 10 of 4096, `BC5_0439_RB_ARM=1`
  (sr439b's capture armed by the trigger); lowest MemAvailable 1.63 / 1.70 GB.
- **Captures:**
  - Most were refused by the frame dump's 20-GB floor: a gameplay frame is 2-11 GB. Two of my own dumps and the pass
    census captures were removed in between to make room.
  - VTP2's first capture went through: `frames/sr439b-20261125-034116-c0`, 2.09 GB, 8,554 ops in 19 submits. It is
    the frame after a trigger at 15; a copy is on the laptop.
- **Measured:**
  - The census of the refused captures still lists 271-441 surfaces with NaN/Inf per frame. That is no evidence by
    itself (sr439b's earlier finding: memory reused within a frame, raw buffers read as floats).
  - In the dumped frame the display surface (raw, DCC-compressed) shows violet blobs on the ground at the left.
  - A tiling-free violet count over every dumped colour surface (`k439/vtsurf439.py`) cannot separate the stage: DCC
    targets read raw, and non-colour buffers (normals, motion) decode as false violet.
  - The colour target 0x5000860000 is, in this mode, 2,176x1,224 in a 14.7-MB allocation (not the 10.7 MB of
    2176x1224x4). The display detiler gives black for it, so its pitch or block layout differs. It needs its own
    detile from its descriptor (SQ_IMG_RSRC pitch and swizzle) before the first pass with the patches can be named.
- **The whole-frame noise in gameplay, twice now** (count 260 in RBP, 215 in VTP2). Both are in the display surface
  right after the flip decompress: the grain pattern over a whole gameplay frame, in Performance mode, with the
  chained-piece flip-label wait served.
  - Reading: a DCC surface decompressed while its data and keys disagree. Either the flip's decompress ran before
    the frame's last writes landed, or the next frame started writing the buffer during it.
  - The second points again at a flip-label wait not served; the first at the flip's own wait for its frame.
  - Neither capture went through (disk), so the submit's waits are not listed yet.
- **Next:**
  - room for one gameplay dump. Either the frame dump's floor lowered for a private run (it is a guard of mine, 20 GB),
    or more space.
  - for the noise frame, a lighter catcher that needs no dump: at the flip, log the frame's flip-label wait packets by
    path (top level, chained, served or not) for the last 4 frames, written out when the trigger sees a count of 100
    or more.

### fl439: which flip-label wait is not honoured (11-25 04:00-, priv40)

- **The paths, from the code** (bc5LleAgc.cpp of the kit):
  - The title's flip-label waits (WAIT_REG_MEM on a sceVideoOutGetBufferLabelAddress label in host memory) are dropped
    from the GPU stream by the filter and served on the CPU before the submit, on one of two paths:
    - T: the top level of a command buffer (exp 0069's rule);
    - C: a chained or called piece (vl439 b, on by default since vlon439).
  - In a 20-min Performance ride the journal shows no T case ("set by a queued flip" 0, "still set at the wait:
    cleared" 0) and about 15,000 C cases.
  - The flip runs deferred (`BC5_DIRECT_FLIP_DEFER=1` in bc5-run.env): the title's flip increments
    `g_flip_pending[buffer]`, is queued behind the frame's jobs, is submitted once the GPU has finished them, and
    `bc5-flipdone` clears the label and decrements the count once the presenter has copied the buffer.
- **The hole, read from the code:**
  - Both paths wait while the flip is pending **and** the label reads set. Frame N sets its buffer's label with its
    last GPU write (RELEASE_MEM).
  - When frame N+2's submit is checked before frame N's GPU work is done, the label still reads 0, so the wait passes
    at once. Frame N+2 then renders into a buffer whose frame and flip are not done.
  - On the console the GPU runs N+2's wait after N's RELEASE_MEM in ring order, so the label is set by then.
  - The faithful CPU form is "wait while this buffer's flip is pending".
- **Build priv40** (`k439/mkfl439.py`; the tag fw439 was already taken by a completion-thread watchdog):
  - `BC5_0439_FLIP_WAIT_PENDING=1`: the C-path wait waits while the buffer's flip is pending, whatever the label
    reads (still at most 100 ms).
  - `BC5_0439_FL_CATCH=1`: a ring of the last 512 events (waits, flips queued, flips copied), the count of waits that
    passed with their buffer's flip pending, a journal line every 10 s, and the ring written beside the vt439 surface
    when the trigger counts 100 or more.
- **First measure** (WC, fix off, Performance): by 22 s, 2 of 625 flip-label waits had passed with their buffer's flip
  pending. The 20-min results follow.

### The 60-ms frames and the ~5 wait timeouts a second (step 3, from the existing journals)

- **What times out:** every "TIMED OUT" line of the D run (QD, 732 lines) and of his 19:01 play (946 lines) is the
  same kind of wait.
  - It is a WAIT_REG_MEM with compare function 3 (equal) in a 103-dword GFX command buffer, on one of six labels at
    0x20000080c0-0x20000082e0 (the start of the "anon" direct heap; 0x82e0 is the most frequent: 413 of 732, 472 of
    946).
  - In every case the reference is the current value plus 1: the wait expects the next increment of a counter that
    another writer (a compute queue's release or the CPU) has not made yet. The soft CP gives up after its 8-ms bound
    and goes on (the "marks set").
- **Where the 8 ms goes:** frames around 60 s (QD) run 66-73 ms flip to flip. Per frame:
  - the game thread inside the host: 8-12 ms (prepare 5-8, cs 3-4, label waits 0.0, event waits 0.0);
  - outside the host, the title's own CPU work: 58-61 ms;
  - GPU busy: 28 ms;
  - soft-CP passes: 10-12 ms in 6, with the timed-out waits inside them.
  - So the timeouts are not on the game thread and not in its frame time. They delay the GPU submission path while the
    GPU has room (28 of 67 ms busy).
- **Reading:**
  - The 60-ms frames of the first minutes are the title's own CPU time (streaming in his route), not BC5's waits.
  - The timed-out counter waits are a correctness question of their own: a GFX wait for a counter that its writer
    increments later than the soft CP's bound. What writes those six counters is not in these logs.
- **WC and WF** (priv40, Performance, his save, the ride, 1,200 s each, the catcher on, the trigger from 60 s at 10; 0 GPU
  lines):

| Run | flip-label waits | passed with the buffer's flip pending | ended by the 100-ms bound | largest trigger count |
|---|---|---|---|---|
| WC (fix off) | 21,424 | 2 (both in the first second) | 17 | 23 |
| WF (BC5_0439_FLIP_WAIT_PENDING=1) | 22,042 | 5 (counted at entry; the fix makes them wait) | 37 | 11 |

- **Measured:**
  - The label check passes a pending flip almost never after the start.
  - The 100-ms bound ends a wait with the buffer's flip still pending 17-37 times in 20 min. When it does, the label is
    cleared and the next frame renders into a buffer still being flipped: the pattern of the noise frames.
  - No run had a trigger of 100+ (the noise frame came once in each of the two earlier 20-min rides), so no ring was
    written yet.
- **Reading:** the wait that is not honoured is the C-path flip-label wait at its 100-ms bound. The console's wait has
  no bound; the presenter here sometimes takes longer than 100 ms to copy a queued flip.
- **Next (WB, priv41 412e1290):** `BC5_0439_FLIP_WAIT_PENDING=1` plus `BC5_0439_FLIP_WAIT_MS=2000` (`mkfl439.py`'s
  bound switch, default 100).
- **WB** (priv41 412e1290: `BC5_0439_FLIP_WAIT_PENDING=1`, `BC5_0439_FLIP_WAIT_MS=2000`; the same ride, 1,200 s, 0 GPU
  lines; lowest MemAvailable 1.81 GB):
  - 20,858 flip-label waits, 2 passed with the flip pending (the start), **0 ended by the bound**; largest trigger
    count 29.
  - Frame times from the journal's frame profile, from 60 s:

| Run | frames | median | p90 | p99 | p99.9 | longest | frames over 100 ms |
|---|---|---|---|---|---|---|---|
| WC (bound 100 ms, fix off) | 18,981 | 56.9 | 69.8 | 88.7 | 971.7 | 3,135.8 | 156 |
| WF (wait-pending, bound 100 ms) | 19,646 | 56.1 | 68.6 | 93.7 | 674.2 | 2,066.4 | 177 |
| WB (wait-pending, bound 2,000 ms) | 19,344 | 57.5 | 69.5 | 82.2 | 127.7 | 1,148.0 | 51 |

- **Measured:** with the bound out of the way, no wait gives up on a pending flip. The median frame is unchanged, and
  the tail is much shorter (frames over 100 ms from 156-177 to 51; p99.9 from 674-972 to 128 ms).
- **Not yet shown:** that the noise frame is gone. Its rate was about one per 20-min ride (RBP, VTP2), and none of WC,
  WF or WB had one. It needs several WB-style rides with no 100+ trigger against rides of the old form that do have
  one.
- **Candidate fix (universal, both builds):** the C-path flip-label wait waits while its buffer's flip is pending, with
  a bound well above a presenter's slow copy (2 s here); the top-level path in the same form. The console's wait has
  no bound; the bound stays only as a guard against a presenter that never copies.

### io439: where the I/O pressure comes from (step 2; 11-25 05:16-05:47, priv35, his save, the ride)

- **Sampler** `k439/io439.sh`, every 5 s:
  - the emulator's /proc/<pid>/io;
  - Dirty and Writeback;
  - IO and memory PSI full;
  - the sizes of the journal, play-last.log, play-lean-last.log, the frame-dump directory and the samplers;
  - every 60 s, the emulator's open game files with their mount (findmnt).
- **Runs:** IOD = the D configuration, normal build 138e6779, logs on, 1,200 s. IOL = priv35's lean 2d08049d, the same
  words, no logs (BC5_LOGS=0, no PLAY_CAPTURE, no FRAME_DUMP or RUN_ENV); stopped by the guard at 614 s (MemAvailable
  1.87 GB with IO full 1.68).

| Run | read from disk | written (write_bytes) | play-last.log | lowest MemAvailable | PSI mem full / IO full, max | allocstall |
|---|---|---|---|---|---|---|
| IOD (normal, logs on, 1,200 s) | 6,395 MB | 612.5 MB | 595 MB | 2,393 MiB | 6.82 / 12.33 | +8,483 |
| IOL (lean, logs off, 614 s) | 6,906 MB | 6.0 MB | - | 1,763 MiB | 11.79 / 9.09 | +7,324 |

- **Measured:**
  - Every game file the emulator holds open lives on the local NVMe (`/dev/nvme0n1p3`, /var/home); none on the NAS.
  - The reads come in the first two minutes: 6.3 GB by 125 s, about 50 MB/s, when IO full peaks (7-12). Afterwards
    reads are about 1 MB/s and IO full is about 0.2.
  - The normal build writes 0.5 MB/s, almost all of it play-last.log (595 MB in 20 min; the journal 7 MB). Dirty
    stays near 12 MB and Writeback near 0. The lean build writes 6 MB in 10 min.
- **Reading:**
  - The IO pressure is the title's own loading and streaming reads while the page cache is squeezed by the pinned
    pool, not BC5's logging. The lean build with no logs ran lower on memory (it reaches farther along the route in
    the same time) and had the same IO peaks.
  - What the test launcher could drop: nothing for memory. The normal build's play-last.log grows 1.8 GB an hour,
    which costs disk and page cache over a long play. For his plays it could go to a smaller log level, or into a
    rotation, but it is not his freeze.
  - F927's IO full of 43 % (a ride without the lock) sits with these first-minutes reads under a pool near its peak.

### Step 4, the detile of the 2,176x1,224 colour target (not finished)

- The target's dump (0x5000860000, format 56, swizzle 27) is 14,745,600 B, exactly 2,560 x 1,440 x 4: the
  allocation is 1440p (the dynamic-resolution maximum), and the 2,176x1,224 render is a sub-rectangle of it.
- Detiled at 2,560x1,440 with the display surface's 64-KiB block order, the data lands as a garbled band. The layout
  differs (block order for this format and swizzle, or an offset).
- It needs the swizzle from the descriptor (SQ_IMG_RSRC SW_MODE and the pipe/bank bits) before the first pass with the
  patches can be named. The dumped frame stays on the box and the laptop for that.
- **WB2 and WC2** (priv41; WB2 = WB's words, WC2 = the old form: no wait-pending, bound 100 ms; 1,200 s each; 0 GPU
  lines):

| Run | waits | passed with the flip pending | ended by the bound | largest trigger | ring written | frames from 60 s: median / p99 / p99.9 / longest / over 100 ms |
|---|---|---|---|---|---|---|
| WB2 (fix) | 24,386 | 2 | 0 | 12 | no | 49.4 / 68.7 / 84.3 / 198.1 ms / 16 |
| WC2 (old) | 19,326 | 2 | 7 | **214** | **yes** | 63.6 / 94.5 / 158.2 / 2,562 ms / 102 |

- **The caught noise frame (WC2, count 214), its ring** (`frames/vt439-40366.5-214-3840x2160.raw.fl439.txt`, 512
  events, about 8 s):
  - Buffers 2 and 3 alternate.
  - Every flip (F) was copied (D) about 1.4 ms after it was queued. The next wait on that buffer (W) found pending 0
    and its label clear, waited 0.001 ms, and passed.
  - No wait in the ring ended at the bound, and none cleared a label (the run's 7 bound endings were earlier).
- **Answer to "which wait was not honoured": none**, for this noise frame. Every flip-label wait in the 8 s before it
  found its buffer's flip complete.
  - The noise frame therefore does not come from rendering into a buffer still being flipped. It lies inside the
    flip itself: the display surface right after dc439's in-place decompress already shows it.
  - The candidates are the decompress running before the frame's last writes (on another ring) landed, or DCC
    keys out of step with the data.
  - The catcher did not record whether the frame's own work had completed when the decompress ran: that part of the
    request is not built yet.
- **What the fix rides do show:**
  - With the wait-pending rule and a 2-s bound (WB, WB2) no wait gives up on a pending flip, and the frame tail is
    shorter (frames over 100 ms: 16-51 against 102-177 in WC, WF, WC2).
  - No noise frame in 40 min of WB/WB2, against 3 in 100 min of the old form (RBP, VTP2, WC2; 0 in WC and WF). The
    counts are too small to call, and the ring above says the wait is not the mechanism. So the noise question stays
    open while the tail gain is real.
