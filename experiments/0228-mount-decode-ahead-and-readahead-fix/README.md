# 0228 — bc5-mount's decode-ahead, the read-ahead fix's load time, and NVMe read_ahead_kb

**Question.** Exp 0227 (F286) found ASTRO BOT's start bound by latency: ~8,000 small image reads through `bc5-mount`,
made worse by a nearly full drive. Three follow-ups, approved by the top session:
- (A0) Does a larger `bc5-mount` decode-ahead shorten a cold start?
- (B) Does exp 0227's read-ahead fix (`patch_0227-readahead-fix.diff`) load the second title as fast as the read-ahead
  off? Does the unfixed read-ahead slow it, as reported on 2026-10-22?
- (C) Does `read_ahead_kb` 1024 on the NVMe (set by the maintainer at ~11:01) speed a cold start?

**Setup.**
- Exp 0227's scripts with this directory: `run0228.sh`, `chain0228.sh`, `io0228.sh`, `bcm0228.sh`, `load0228.py`,
  `build0228.py`, and the launcher copy `play-astro-0228.sh` (a `BC5_EMU` line, the `'^kyty_emulator'` guard).
  - The fresh boot of 2026-10-23 (31c1a6ac).
  - Every run keeps the live saves aside and puts them back (`diff -rq`), stops only its own emulator PID, and
    screenshots the active window about every 1.1 s for the first 60 s (kept on the box).
- New per run:
  - `bc5-mount`'s own log (`<tag>-mount.log`: its workers and decode-ahead);
  - `bcm0228.sh` for `bc5-mount`'s worker CPU;
  - from B on, a drive probe just before the launch: a 256-MiB O_DIRECT read of the title's image at 8 GiB;
  - from the read_ahead_kb runs on, `read_ahead_kb` itself.
- New arms:
  - DA32C: cold, `BC5_MOUNT_PREFETCH_KIB=32768`; COLD is the same with the default 2048;
  - RA0C, RA4C, FIXC: the B arms, cold;
  - FIX: `~/bc5-work/exp0228/kyty_emulator`, a one-file build of `src/libAmpr.fix.cpp` (md5 `5f2ec30b…`, binary
    `0eb4a575…`) against the shared objects, with `KYTY_BC5_APR_READAHEAD=4`.
- "presents" (ASTRO BOT's first logo) is timed from the screenshots, as in exp 0227, from the launcher's start. For the
  second title, the logo load's end and the Continue load (after the press at 88.2 s) come from `/proc/<pid>/io`.
- B also read its GPU journals with O_DIRECT at 15 MB/s (exp 0214's `ra0214.py`, `gu0214.py`).

**Result.**
1. **A0, decode-ahead, ASTRO BOT cold, 10:22–10:31** (`raw/load-A0.txt`, `raw/presents-A0.txt`, `raw/rates-A0.txt`;
   `bc5-mount` logged decode-ahead 2048 and 32768 KiB). Seconds from the launcher's start:

   | run | arm | emulator start | "presents" | startup reads end (from emulator start) |
   | --- | --- | --- | --- | --- |
   | B01 | COLD (2 MiB) | 8.6 | 32.9 | 32.5 |
   | B02 | DA32C (32 MiB) | 7.2 | 35.3 | 37.2 |
   | B03 | DA32C | 2.9 | 13.4 | 13.3 |
   | B04 | COLD | 2.9 | 12.2 | 13.3 |

   - A 32-MiB decode-ahead gives no gain: each pair is equal.
   - The second pair started 20 s sooner than the first with the page cache dropped too. In the first 15 s its reads ran
     118–320 MiB/s against 52–103, and `bc5-mount`'s workers ran at 54–106 % of a core against 20–38 %.
   - B01/B02 came 25–30 min after the top session's compression freed ~130 GB; btrfs had trimmed 181 GB by 10:31
     (224 MB pending). A DRAM-less drive collecting garbage after that is the likely reading; it can't be seen from the
     host.
2. **B, the second title through `play-pkg.sh` (`KYTY_BC5_APR_PARALLEL=8`), 10:32–10:59** (`raw/load-B.txt`,
   `raw/frames-B.txt`, `raw/giveups-B.txt`, `raw/BP*-apr-journal.txt`):
   - Drive probe 495–597 MB/s; launcher to emulator 0.6–1.7 s.
   - Times in s; the clock voice's queue is submit → finish, p95 / max in ms:

   | run | arm | logo load end (from emulator start) | Continue load | flips/s | > 100 ms | > 1 s | given up (0x12004b5438) | clock-voice queue p95 / max |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | BP1 | RA0 | 14.6 | 39.4 | 35.3 | 48 | 0 | 9 (3) | 291 / 419 |
   | BP2 | RA4 | 14.2 | – | 35.7 | 47 | 0 | 8 (3) | 392 / 463 |
   | BP3 | FIX | 14.1 | 39.9 | 33.7 | 57 | 0 | 12 (6) | 156 / 230 |
   | BP4 | FIX | 14.1 | 38.9 | 35.0 | 55 | 0 | 11 (5) | 130 / 244 |
   | BP5 | RA4 | 13.2 | 41.0 | 35.3 | 42 | 0 | 7 (1) | 223 / 389 |
   | BP6 | RA0 | 14.2 | 37.0 | 35.9 | 44 | 0 | 9 (3) | 225 / 304 |
   | BP7 | RA0, cold | 14.5 | – | 34.0 | 57 | 0 | 12 (2) | 209 / 401 |
   | BP8 | RA4, cold | 14.4 | 40.2 | 35.5 | 44 | 0 | 10 (5) | 218 / 353 |
   | BP9 | FIX, cold | 15.3 | 38.1 | 35.5 | 52 | 0 | 10 (5) | 129 / 176 |

   - "–": the reads never stayed under 5 MB/s for 5 s after the press.
   - All runs: TIMEOUT, fault, reopen, crash and kernel lines 0.
   - FIX left 40–48 of the clock voice's journaled buffers to the worker (over 1 MiB or a parallel run) and read
     125–141 ahead. RA4 read 185–204 ahead.
   - BP3 (FIX) and BP7 (RA0, cold) ran under heavy swap (pswpout +132k and +230k).
3. **The cold start after the compression** (ASTRO BOT, `raw/presents-RA.txt`):
   - BC1 at 11:00 had "presents" at 11.5 s. `read_ahead_kb` changed from 128 to 1024 during it, so the run is mixed.
   - B03/B04 had 13.4 and 12.2 s.
   - Before the compression: 38.5, 49.9 (exp 0227 AR1, AR3) and 33.3 s (AU5).
4. **C, `read_ahead_kb` 1024, cold, 11:02–11:09** (BR1–BR3, probe 620–637 MB/s):
   - "presents" 11.8, 11.5 and 11.6 s; startup reads end 12.2–12.6 s.
   - At 128 (B03/B04): 13.4 and 12.2 s; reads end 13.3 s.
   - Under 1 s apart, within the shots' ~1.1-s resolution. No control runs at 128 after the change (that needs root).

**Verdict.**
- **A larger `bc5-mount` decode-ahead does not help** (A0); not for the launcher.
- **The read-ahead does not slow the second title's loads, fixed or not** (B): the logo load ends at 13–15 s and the
  Continue load takes 37–41 s in every arm, warm and cold. The slow loads reported on 2026-10-22 were the drive (F286).
- **The fix gives the clock voice's queue the best tail**: p95 129–156 ms against 209–291 (off) and 218–392 (unfixed).
  It has no frame, timeout or crash regression.
- To watch, as in F273: given-up waits on 0x12004b5438 (FIX 16 against 8 and 9 over three runs each), and slightly more
  frames over 100 ms (52–57 against 42–57).
- Under the maintainer's rule the fixed read-ahead is eligible to come back (the top session's call). That means
  `patch_0227-readahead-fix.diff` into the tree, both shared builds, and the launchers' default to 4.
- **The cold ASTRO BOT start is ~12 s now**, against 33–50 s before the compression. The drive's state after the
  freeing explains B01/B02.
- **`read_ahead_kb` 1024: under 1 s of gain at most**; not shown.
- Open: `bc5-mount`'s startup preload (ADR 0014; code in `tools/bc5-mount/src/preload.rs`, not built yet), whose
  headroom is now smaller.
