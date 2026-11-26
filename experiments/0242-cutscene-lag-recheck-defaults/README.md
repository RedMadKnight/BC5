# 0242 — cutscene lag re-check on the defaults of 2026-10-23

**Question.** Do the second title's cutscene characters still lag behind effects and sound (README "Known
issues"; F259, F267) on the defaults of 2026-10-23?
- In exps 0200 and 0203 the lag was the cinematic clock voice starving when its next streamed read came late.
  The characters, slewed to that clock, then crawl while the mix plays on.
- Since then the defaults have changed:
  - the APR read-ahead, fixed (F273, F287, F288);
  - the condition-variable wait of the readers (F281);
  - reflections on (F277);
  - the full DRAM-less drive cleaned (F286);
  - from 19:44 that day, exp 0243 (the top session's): the title's ATRAC9 vibration tracks (configurations 6/7,
    F300) are decoded by vgmstream instead of played as silence. It is on by default; `KYTY_BC5_AT9_VIBRATION=0`
    restores the silence.
    - F200 noted that the cinematic clock syncs to the opening's haptic track, so this run also checks the
      decoder: its "bc5 ajm: ATRAC9 vibration layout" lines and any AJM CODEC_ERROR.
    - It doubles as exp 0243's smoke test.

**Setup.**
- One scripted run, `run0242.sh <tag> 600`, of the shared build through the shortcut's launcher (`play-pkg.sh`).
  No `BC5_EMU` and no switch is set, so the run has every default the maintainer plays with.
- Route: exp 0203's O2.
  - Start: S1's end saves (`exp0196/saves-before-152617`). Their slot-3 autosave lies just before a lagging cutscene.
  - Input: `exp0203/o2-continue.cmd` plays the menu inputs to Continue it.
  - In O2 the main cinematic player ran at t ≈ 126–183 s.
- Earlier runs on this route, for comparison:
  - O2: read-ahead off; lost about 4 s of clock in t 100–250 s.
  - O3: read-ahead v1 at 4; lost 7.9 s, of which 5.6 s was one GPU stretch.
  - S1N: read-ahead default, F273; lost 1.3 s.
- Beside the run, read-only:
  - exp 0200's `sample0200.py` at 20 Hz: the clock (Wwise's play position of the 10-s clock voice), the main
    cinematic player's clip time, debt and rate, vmstat and PSI, and the watched threads;
  - exp 0220's `mem0220.sh`: the box's memory every 15 s;
  - `KYTY_BC5_APR_FILE_JOURNAL=7cd713df`: the clock voice's record-to-run delays.
- Run handling:
  - The live saves are kept aside by `ab-restore.sh`, put back and checked with `diff -rq`.
  - Only the emulator PID the run started is stopped.
  - The laptop streams the kernel log (`kstream0242.sh`), and the stream ends by itself.
- `ana0242.sh` scores the run:
  - `ana0200.py` in 5-s windows;
  - the clock time lost in t 100–250 s and over the run;
  - the clock voice's record-to-run delays;
  - frames, long frames and given-up waits by label (`long0242.py`, O_DIRECT at 15 MB/s).
- Reading:
  - The lag is the characters' clip advancing slower than wall time while effects and sound run in real time. It
    shows as clock windows under 1.0× and the main player's clip rate falling with them.
  - A clock that keeps 1.0× through the cutscene, with the player's debt near 0, means no lag on this route.
- Started from the laptop by `go0242.sh` on the top session's grant. The box had had no lock and no emulator for
  120 s (19:37:47–19:39:47).

**Result.**
1. **Run R1 (2026-10-23 19:39:54–19:50:06, 600 s, boot 31c1a6ac).**
   - Binary: the shared build of 19:28:07, md5 48a8f3ac…, i.e. exp 0243's.
   - Launcher: `play-pkg.sh` md5 714b6663…, with its defaults: `KYTY_BC5_APR_READAHEAD=4`, `KYTY_BC5_APR_PARALLEL=8`,
     `BC5_DIRECT_FLAT_APERTURE=1`, `BC5_DIRECT_AMM_PRT=1`, `BC5_DIRECT_SKIP_PGM=909974400` (`raw/R1-start.txt`).
   - It ran the full 600 s, with no crash line and no kernel line. The laptop's stream (`raw/kernel-stream.txt`)
     has only six IPv6 MLD lines. The live saves were back and identical (`raw/R1-restore-back.txt`).
2. **No lag in the cutscene (`raw/R1-ana5.txt`, `raw/R1-clock.txt`).**
   - The main cinematic player ran at t 105.5–159.1 s, about 20 s earlier than in O2, as the loads are faster now.
   - In every 5-s window of it the clock ran at 1.00×, and the player's clip at 0.99–1.01×.
     - The player's debt stayed within −0.05…+0.13 s and its rate within 0.976–1.000, as in O2.
     - The last window (t 155 s, 0.92) is the player ending.
   - Clock time lost in t 100–250 s: −0.1 s, against about 4 s in O2, 7.9 s in O3 and 1.3 s in S1N.
   - Over the whole run 6.8 s were lost, all of it in t 0–10 s, before the clock voice starts. No window after that
     is under 0.95×.
   - After the cutscene the main player's dt divisor (0x90bee5f48) reads 0.20, as it did in O2 (82 of O2's
     windows). That is the title's own value, not a change.
3. **The clock voice's reads came on time (`raw/R1-voice.txt`).** 60 record-to-run pairs of its entry
   (+0x7c69535a of file 0x7cd713df), one per 10-s pass. Max delay 0.04 s, none over 0.5 s, no run without a new
   record.
4. **Frames (`raw/R1-frames.txt`).**
   - 41.2 flips/s (42.6 for t ≥ 100 s), 24.2 ms mean between flips.
   - Frames over 100 ms 33, over 250 ms 2, over 1 s 0; longest 344 ms; no GPU stretch.
   - TIMEOUT, fault and reopen 0. Given-up waits 15: 0x12004b3c38 6, 0x12004b4838 4, 0x12004b5438 4,
     0x12004b4c38 1.
   - Memory during the cutscene: MemAvailable 0.5–1.3 GB, PSI memory full 2.5–6 %, io full 5–23 %.
5. **Exp 0243's ATRAC9 decoder, on by default (`raw/R1-at9.txt`).** The log has one "bc5 ajm: ATRAC9 vibration layout
   7 decoded by vgmstream (haptics)" line and no AJM CODEC_ERROR. The clock and the player look as in a clean run,
   so nothing points at the decoder, and no second run with `KYTY_BC5_AT9_VIBRATION=0` was needed. As exp 0243's
   smoke run: no crash, no kernel line, no timeout.

**Verdict.**
- **On the defaults of 2026-10-23 the cutscene on exp 0203's O2 route has no slow motion.** The cinematic clock
  kept 1.00× and the characters' clip 0.99–1.01× through the whole cutscene. Every clock-voice read ran within
  0.04 s of its record, and no frame took over 1 s.
- On the same route, O2 (read-ahead off) lost about 4 s and O3 7.9 s, S1N (read-ahead on, F273) 1.3 s.
- The lag was intermittent before: O1 had none either. So one clean run shows it is gone from this cutscene, not
  from every cutscene and every session. It came with late clock-voice reads (F267), which the read-ahead removes
  on the queue's side, and under memory pressure, which the cleaned drive (F286) and the fixed read-ahead (F287)
  have eased.
- Next, if the maintainer still sees it in play: the same samplers on his session (`sample0200.py` beside play,
  read-only) to catch the clock in the act, rather than more scripted runs on this route.
