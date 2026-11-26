# 0186 — The second title's night drift is older than every change since 10-19 morning; its music runs up to 3.2× fast on the same host inputs

**Question.** Two, from the maintainer, 2026-10-20 evening:
1. Which value inside the title drives its clock in the night scenes (F243), so that it can be
   fixed on the host's side?
2. "Review the commits of the last three days and find which change broke the sound's speed.
   Probably one about performance."

**Setup.**
- The clock voice of F242/F243 as the measure (`KYTY_BC5_AJM_DUMP`, complete passes of 479,352
  samples). The idle night run of exp 0185 (`idle-run.sh`, slot 1, no input after loading, saves
  restored around each run), 30-fps cap unless the build has none.
- New in the host: `KYTY_BC5_FLIP_STATUS_TRACE=1` (diagnostic, cleared in the lean build), one stderr
  line per `VideoOutGetFlipStatus` (count, process time of the presented flip, flipArg, queue and
  pending counts, buffer) and per `VideoOutGetVblankStatus` (count, process time).
- For a build older than the AJM dump: `emu-ts.sh` runs a kept binary (copied as
  `old-prev/kyty_emulator` so that the run scripts find it by name) with `KYTY_BC5_AJM_TRACE=1`,
  and `ajm_ts.py` turns its per-job lines into the same index with a timestamp each.
- Scripts (here): `fs_analyze.py` (the reads per 10-s window next to the clock speed), `stalls.py`
  (frames of eight or more vblanks between two of the title's reads, with the clock before and
  after), `ajm_jobs.py` (the clock voice's decode jobs per window), `instances.py` (decoder
  instances' lifetimes), `patch_history.py` (which host files each commit's patch changed).
- **Runs** (box, 2026-10-20 20:50–21:40):

  | run | binary | switches | length |
  |---|---|---|---|
  | L5 | current (patch of this experiment) | flip-status trace | 8 min |
  | L6 | current | flip-status trace | 13 min |
  | L7 | current | flip-status trace, `BC5_DIRECT_CHAIN=0` (submission chains off) | 10 min |
  | L8 | `kyty_emulator.prev`, built 2026-10-19 09:06 (sha256 f5cabcb9c95663ae…) | `BC5_DIRECT_CHAIN=0`; no cap, 100-ms audio hold, no guest priorities, SDL's default audio driver (the build has none of them) | 8 min |

  The L8 binary predates, in commit order: the AnyPS5 ports (8114548 …), the logging switch
  (27338e4), the pause that stops the clocks (ff45ba2), the mapping fixes (849fa7e, 6a06a39,
  47c279f), chains across ioctls (c69f141), the lean build (0dea902), the 1-s audio hold and guest
  priorities (5ac72bb), the PipeWire backend (8c9dccb), the pause hold and chains by default
  (3ef4048), the AJM dump (8673105) and the 30-fps cap (aa73775).
- Raw: `raw/L5-L6.txt`, `raw/L7.txt`, `raw/L8.txt`, `raw/patch-history-since-10-17.txt`.

**Result.**
- **L5 did not drift, L6, L7 and L8 did.** L5's night part runs at 0.76–0.98× (about
  flips/s ÷ 30). In L6 the clock sits at exactly 1.00× for 20 s after the scene starts, then rises
  1.17 → 1.74× over 150 s, jumps to 2.5× and climbs to 3.00×, where it stays for the last five
  minutes (±0.03). On the title screen L6 also ran 1.3–1.4×, against 0.98× in L5.
- **L7 (submission chains off) drifts exactly like L6:** 1.00× to 210 s, 1.11 → 1.63× to 345 s,
  2.61× at 360 s, 3.00× from 500 s. The night frame rate is the same without chains (~28 flips/s,
  the same 2/3/4-vblank mix): the night is GPU-bound, the chains only cut CPU time.
- **L8 (the 10-19 09:06 build) drifts the same way:** title screen 1.01 → 1.56×; night 1.13 → 1.83×
  to 209 s, 2.36–2.64× from 214 s, 3.00× from 335 s to the end. Its main port is pushed at 1.000 and
  held ~1000 ms a second from 75 s on, as in the current build.
- **The flip and vblank reads are the same at 1.0× and at 3.0×.** In every 10-s window of L6's and
  L7's night parts: ~280 flip-status reads for ~279 presented flips, pending 0, GC queue 0,
  flipArg 0, vblank steps between reads ~250 × 2, ~20 × 3, ~10 × 4, presented-to-presented
  35–36 ms. So the clock is not a function of what the title reads from VideoOut frame by frame.
- **Long frames do not trigger it.** L5 has 57 frames of 8+ vblanks (up to 567 ms) in its night part
  and no drift; L6 has 29. In L6 the steps up come after clusters of such frames (1.74 → 2.53× after
  400–433-ms frames at 365–368 s), in L5 the same clusters move the clock up or down by ~0.1.
- **The decoder answers consistently.** At 3.0× the title asks for three times as many 512-sample
  jobs for the clock voice (280 a second against 94), and the samples it gets match the bytes
  written exactly (`ajm_jobs.py`).
- **The music speeds up with the clock voice.** The night scene's music comes as stems of two to
  five decoder instances started together, each stem the same encoded clip every time it recurs.
  Without drift (L5) the three recurring stems last 16.0–18.9, 22.6–26.3 and 28.4–29.7 s. In L6,
  L7 and L8 the same stems shrink with the clock voice (1.0 → 1.3 → 1.6 → 3.0×) to 5.1–5.2, 7.0–7.3
  and 9.1–9.2 s. So the title runs its music (and whatever follows the music's clock) up to ~3.2×
  fast, not one voice.
- **The host's audio output stays exact.** Main port (8 ch) and the pad's vibration port (2 ch) are
  pushed at 1.000 (exp 0185 L1/L2, L8); `AudioOutGetPortState` returns constants; no pause occurred.
- **When it starts varies.** L6 and L7 leave 1.00× at the same moment (~210 s, about 90 s into the
  night scene with no input since), L4 of exp 0185 at ~200 s, L8 at ~140 s, L2 and L8 already on
  the title screen; L5 never.

**Commit review (question 2).** `raw/patch-history-since-10-17.txt` lists the host files every
commit changed. Two effects have to be told apart:
- **The daytime cutscene and looped sounds (F241): yes, performance.** The title steps them 1/30 s
  per presented frame, so their speed is flips/s ÷ 30. On 10-17 the opening ran at 25–30 frames a
  second (exp 0153, 0156) and its sound at its natural speed or a little slow. Each speed-up since
  then made it faster: the start-up stalls (a6f2c8b, exp 0156), the mapping fixes 849fa7e,
  6a06a39, 47c279f (F221–F223), logging off (27338e4, +2.6 fps, F227), the submission chains
  (6257ec1/c69f141, default for this title in 3ef4048: 37–41 → 48 flips/s, F240). Since aa73775 the
  30-fps cap holds it at 1.00×.
- **The night drift (F243): no commit since 10-19 09:06.** The binary built then (L8) drifts like
  the current one, with none of the later changes, chains off and no cap. The night scenes were
  first reached on 10-18 at 17:08 (the opening's GPU fault worked around, F207), and slot 1's
  gameplay first loaded reliably in the runs of 10-19 morning (F212); the builds of those 16 hours
  are not tested here. The sound that "went naturally" in an early build was the opening of 10-17,
  whose picture was stuck (F198): the title's clock stood still and nothing was synchronised to it.

**Verdict.**
- Question 2: the per-frame cutscene speed-up came with the performance work and is held by the
  30-fps cap. The night drift is not a regression of the last two days: the build of 10-19 09:06
  has it, on the same host inputs.
- Question 1, narrowed: the drift is not computed from the flip and vblank status the title reads,
  the decoder's answers, the audio output's pacing or state, the submission chains, the cap, the
  pause or the audio changes of 10-20. It speeds up the music as a whole. It is a state the title
  enters (L5 never did) and then winds up to ~3×, as an integrator would that cannot close its
  error.
- TODO(verify): which input the title's music clock integrates. Next: find the controller in the
  title (the music engine's playback rate, with gdb on the audio threads during a rise), and the
  host input it reads.
