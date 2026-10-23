# 0227 — slower loading reported on 2026-10-22: read-ahead, today's libAmpr code, the launcher, or the box?

**Question.**
- The maintainer reported on 2026-10-22, late in the evening: "zauważyłem już wcześniej w drugiej grze i potwierdzam
  teraz w astrobot że wczytywanie poziomów trwa teraz o wiele dłużej". In short: level loading takes much longer now,
  in both titles.
- After a reboot (2026-10-23 00:05) he added that the wait comes before ASTRO BOT's first logo ("zanim wczyta się
  Sony Entertainment Presents mamy już tutaj dość długi czas oczekiwania"), on both the normal and the lean build.
- Our A/Bs (exps 0214–0222) measured frames, never load time. What makes the start and the loads slow, and is it
  something changed on 2026-10-22?

**Mitigation already in place (not this experiment's work).**
- 2026-10-22 23:59, on the maintainer's word: both launchers (`play-pkg.sh`, `play-astro.sh`) export
  `KYTY_BC5_APR_READAHEAD=${…:-0}`, so the read-ahead is off (backups `*.bak-ra0`).
- He then found loads "even longer" with it off ("Jest jeszcze dłużej"). The box had thrashed after 7.4 h of runs
  (kcompactd ~33 % of a core, 168,300 compact stalls, ~75 GB swapped in), and he rebooted at 00:05:34.

**Setup.**
- Offline review of the read path (`~/src/KytyPlus/src/libs/libAmpr.cpp`, `tools/bc5-mount/src/fuse.rs`) for ways the
  read-ahead (F273) or the condition-variable wait (F276, F281) could slow a load:
  - The condition-variable wait can't hold a buffer: a buffer no reader takes runs on the worker, and the worker's
    50-ms wait ends on a notify sent under the same mutex.
  - The read-ahead bypasses `KYTY_BC5_APR_PARALLEL=8` (`play-pkg.sh` line 60, exp 0112). `RunOrderedAprCommands` runs a
    buffer's reads on 8 threads only when the buffer was not read ahead. A reader reads them one by one, and the
    worker waits for it.
  - `bc5-mount` decodes ahead per file, not per handle (`fuse.rs`, `Stream { last_end, ahead_to }`). A read counts as
    in order only within 1 MiB of where that file's last read ended. Readers and the worker reading one archive at
    once would defeat it.
  - A fix for both is written (`patch_0227-readahead-fix.diff` against the tree's `eaef1da1…`; `src/libAmpr.fix.cpp` on
    the box, md5 `5f2ec30b…`; not built): a reader leaves to the worker any
    buffer over `KYTY_BC5_APR_READAHEAD_MAX_KIB` (1024) and any buffer the worker would read in parallel.
- Runs on ASTRO BOT (`run0227.sh`, `chain0227.sh`), on the fresh boot only (31c1a6ac, up since 2026-10-23 00:05:57):
  - A copy of `play-astro.sh` with a `BC5_EMU` line (`play-astro-0227.sh`).
  - astro-route's start: its own saves (`save-backup-astro`), cross at 50 s, cross 25 s later to load the save.
  - The maintainer's LIVE saves are copied aside before each run and put back after it (`diff -rq`).
    `astro-route.sh` as it was would have overwritten his progress with the 10-21 backup.
  - Each stops only the emulator PID it started; 150 s a run.
- Beside each run:
  - `io0227.sh`: the emulator's `/proc/<pid>/io` every 0.5 s (rchar, read_bytes, wchar, write_bytes);
  - exp 0220's `mem0220.sh`;
  - the box's state at the start and end: MemAvailable, SwapFree, PSI full totals, vmstat compact_stall, pswpin,
    pswpout, pgmajfault;
  - from run AQ1 on, the switches that reached the emulator (`/proc/<pid>/environ`) and screenshots of the active
    window, one about every 1.1 s for the first 60 s (`spectacle`, kept on the box: private).
- `load0227.py`, defined before the runs:
  - the startup load ends at the first moment the read rate stays under 5 MB/s for 5 s;
  - the first flip comes from the fps counter;
  - bytes are written during the startup load.
- "presents" (the first logo) comes from the screenshots: the first shot 0.3 points brighter than the black window's
  3.2 % (its title bar). Three frames were checked by eye.

**Result.**
1. **Incident, 08:35–08:37: two emulators at once.**
   - The OLD binary's file is `kyty_emulator.before-0214`, so its process name is `kyty_emulator.b`.
   - `pgrep -x kyty_emulator` (my scripts' guards and the launcher's own check) never saw it. Run AM1-OLD reported
     "no emulator" and stopped nothing, so AM2-CUR started the shared build beside it at 08:36:25.
   - Stopped at 08:37:35 by PID.
   - In those ~60 s: swap-in +764k pages, swap-out +1.58M, compact_stall +11,796, and 548 kernel lines
     "amdgpu … Not enough memory for command submission!". No ring timeout, reset or fault.
   - His live saves were identical afterwards.
   - Fix: OLD runs through a symlink named `kyty_emulator` (`old/`), every guard matches `pgrep '^kyty_emulator'`, and
     a run that sees no emulator, or leaves one, stops the chain.
   - Any binary not named exactly `kyty_emulator` is invisible to every session's guards.
2. **OLD (`kyty_emulator.before-0214`, before every libAmpr change of 2026-10-22) against CUR (the shared build,
   read-ahead off by the launcher), ASTRO BOT, 08:43–08:55** (`raw/load-AP.txt`):

   | run | arm | emulator start after launch | first flip | startup reads end | read in 150 s |
   | --- | --- | --- | --- | --- | --- |
   | AP1 | OLD | 1.9 s | 4.8 s | 12.2 s | 11.8 GB |
   | AP2 | CUR | 4.0 s | 4.6 s | 14.2 s | 11.7 GB |
   | AP3 | OLD | 6.0 s | 7.2 s | 24.3 s | 11.4 GB |
   | AP4 | CUR | 8.0 s | 6.3 s | 22.4 s | 11.9 GB |

   - No difference between the arms; run order matters more.
   - The same ~3.5 GB of startup reads took 15 s in the first pair and 25 s in the second.
   - The launch delay grew by ~2 s a run.
   - So today's libAmpr code (the exp 0203 journal hooks, the read-ahead, the condition-variable wait) does not
     explain ASTRO BOT's slow start.
3. **Read-only diagnosis, 08:59–09:01 (no emulator):**
   - `play-astro.sh` mounts the image with `bc5-mount` at every launch and unmounts it on exit, so the decode cache
     starts empty every time.
   - The launcher gained `BC5_DIRECT_CHAIN=2` on 2026-10-22.
   - `bc5-mount` (10-17) and `bc5-run.env` (10-15) are unchanged.
   - `~/bc5-data/captures` 157 GB in 490 dirs; `~/bc5-work` 55 GB; disk 94 % full; btrfs 11 GiB unallocated.
   - O_DIRECT reads of the 47.5-GB image ran at 333 MB/s at offset 0 and 154 MB/s at 12 GB. exp 0002 had 389 MB/s
     cold.
4. **D (launcher defaults) against P (`PLAY_CAPTURE=0`, through a copy of `bc5-run.env`, which would override the
   variable) against C (`BC5_DIRECT_CHAIN=0`), order D P C C P D, 09:08–09:26** (`raw/load-AQ.txt`,
   `raw/presents-AQ.txt`, `raw/rates-AQ.txt`). Seconds from the launcher's start:

   | run | arm | emulator start | "presents" | intro | startup reads end (from emulator start) | written in startup |
   | --- | --- | --- | --- | --- | --- | --- |
   | AQ1 | D | 1.2 | 23.5 | 28.2 | 28.4 | 8 MiB |
   | AQ2 | P | 6.4 | 32.1 | 36.4 | 31.5 | 4 MiB |
   | AQ3 | C | 5.2 | 27.2 | 32.2 | 26.0 | 9 MiB |
   | AQ4 | C | 6.8 | 29.4 | 34.2 | 25.6 | 8 MiB |
   | AQ5 | P | 5.0 | 18.8 | 25.3 | 18.3 | 4 MiB |
   | AQ6 | D | 8.2 | 34.1 | 39.0 | 31.2 | 8 MiB |

   - Neither the capture journal nor the submission chains explain it: the arms overlap, and the spread within an
     arm is up to 15 s. The journal writes only 4–9 MiB during startup.
   - "presents" appears about 5 s before the ~3.5 GB of startup reads end, and the bright intro starts as they end.
     The wait is the launch delay (1–8 s) plus those reads, at 75–390 MiB/s per 5-s bin.
   - `BC5_DIRECT_FLIP_BRIGHT` is never reached while `BC5_DIRECT_FLIP_DEFER=1`: the defer branch returns first, so the
     AP runs journaled no line.
   - In three of the six runs, one per arm, the level never loaded. The title came up at 45–60 s, after the scripted
     press at 50 s.

5. **The disk, 09:33–09:36, no emulator** (`diag0227.sh`, `raw/diag-0933.txt`):
   - NVMe: Fanxiang S501Q 512GB, firmware VC406624, on a 5.0 GT/s ×2 link (it can do 8.0 GT/s ×4), the kyber
     scheduler, read_ahead_kb 128.
   - SMART needs root. Swap is zram. btrfs is mounted ssd, discard=async, space_cache=v2.
   - O_DIRECT reads of the ASTRO BOT image, 1 GiB each: 544, 600, 581 and 623 MB/s at 0, 12, 30 and 12 GiB.
     At 09:00 the same image gave 333 and 154 MB/s.
   - A fresh 2-GiB file read back cold at 617 and 559 MB/s, so old data reads no slower.
   - Writing that file with `conv=fsync` took 148 s: 14.5 MB/s, with 29–31 GB free on the drive.
   - The `bc5-mount` disk cache (the second title's package only; ASTRO BOT's image has none) holds 8.1 GB against
     its 8,192-MiB limit and was last written 2026-10-18 11:40. It writes nothing during loads now.
6. **Cold against warm page cache, ASTRO BOT, 09:37–09:49** (`raw/load-AR.txt`, `raw/presents-AR.txt`,
   `raw/rates-AR.txt`; COLD = the page cache dropped just before the launch). Seconds from the launcher's start:

   | run | cache | emulator start | "presents" | intro | startup reads end (from emulator start) |
   | --- | --- | --- | --- | --- | --- |
   | AR1 | cold | 21.1 | 38.5 | 44.4 | 23.4 |
   | AR2 | warm | 5.5 | 28.8 | 34.3 | 29.2 |
   | AR3 | cold | 11.9 | 49.9 | 55.8 | 43.3 |
   | AR4 | warm | 3.7 | 28.7 | 33.5 | 30.5 |

   - A cold page cache adds 10–21 s before "presents". Much of it comes before the emulator starts (12–21 s against
     4–6 s): distrobox, the mount and the 165-MB binary, all read cold.
   - `bc5-mount`'s 8 read workers used 5–60 % of one core in all during the startup (`bcm0227.sh`), so decoding
     doesn't bound it.
   - The startup reads ran at 14–290 MiB/s per 5-s bin, against ~600 MB/s in bulk, so they are bound by latency: many
     small dependent reads.
   - The kernel logged `clocksource: Watchdog remote CPU 10 read timed out` at 09:38:19, during AR1.

7. **Space freed, by the top session under the maintainer's grant, 09:5x–09:57:28** (`~/bc5-work/compress-captures.sh`,
   log `~/bc5-work/compress-captures-20261023.log`):
   - zstd -3 on the files over 10 MB in the capture dirs dated 10-16..10-20, mostly `direct.log` and
     `guest-printf.txt`.
   - Each file was tested before its original was removed, and the job paused for any emulator.
   - 410 files, 136.5 GB → 6.32 GB, 0 failures; /var/home went from 94 % full (31 GB free) to 68 % (152 GB free).
   - The compression is lossless, so the citations stay valid: a `.zst` decompresses back.
   - This experiment's candidate list (`compress-list.txt`, `comp0227.sh`) was not used.
8. **The write test after it, 09:58:30** (`wtest0227.sh`, `raw/wtest-0958.txt`):
   - 2 GiB from /dev/urandom with `conv=fsync` in 7.75 s = 277 MB/s, against 14.5 MB/s at 09:34. 19 times faster.
   - The cold O_DIRECT read-back ran at 759 MB/s.
9. **ASTRO BOT's startup submits, warm, 09:58–10:00** (run AT1, 90 s, `KYTY_BC5_AMM_TRACE=1`, `trace0227.py`,
   `raw/trace-AT1.txt`):
   - The startup reads ended 14.5 s after the emulator's start. The warm runs before the compression had 29.2 and
     30.5 s (AR2, AR4).
   - In those 14.5 s: 5,028 submits, 8,066 reads, 3,199 MiB. Read size median 13 KiB, p90 448 KiB, max 24.9 MiB.
   - 46 % of the reads sit in submits with two or more reads (1 read: 4,389 submits; 2: 316; 3: 98; …; up to 64+).
   - By the rule fixed before the run (≥ 25 %), `KYTY_BC5_APR_PARALLEL=8` was then tested (10).
10. **`KYTY_BC5_APR_PARALLEL=8` against the launcher's default (unset), warm, then one cold run, 10:01–10:16**
    (`raw/load-AU.txt`, `raw/presents-AU.txt`, `raw/rates-AU.txt`; PAR8's environment confirmed). Seconds from the
    launcher's start:

    | run | arm | emulator start | "presents" | intro | startup reads end (from emulator start) | `bc5-mount` workers, first 10 s |
    | --- | --- | --- | --- | --- | --- | --- |
    | AU1 | CUR | 1.4 | 9.8 | 15.1 | 12.2 | 83–108 % of a core |
    | AU2 | PAR8 | 3.2 | 27.0 | 31.5 | 30.5 | 28–43 % |
    | AU3 | PAR8 | 3.2 | 26.9 | 32.0 | 30.5 | 30–37 % |
    | AU4 | CUR | 5.9 | 25.3 | 30.5 | 25.4 | 38–46 % |
    | AU5 | cold | 7.7 | 33.3 | 39.2 | 33.3 | 22–34 % |

    - `KYTY_BC5_APR_PARALLEL=8` gives ASTRO BOT no gain: 27.0 and 26.9 s against 25.3 s for CUR in the same state.
    - The startup is fast when the image's startup data is still in the page cache: AU1, and AT1 before it, followed
      a short or idle stretch. `bc5-mount` then decodes at about one core.
    - It is slow when a full 150-s run, with ~12 GB of game memory, has just evicted that data. `bc5-mount` then waits
      on the ~8,000 small reads going to the disk one after another. AP1/AP2 against AP3/AP4 showed the same.
    - Before and after the space was freed:
      - writes 14.5 → 277 MB/s;
      - cold "presents" 38.5 and 49.9 s (AR1, AR3) → 33.3 s (AU5), the launcher's cold delay 21.1 and 11.9 → 7.7 s;
      - warm 28.7 and 28.8 s (AR2, AR4) → 9.8 and 25.3 s (AU1, AU4).
      - One run per state: a direction, not a size.

**Verdict.**
- **The slow start is not code changed on 2026-10-22.** The old binary starts like the current one (2). The capture
  journal, the submission chains and `KYTY_BC5_APR_PARALLEL` don't change it (4, 10).
- **ASTRO BOT's start is bound by latency.** It is ~8,000 small reads (median 13 KiB, ~3.2 GB) of the game image
  through a freshly mounted `bc5-mount`, one after another. So it is set by:
  - the page cache: "presents" came at ~10 s with the startup data cached, 25–30 s without it, 33–50 s fully cold;
  - the drive: a DRAM-less Fanxiang S501Q at 94 % full wrote at 14.5 MB/s, and its reads swung between 154 and
    623 MB/s.
- **Freeing space helped.** The top session compressed 136.5 GB of old capture journals to 6.3 GB (68 % full). Writes
  went 19 times faster and the cold start got shorter.
- The read-ahead's own effect on load time (RA4 against RA0) was not measured: today's evidence did not point at it.
  The fix for its known flaws (`src/libAmpr.fix.cpp` on the box, not built) waits for that measurement. Read-ahead
  stays off in the launchers.
- To do:
  - keep /var/home under ~80 %: the `PLAY_CAPTURE=1` journals grew ~157 GB in a week;
  - try a larger `read_ahead_kb` on nvme0n1 (root, the maintainer's call; untested);
  - keep the image's startup data cached, or read it ahead in `bc5-mount`;
  - measure the second title's load time;
  - the RA4 against FIX arms, if the read-ahead is to come back.
