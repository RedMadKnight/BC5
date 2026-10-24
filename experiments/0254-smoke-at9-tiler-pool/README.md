# 0254 — smoke runs of both shared builds after the ATRAC9 decoder, the tiler pool, the held tail and the CS prefix

**Question.** Both shared builds took four changes within a few hours:
- 2026-10-23 19:28/19:31: F301's ATRAC9 vibration decoder (vgmstream, `KYTY_BC5_AT9_VIBRATION`, on by default);
- 22:44: F311's tiler scratch pool (`KYTY_BC5_TILER_POOL`, on by default; normal build md5 `fd84c785…`, lean
  `cf5b3665…`);
- 2026-10-24 00:13: the top session's integration of F312's held tail (exp 0226, `BC5_DIRECT_HOLD_TAIL`, on by default;
  normal `bf9bebcb…`, lean `3e9d4009…`). It acts only with a compute ring. The second title's launcher sets one, and so
  does ASTRO BOT's second shortcut `play-astro-compute.sh`, which had not been tested with it;
- 00:23: the top session's integration of exp 0195's compute-state prefix (F254/F266; `BC5_DIRECT_CS_PREFIX=1` set in
  `play-pkg.sh`) with patch_0195's alias_learn guard, on for every title (normal `02ed5340…`, lean `fb894c12…`).

Do the shared builds still run cleanly? Each run is checked for:
- its full time, crash lines and kernel lines;
- the pool's counters (pool on, few new buffers) and the decoder's AT9 lines;
- the held tail's lines and the give-ups;
- in part 2, the prefix's lines, the alias guard's lines and F251's SQC fault;
- the live saves coming back identical.

**Setup.**
- **Part 1** (00:14:53–00:21:08, builds `bf9bebcb`/`3e9d4009`): `chain0254.sh` runs `run0254.sh <astro|astroc|pkg> <tag>
  <secs>` three times under one BOX-LOCK line, after the held tail's integration ended with "done". It stops at the
  first run that does not pass, at a new amdgpu fault/timeout/reset/error line, or at a changed boot id.
  - Each run goes through the shortcut's own launcher with its defaults. Nothing is set but the route's input file, plus
    `BC5_LEAN=1` for the lean build. The runner is built from exp 0229's `run0229a.sh` and `run0229.sh`.
  - **S5A:** ASTRO BOT, normal build (`play-astro.sh`), S4A's route: the route saves (`save-backup-astro`), cross at
    50 s on the title, cross 25 s later to load the save. The live saves are kept aside and put back (`diff -rq`).
  - **S5C:** the same through `play-astro-compute.sh` (the compute ring), so the held tail acts.
  - **S5L:** the second title, lean build (`play-pkg.sh`, `BC5_LEAN=1`), S4L's route: exp 0203's O2
    (`saves-before-152617`, `o2-continue.cmd`, Continue at 85 s). Saves by exp 0196's `ab-restore.sh`.
  - Each run records:
    - the binary's md5 against the expected one (`WANT_N`, `WANT_L`, from the integration's `int.out`), and the
      switches that reached the emulator (`/proc/<pid>/environ`);
    - crash lines, and new `dmesg` lines mentioning the GPU, OOM or hangs;
    - the play log's `bc5 tiler scratch:` lines (one per 1024 requests, F311) and its `bc5 ajm: ATRAC9` and
      `CODEC_ERROR` lines (F301);
    - for ASTRO BOT, the GPU journal (`PLAY_CAPTURE=1`) with exp 0226's `ab0226.py` counts: `cpu-wait … GIVEN UP`,
      `two rings … NOT served`, `hold tail: the wait on … GIVEN UP`, `TIMEOUT`, the `hold tail` lines and the last
      `hold tail: N holds` summary. The lean build writes no journal;
    - the box's memory state, as in exp 0229.
  - Each run writes `<tag>-verdict.txt`: "pass" means the full time, the expected binary, no crash or kernel line, and
    the live saves back identical.
  - `kstream0254.sh` (laptop) streams the kernel log into `raw/kernel-stream.txt`. It ends by itself once the chain's
    lock line is gone and no emulator runs.
- **Part 2** (from 00:24:18, builds `02ed5340`/`fb894c12`): `chain0254b.sh` with `run0254b.sh` and `jcount0254.awk`,
  under one lock line, after the prefix's integration ended with "done":
  1. part 1's journal counts of S5A and S5C, redone (see "Two faults of mine" below);
  2. **S6N:** the second title, normal build, `play-pkg.sh` with its defaults (the prefix on), S4N's route, 300 s. Its
     journal is also searched for the prefix's `cs prefix (exp 0195)` lines, and exp 0214's `ra0214.py` gives flips a
     second as for S4N. `dmesg`'s SQC lines (F251) are counted apart;
  3. **S6A:** ASTRO BOT, normal build, S4A's route, 150 s: the alias guard (`aliases: fault …: no guest memory at …,
     not learned`) had not run with ASTRO BOT;
  4. **S5L** from part 1.
  - `run0254b.sh` is `run0254.sh` with the title `pkgn` and the saves fix. Every journal is searched for the alias
    guard's lines (`jcount0254.awk`).
  - `kstream0254b.sh` streams the kernel log into `raw/kernel-stream-b.txt`.

**Result.**

| run | build | title, launcher | length | crash / kernel lines | tiler pool | AT9 | journal | saves |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S5A | `bf9bebcb` normal | ASTRO BOT, `play-astro.sh` | 200 s, full | 0 / 0 | on, 3 new buffers in 11,264 requests | none | 19 cpu-wait given up; no two-ring wait, TIMEOUT or hold | back, identical |
| S5C | `bf9bebcb` normal | ASTRO BOT, `play-astro-compute.sh` | 150 s, full | 0 / 0 | on, 3 in 8,192 | none | no give-up, no TIMEOUT; 12,348 holds, none given up | wrong folder (my fault), put right by hand |
| S6N | `02ed5340` normal | the second title, `play-pkg.sh` | **hung at ~140 s** | 0 / **a compute-ring timeout and a GPU reset** | on, 3 in 4,096 (by 00:26:29) | layout 7 decoded by vgmstream | 2 TIMEOUTs at the end; 9,129 holds, 1 given up; 33 prefixed buffers; 0 alias lines | restored after the reboot, identical |

Not run: S5L (part 1 stopped at S5C's saves; part 2 stopped at S6N) and S6A.

1. **S5A passed:**
   - no crash or kernel line, and the live saves came back identical;
   - tiler pool on: 11,264 requests, 3 new buffers (96 MiB), 11,261 reused;
   - no AT9 line and no `CODEC_ERROR`;
   - journal: 19 `cpu-wait … GIVEN UP`, no two-ring wait, no TIMEOUT, no hold line. The held tail is inactive without
     a compute ring.
2. **S5C ran clean; only its saves went wrong**, by my runner's fault (below):
   - no crash or kernel line;
   - pool on: 8,192 requests, 3 new buffers;
   - no AT9 line;
   - `BC5_DIRECT_COMPUTE_RING=0` and `BC5_DIRECT_CROSS_RING_WAITS=all` reached the emulator;
   - journal: no give-up of either kind, no TIMEOUT;
   - the held tail acted, its first run on ASTRO BOT's compute shortcut: 12,348 holds, 7,142 released with the writer on
     a ring and 5,205 satisfied, none given up; held 2.39 ms on average, 30.55 ms at most.
3. **S6N: the compute ring timed out ~140 s in, the ring reset failed, and the box went down after a full GPU reset.**
   - The emulator (pid 474927) had `BC5_DIRECT_CS_PREFIX=1`, the compute ring and the cross-ring waits
     (`raw/S6N-start.txt`).
   - Until then (`raw/S6N-journal*.txt`, `raw/S6N-frames.txt`, `raw/S6N-play-lines.txt`):
     - 4,945 flips in 137.6 s, 35.9 a second; 38 frames over 100 ms, 4 over 250 ms, the longest 298 ms. S4N had
       39.2/s over 297 s, but S6N's window ends at 140 s, inside the route's load, so the two are not compared;
     - the prefix went in front of 33 buffers, from t 42.6 s (a 5,839-dword buffer inheriting the BVH program
       0x0909974c00) to t 139.871 s (a 31,124-dword buffer inheriting 0x11d0287900). The last was 0.2 s before the
       last flip, at t 140.071 s;
     - the held tail: 9,129 holds, 8,285 released with the writer on a ring, 843 satisfied; one given up after 217 ms
       ("its kept wait dropped, the chain goes"); 0.89 ms on average;
     - no alias-guard line, no `cpu-wait` give-up, no two-ring wait;
     - the play log: the tiler pool's lines (3 new buffers) and `bc5 ajm: ATRAC9 vibration layout 7 decoded by
       vgmstream (haptics)`. No crash line and no `CODEC_ERROR` up to its last write at 00:26:29.
   - The end, from the GPU journal:
     - its last line is at t 140.089 s;
     - at t 142.126 s two submits ended in TIMEOUT, after 2,040 and 2,047 ms: graphics buffer #163953 (1,813 dwords,
       submitted at t 140.086 s) and compute buffer #163938 (5,278 dwords).
   - The kernel, from the laptop's stream (`raw/kernel-stream-b.txt`):
     - 00:25:04: `clocksource: Watchdog remote CPU 14 read timed out`;
     - 00:26:46: `ring comp_1.1.0 timeout, signaled seq=1049882, emitted seq=1049884`, `Process kyty_emulator pid
       474927 thread bc5-ring`, then `Ring comp_1.1.0 reset failed` and a MODE1 GPU reset ("VRAM is lost due to GPU
       reset!");
     - the last line received, 00:26:50: `SMU is resumed successfully!`. The stream's ssh was then reset.
     - No SQC or page-fault line: not F251's fault.
   - The box's own persistent journal of that boot ends at 00:26:45 (`raw/S6N-kernel-crash-boot.txt`), one second
     before the timeout. So, as in F260, only the laptop's stream holds the timeout and the reset.
   - The box answered nothing over Tailscale or the LAN until it booted again at 13:52 (a 25-s boot at 13:52:00, then
     13:52:42). The top session reported it as a machine-down.
4. **The saves after the reboot** (`post0254.sh`, 13:54:00–13:54:04, under this experiment's lock line, which replaced
   its stale one):
   - S6N's `ab-restore.sh` had put the route saves into `PPSA03671` and kept the live ones in
     `exp0196/saves-before-002421-480336769-474626`. That copy checksummed to `1a39860996fdac5c`, the same as the 00:21
     copy;
   - it was restored and is `diff -rq` identical. `PPSA03671` itself now checksums to `1a39860996fdac5c`. What it held
     (the route saves, `f0648d02…`) is kept in `exp0254/pkg-after-S6N`;
   - `PPSA21564` is identical to `astro-live-S5A`, untouched;
   - both moved copies (00:21, 00:24) are kept.

**Two faults of mine in part 1.**
- **The saves of S5C.** `run0254.sh` put saves back with ASTRO BOT's method only for the title `astro`. S5C (`astroc`)
  therefore ran the second title's `ab-restore.sh` with ASTRO BOT's kept saves:
  - ASTRO BOT's live saves were copied into the second title's folder `PPSA03671`;
  - the second title's own saves moved to `~/bc5-work/exp0196/saves-before-002108-610387381-471392`;
  - ASTRO BOT's folder kept the route saves.

  The chain stopped there, and the top session was told at once. Nothing was launched in between. The top session's
  integration took the box at 00:22 over my restore lock line of 00:22:04. At 00:23:33, under my own lock line, both
  folders were put back:
  - `PPSA03671` from that copy;
  - `PPSA21564` from `exp0254/astro-live-S5A`, which matches `astro-live-S5C`.

  Both are `diff -rq` identical to their sources. The copy's checksum, by the water session's `ab0253.sh` method (the
  md5 of the sorted per-file md5s), is `1a39860996fdac5c` over 52 files: the value that session took at 00:11. So the
  second title's saves were exactly as the maintainer left them at 23:10. `run0254b.sh` restores per title:
  `astro|astroc` restore ASTRO BOT's folder; `pkg|pkgn` use `ab-restore.sh` and refuse a copy that is not its own.
- **The journal counts.** The `awk` program in `run0254.sh` had a newline inside its `printf` string, so it failed
  (`niezakończony łańcuch`) and S5A and S5C recorded only their journals' paths. Part 2 redid the counts from those
  journals with `jcount0254.awk` (`raw/S5A-journal-b.txt`, `raw/S5C-journal-b.txt`).
- `post0254.sh` also saved `journalctl -k -b -1`, which after the two boots at 13:52 was the 25-s boot, not the crashed
  one; it is not kept. The crashed boot (`-b -2`) was read afterwards.

**Verdict.**
- **Part 1: ASTRO BOT runs clean on the normal build with the ATRAC9 decoder, the tiler pool and the held tail, on both
  of its shortcuts** (S5A 200 s, S5C 150 s). There was no crash, kernel line or TIMEOUT. The pool held 3 buffers. On the
  compute shortcut, the held tail's first run there, it made 12,348 holds and gave none up, and the run had no give-up
  of either kind. The lean build was not run.
- **Part 2: the first run with all of them plus the compute-state prefix (S6N, the second title, build `02ed5340`) hung
  the compute ring after ~140 s.** The ring reset failed, a MODE1 reset followed, and the machine stayed down until it
  was booted again 13.5 h later.
  - Up to then: no fault line and 33 prefixed buffers; one hold given up after 217 ms; the ATRAC9 line and the pool's
    lines as expected.
  - The cause is not shown. One run cannot tell the prefix, the held tail, the other changes or a GPU hang of the
    title's own apart. The journal ends with a graphics and a compute buffer timing out together, and the last
    prefixed buffer was 0.2 s before the last flip.
  - Not run: S6A (the alias guard on ASTRO BOT) and S5L (the lean build).
- The saves of both titles are as the maintainer left them (`1a39860996fdac5c` for the second title; `astro-live-S5A`
  for ASTRO BOT).
