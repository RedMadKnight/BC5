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

(more to come)

**Verdict.** (to come)
