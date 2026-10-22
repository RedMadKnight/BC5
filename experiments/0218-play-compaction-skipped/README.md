# 0218 — The maintainer's play with the reflection traversals on and only the BVH compaction skipped: the frame rate of a reflections-off session

**Question.** With the reflections running (`BC5_DIRECT_FLAT_APERTURE=1`, nothing skipped) the maintainer's long play
ran at half its usual frame rate (exp 0210, F268: 18.5 against 39.4 flips/s). In the frozen lake view the six
traversal variants cost nothing measurable, and the BVH neighbour-link compaction 0x909974400 was the path tied to
the faults (exp 0211, F275). In real play, with the traversals on and only the compaction skipped, where does the
frame rate land?

**Setup.**
- BC-250 dev box, 2026-10-22 20:58:16–21:16:33, the maintainer playing ~18 minutes; the box granted by the top
  session (box supervisor) with the maintainer's consent, `BOX-LOCK` held for the run; no `umr` wave dumps (F229);
  nobody else on the box during the play.
- The shared build `~/bc5-work/kytyplus-build/src/kyty_emulator`, started by `start.sh` (here) on the box display:
  `play-any.sh ~/bc5-data/pkg/game.pkg` with `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_SKIP_PGM=909974400
  BC5_DIRECT_AMM_PRT=1` over `play-pkg.sh`'s defaults (TF ring on), checked in the running process's environment.
  All six traversal variants run; only the compaction is dropped. Unlike exp 0210 (18:46) the shared build has the
  APR read-ahead on by default since 20:03 (F273).
- Saves: the live `_SaveData/PPSA03671` copied to `~/bc5-work/exp0218/saves-before-205816`, not restored (the
  progress is the maintainer's). `stop.sh` kept the emulator log (`exp0218/emu.log`) and released the lock.
- Kernel log: `kstream.sh` (here) streamed it to the laptop (`raw/kernel-stream.txt`) and ended by itself 30 s after
  the play. Journal: `~/bc5-data/captures/play-20261022-2058` (368 MB); `extract0218.sh` (here) pulled the summary and
  frame-profile lines in one pass after the play; statistics on the laptop with exp 0211's `frameprof.py` and
  `trend.py`.
- Raw: `raw/play-summary.txt` (journal counts, fence waits over 300 ms, flip gaps over 0.4 s), `raw/frame-stats.txt`,
  `raw/trend.txt`, `raw/kernel-stream.txt`.

**Result.**
- **No hang, no fault.** The title ran 1,093 s and the maintainer quit it from the menu (exit 0); the same boot
  before and after (16:37:49). The journal has the six `flat aperture` lines (each variant patched at its first
  dispatch), `skip pgm 0x909974400` dropping the compaction (the counter's last report at 8,193 dropped dispatches), 0 fence
  timeouts, no `timeout: fault`; the kernel stream has only the periodic IPv6 MLD lines, no amdgpu line.
- **The frame rate is that of a reflections-off session.** Against exp 0210's table:

  | Session | Setup | Flips/s (mean; per 20 s median, min) | Flip gaps > 0.4 s / > 2 s, longest | GPU busy per frame median / p90 | Outside-host > 0.1 s / > 1 s |
  |---|---|---|---|---|---|
  | 2058 (this run, 1,089 s) | traversals on, compaction skipped, AMM_PRT, shared build + read-ahead | 37.5; 38.6, 13.7 | 42 / 4, 2.81 s | 12.3 / 16.5 ms | 147 / 6 |
  | 1846 (exp 0210, 879 s) | traversals and compaction on, AMM_PRT, shared build | 18.5; 17.6, 3.9 | 219 / 6, 7.05 s | 15.7 / 32.5 ms | 637 / 30 |
  | 1430 (exp 0210, 1,151 s) | reflections skipped, AMM_PRT, shared build | 39.4; 40.1, 22.9 | 12 / 1, 2.68 s | 11.4 / 16.1 ms | 85 / 3 |

  Per minute (`raw/trend.txt`) 33–48 flips/s from minute 2 on (24 and 29 in the two loading minutes), with 0–17 frames a minute of GPU
  busy over 50 ms (1846: 31–55 in its slow minutes; 1430: 1–7); pinned memory 9.5 → 11.6 GiB and 20–24 k host
  mappings, as in both earlier sessions. Long GPU jobs: about 18 moments of 0.3–2.3 s (longest t 109.2 s, 2.27 s;
  then 1.08 s at t 485 and 1.03 s at t 669), against exp 0210's twelve of 0.37–4.23 s in a shorter session.
- **The maintainer's report** (verbatim): "Wygląda świetnie. Nie zacinało się szczególnie. W pełni grywalne. Zacięcia
  minimalne. Przekłamania tekstur znikome."

**Verdict.**
- In real play the reflection traversals (all six variants with the aperture fix) are not what halved the frame
  rate: with them on and only the compaction 0x909974400 skipped the play runs at 37.5 flips/s, within 5 % of the
  reflections-off session (39.4), against 18.5 with the compaction running too (exp 0210). The GPU time per frame
  rises ~1 ms at the median (12.3 vs 11.4 ms) and not in the tail (p90 16.5 vs 16.1, 1846: 32.5). This matches the
  frozen-view result (exp 0211): the cost and the faults (F275) go with the compaction path.
- Caveats: one session per setting, played through different parts of the game; the APR read-ahead (F273) is on here
  and was not in 1846 or 1430 (its measured effect is on the cutscene queue and a few more flips at the lake, not a
  factor of two); flip gaps over 0.4 s are still 3.5 times 1430's count. **Not shown:** that the reflections are
  drawn correctly with the compaction skipped — the compaction feeds the per-frame BVH work (exp 0160), so with it
  dropped the traversals may walk a stale or partial tree; no screenshots were taken in this run.
- Next: a play setting worth offering in the launcher is `FLAT_APERTURE=1` with only 0x909974400 skipped (the
  maintainer's decision); then a look at reflective surfaces with screenshots, and the compaction's own cost and
  heap writes (the TCP session's fault class, F275).
